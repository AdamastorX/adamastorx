# Architecture overview

Status: M1 in progress — the platform layer is live; the application and
observability layers are still target-only. The diagram below shows the
target shape, with a note underneath marking what exists today; it is the
map, not the territory.

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
with TLS from that CA.

**Not yet:** the Gateway/API/Workers application with Kafka, PostgreSQL, and
Redis; the entire observability row (OTel Collector, Prometheus/Mimir, Loki,
Tempo, Grafana); and the Actions CI pipeline (remainder of M1).

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
