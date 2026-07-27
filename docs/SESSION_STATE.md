# Session state (agent handoff notes)

Working notes for picking up where the last Claude Code session left off.
Not a design doc, not an ADR — a scratch log of in-flight work, open
threads, and things the next session shouldn't have to re-discover the
hard way. Prune/rewrite freely as work completes; this file describes
*current* state, not history (git history is the record of the past).

Last updated: 2026-07-27.

## Where things stand

**Chaos scenarios 1 and 2 (backlog #23) done live, real fact packs in
`observability/chaos/`.** Real, unscripted incidents surfaced in both.
Scenario 2's is the most reusable for future work: **nested app-of-apps
self-healing defeats a live sync pause.** `root` (the GitOps entrypoint)
manages every child `Application` object under `argocd/apps/` as one of
its own tracked resources — a `kubectl patch` on a child's
`spec.syncPolicy.automated` gets reverted by `root`'s own selfHeal just
as fast as `root` reverts any other drift. To genuinely pause one
component's sync for a test, the only way that sticks is a real,
committed git change to that Application's manifest (removing
`automated`), and even then `root` itself needs an explicit
`argocd.argoproj.io/refresh=hard` (not just a refresh on the child) to
pick up the change to the tracked file — refresh the parent that tracks
the manifest, not the child whose live object you're diffing. Revert
the same way (a real PR), and expect the same refresh lag.

**Two independent integration points share the same "blocks for tens of
seconds before failing" shape**: Kafka's producer `send()` (found in
scenario 1, ~60s `max.block.ms`) and HikariCP's connection acquisition
(found in scenario 2, ~30s default). Neither is what "fire-and-forget
async publish" or "connection pooling" sound like they'd do — both hang
the calling HTTP thread first. New backlog #43 tracks re-examining the
Kafka side; the Postgres side doesn't have its own item yet (the
underlying HikariCP timeout is a reasonable default, the real finding is
just that it exists and is user-facing).

**Readiness probe blind spot, confirmed live (new backlog #44)**: `api`'s
readiness group never reflected a real, 6-minute-sustained PostgreSQL
outage — Kubernetes kept routing traffic to a pod that could not
actually serve a DB-backed request. The full `/actuator/health` endpoint
correctly hung (confirming the DataSource check itself works), it's
specifically excluded from Boot's readiness *group*. Very likely
Spring's own intentional design (avoid one DB blip pulling every replica
out of rotation) rather than a bug — but with this project's single
replica per service, that specific tradeoff doesn't actually apply, so
it's worth a stated decision rather than an unexamined default.

**`local-path`'s unenforced PVC quota (already known) ruled out "PVC
full" as a safely-testable chaos scenario entirely** — the "2Gi" a PVC
requests is nominal only; the real mount is the node's shared disk, and
deliberately filling it risks the whole node, not just the one
component. #23's scenario 2 dropped that half rather than attempting it.

**No existing alert caught either brief-outage window on the first
try** in both scenarios 1 and 2 — `ApiHighErrorRate`/the Kafka-adjacent
signals all need a sustained 5-minute window of real, non-zero traffic
to trip, and this project's actual traffic (manual/test requests) rarely
produces that on its own. Scenario 2 eventually proved `ApiHighErrorRate`
*does* fire correctly once ~6 minutes of real sustained failing traffic
was generated on purpose — the alert itself works, the gap is realistic
traffic volume, not the rule. A real notification was confirmed
delivered to the live `ntfy.sh` topic, the first real end-to-end alert
fire on this cluster.

