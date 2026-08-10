# Session state (agent handoff notes)

Working notes for picking up where the last Claude Code session left off.
Not a design doc, not an ADR — a scratch log of in-flight work, open
threads, and things the next session shouldn't have to re-discover the
hard way. Prune/rewrite freely as work completes; this file describes
*current* state, not history (git history is the record of the past).

Last updated: 2026-08-10.

## Where things stand

**Backlog #49 (Cilium/Hubble, replacing flannel) and #50 (first
NetworkPolicies) are both Done and live, 2026-08-10** — the day's major
work: a real, live, deliberate single-node cluster rebuild, followed by
6 real `CiliumNetworkPolicy` batches (`clinvar`/`api`/`workers`/`alloy`/
`prometheus`, plus two ingress-enforcement follow-up fixes found and
applied during the closure itself) across `platform`#148–#162 and
`adamastorx`#239–#249. `docs/roadmap/backlog.md`'s own #49/#50 entries
and `docs/architecture/overview.md`'s "Network dataplane" section have
the full, real account (including a genuine production incident and its
root cause) — this section only keeps the gremlins worth knowing before
touching this stack again, since a live Cilium/CiliumNetworkPolicy quirk
belongs here more than duplicated into the permanent record.

**Real, still-relevant gremlins from that work**:

- **Cilium's DNS proxy (`toFQDNs`/`rules.dns`) is genuinely broken in
  this cluster's exact config** (`routingMode: tunnel`/vxlan +
  `kubeProxyReplacement`/socket-LB, matches open upstream
  `cilium/cilium#46284`) — the moment any policy adds an L7 `rules.dns`
  selector, it drops **all** locally-originated pod DNS, not just the
  intended FQDN. Confirmed live, twice, independent of
  `dnsProxy.enableTransparentMode`. Worked around with `toCIDR` real IP
  ranges instead (pure L3, never touches the DNS proxy) for the three
  real flows that needed public egress (NCBI, GitHub, `ntfy.sh`). If a
  future policy seems to want `toFQDNs` again, check the upstream issue
  before assuming it's fixed — it wasn't as of this rebuild.
- **`CiliumNetworkPolicy` `toPorts` needs the real backend *container*
  port, not the Service's own port.** `clinvar-service`'s Service is
  port 80, its container listens on 8000 — Cilium evaluates policy on
  the post-DNAT packet, so a rule naming port 80 lets nothing through
  even though the Service "looks" reachable. Caused a real false-alarm
  emergency rollback mid-investigation once (the manual connectivity
  test used the wrong port, not an actual bug). Check
  `kubectl get svc -n <ns> <name> -o jsonpath='{.spec.ports}'` before
  writing a `toPorts` rule, or before concluding a policy is broken.
- **Cilium only enables per-direction policy enforcement when that
  direction has at least one real rule object.** An omitted or
  explicitly-empty `ingress:`/`egress:` key does nothing — that
  direction stays fully unenforced (real default-allow), even though
  the policy "looks" like default-deny. Bit two already-merged policies
  (`alloy`, `alertmanager`) before being caught by a deliberate audit
  pass. Check `cilium-dbg endpoint list`'s `policy-enabled` says `both`,
  not just one direction, whenever a policy is meant to enforce both.
- **`hostNetwork: true` pods share Cilium's `reserved:host` identity
  with no distinct endpoint of their own** (node-exporter,
  cilium-agent/cilium-operator, Beyla, confirmed live via
  `cilium-dbg endpoint list`) — a `CiliumNetworkPolicy` can't select
  them by pod label at all. Egress to them needs `toEntities: host`;
  they can't get their own ingress policy. Not a bug, a real Cilium
  constraint worth knowing before assuming a missing policy is an
  oversight.

## Where to look next

- No open PRs or in-flight work as of this update — #49/#50 closed
  clean, nothing left mid-flight.
- `docs/roadmap/backlog.md` is the live source of truth for what's open
  next (currently #1–#121, structural integrity enforced by
  `scripts/check_backlog_structure.py` and CI's `backlog-structure`
  check on every PR).
- `.claude/PROJECT.md`'s "Current milestone" section is the stable,
  point-in-time picture of where the project stands overall — check it
  before this file for the big picture; this file is for tactical
  gremlins and in-flight state, not milestone status.

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

Real, current kubeconfig, generated fresh by the 2026-08-10 cluster
rebuild:
```
export KUBECONFIG=/home/lmpeixoto/repos/AdamastorX/platform/terraform/kubeconfig
```
`kubectl` here does **not** default to it on its own — always set
`KUBECONFIG` explicitly, every session (not persisted in `~/.bashrc`,
blocked by the permission classifier).

**The older `~/.kube/config` is stale/pre-rebuild** — a review agent
that tried it during the rebuild's own follow-up work got real TLS
errors against it. Use the path above, not `~/.kube/config`.

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

**A confirmed real trigger for this (2026-08-02, syncing `kafka` to pick
up backlog #79's new topic): setting `.operation.sync.revision` to
`"HEAD"` when manually patching a Helm-chart-sourced Application.**
`"HEAD"` is a git-ism, not a valid value for a Helm chart source's
revision (which needs a real semver constraint or an empty string to
fall back to `spec.source.targetRevision`) — the sync fails at manifest
generation (`ComparisonError: ... invalid revision ... improper
constraint: HEAD`), but the automatic retry doesn't cleanly re-fail: it
re-applied a **stale, previously-cached** `operation.sync.source` (an old
snapshot missing the new topic entirely), actually ran a real sync
against that stale manifest, and reported per-resource `Succeeded`
statuses in `status.operationState.syncResult.resources` even though the
overall `phase` was `Error` — genuinely misleading, easy to mistake for
a real (if oddly-labeled) success. Confirmed via
`status.operationState.operation.sync.source.helm.valuesObject` still
showing the old `provisioning.topics` list post-failure. **Fix: never set
`revision` in a manual sync patch for a Helm-sourced Application** —
omit the field entirely (`{"sync":{}}`) so the controller reads the
live `spec.source.targetRevision` fresh. (Note: this is specifically
about Helm-chart-sourced Applications — `"HEAD"` is fine, and was used
successfully throughout the 2026-08-10 NetworkPolicy work, for
git-path-sourced Applications like every `*-network-policies` one.)

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
