# Session state (agent handoff notes)

Working notes for picking up where the last Claude Code session left off.
Not a design doc, not an ADR — a scratch log of in-flight work, open
threads, and things the next session shouldn't have to re-discover the
hard way. Prune/rewrite freely as work completes; this file describes
*current* state, not history (git history is the record of the past).

Last updated: 2026-07-25.

## Where things stand

M2 Distributed Application: services#1 (gateway), services#2 (API),
services#3 (Kafka, ADR 0011), and services#4 (PostgreSQL, ADR 0012) are
done and closed. **services#5 (Redis, ADR 0016) is in flight — 3 PRs
open, none merged yet, nothing deployed or verified against the real
cluster:**
- `adamastorx`: ADR 0016 (+ this note).
- `platform`: `argocd/apps/redis.yaml` only — standalone chart, no PVC
  (deliberate, cache-aside means Postgres stays the only source of
  truth), auth kept on (chart default), deployed into `api`'s namespace
  (single consumer + credential, same reasoning ADR 0012 used for
  Postgres). Deliberately does **not** touch
  `kubernetes/api/deployment.yaml` yet — no real image SHA exists to bump
  to until the `services` PR below is merged and CI publishes one
  (`docs/runbooks/cross-repo-rollout.md`'s ordering). That env-var
  (`REDIS_HOST`/`REDIS_PASSWORD` secretKeyRef) + SHA-bump PR is the next
  step once the `services` PR merges.
- `services`: cache-aside for `GET /work-items/{id}` (hand-rolled
  `RedisTemplate`, not `@Cacheable` — see ADR 0016 for why), hit/miss/error
  Micrometer counters, a Testcontainers test that stops the Redis
  container mid-test and proves the read still succeeds (fail-open).
  Compiled locally (JDK 25, `./mvnw test-compile`); the Testcontainers
  tests themselves were **not** run locally — no Docker in that sandbox —
  so CI is the first real execution of them. Don't treat this as "tested"
  until CI actually goes green.
- ADR 0016 also has the honest answer to "is `GET /work-items/{id}` even
  a good candidate": yes for the AC's actual requirements (hit/miss
  metric, tested fail-open), no for demonstrating invalidation-on-write
  specifically, since `work_items` has no update path to invalidate
  against — stated plainly rather than picked around, per the issue's
  own ask.
- Once the `services` PR is merged: rest of the rollout checklist
  (image SHA bump PR, ArgoCD sync, functional proof against the real
  cluster, then — only once actually verified — the `docs/architecture/overview.md`
  "Live today" addition and this note gets pruned).

M3 Observability: **observability#1 (OpenTelemetry tracing, ADR 0013,
backlog #17), #2 (Prometheus + Grafana, ADR 0014, backlog #18), and #3
(Loki + Tempo + Alloy, ADR 0015, backlog #19) are all done.** A real
trace from a live `POST /work-items` request was confirmed end to end:
landed in Tempo (2 spans, `api` + `workers`), its log line (same trace
ID) landed in Loki, and Grafana's Loki↔Tempo pivot (`derivedFields`/
`tracesToLogsV2`) works both directions. All 4 Prometheus targets
(`gateway`/`api`/`workers`/`otel-collector`) confirmed `up`. **Only
remaining M3 item: #20 dashboards** — can run in parallel with Redis,
see `docs/roadmap/milestones.md`. Backlog #19a (Prometheus exemplars,
the metric→trace pivot) is tracked but deliberately not built —
separate app-level change.

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

- services#5 (Redis) is next — write/confirm the measurable hypothesis
  in its issue body before touching code (this session's staff-eng
  review already rewrote the issue for this reason).
- M3 #20 (dashboards-as-code) can run in parallel with Redis — Grafana
  has no dashboards yet (deliberate, ADR 0014/0015). Datasources
  (Prometheus, Loki, Tempo) are already provisioned as code; dashboards
  should be too, alongside the alert/SLO each exists to support (per
  the `observability-engineer` persona's rule already referenced in ADR
  0014).
- Backlog #19a (Prometheus exemplars, metric→trace pivot) is a real,
  tracked gap — needs native histograms + a Micrometer exemplar bridge
  added to all three services' actuator config, not started.