**Simplification pass executed (ADR 0021).** The user asked to argue for
maximum simplification — remove anything that doesn't earn its
complexity. A staff-engineer audit found `gateway` had exactly one
route (a placeholder from M1, never wired to real traffic) while
carrying a full tax (its own module, CI pipeline, namespace, ArgoCD
Application, Ingress, TLS cert) — the same shape as `whoami`, the
original one-time Traefik+TLS proof, now redundant. Both **removed
entirely, verified live**: `services/gateway` and `platform/kubernetes/
{gateway,whoami}` deleted, both namespaces deleted from the live
cluster, `api` given its own Ingress+cert (`api.local.adamastorx.dev`,
`adamastorx-ca`), confirmed reachable through Traefik with real TLS
(`curl --resolve ... --cacert adamastorx-ca.crt` → `200`). Also cut:
gnomAD enrichment (never built, ~7.7GB real size didn't fit this
cluster), M6 (backlog #30, the reserved FASTQ/alignment milestone —
judged to extend the "bio coat of paint" risk rather than resolve it),
HGVS/liftover (#40/#41 — bio depth for a bio audience, no new SRE
signal), and several M4 items that read as ceremony for a solo project
(#21b burn-rate policy, #33 solo postmortems, #34 laptop load-testing,
#23b folded into #23a, chaos trimmed from 7 scenarios to 3). `#38`/`#39`
(real correctness bugs/fixes) and the ClinVar provenance/invalidation
story were explicitly kept — judged the project's most defensible
portfolio content, not cut for cutting's sake.

**Real incident found executing this**: after the resource-governance
work (backlog #35) added a 500m CPU limit to `api`, a routine rollout
got stuck in `CrashLoopBackOff` for 95 minutes — `kubectl top pod`
confirmed the new pod pegged at 498m/500m (cgroup-throttled) during
JVM cold start (Hibernate/Flyway/Kafka bootstrapping), missing the
liveness probe's 80s budget every single time, while the old pod kept
serving traffic the whole time (rolling-update default masks this kind
of stuck deploy from being visibly "down"). Fixed by raising `api`'s
CPU limit to 1 core (and the namespace's `ResourceQuota` to match) —
confirmed live: new pod `1/1 Running`, 0 restarts, steady-state usage
~30m, nowhere near the new ceiling. **Lesson**: a CPU limit sized from
steady-state usage alone can starve a JVM's cold start even when
steady-state headroom looks generous — check an actual cold start
under the proposed limit, not just steady-state `kubectl top`, before
trusting a resource-governance change on any JVM workload.

**Backlog #21 (SLOs + alerting) and #21c (Alertmanager receiver) implemented
and merged.** `argocd/apps/prometheus.yaml`:
`alertmanager.enabled` flipped to `true`, seven alert rules added under
`server.serverFiles.alerting_rules.yml` (one per ADR 0020 SLO-table row,
except clinvar-service's lookup non-5xx — see gap below), Alertmanager's
own `config` wired to a single real receiver: a `webhook_configs` entry
pointed at a randomly-generated-once `ntfy.sh` topic (zero account/
credential needed, verified live with a real `curl` POST before choosing
it), plus a minimal severity-routing tree (`critical` gets a faster
`group_wait`/`repeat_interval`, everything else shares the same receiver
on a slower cadence — #21b's future burn-rate work gets a place to attach
a second receiver later, not built now). Also fixed in the same PR:
`clinvar-service` was never actually added to Prometheus's
`extraScrapeConfigs` when #21a shipped its `/metrics` endpoint — confirmed
missing on the live `/api/v1/targets` output before writing any
clinvar-service alert rule, since an unscraped metric's rule would just
silently never fire rather than error. **Stated gap, tracked as new
backlog #21e**: `clinvar_lookup_duration_seconds` has no status/outcome
label, so `GET /internal/clinvar/lookup`'s non-5xx-rate SLO has no alert
yet (shipped without one rather than faking it against data that isn't
there); `clinvar_ingestion_duration_seconds_count` increments on both
success and failure, so the `ClinVarIngestionFreshnessBreach` alert that
did ship can only detect "no attempt in 8 days", not "attempts happened
but every one failed" (ADR 0020's own wording is "last *successful*
ingestion"). All 7 PromQL expressions verified syntactically valid and
evaluable against the live cluster's real Prometheus
(`kubectl -n prometheus port-forward svc/prometheus-server`) before
opening the PR. See the PR description for exactly what was/wasn't
verified live end to end (rules loaded into `/api/v1/rules`, a real
alert firing into the ntfy topic) vs. left for post-merge.

**M4 kicked off (ADR 0020): backlog #21a (real histogram/consumer-lag/
clinvar-service metrics) is done and verified live.** A five-persona
survey (architect, backend-engineer, platform-engineer,
observability-engineer, documentation-engineer) converged
independently on "M4 is the most overdue milestone." ADR 0020 made
ADR 0017's own named gaps (no true latency percentiles, no real Kafka
consumer-lag metric) the explicit prerequisite for #21's SLOs, plus
gave `clinvar-service` its first Prometheus metrics from zero. All
three now confirmed live with real traffic: a real `POST /work-items`
produced genuine `http_server_requests_seconds_bucket` series, a real
produce/consume cycle produced a genuine
`kafka_consumer_fetch_manager_records_lag` gauge on `workers` (the
hand-built `ConsumerFactory` needed an explicit
`KafkaClientMetrics(...).bindTo(meterRegistry)` call — Boot's
auto-configured Kafka metrics binder never applies here, same root
cause as the `observation-enabled` no-op below), and `clinvar-service`'s
new `GET /metrics` returned real `clinvar_ingestion_duration_seconds`/
`clinvar_ingestion_in_progress`/`clinvar_ingestion_rejected_total`/
`clinvar_lookup_duration_seconds` series. Dashboards (ADR 0017) updated
to plot the real values instead of the average/max/thread-pool
stand-ins. Backlog #27 closed as superseded (ADR 0019); #28/#29
rescoped for `clinvar-service`'s real Python architecture. Next: #21
(SLOs), #22 (runbooks), #23 (7 chaos scenarios now, `clinvar-service`'s
own Postgres/PVC added as #7).

**platform#34 (Postgres Secret regeneration) root-caused, fixed, and
then immediately demonstrated its own pre-fix damage.** Confirmed by
rendering each affected Bitnami chart (`postgresql`, `redis`,
`clinvar-postgresql`, `kafka`) twice offline with identical inputs —
the auto-generated Secret's password/cluster-id differs on every
render, since `common.secrets.passwords.manage`'s reuse-idempotency
needs a live-cluster Helm `lookup()` that ArgoCD's `helm template`
rendering never has. Fixed going forward with `spec.ignoreDifferences`
on each Secret's `/data` (platform#40) — but this only stops *future*
drift; deploying the M4 metrics work bounced `api`'s pod, and the fresh
pod's first-ever connection attempt hit `FATAL: password authentication
failed for user "api"` — the Secret had *already* silently diverged
from Postgres's real password at some earlier point, before the fix
landed, and nothing had forced a fresh connection since. Confirmed via
`kubectl exec postgresql-0 -- env | grep PASSWORD` vs. the Secret's own
value (different), fixed live with explicit confirmation (`ALTER USER
api WITH PASSWORD '<Secret's value>'`) — same playbook as the original
incident, see the gotcha below. **Lesson**: `ignoreDifferences` prevents
new drift, it does not retroactively repair a Secret that already
drifted — if this recurs on Redis/Kafka/clinvar-postgresql, check for
a *pre-existing* mismatch the same way before assuming the fix already
covers it.

**Same rollout, separately: all 3 Kafka topics vanished** (`work-items`,
`work-items.DLT`, `clinvar.ingestion.completed`) — confirmed a
coincidental broker restart (`kafka-controller-0` at 85m age, so within
this session), matching ADR 0011's known ephemeral-storage behavior
(`auto.create.topics.enable: false`). Recreated manually (3 partitions
for `work-items`/`.DLT`, 1 for `clinvar.ingestion.completed`), then
restarted `api`/`workers`/`clinvar-service` for clean consumer-group
state. No data lost (in-flight messages only), but worth remembering
this can wipe topics silently again on any future Kafka pod restart.

**Independent staff-engineer audit** (a genuinely cross-cutting review,
not one of the 5 narrow repo personas) found: `.claude/PROJECT.md`'s
"Current milestone" section had drifted badly stale (still said "M2 in
progress, services#5 remaining" after M3 and M5 had both shipped) —
fixed directly, and backlog #32 added to make that drift checkable
going forward instead of silently possible. Also found a genuinely
uncovered gap: **no backup/restore path exists for any stateful data**
(`api`'s Postgres, `clinvar-service`'s own Postgres, Loki, Tempo — all
a single node-pinned PVC each, no `pg_dump`/snapshot/off-node copy
anywhere) — added as backlog #23a. And #31, a proposed top-level "what
this project demonstrates" narrative doc, since the real throughline
(incidents found and fixed live, the ADR 0018→0019 pivot) is currently
only reconstructable by reading ~20 ADRs end to end.

**M5 Clinical Variant Annotation is live and verified end to end.**
`clinvar-service` (Python/FastAPI, ADR 0019, own `clinvar` namespace,
own dedicated Postgres) replaced ADR 0018's original design after two
real cross-namespace bugs (a PVC, then a Postgres Secret — neither
shareable across `api`/`workers`) surfaced deploying it. `api` calls it
over HTTP and fronts the result with the existing Redis cache-aside
layer, invalidated on write via a Kafka event carrying the specific
changed cache keys. Verified live: a real ingestion (4,453,798 VCF
records, 2,895,514 rsID-indexed rows) followed by `GET
/variants/lookup?rsid=rs80357906` through `api` returning BRCA1's real
ClinVar classification, `"Pathogenic"`. `docs/architecture/overview.md`
now documents this as live, not aspirational.

**Real incident found and fixed during the same rollout**: two manual
ingestion triggers sent close together ran two full ClinVar VCF scans
concurrently — no lock existed, and the slowest step (`_build_variant_
index_rows`, a pure-Python scan building ~2.9M in-memory tuples) had no
logging at all, so the stall was invisible until `--previous` container
logs were read directly. The pod was SIGKILLed (`exit 137`) with **no
OOM evidence anywhere** — checked `dmesg -T`, `journalctl -k`, and
`journalctl -u k3s.service` around the exact timestamp, all clean; the
node itself had memory headroom afterward too. Root cause is
circumstantial (two overlapping multi-hundred-MB Python object builds
contending for the 768Mi limit) rather than confirmed via a single
smoking-gun log line — worth knowing if this ever recurs, since the
usual "check dmesg for OOM" playbook doesn't work here. Fixed
(services#36): `ingest()` now holds a lock for its duration and rejects
a second concurrent call (409), plus progress logging every 250k
records so a future stall is visible instead of a silent multi-minute
gap.

M2 Distributed Application: services#1 (gateway), services#2 (API),
services#3 (Kafka, ADR 0011), services#4 (PostgreSQL, ADR 0012), and
**services#5 (Redis cache-aside, ADR 0016) are all done and closed.**
Redis verified end to end against the real cluster: `GET
/work-items/{id}` twice on a fresh item produced `cache_gets_total{
result="miss"} 1.0` then `{result="hit"} 1.0`, `error 0.0`, read
straight off `/actuator/prometheus`. Fail-open on a Redis outage is
proven in CI (`WorkItemCacheOutageIntegrationTest` stops the
Testcontainers Redis mid-test), not repeated live to avoid disrupting
the real Redis for a case already covered. Honest answer baked into
ADR 0016: `GET /work-items/{id}` is a good candidate for this issue's
actual AC (hit/miss metric, tested fail-open) but not for demonstrating
invalidation-on-write, since `work_items` has no update path — any
invalidation here is TTL-only, stated plainly rather than picked
around.

**Real incident found during the Redis rollout, unrelated to Redis
itself**: the `postgresql` Secret had silently regenerated to a value
different from what Postgres was actually initialized with — see the
gotcha below. Fixed live with explicit human confirmation
(`ALTER USER api WITH PASSWORD`); root cause tracked as
`platform`#34, unresolved.

M3 Observability: **observability#1 (OTel tracing, ADR 0013, backlog
#17), #2 (Prometheus + Grafana, ADR 0014, #18), #3 (Loki + Tempo +
Alloy, ADR 0015, #19), and #4 (golden-signal dashboards, ADR 0017,
#20) are all done — M3 is complete.** A real trace from a live `POST
/work-items` request was confirmed end to end: landed in Tempo (2
spans, `api` + `workers`), its log line (same trace ID) landed in
Loki, Grafana's Loki↔Tempo pivot works both directions, and all 4
Prometheus targets confirmed `up`. Dashboards were built by a
background agent (per-service golden signals, provisioned as code,
confirmed via the Grafana pod's own provisioning logs — "finished to
provision dashboards," no errors, `grafana-dashboards-golden-signals`
ConfigMap has 3 keys). Backlog #19a (Prometheus exemplars, metric→trace
pivot) and #21 (SLOs/alerting, M4) are tracked but deliberately not
built yet — #21 explicitly depends on #20's dashboards, see ADR 0017's
"tension worth resolving explicitly" section for the reasoning.

## Recurring gotcha worth knowing before touching this stack again

**Boot 4.1 modularized its autoconfiguration**: the client library
(`spring-kafka`, `flyway-core`, classic Jackson 2, `opentelemetry-exporter-otlp`)
and the `FooAutoConfiguration` classes that actually wire it into a
Spring context live in *separate* artifacts (`spring-boot-kafka`,
`spring-boot-flyway`, `spring-boot-micrometer-tracing` +
`-opentelemetry`). Adding the client library alone compiles fine and
then silently doesn't work at runtime — no error, the feature just
never activates. Hit this four separate times now (services#3, #4,
observability#1). If a future integration (Redis, anything else)
compiles clean but a Boot feature just isn't activating, check for a
matching `spring-boot-<name>` artifact before assuming the library
itself is broken.

**Boot property names move between major versions without a compile
error.** `management.otlp.tracing.endpoint` looked right (matches the
Boot 3.x docs pattern still floating around) but is deprecated at error
level since Boot 4.0 and silently binds to nothing — no startup
failure, no export failure, just a property nobody reads. Correct path:
`management.opentelemetry.tracing.export.otlp.endpoint`. When a
property "should" work and doesn't, check the actual
`spring-configuration-metadata.json` inside the relevant
`spring-boot-*` jar (`unzip -p <jar> META-INF/spring-configuration-metadata.json`)
before assuming the code is broken — it's often the property name that
moved.

**`OTEL_*`-prefixed environment variables are reserved by the
OpenTelemetry SDK itself**, independent of whatever Spring property
you meant them to override. Naming a Kubernetes Deployment env var
`OTEL_EXPORTER_OTLP_ENDPOINT` (seemed like the "correct, standard"
choice) made the OTel SDK's own `autoconfigure-spi` module pick it up
directly and build a second, conflicting exporter, doubling the
`/v1/traces` path into a silent 404. Any future OTel-adjacent
deploy-time override needs a name outside the `OTEL_*` namespace.

**Hand-built Spring beans bypass Boot's `*.observation-enabled`
properties.** `WorkItemProducerConfig`/`WorkItemConsumerConfig`
construct their own typed `KafkaTemplate`/listener container factory
(documented reason: Boot's auto-configured ones are untyped) —
`spring.kafka.template.observation-enabled`/`.listener.observation-enabled`
only wire into Boot's *own* auto-configured beans, so those properties
were silent no-ops here. Needed an explicit
`.setObservationEnabled(true)` call in the `@Bean` methods themselves.
Same likely applies to any other hand-built Spring integration bean
going forward — check whether a "just set this property" fix is
actually reaching the bean in use.

**`spring-boot-starter-actuator` alone does not expose
`/actuator/prometheus`.** Two separate things are needed, both easy to
assume are already covered: the `micrometer-registry-prometheus`
dependency (actuator brings Micrometer's core, not the Prometheus
registry), and `management.endpoints.web.exposure.include:
health,prometheus` (Boot doesn't expose non-default endpoints over HTTP
just because the registry is present). Both ADR 0013 and the first pass
of ADR 0014 assumed this endpoint "already existed" from actuator alone
— it took an actual Prometheus scrape returning 404 on all three
services to find it (observability#2).

**Helm chart `ports.*.enabled: false` can hide a port the process is
already listening on.** The otel-collector chart's own self-monitoring
metrics (`:8888`) are always active internally (default telemetry
config), but the chart's `ports.metrics.enabled` defaults to `false`,
so the generated Service never got a port for it — Service-DNS
connections just timed out (process running, nothing routing to it).
Fixable by `helm template`-ing the chart locally with the flag flipped
and diffing the rendered Service before assuming a scrape-target
timeout is a network/firewall problem.

**A chart's `deprecated: true` + a stated migration deadline is worth
checking against today's date before writing the manifest**, not
after. `grafana/grafana`'s stated migration deadline (Jan 30th 2026) had
already passed by the time this was deployed — verified
`grafana-community/helm-charts` was a real, actively-published
continuation (same values schema, newer version) before switching the
`repoURL`, rather than deploying an already-stale chart into a project
meant to model this discipline. Same finding recurred for Loki/Tempo/
Promtail (observability#3): `tempo`/`promtail` are `deprecated: true`
outright, `loki`'s original repo now serves GEL-enterprise only.

**A "ring: ACTIVE, /ready: ready" single-instance chart can still
0% work if `replication_factor` doesn't match replica count.** Loki's
chart defaults `common.replication_factor: 3` (inherited from its
multi-replica modes) — with one `singleBinary` replica, every query
500'd with "too many unhealthy instances in the ring," no startup or
readiness-probe failure at all. Only actually querying surfaced it.
Fixed with `commonConfig.replication_factor: 1`. Worth checking on any
future single-replica chart that was originally designed to scale out.

**GitOps branch-vs-stale-local-main trap**: creating a new branch from
a local `main` that hasn't been `git pull`ed since the last squash-merge
produces a branch whose history diverges from `origin/main` even when
the file content is identical — GitHub reports the PR as `CONFLICTING`
despite `git diff origin/main` showing a clean, minimal diff. Fix:
`git fetch && git rebase origin/main` before pushing. Always `git fetch
origin --quiet && git checkout main --quiet && git pull origin main
--quiet` immediately before branching for a new PR, not just at the
start of a work session.

**Kafka topics don't survive a broker pod restart** (ADR 0011,
deliberately ephemeral storage) — if `work-items` is suddenly
`UNKNOWN_TOPIC_OR_PARTITION` after having worked before, check
`kubectl get pods -n kafka` for a recent restart before assuming a
config regression; recreate the topic manually
(`kafka-topics.sh --create --topic work-items --partitions 3
--replication-factor 1`) to unblock testing, no chart-side provisioning
Job re-runs this automatically.

**A Bitnami chart's auto-generated password Secret can silently
regenerate and diverge from the live database/service's actual
credential** (found deploying services#5, tracked unresolved as
`platform`#34). Postgres never restarted, but its `postgresql` Secret's
`password`/`postgres-password` values stopped matching what the
container was actually started with (visible in the running pod's own
`POSTGRES_PASSWORD`/`POSTGRES_POSTGRES_PASSWORD` env vars, baked in at
container start and never changed). An already-running pod with an
established connection pool won't notice — only a *new* connection
attempt (a fresh pod, a rolling restart) fails with
`FATAL: password authentication failed`. If this recurs: compare the
Secret's current value against the target pod's own env
(`kubectl exec <pod> -- env | grep PASSWORD`) before assuming a config
regression — if they differ, `ALTER USER <role> WITH PASSWORD
'<current Secret value>'` inside the DB pod restores access (get
explicit confirmation first, this mutates live data). Suspected but
unconfirmed cause: ArgoCD's Helm rendering may not preserve
`common.secrets.passwords.manage`'s "reuse existing Secret" idempotency
the way a real `helm upgrade` would. Same auto-generation pattern is
used by Redis's password and Kafka's cluster ID — unconfirmed whether
they're equally at risk.

**A crash-looping pod's exponential backoff can take minutes to retry
even after the underlying cause is fixed.** `kubectl delete pod
<name>` (the Deployment/StatefulSet recreates it immediately) is a
safe, reversible way to force an immediate retry instead of waiting out
the backoff timer — not a persistent or destructive action, just a
faster feedback loop.

**Namespace scoping breaks PersistentVolumeClaims the exact same way it
breaks Secrets** (ADR 0012 already established this for Secrets; ADR
0019 hit it again for a PVC). `workers` tried to mount a PVC that only
existed in `api`'s namespace — pod stuck `Pending`,
`persistentvolumeclaim "X" not found`. Same root cause, same fix
shape: give the consumer its own namespace-scoped copy (its own PVC, or
in this case, redesign so only one component ever touches the volume
at all), don't try to share either resource type across a namespace
boundary.

**`tcpSocket` liveness/readiness probes can't detect a wedged
single-threaded app.** The kernel completes a TCP handshake into the
accept queue regardless of whether the application ever calls
`accept()` — a process fully blocked on CPU-bound synchronous work
(e.g. `clinvar-service`'s pure-Python VCF scan) can still pass a
`tcpSocket` probe indefinitely. Use a real `httpGet` health route
whenever the app has one; a TCP-only check is a last resort for apps
that genuinely don't expose HTTP, not a shortcut for ones that do but
haven't had their manifest updated yet.

**A step with no logging is invisible when it stalls, and "add a
progress log line" is cheap insurance worth adding proactively** for
any loop expected to run more than a few seconds over real (not
fixture-sized) data — `clinvar-service`'s per-record VCF scan had zero
log output for its ~90-second real-data runtime until this was fixed;
during the double-ingestion incident, this silence was the reason
`kubectl logs --previous` alone couldn't immediately show which step
was actually stuck.

## Cluster access (this machine)

k3s kubeconfig at `~/.kube/config`. `kubectl` here does **not** default
to it on its own — always run with `KUBECONFIG` set explicitly:
```
export KUBECONFIG=~/.kube/config
```
Not persisted in `~/.bashrc` (blocked by the permission classifier) —
set it per session.

## ArgoCD stuck-operation gremlin (if it recurs)

An `Application`'s `.operation` field (the in-flight sync request) can
get stuck holding a **stale** values snapshot from an earlier commit and
keep re-applying it on retry, ignoring that `.spec.source` has since
changed. Refresh annotations and restarting `argocd-repo-server`/
`argocd-application-controller` don't clear this. What works:
```
kubectl patch application <name> -n argocd --type merge -p '{"operation":null}'
```
Check `kubectl get application <name> -n argocd -o jsonpath='{.operation}'`
before assuming a "keeps reapplying the wrong thing" symptom is a
caching/chart problem — it might just be a frozen operation.

## Namespace-per-component isn't absolute

Established pattern: each service/infra component gets its own
namespace (gateway, api, workers, kafka, otel). PostgreSQL broke that
pattern deliberately (ADR 0012) — it lives in `api`'s namespace, not
its own, because `secretKeyRef` can't cross namespaces and Postgres has
exactly one consumer here. The OTel Collector (ADR 0013) got its own
`otel` namespace like Kafka, not Postgres's treatment — three consumers,
no credential to worry about (open OTLP receiver, like Kafka's
PLAINTEXT). If Redis ends up needing credentials and has a single
consumer, the Postgres reasoning likely applies again — don't assume a
new namespace by default.

## Where to look next

- `platform`#34 (Postgres Secret regeneration) is **fixed** (PR #40,
  `ignoreDifferences` on 4 charts' Secrets) — but re-check any
  stateful component's Secret against its pod's actual env on the next
  incident, since the fix only stops new drift, not an
  already-diverged credential (see above, `api` hit exactly this right
  after the fix landed).
- M4: #21 (SLOs/alerting) is next, now unblocked — #21a's real
  histogram/lag/clinvar metrics are live. #22 (runbooks) and #23 (7
  chaos scenarios) follow. #19a (Prometheus exemplars) still not
  started, lower priority than #21.
- observability#13/#14 (release-ID trace propagation, `clinvar-service`
  dashboard + `ClinVarInvalidationLag` alert) — rescoped for ADR 0019
  (see backlog #28/#29), not started.
- backlog #23a (backup/restore for stateful data — no Postgres/Loki/
  Tempo backup exists anywhere), #31 (top-level project narrative
  doc), #32 (keep `.claude/PROJECT.md` from drifting stale again) — all
  new from the staff-engineer audit, none started.
- gnomAD's real size (~7.7GB, not the "a few hundred MB" ADR 0018
  originally assumed) — flagged during M5 planning, not yet tracked in
  a dedicated issue or resolved.
- The manual ingestion trigger (`POST /internal/clinvar/ingest`) is
  still fully synchronous for several minutes; services#36 stops a
  second overlapping call from running concurrently, but the endpoint
  itself blocking the request for the whole ingestion is still a
  fragile shape (client/proxy timeouts) worth revisiting as a
  fire-and-poll design if this becomes a recurring pain point.
- observability#7 (chaos/incident-lab scenarios) — 7 concrete scenarios
  defined (ADR 0020 added a 7th for `clinvar-service`), none
  implemented yet.

## Working via background agents (new pattern, this session)

For independent, parallelizable work (e.g. Redis + dashboards run
side by side), dispatch background agents that clone their own scratch
copies of whichever repos they need — never point them at the shared
`/home/lmpeixoto/repos/AdamastorX/*` checkouts, since a second
agent (or the primary session) may be using them at the same time.
Each agent should: read this file first, follow the same ADR/
verification discipline documented here, open PRs, wait for CI, then
**stop without merging** — every PR merge needs explicit human
confirmation, agents included, no exceptions. The orchestrating session
reviews the diff and handles the merge once a human confirms.
