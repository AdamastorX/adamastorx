# Milestones

Ordered by goal, not a hard gate — an item starts when *its own* listed
dependencies in `backlog.md` are met, not when every item in the previous
milestone is closed. M3's OTel instrumentation (#16) only depends on
Kafka (#13, done); it doesn't need to wait on Redis (#15, still open in
M2) just because of the table row it happens to sit in. Observability is
meant to grow alongside the system it observes, not get bolted on after
the fact — see `docs/SESSION_STATE.md` for the current parallel-work
state.

| Milestone | Goal |
|---|---|
| **M0 Foundation** | Org, repos, docs, workflow, backlog exist and are usable. |
| **M1 Platform Bootstrap** | k3s cluster up, ArgoCD as GitOps entrypoint, ingress/TLS, CI pipeline with security scanning. |
| **M2 Distributed Application** | Gateway + API + workers running, wired to Kafka, PostgreSQL, Redis. |
| **M3 Observability** | Full telemetry pipeline (OTel → Prometheus/Mimir, Loki, Tempo) with baseline dashboards. |
| **M4 Reliability** | SLOs, alerting, runbooks, failure testing — the system can be operated, not just run. |

A milestone is Done (Definition of Done, `.claude/PROJECT.md`) when every
item in it is closed — that gate is unchanged. What's relaxed is only the
assumption that work on the *next* milestone can't begin until then;
individual items can start as soon as their own dependencies clear.
