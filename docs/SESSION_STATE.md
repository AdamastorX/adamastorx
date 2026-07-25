# Session state (agent handoff notes)

Working notes for picking up where the last Claude Code session left off.
Not a design doc, not an ADR — a scratch log of in-flight work, open
threads, and things the next session shouldn't have to re-discover the
hard way. Prune/rewrite freely as work completes; this file describes
*current* state, not history (git history is the record of the past).

Last updated: 2026-07-25.

## Where things stand

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

- `platform`#34 (Postgres Secret regeneration, P1) — real, unresolved,
  can silently break any stateful component's next pod restart. Worth
  picking up before it happens again on Kafka or Redis's own
  credentials.
- M4: #21 (SLOs/alerting, depends on #20's now-live dashboards) and
  #19a (Prometheus exemplars, metric→trace pivot) are the next real
  gaps — neither started.
- observability#7 (chaos/incident-lab scenarios) — expanded with 6
  concrete scenarios earlier this session but not implemented.

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
