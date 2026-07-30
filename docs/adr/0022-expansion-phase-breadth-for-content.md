# 0022. Expansion phase: breadth and novelty for content, and which ADR 0021 cuts stand

Status: Proposed

## Context

ADR 0021 answered one specific question — "for a tight SRE/platform
portfolio, what should this project stop doing?" — and answered it well:
`gateway` and `whoami` (infrastructure maintaining zero function) were
removed, gnomAD/HGVS/liftover (domain breadth with no new operational
signal) were cut, and several M4 items that a single operator cannot
meaningfully exercise were closed.

The owner has since stated a *different* goal, which does not contradict
that one: **have a genuinely interesting home lab to publish articles
about, experiment with new technologies, expand the platform's usage, and
build more services and application logic.** The audience changed from
"a hiring manager skimming a repo" to "a reader who wants to learn
something they didn't know." What "earns its keep" changes with it: a
component now earns its place if it produces a *new class of operational
problem* — a new failure mode, a new scaling shape, a new data pattern —
not only if it is minimal.

This ADR exists because without it, the next person (or agent) reading
ADR 0021 will reasonably conclude that adding anything is a regression.
It is not. But the reversal must be selective, and the two categories of
ADR 0021 cut must be kept apart:

- **"This teaches nothing new"** — gnomAD (a second data source with no
  signal ClinVar lacks), HGVS (#40), liftover (#41), chaos scenarios 4–7
  (the same alert-fires-and-routes muscle), `gateway` (a two-method
  forwarder), `whoami` (a superseded proof), #33 (a solo "blameless"
  postmortem). **These stay cut.** A new goal does not make a
  content-free thing interesting; an article about re-adding gnomAD would
  be an article about downloading a file.
- **"This does not serve a *tight* portfolio"** or **"this cannot be
  exercised at this scale"** — #34 (capacity baseline), #23b (node-loss
  game day), M6/#30's whole shape. These were correct *given a
  single-node laptop and no real traffic*. Both of those premises are
  changing (a dedicated desktop host; a deliberate continuous workload),
  so these are **reopened on their merits, in a changed form** — not
  restored verbatim.

## Decision

**1. Adopt an expansion phase, M6–M9, defined in
`docs/roadmap/milestones.md` and backlog #45–#58.** Each milestone must
produce at least one operational problem this project has never had, and
each backlog item's Purpose must name the real, already-observed gap or
incident it derives from. "Interesting technology" alone is not a
purpose; the exclusion list in `.claude/PROJECT.md` stays a real gate.

**2. The following ADR 0021 cuts are explicitly upheld** and must not be
reopened without superseding this ADR: gnomAD (S3), #40 HGVS and #41
liftover (S5), chaos scenarios 4–7 (S6), the `gateway` service (S1) and
`whoami` (S2), #33 solo postmortems, and **#21b multi-window burn-rate
alerting**. #21b deserves a specific note because M6's workload generator
(#45) superficially removes its stated blocker: it does not. Burning an
error budget against traffic whose shape you authored is still theatre —
you would be alerting on your own generator's config. #21b stays closed.

**3. The following are reopened, in changed form, because their premise
changed — not because the original reasoning was wrong:**

- **#34 (capacity baseline) → #45 (continuous shaped workload).** ADR
  0021 was right that a one-off k6 run on a laptop measures the laptop.
  #45 is not a capacity measurement: it is *permanent demand*. Its
  purpose is to make SLOs, alerts, autoscaling, and canary analysis
  evaluate against something other than an idle cluster — a gap both
  chaos scenarios recorded in writing ("no existing alert caught either
  brief-outage window", `docs/SESSION_STATE.md`). It does not produce a
  "capacity baseline" number and must not claim to.
- **#23b (node-loss game day) → #52.** ADR 0021/S7's exact wording was
  "ceremony *on a single-node laptop cluster*". On a real multi-node
  cluster (#48), draining a node, watching a PDB deny an eviction, and
  losing a replica are not ceremony — they are the entire point of the
  substrate. The reasoning is unchanged; the substrate is not.
- **The "reintroduce an edge concern" clause of S1.** ADR 0021 stated
  that if a real cross-cutting concern (auth, rate-limiting across
  backends) ever arrived, an edge layer would be a fresh deliberate
  decision. #56 is that decision — and it is deliberately **Traefik
  middleware plus an auth layer, not a resurrected `gateway` service**.
  `gateway` was cut for having no function; nothing here restores an
  empty forwarder.
- **Batch/object-storage work (M6/#30, S4)** remains closed *as a
  bioinformatics pipeline*. #54 (an async job control plane for the
  ingestion that already exists) is not a resurrection of it: no new data
  domain, no alignment tooling, no multi-GB object store — it is a
  request-shape fix for a fragile synchronous endpoint the project
  already runs and has already documented as a problem.

**4. New services must create a new operational shape, not more CRUD.**
The existing shapes are synchronous CRUD (`work-items`), cache-aside with
invalidation-on-write (`/variants/lookup`), and a scheduled batch ingest.
M8's services are chosen for the shapes the project *lacks*: guaranteed
fan-out delivery (#53), long-running asynchronous work with an
observable state machine (#54), and stateful stream processing with
recoverable local state (#55).

## Consequences

- The project's stated mission in `.claude/PROJECT.md` ("boring,
  well-understood tools") is now in tension with "experiment with new
  technologies". The resolution is a rule, not a vibe: **boring for
  anything on the critical path of an existing story; novel where the
  novelty is itself the thing being learned, and isolated enough that its
  failure does not take the existing stack with it.** Cilium (ADR 0023)
  is the deliberate exception — it *is* on the critical path, which is
  why it gets its own ADR and its own rebuild window.
- Operational surface grows substantially. That is the point now, but it
  has a real cost: more components to keep synced, more CI, more alert
  rules, more that can rot silently. #32 (keeping canonical docs from
  drifting) matters more after this ADR than before it.
- ADR 0021 is **not** superseded. It remains the correct record of why
  the core is the shape it is. This ADR narrows its scope to the goal it
  was written under, and enumerates above exactly which of its cuts stand.
- Four of the five excluded tools stay excluded, with reasons stated in
  ADR 0023's context rather than left implicit.
