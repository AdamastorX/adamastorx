# AdamastorX — Project Context

Canonical source. Other repos (`platform`, `services`, `observability`)
carry a short pointer back here instead of a copy — one file to keep
current beats four copies drifting apart.

## Mission

Operate a small, realistic distributed system — cluster, GitOps delivery,
application, observability stack — using boring, well-understood tools, to
generate genuine platform/SRE/DevOps problems worth solving.

## Goals

- A cluster and delivery pipeline that could plausibly run in a small
  real-world platform team.
- An application (gateway/API/workers) that's just complex enough to need
  Kafka, PostgreSQL, and Redis for real reasons, not for show.
- Observability and reliability practice that's actually exercised (alerts
  fire, runbooks get used, SLOs get burned), not decorative.

## Current architecture

None yet — M0. See `docs/architecture/overview.md` for the target shape.

## Technology decisions

Approved: Kubernetes (k3s), Terraform, Helm, ArgoCD, GitHub Actions, Kafka
(KRaft), PostgreSQL, Redis, OpenTelemetry, Prometheus, Grafana, Loki, Tempo,
Mimir, Traefik, cert-manager, Trivy, Spring Boot.

Explicitly excluded — do not introduce without an ADR overturning this:
service mesh, Vault, Crossplane, Backstage, Cilium. The platform stays
intentionally small.

## Current milestone

**M0 Foundation.** See `docs/roadmap/milestones.md`.

## Repository map

| Repo | Owns |
|---|---|
| `adamastorx` | Docs, roadmap, backlog, Claude context — this repo |
| `platform` | Terraform, Helm, ArgoCD, Kubernetes manifests, bootstrap |
| `services` | Gateway, API, workers, shared libraries |
| `observability` | Grafana, dashboards, alerts, runbooks, OTel config |

## Coding principles

- Small PRs, incremental delivery.
- Simple over clever; boring over novel.
- No gold plating, no premature optimisation, no framework for a problem you
  don't have yet.
- Three similar lines beat a premature abstraction.

## Definition of Ready

- Purpose and acceptance criteria are written.
- Dependencies are identified and either resolved or explicitly `blocked`.
- Fits in one epic, ideally one repo.

## Definition of Done

- Acceptance criteria met.
- Tests pass (where the change has runtime behaviour to test).
- Docs updated — architecture, ADR, or runbook, whichever applies.
- Reviewed and merged.
