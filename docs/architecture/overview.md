# Architecture overview

Status: M0-M3 and M5 complete/verified live; M4 Reliability under way
(ADR 0020) — real histogram/consumer-lag/`clinvar-service` metrics,
SLO-backed alert rules, and Alertmanager are live; runbooks and chaos
scenarios are not yet. M5 Clinical Variant Annotation is live:
`clinvar-service` (Python, ADR 0019) ingests real ClinVar data and
answers lookups through `api`, proven end to end against the live
cluster (`rs80357906` → BRCA1, "Pathogenic"). **A simplification pass
(ADR 0021) removed `gateway` and `whoami` entirely** — both carried
real infrastructure (a Spring Boot module, CI pipeline, namespace,
ArgoCD Application, Ingress, TLS cert each) while doing no real work
(`gateway` forwarded exactly one placeholder route; `whoami` was a
one-time Traefik+TLS proof, superseded once `api` got its own real
Ingress). The diagram below shows the current shape, with a note
underneath marking what exists today; it is the map, not the
territory.

## Shape of the system

```
                      ┌──────────────────────────┐
                      │        GitHub            │
                      │  (source of truth, all   │
                      │   repos, Actions CI)      │
                      └────────────┬─────────────┘
                                   │ push
                                   ▼
                      ┌──────────────────────────┐
                      │         ArgoCD           │
                      │   (GitOps entrypoint,    │
                      │    watches `platform`)   │
                      └────────────┬─────────────┘
                                   ▼
┌─────────────────────────── k3s cluster ───────────────────────────┐
│                                                                     │
│  Traefik (ingress) ─────────────▶ API ─┬─▶ PostgreSQL               │
│  cert-manager (TLS)                    ├─▶ Redis                   │
│                                        ├─▶ Kafka (KRaft) ─▶ Workers │
│                                        └─▶ clinvar-service (Python) │
│                                             ├─▶ its own PostgreSQL  │
│                                             └─▶ ClinVar VCF (PVC)   │
│                                                                     │
│  OTel Collector, Prometheus + Alertmanager, Loki, Tempo ─▶ Grafana  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Live today:** GitHub as source of truth; a single-node k3s v1.36.2 cluster
(provisioned via Terraform from `platform/terraform/`); ArgoCD v3.4.5
(app-of-apps over the `platform` repo's `argocd/apps/`, prune + selfHeal);
Traefik 41.0.2 on hostPort 80/443; and cert-manager v1.21.0 with a local CA
chain (`selfsigned` → `adamastorx-ca` ClusterIssuer — Let's Encrypt deferred
until a host with public DNS). The `services` repo's CI builds and
Trivy-scans every PR image as a required merge gate — a fixable
CRITICAL/HIGH CVE in a base image blocks the merge, as already happened
once. The API service (Maven module in `services`, Spring Boot/webmvc/
actuator) is built, published to GHCR, and deployed in-cluster in its
own namespace (manifests in `platform/kubernetes/api/` +
`argocd/apps/api.yaml`) — **with its own public Ingress and TLS
certificate** (`api.local.adamastorx.test`, ADR 0021), the live
Traefik+TLS+service path. This replaces an earlier design (ADR 0010)
where a separate `gateway` service forwarded to `api`: `gateway` never
grew past one placeholder route and was removed entirely (ADR 0021),
along with `whoami`, the original one-time Traefik+TLS proof app.
`workers` (services#3) is deployed the
same way — its own module, its own namespace, no Service (it has no
business HTTP API, ADR 0011) — consuming from a single-broker Kafka
(KRaft, combined controller+broker mode) deployed as a Helm-chart ArgoCD
Application in its own `kafka` namespace, ClusterIP only. `api` publishes
to the `work-items` topic (3 partitions, RF 1) on `POST /work-items`;
`workers` consumes and logs it — the async produce→consume path and
multi-replica consumer-group rebalance are both proven against this real
cluster, not just unit tests. `api` also persists to PostgreSQL
(services#4, ADR 0012): `POST /work-items` writes a row via Spring Data
JPA before publishing to Kafka, `GET /work-items` reads it back. Schema
is a Flyway migration (versioned, repeatable). Postgres runs as a
single-instance Bitnami chart deployed into `api`'s own namespace rather
than a separate one — it has exactly one consumer, unlike Kafka's two,
and its generated credentials Secret can't be read across namespaces —
with a real PVC (2Gi, k3s's `local-path` StorageClass), the first
genuinely persistent storage in this cluster (Kafka's topic data is
deliberately ephemeral, ADR 0011).

**Known gap:** the Postgres write and the Kafka publish are two separate
operations with no compensating logic — a publish failure after a
successful save leaves a work item persisted but never handed to
`workers`. Flagged in ADR 0012, tracked as services#16 (transactional
outbox / idempotent consumer), not fixed speculatively.

`api` also fronts `GET /work-items/{id}` with a Redis cache-aside layer
(services#5, ADR 0016): a hand-rolled `RedisTemplate`-based service
(not `@Cacheable` — Boot has no Redis cache-metrics binder), hit/miss/
error counters on `/actuator/prometheus`, fail-open to PostgreSQL on a
Redis outage (tested in CI by stopping the Testcontainers Redis
mid-test, confirmed against the live cluster too: a real
`GET`/`GET` round-trip produced one `miss` then one `hit`, zero
errors). Redis (Bitnami chart, standalone architecture, no PVC — cache-
aside means Postgres stays the only source of truth) lives in `api`'s
namespace, not its own, same reasoning ADR 0012 used for Postgres
(single consumer, real credential, `secretKeyRef` can't cross
namespaces). No invalidation-on-write is demonstrated here, on
purpose and stated plainly: `work_items` rows are immutable post-
creation, so there's nothing to invalidate against — any expiry here
is TTL-only hygiene, not a correctness mechanism.

**Observability (M3, extended by M4):** `api`/`workers` export traces via
Micrometer Tracing + OTLP to an OpenTelemetry Collector (observability#1,
ADR 0013) deployed as an ArgoCD Application in its own `otel` namespace —
a real trace ID correlates `api`→Kafka→`workers` (message hop; the
original `gateway`→`api` HTTP hop this was first proven against no
longer exists, ADR 0021), proven in live application logs. Traces land
in Tempo (single-binary chart, own `tempo` namespace, 72h retention, 2Gi
PVC — observability#3, ADR 0015), the Collector's traces pipeline
exporting `otlp/tempo` in place of ADR 0013's `debug` placeholder.
Metrics flow the existing Boot actuator way: `api`/`workers` expose
`/actuator/prometheus`, `clinvar-service` exposes `GET /metrics`
(`prometheus_client`, backlog #21a), scraped by a plain
`prometheus-community/prometheus` chart (own `prometheus` namespace, no
Operator, 3-day retention, 2Gi PVC — observability#2, ADR 0014); `api`/
`clinvar-service` via static targets, `workers` via Kubernetes pod-role
service discovery (it has no Service, ADR 0009/0011), plus the
Collector's own self-monitoring metrics. Logs are shipped by Alloy (a
DaemonSet, own `alloy` namespace, explicit River pipeline reading pod
logs via the Kubernetes API — no hostPath mount) into Loki
(`Monolithic` mode, filesystem storage, own `loki` namespace, 72h
retention, 2Gi PVC). Grafana (own `grafana` namespace, no PVC, charts
sourced from `grafana-community/helm-charts` since the original
`grafana/helm-charts` repo is deprecated) has Prometheus, Loki, and
Tempo pre-provisioned as datasources, with the Loki↔Tempo trace/log
pivot wired via `derivedFields`/`tracesToLogsV2` — proven end to end
with a real request's trace ID appearing in both. No metric→trace
exemplar pivot yet (backlog #19a). Grafana has one golden-signal
dashboard per service (`api`/`workers`, backlog #20, ADR 0017;
`clinvar-service`'s own signals tracked separately, backlog #29),
provisioned as code (`platform/argocd/apps/grafana.yaml`'s
`dashboardProviders`/`dashboards` values, file-based, no sidecar).
Real latency percentiles and a real Kafka consumer-lag metric (both
originally stated as known gaps) shipped under backlog #21a and are
plotted on the dashboards today, not the earlier average/max/thread-pool
stand-ins. **M4** (ADR 0020) built on this: Alertmanager is live with one
real notification channel (an `ntfy.sh` webhook, backlog #21c) and seven
SLO-backed alert rules (backlog #21), verified firing into real
Prometheus/Alertmanager state. Runbooks (#22) and the trimmed 3-scenario
chaos plan (#23, ADR 0021/S6) are not yet built.

**M5 Clinical Variant Annotation:** `clinvar-service` (own `clinvar`
namespace, ADR 0019) is this project's first non-JVM component —
FastAPI + `pysam` + `psycopg` + `confluent-kafka`, built specifically
because the domain (real ClinVar VCF/tabix data, real bioinformatics
libraries) justified it, not a wholesale language migration. It owns
ClinVar end to end: a weekly (and admin-triggerable, `POST
/internal/clinvar/ingest`) download from NCBI, a real pysam tabix
rebuild (NCBI's published `.tbi.md5` checksum sidecar turned out not to
exist at the documented URL — a real discrepancy found live, not in
any doc — so validation always falls through to the rebuild path), a
dedicated Postgres instance (its own namespace, its own generated
credential — ADR 0019 exists specifically because a shared Postgres
Secret and a shared PVC both turned out not to be able to cross the
`api`/`workers` namespace boundary, two real bugs that drove this
redesign), and a `clinvar_variant_index` table for rsID lookups. `api`
holds no ClinVar file or DB access at all; it calls `clinvar-service`
over HTTP (`ClinVarServiceClient`, Spring `RestClient`, the same
service-to-service HTTP pattern ADR 0010 originally established for
`gateway`→`api`, before `gateway` was removed entirely — ADR 0021) and
fronts the result with the Redis
cache-aside layer from ADR 0016, invalidated on write via a Kafka event
(`clinvar.ingestion.completed`) carrying the specific cache keys a new
release actually changed — this project's first skewed-access,
invalidate-on-write cache pattern, as opposed to `work-items`' pure
TTL hygiene. Proven end to end against the real cluster: a real
ingestion run (4,453,798 VCF records, 2,895,514 rsID-indexed rows) and
a real `GET /variants/lookup?rsid=rs80357906` through `api` returning
BRCA1's real ClinVar classification, `"Pathogenic"`. **Known gap:** the
ingestion endpoint runs synchronously for several minutes; a
concurrency guard (services#36) now rejects a second overlapping
trigger (409) after two overlapping manual triggers once ran two full
VCF scans side by side and took the pod down, but the endpoint itself
is still blocking rather than fire-and-poll.

**Not yet:** Mimir (long-term/multi-tenant metrics storage,
backlog #18a, a separate experiment not required for the single-node
Prometheus already live); runbooks (#22) and the 3-scenario chaos plan
(#23); `ClinVarInvalidationLag` alert and release-ID trace propagation
for `clinvar-service` (observability#13/#14, re-scoping against ADR
0019's actual Python architecture, not yet started).

## Boundaries

- **platform** owns everything below the application: cluster, ingress, TLS,
  GitOps delivery, CI pipeline definitions.
- **services** owns the application: API, workers, `clinvar-service`, shared libraries.
- **observability** owns what you look at when something breaks: dashboards,
  alerts, runbooks, OTel config. Kept separate from `platform` deliberately —
  different change cadence and different owners in a real org (SRE vs.
  platform team), and it keeps blast radius of a dashboard edit away from
  cluster-changing Terraform/Helm.

## Why this split and not fewer repos

Four repos, not one monorepo, because the repo boundary doubles as the
ownership/blast-radius boundary — a Terraform change in `platform` should
never be gated on an unrelated Spring Boot PR in `services`. This is a
deliberate real-world constraint, not an accident of scale.

Decisions that deviate from the approved stack, or that are non-obvious and
worth defending later, go in `docs/adr/` — this file only describes the
current shape, not the reasoning.
