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
| **M5 Clinical Variant Annotation** | Real ClinVar/gnomAD-backed variant lookup, added alongside the work-item domain (ADR 0018) — the project's first skewed cache access pattern, invalidation-on-write, and data-provenance story. |
| **M6 Real Demand and Progressive Delivery** | Continuous, shaped traffic replaces an idle cluster, and deploys become canaries gated on the SLOs that traffic finally makes real. |
| **M7 Multi-Node Substrate** | Rebuild on the dedicated host as a real multi-node cluster — Cilium/Hubble, the project's first NetworkPolicies, replicated storage, and the drain/node-loss exercises one node cannot produce. |
| **M8 Application Logic: Delivery Semantics and Stream State** | New services chosen for the operational shapes the project lacks — guaranteed fan-out delivery, long-running async jobs, and stateful stream processing. |
| **M9 New Signal Classes** | Continuous profiling and admission-time policy — one new class of evidence, one new class of control, each grounded in an incident that already happened. |

M6–M9 are the expansion phase (ADR 0022). The goal changed — breadth and
novelty, on top of the tight core ADR 0021 produced — and ADR 0022 states
explicitly which of ADR 0021's cuts stand (gnomAD, HGVS/liftover,
`gateway`, `whoami`, solo postmortems, burn-rate policy) and which are
reopened *in changed form* because their stated premise changed
(#34 → #45, #23b → #52). The remaining M4 work (#23 scenario 3, #23a,
#21d, #21e, #42, #43, #44) and the cross-cutting items (#31, #32) are
not superseded by any of this and mostly gate it: **#23a in particular is
a hard prerequisite for all of M7** — migrating hosts without a proven
restore is how this project loses its data.

M6 has no new dependencies and unblocks the rest: chaos scenario 3
(consumer lag) is not meaningfully testable until #45 produces a
sustained produce rate, and both #46's canary analysis and #57's profiles
are meaningless against an idle cluster. M7 is gated on hardware and on
#23a. M8 and M9 can run in parallel with each other.

A milestone is Done (Definition of Done, `.claude/PROJECT.md`) when every
item in it is closed — that gate is unchanged. What's relaxed is only the
assumption that work on the *next* milestone can't begin until then;
individual items can start as soon as their own dependencies clear.
