# Milestones

Sequential — each depends on the previous one landing.

| Milestone | Goal |
|---|---|
| **M0 Foundation** | Org, repos, docs, workflow, backlog exist and are usable. |
| **M1 Platform Bootstrap** | k3s cluster up, ArgoCD as GitOps entrypoint, ingress/TLS, CI pipeline with security scanning. |
| **M2 Distributed Application** | Gateway + API + workers running, wired to Kafka, PostgreSQL, Redis. |
| **M3 Observability** | Full telemetry pipeline (OTel → Prometheus/Mimir, Loki, Tempo) with baseline dashboards. |
| **M4 Reliability** | SLOs, alerting, runbooks, failure testing — the system can be operated, not just run. |

No milestone starts before the previous one is Done (see Definition of Done
in `.claude/PROJECT.md`).
