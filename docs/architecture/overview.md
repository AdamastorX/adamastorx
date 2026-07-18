# Architecture overview

Status: M0 — no infrastructure exists yet. This document will grow as
`platform` and `services` are bootstrapped; it is the map, not the territory.

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
