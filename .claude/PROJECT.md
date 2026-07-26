# AdamastorX — Project Context

Canonical source. Other repos (`platform`, `services`, `observability`)
carry a short pointer back here instead of a copy — one file to keep
current beats four copies drifting apart.

Before starting work, also check `docs/SESSION_STATE.md` — in-flight
work, open PRs, known gremlins, and anything the last session left
unfinished. This file (`PROJECT.md`) is the stable picture; that one is
the scratch log of *right now*.

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

A single-node k3s v1.36.2 cluster (the owner's local machine, provisioned via
Terraform SSH remote-exec from `platform/terraform/`; moving to a dedicated
host is a planned variable change) runs ArgoCD v3.4.5 as the GitOps
entrypoint — an app-of-apps root Application watches the `platform` repo's
`argocd/apps/` on `main` with prune + selfHeal, so all cluster changes flow
through Git. Traefik 41.0.2 (hostPort 80/443) and cert-manager v1.21.0 are
deployed as ArgoCD Helm Applications, with a local CA chain (`selfsigned` →
`adamastorx-ca` ClusterIssuer); Let's Encrypt is deliberately deferred until
a host with public DNS. The proof app `whoami` serves through Traefik with
TLS from that CA. See `docs/architecture/overview.md` for what's live vs.
the target shape.

## Technology decisions

Approved: Kubernetes (k3s), Terraform, Helm, ArgoCD, GitHub Actions, Kafka
(KRaft), PostgreSQL, Redis, OpenTelemetry, Prometheus, Grafana, Loki, Tempo,
Mimir, Traefik, cert-manager, Trivy, Spring Boot.

Explicitly excluded — do not introduce without an ADR overturning this:
service mesh, Vault, Crossplane, Backstage, Cilium. The platform stays
intentionally small.

## Current milestone

**M4 Reliability** in progress (M0-M3 and M5 complete/verified live).
M2 Distributed Application: done — gateway, API, workers wired to Kafka
(ADR 0011), PostgreSQL (ADR 0012), and Redis cache-aside (services#5, ADR
0016). M3 Observability: done — OTel tracing (ADR 0013), Prometheus/Grafana
(ADR 0014), Loki/Tempo/Alloy (ADR 0015), golden-signal dashboards (ADR
0017), all proven against the real cluster. M5 Clinical Variant Annotation:
done — `clinvar-service` (Python/FastAPI, ADR 0019, superseding ADR 0018's
original in-Java design after two real cross-namespace bugs) verified live
end to end (`rs80357906` → BRCA1, `"Pathogenic"`). M4 Reliability
(ADR 0020) is now the active milestone: real histogram/consumer-lag/
`clinvar-service` metrics (backlog #21a) are the current prerequisite,
ahead of SLOs/alerting (#21), runbooks (#22), and chaos scenarios (#23).
See `docs/roadmap/milestones.md` and `docs/SESSION_STATE.md` for exactly
what's in flight right now — this section is a point-in-time summary, that
file is the current source of truth.

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
- Opened as a PR (never committed straight to `main`) and merged only after
  the human owner reviews and approves it — see `.claude/WORKFLOW.md`.
