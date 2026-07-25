# Architecture overview

Status: M1 Platform Bootstrap complete; M2 Distributed Application in
progress (Kafka/PostgreSQL live, Redis still target-only); M3
Observability under way — tracing (OpenTelemetry Collector + Tempo),
metrics (Prometheus + Grafana), logs (Loki + Alloy), and golden-signal
dashboards for all three services are all live; long-term/multi-tenant
metrics storage (Mimir) and alerting/SLOs are not. The diagram below
shows the target shape, with a note underneath marking what exists
today; it is the map, not the territory.

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
│  Traefik (ingress) ─┬─▶ Gateway ─▶ API ─┬─▶ PostgreSQL              │
│  cert-manager (TLS) │                   ├─▶ Redis                  │
│                     │                   └─▶ Kafka (KRaft) ─▶ Workers│
│                                                                     │
│  OpenTelemetry Collector, Prometheus, Loki, Tempo, Mimir ─▶ Grafana │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Live today:** GitHub as source of truth; a single-node k3s v1.36.2 cluster
(provisioned via Terraform from `platform/terraform/`); ArgoCD v3.4.5
(app-of-apps over the `platform` repo's `argocd/apps/`, prune + selfHeal);
Traefik 41.0.2 on hostPort 80/443; and cert-manager v1.21.0 with a local CA
chain (`selfsigned` → `adamastorx-ca` ClusterIssuer — Let's Encrypt deferred
until a host with public DNS). A proof app, `whoami`, serves through Traefik
with TLS from that CA. The `services` repo's CI builds and Trivy-scans every
PR image as a required merge gate — a fixable CRITICAL/HIGH CVE in a base
image blocks the merge, as already happened once. The Gateway service is
scaffolded (Maven multi-module reactor in `services`), built and published
to GHCR, and deployed in-cluster (manifests in `platform/kubernetes/gateway/`
+ `argocd/apps/gateway.yaml`), reachable at `gateway.local.adamastorx.dev`
through Traefik with TLS, with actuator health checks wired to its
liveness/readiness probes. The API service is scaffolded the same way (its
own Maven module in `services`, same Spring Boot/webmvc/actuator shape as
gateway), built, published to GHCR, and deployed in-cluster in its own
namespace (manifests in `platform/kubernetes/api/` +
`argocd/apps/api.yaml`), ClusterIP-only with no Ingress — it is never
externally reachable except through `gateway`. `gateway` reaches it via a
hand-rolled forwarding controller on Spring's blocking `RestClient`,
resolving it through Kubernetes Service DNS
(`http://api.api.svc.cluster.local`) injected as `API_SERVICE_URL` on the
gateway Deployment, per ADR 0010. `workers` (services#3) is deployed the
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

**Observability (M3):** all three services (`gateway`/`api`/`workers`)
export traces via Micrometer Tracing + OTLP to an OpenTelemetry
Collector (observability#1, ADR 0013) deployed as an ArgoCD Application
in its own `otel` namespace — a real trace ID correlates
`gateway`→`api` (HTTP) and `api`→Kafka→`workers` (message hop), proven
in live application logs. Traces land in Tempo (single-binary chart,
own `tempo` namespace, 72h retention, 2Gi PVC — observability#3, ADR
0015), the Collector's traces pipeline exporting `otlp/tempo` in place
of ADR 0013's `debug` placeholder. Metrics flow the existing Boot
actuator way: all three services expose `/actuator/prometheus` (needs
`micrometer-registry-prometheus` + `management.endpoints.web.exposure.include`,
not on by default — a real gap found deploying this), scraped by a
plain `prometheus-community/prometheus` chart (own `prometheus`
namespace, no Operator, 3-day retention, 2Gi PVC — observability#2, ADR
0014); `gateway`/`api` via static targets, `workers` via Kubernetes
pod-role service discovery (it has no Service, ADR 0009/0011), plus the
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
exemplar pivot yet (backlog #19a — needs Prometheus native histograms +
a Micrometer bridge on all three services). Grafana also has one golden-
signal dashboard per service (`gateway`/`api`/`workers`, backlog #20,
ADR 0017), provisioned as code (`platform/argocd/apps/grafana.yaml`'s
`dashboardProviders`/`dashboards` values, file-based, no sidecar) —
deliberately shipped ahead of alerts/SLOs (backlog #21, M4), a tension
ADR 0017 resolves explicitly rather than silently: these four signals
are the standard SLO precursor, not unrelated dashboard sprawl. Two
known gaps stated on the dashboards themselves: no true latency
percentiles (Boot's histogram buckets aren't enabled), and `workers`'
"saturation" panel uses thread-pool usage as a stated proxy, since no
Kafka consumer-lag metric is wired up yet.

**Not yet:** Redis; Mimir (long-term/multi-tenant metrics storage,
backlog #18a, a separate experiment not required for the single-node
Prometheus already live); alerts and SLOs (backlog #21, M4).

## Boundaries

- **platform** owns everything below the application: cluster, ingress, TLS,
  GitOps delivery, CI pipeline definitions.
- **services** owns the application: gateway, API, workers, shared libraries.
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
