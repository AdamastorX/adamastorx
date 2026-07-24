# Architecture overview

Status: M1 Platform Bootstrap complete; M2 Distributed Application in
progress — the platform layer, CI, gateway, API, workers, and Kafka are
live; PostgreSQL, Redis, and the observability layers are still
target-only. The diagram below shows the target shape, with a note
underneath marking what exists today; it is the map, not the territory.

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
│  OpenTelemetry Collector ─▶ Prometheus/Mimir, Loki, Tempo ─▶ Grafana│
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
cluster, not just unit tests.

**Not yet:** PostgreSQL and Redis; the entire observability row (OTel
Collector, Prometheus/Mimir, Loki, Tempo, Grafana).

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
