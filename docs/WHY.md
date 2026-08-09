# Why this project exists, and what it actually proves

A feature list (the README's Vision and repository map) tells you what
got built. It doesn't tell you what got *learned* — the real bugs found
by actually deploying things, the one architecture decision that got
reversed and why, and what each milestone was chosen to demonstrate.
That's what this page is for: a few minutes, no ADR-reading required,
before you decide whether the detail (`docs/adr/`, `docs/SESSION_STATE.md`,
`docs/roadmap/backlog.md`) is worth your time.

## Real bugs, found by deploying, not by inspection

Four incidents recur across this project's history because each one
generalizes past its own fix:

- **Namespace-scoped resources can't cross namespaces — hit twice.**
  ADR 0018 split a ClinVar feature across two Java components in
  different Kubernetes namespaces, assuming a file written by one could
  be read by the other. It couldn't: PersistentVolumeClaims are
  namespace-scoped, so `api` failed to schedule at all
  (`persistentvolumeclaim "workers-refdata" not found`). The same
  assumption failed a second time in the same rollout — Postgres's
  generated password Secret lived in a different namespace than the
  component that now needed it. Both are the identical mistake, not two
  bugs; ADR 0019 is the fix (below).
- **A Helm chart's own idempotency logic silently regenerated a
  production credential.** Bitnami's `common.secrets.passwords.manage`
  helper reuses an existing Secret only via a live-cluster Helm
  `lookup()` — a call ArgoCD's manifest-only rendering never performs.
  Every automated GitOps sync could mint a fresh password the running
  container was never started with, confirmed recurring twice before
  the real fix (`bootstrap/create-stateful-secrets.sh`): stop the chart
  from being able to generate credentials at all, provision them
  out-of-band instead.
- **A concurrency bug found because the obvious cause was checked and
  ruled out.** Two overlapping manual ingestion triggers ran two full
  VCF scans at once and killed the pod. The instinct was "OOM" — but
  `dmesg`/`journalctl` had no OOM evidence at all. The real fix (a
  `threading.Lock()` rejecting the second concurrent call with `409`)
  came from trusting the missing evidence over the plausible story.
- **Four separate Spring Boot 4 autoconfiguration gotchas**, same root
  cause each time: Boot 4.1 split client libraries from the
  `FooAutoConfiguration` classes that wire them up into separate
  artifacts. Adding `spring-kafka` (or Flyway, or Micrometer Tracing)
  alone compiles clean and then silently does nothing at runtime — no
  error, the feature just never activates, until the matching
  `spring-boot-<name>` artifact is added too. Hit on Kafka, Flyway, and
  OTel tracing independently before the pattern was named (see
  `docs/SESSION_STATE.md`'s "recurring gotcha" section for the other
  three Boot-4 traps this project keeps hitting).

## The pivot: ADR 0018 → ADR 0019

ADR 0018 added real ClinVar variant lookup as a second Kafka-backed
domain, built inside the existing Java `api`/`workers` split. Deploying
it for real surfaced the namespace bug above — and separately, that the
Java tabix library (`htsjdk`) was a real but minority choice next to
what practitioners in this domain actually reach for (`pysam`), which
the project owner is also more fluent in.

ADR 0019 doesn't patch the symptom. It extracts all ClinVar logic into
`clinvar-service` — a new, standalone Python component with its own
namespace, own Postgres instance, own PVC — so the cross-namespace
assumption can't recur for this domain again, and states a real,
narrow rule for when Python earns its place going forward:
bioinformatics-domain logic gets Python because the ecosystem is
genuinely stronger there; everything else stays in whatever already
fits. The reasoning for the original, wrong approach is kept in
`docs/adr/0018-clinical-variant-annotation.md`, not deleted — the
pivot is the point, and pivots need the "before" to mean anything.

## What each milestone was chosen to prove

| Milestone | What it proves |
|---|---|
| M0 Foundation | The org, repos, and workflow exist and are usable — not a detail, the precondition for everything after. |
| M1 Platform Bootstrap | A real GitOps entrypoint (ArgoCD) drives a real cluster, not `kubectl apply` by hand. |
| M2 Distributed Application | A real request crosses gateway → API → Kafka → workers → Postgres/Redis — the base distributed-systems shape everything else builds on. |
| M3 Observability | A trace from one real request is followable end to end across all three telemetry pillars (metrics, logs, traces) in one Grafana session. |
| M4 Reliability | The system can be *operated*, not just run — SLOs, alerting, and runbooks that a real on-call human could follow. |
| M5 Clinical Variant Annotation | A genuinely skewed, invalidation-on-write cache pattern exists alongside the original TTL-only one — a real before/after, not a relabeled demo. |
| M6 Real Demand and Progressive Delivery | Deploys become canaries gated on SLOs that continuous, shaped traffic finally makes real — no more idle-cluster theater. |
| M7 Multi-Node Substrate | *(rescoped 2026-08-09, ADR 0040)* — a real capacity measurement showed the planned multi-node move doesn't fit this machine. Cilium/Hubble and this project's first NetworkPolicies proceed on **one node** via a deliberate cluster rebuild; the multi-node substrate itself (replicated storage, node-drain/rolling-upgrade exercises, the Istio ambient mesh) stays *blocked-on-hardware, no date* — honestly labeled, not faked on one node. |
| M8 Delivery Semantics and Stream State | New operational shapes the project genuinely lacked — guaranteed fan-out, async job orchestration, stateful stream processing — chosen for the shape, not the buzzword. |
| M9 New Signal Classes | Continuous profiling and admission-time policy, each justified by an incident that already happened, not spec'd ahead of need. |
| M10 Platform Automation | Autoscaling, chaos, and cost visibility earn their place once load is real and workloads are diverse enough to need them. |
| M11 AI-Assisted SRE | *(sequenced after M15)* — a real incident-triage agent over this project's own telemetry, graded honestly against human-written fact packs it didn't help write. |
| M12 Bioinformatics Workloads | *(gated on M7)* — the harder batch/object-storage story ADR 0018's own reasoning explicitly reserved and didn't let float away unbuilt. |
| M13 Real-Time Market Sentiment Pipeline | Five services process real, continuously-flowing external data (live stock prices, real financial news) with no synthetic stand-in anywhere in the pipeline. |

M14/M15 (this milestone and the next, ADR 0031) don't get a row here —
they're the reason this page exists, not a subject for it.

## Where the detail actually lives

Every claim above links to something checkable, not to this page's own
authority: `docs/adr/` for the full reasoning behind each decision
(including the rejected alternatives), `docs/SESSION_STATE.md` for the
messier, blow-by-blow incident record, and `docs/roadmap/backlog.md`
for what's actually done versus still open, with the real evidence
attached to each closed item.
