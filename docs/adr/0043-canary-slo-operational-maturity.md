# 0043. M16 canary + SLO operational maturity: exercising and calibrating what already exists, no new components

Status: Accepted

## Context

Backlog #46 (Argo Rollouts canary on `api` with an automated Prometheus-based
SLO analysis gate) is Done. It is not a paper closure — it is proven live in
both directions, on the real cluster, against real traffic: a clean
promotion in **2m56s**, and an automatic abort reproducing the exact real
#35 incident shape (a rollout stuck in `CrashLoopBackOff` for 95 minutes
while the old pod kept serving, invisible because nothing about that state
is "down") in **3m01s**, with the previous pod confirmed undisturbed
throughout (`platform/docs/runbooks/canary.md`). The mechanism is real:
`kubernetes/api/rollout.yaml`'s canary steps (`setWeight: 50` → `pause: 30s`
→ `analysis` → `setWeight: 100`) gated by `kubernetes/api/analysistemplate.yaml`
(`api-slo-check`), which queries the live Prometheus for the exact non-5xx
and p95-latency expressions ADR 0020/#21 already shipped.

Two things about that proof are stated honestly in the same files, not
glossed:

1. **The AnalysisTemplate's p95 threshold is a placeholder, not a derived
   number.** `analysistemplate.yaml`'s own comment says so in as many words:
   "the 1000ms threshold below is genuinely new — stated openly, not
   disguised as reused, because nothing to reuse exists yet: picked as a
   generous ceiling ... the same 'not tuned against a real historical
   distribution yet' caveat ADR 0020 already used for its own thresholds."
   ADR 0020's own §SLOs table carries the identical caveat for every service:
   "Error budgets and exact thresholds are set from each service's real
   current traffic/latency distribution once the histogram/lag metrics are
   live — not picked in the abstract in this ADR." Neither has happened yet.
2. **The analysis measures the whole Service, not the canary pod in
   isolation.** Prometheus scrapes `api` via its Service DNS target (ADR
   0014), not per-pod, so the AnalysisTemplate's numbers are the aggregate
   of stable + canary traffic during the canary window — `rollout.yaml`'s
   own comment states plainly that this "cannot distinguish 'the new pod is
   bad' from 'the old pod got worse' by itself," and that closing it (per-pod
   scrape labels) is real, out-of-scope follow-on work, deliberately not
   done in #46 to keep that item's AC literal.

Separately, backlog #94 (raise Prometheus retention, publish the first
SLO-over-time report) shipped its config on **2026-08-07**
(`retention: 30d`, `persistentVolume.size: 16Gi`, platform#125, ADR 0014
addendum) and is running its real clock now. As of this ADR the retained
history is real and intact (`up` queried at 1–7-day offsets returns real,
non-zero series counts per the 2026-08-11 staff review, §4a) but the 30-day
window itself does not close until **~2026-09-06**. This is a hard,
real-calendar dependency — nothing in this ADR can make that data exist
early, and nothing here should pretend otherwise.

The 2026-08-11 staff review
(`docs/reviews/2026-08-11-staff-review-differentiation-and-article-strategy.md`)
is the binding constraint on how this milestone is shaped, not just useful
context. §3c's verdict, reached after weighing "add a small new domain"
against three named criteria (the standing ADR 0031 gate not clearing, CPU
headroom at 84% requested, and ADR 0022's own "new operational shape" test
having no cheap unclaimed shape left) is explicit: **"no new domain, no new
application service, no new always-on component this stretch ... not
'later' — not this stretch, as a stated stop, so it does not erode into a
default."** §3c's own operational-shape inventory already lists
**"canary-with-SLO-gate"** among the shapes this project has already
claimed — this ADR is not inventing a capability, it is exercising and
proving out one that exists. §3d's verdict, having weighed "deeper
technically" (exemplars, Chaos Mesh, Kyverno, Kubecost — each defensible in
isolation, none of them differentiated) against "deeper operationally,"
calls the second one the project's actual differentiating asset: **"the
project's next differentiating asset is not a component; it is a dated
series of real operational events with real response times and honest
outcomes."** This ADR exists to produce exactly that, in the canary+SLO
domain specifically, and it upholds §3d's verdict rather than relitigating
it — the owner was asked directly whether to overturn or stay inside that
verdict for this milestone and chose to stay inside it.

Backlog #21b (multi-window burn-rate alerting) was closed under ADR 0021 as
unearned complexity for "a single-operator project whose traffic is
self-generated (manual/test requests, not real users) — there is no budget
to unknowingly burn." ADR 0031 §5 restated that closure explicitly as
something that does not change under the post-expansion consolidation
phase. The owner was asked directly whether this new milestone — which
touches the same SLO/threshold surface #21b would have extended — is reason
to reopen it, and chose not to. That premise (self-generated traffic, no
real error budget at risk of silent depletion) has not changed between
ADR 0021 and today: #45's workload-generator is still the traffic source
behind #46's canary proof and behind #94's retained history alike. This ADR
records that as a **deliberate, considered non-reopening**, not a silent
omission — the same way ADR 0031 §5 did, so a future reader finds a decision
rather than an absence.

`docs/WHY.md`'s own stated values — real incidents over inspection, honest
reporting of gaps rather than glossing them — are the voice this ADR's
deliverables are held to: a drill that produces an ambiguous or genuinely
bad result is worth recording as such, the same way #46's own runbook
recorded a real bug (`or vector(0)`) found live rather than absorbed
silently, and the same way ADR 0020's 2026-08-14 addendum corrected a stale
baseline in the record instead of quietly editing the number.

## Decision

### 1. A new milestone, M16, defined narrowly: prove out and calibrate the canary+SLO machinery that already exists

M16's goal is real, dated operational evidence in the canary+SLO domain —
nothing else. It adds **zero** new ArgoCD Applications, zero new namespaces,
zero new always-on workloads, and zero new steady-state CPU/memory
requests, matching the "total added CPU: zero" shape the 2026-08-11 review
found available across its entire recommended stretch. ADR 0022's "new
operational shape" test does not even apply here in the way it applies to a
new service: this milestone deliberately produces no new shape, only more
and better-calibrated evidence for a shape (`canary-with-SLO-gate`) §3c
already credits the project with having.

Three real backlog items fall out of this decision, described below by
their goal rather than pre-assigned to final numbers (this ADR does not
edit `backlog.md`; a follow-up PR mints them contiguously from the current
backlog maximum). A fourth candidate item the requester's analysis raised —
duplicating #94's SLO-over-time report — is deliberately **not** spawned;
see §3.

| Item (working title) | What it does | Dependency | Can start |
|---|---|---|---|
| Canary drill cadence | Recurring, deliberately exercised good/bad deploys against `api`'s existing Rollout, each producing a real dated outcome | None — #46's mechanism and #45's real traffic already exist | Immediately |
| SLO threshold calibration | ADR 0020 addendum replacing placeholder thresholds (incl. the AnalysisTemplate's 1000ms p95) with values derived from #94's real 30-day data | #94 (its 30-day window, ~2026-09-06) | Only after #94 closes |
| Canary narrative / article | One article's evidence pack: real drill data + real calibration numbers + the existing #46 proof, feeding #129's cadence | Both items above (needs their real output to write about) | After both land |

### 2. Item: a recurring canary drill cadence, using the existing mechanism only

**Purpose.** #46 proved the mechanism works, once, in a pre-merge test on
2026-07-30. A single proof is a demo; a **recurring, dated series** of
drills is the "dated series of real operational events" §3d calls for,
specific to this domain — each drill is a real event with a real elapsed
time and a real, honestly recorded outcome, not a rerun of the same demo.

**Mechanism — nothing new is built.** Every drill uses commands
`platform/docs/runbooks/canary.md` already documents: a deliberately-good
image bump (clean promotion) or a deliberately-reintroduced fault (the #35
`CrashLoopBackOff` shape, or any other real fault this project's chaos
history already knows how to induce) driven through `kubectl argo rollouts
get/promote/abort/retry`, gated by the same `api-slo-check`
`AnalysisTemplate` #46 already shipped. No new AnalysisTemplate, no new
Rollout, no new dashboard.

**Cadence and record.** At minimum one drill (alternating clean-promotion
and induced-fault shape run over run, so the abort path stays exercised
too, not just the happy path) per operations-review cycle once backlog #124
(the standing operations review) is running — reusing that cadence rather
than inventing a second one. Each drill's outcome is appended as a dated
entry to `platform/docs/runbooks/canary.md`'s existing "Live verification"
section, the same postscript pattern #47 already established for the
chaos-scenario fact packs (`observability/chaos/01-*.md`/`02-*.md` grew
dated postscripts rather than spawning new files per re-run) — elapsed
time, abort/promote reason, and explicit comparison against the #46
baseline (2m56s clean / 3m01s abort): confirms the baseline, or names a
real divergence and why. A drill whose result is ambiguous because of the
known whole-Service-scrape limitation (§Context point 2 — the analysis
cannot always tell "new pod bad" from "old pod worse") is recorded as
ambiguous, honestly, not smoothed into a clean result it wasn't.

**No dependency.** #46's mechanism and #45's continuous real traffic both
already exist; this item can start immediately and does not wait on M16 as
a whole, #94, or M15 closing.

### 3. Item: real SLO threshold calibration, gated on #94's real 30-day window

**Purpose.** Two files currently carry the same stated caveat: ADR 0020's
SLO table ("not picked in the abstract in this ADR") and
`analysistemplate.yaml`'s p95 threshold comment ("not tuned against a real
historical distribution yet ... revisit once a real p95 distribution exists
to tune against"). #94 is what makes a real distribution exist. Once its
30-day retention window closes (~2026-09-06, a hard calendar dependency —
nothing here accelerates it), this item is the follow-through the caveats
already promised.

**Scope.** Every ADR 0020 SLO-table threshold still carrying that caveat is
revisited against #94's real accumulated data — not just `api`'s canary
gate, since the caveat is stated project-wide, not row-by-row. In practice
the highest-value, most concrete instance is the AnalysisTemplate's own
`p95-latency-seconds` `successCondition: result[0] <= 1.0` (the 1000ms
placeholder named directly in the requester's analysis and in the file's
own comment): replaced with a value derived from `api`'s real p95/p99
distribution over the closed 30-day window, computed the same way #94's own
report computes it.

**Recorded as an ADR 0020 addendum — the pattern ADR 0020 already used on
itself.** ADR 0020's 2026-08-14 addendum corrected a stale ~90s ingestion
baseline to a real, measured ~420s once real full-scale data existed, in
the record, with the old number, the new number, and the reason for the
gap stated side by side — not a silent edit. This item's calibration
follows the identical shape: a new dated ADR 0020 addendum stating the old
placeholder value, the new derived value, the real distribution it was
derived from (with enough of #94's own numbers quoted to be checkable), and
the `analysistemplate.yaml`/alerting-rules PR that lands alongside it in
the same change. A threshold changing with no addendum is exactly the
"quietly edited with no trail" outcome this item exists to prevent.

**Dependency.** Hard-gated on #94 closing (~2026-09-06). This is the one
piece of M16 that cannot be pulled forward by effort — the same honesty
this project applied to #94 itself ("nothing here should fake this data
early") applies here without exception.

### 4. #94's own report is referenced, not duplicated

The first SLO-over-time report is #94's own stated deliverable
("A first per-service SLO-over-time report from ADR 0020's table published
as a dated doc once enough real days have accumulated — the article's
evidence pack"). M16 depends on it and reads it; M16 does not re-scope or
re-file it under a new number. The requester's analysis correctly treated
this as a dependency rather than a new item, and this ADR confirms that
judgment rather than inventing a parallel reporting item that would just
restate #94's own AC.

### 5. Item: a canary-specific narrative feeding the existing article cadence, not a new publishing mechanism

**Purpose.** Backlog #129 already exists and already names the mechanism —
"an article publishing cadence, with the next three targets named" — and
already has three targets queued (the rebuild aftermath, the hardware
ceiling story, the sre-agent grading). This item adds a **fourth queued
target**, using #129's existing cadence and evidence-linking convention
(each article links checkable in-repo evidence rather than restating
claims), not a new mechanism.

**What it is.** One evidence pack combining three real, dated things this
ADR's other two items and #46 together produce: the recurring drill
series's real outcomes (§2), the real calibration numbers and the old→new
threshold delta (§3), and #46's own already-proven clean/abort timings —
one article, e.g. "what a canary gate actually catches, measured against
real thresholds instead of a guess." No new evidence-gathering step is
invented for this; the article is assembled from what the other two items
already produced.

**Dependency.** Needs real output from both §2 and §3 to be worth writing —
sequenced after both, which in practice means after #94 closes, since §3
cannot complete before then. §2's drill series should already have
accumulated more than one dated entry by that point for the narrative to
be a series rather than a single data point.

### 6. Explicitly out of scope, and why — all three would be "deeper technically," which this ADR is not doing this stretch

- **Extending Argo Rollouts to more services (`clinvar-service` named
  specifically).** `rollout.yaml`'s own comment already gives the honest
  reason `clinvar-service` was left as a plain `Deployment`: it has no
  direct continuous traffic source of its own (reached only indirectly via
  `api`'s `GET /variants/lookup`), so a canary there "would have nothing
  but api's occasional proxied calls to analyze, a much weaker live proof,"
  and the same comment already names this as "a real follow-up once
  clinvar-service has its own direct traffic source" — a condition that has
  not changed. Adding it now would be a new operational shape's *breadth*,
  not depth, and §3c's verdict rules that out this stretch regardless of
  the specific service.
- **Istio traffic-routing canaries (ADR 0024, backlog #59–#62).** Already a
  separately scoped, separately gated decision — layered onto Cilium as
  part of M7, and M7 is blocked-on-hardware with no date (ADR 0040). Not
  reachable from this milestone's own dependencies regardless of this
  ADR's scope, and folding it in here would misrepresent M16 as unblocking
  something it doesn't.
- **Closing the whole-Service-scrape / per-pod-isolation gap** (§Context
  point 2). Real, valuable, and explicitly out of scope for the same reason
  #46 itself gave it: it is a new scrape/label shape, which is "deeper
  technically" work, not evidence-generation from what exists. M16 works
  *within* this limitation — drills whose results it makes ambiguous are
  recorded as ambiguous (§2), which is itself honest operational content,
  not a reason to build around it this stretch.
- **Reopening backlog #21b (multi-window burn-rate alerting).** Stays
  closed. The reason, restated for this milestone specifically rather than
  left as an inherited default: burn-rate alerting exists to catch a
  slow-burning error budget across real, externally-generated,
  unpredictable traffic — the premise ADR 0021 found absent for this
  project and ADR 0031 §5 confirmed still absent. M16's own real traffic
  source is still #45's workload-generator, the identical self-generated
  traffic ADR 0021's reasoning was written against. Calibrating thresholds
  against real data (§3) is a different, smaller, already-justified move —
  ADR 0031 §5 named this exact distinction in advance: "M15's retention
  enables honest SLO *reporting* ... without the theatre" of burn-rate
  policy. Nothing about M16 changes that math, so nothing about M16
  reopens it.

### 7. Sequencing: M16 follows M15 in `docs/roadmap/milestones.md`, gated item-by-item, not as a block

M16 is added to the milestone table after M15, the last currently-defined
milestone. It is **not gated on M15 closing as a whole** — the same
relaxed-sequencing rule `milestones.md` already states for itself ("an item
starts when its own dependencies listed in `backlog.md` are met, not when
every item in the previous milestone is closed") applies here without a new
exception:

- The **drill-cadence item (§2) has no dependency on M15 or on #94** and
  can start immediately, in parallel with whatever of M15 is still open and
  with M11 once it begins. It only needs #46 (Done) and #45 (Done, already
  the traffic source behind #46's own proof).
- The **calibration item (§3) hard-depends on #94**, which is itself an
  M15 item. In practice this means §3 (and, downstream, §5) cannot complete
  before **~2026-09-06** regardless of when M16 opens — a real calendar
  floor, not a milestone-ordering one.
- **M16 does not gate M11 (`sre-agent`).** M11 is already sequenced after
  M15 by ADR 0031 §3, for its own stated reason (needing the retention
  window and richer signals M15 delivers), and that reasoning is unaffected
  by M16 existing alongside it. There is a plausible **soft** connection
  worth naming without turning it into a dependency either direction: M16's
  dated canary-drill fact packs (§2) are exactly the shape of new,
  human-diagnosed operational event backlog #128 already wants for
  `sre-agent`'s graded corpus ("a growing graded incident corpus" — three
  Mimir bundles today). If M11 starts before M16's drills accumulate, it
  simply has one fewer bundle to grade against; if M16's drills exist
  first, #128 can choose to fold one in. Neither milestone is rescoped to
  force this connection.
- **M16 gates nothing else.** No other milestone, and no other backlog
  item outside the three named in §1–§5, is blocked on M16 opening or
  closing.

## Consequences

- **Zero added steady-state CPU/memory, zero new ArgoCD Applications.**
  M16 is entirely evidence-generation and threshold correction against
  components that already exist — the same "total added CPU: zero" shape
  the 2026-08-11 review found across its own entire recommended stretch,
  extended into this specific domain.
- **ADR 0020 gains a second addendum-in-place-of-silent-edit**, once §3
  lands, following the exact shape its own 2026-08-14 addendum already
  established (old value, new value, real distribution behind the change,
  stated side by side). This becomes the standing pattern for any future
  threshold correction in this project, not a one-off.
- **`platform/docs/runbooks/canary.md` stops being a single dated snapshot
  and becomes a growing operational record.** Its "Live verification"
  section, currently one entry (2026-07-30), gains dated postscripts over
  time, the same shape #47 already proved out for the chaos-scenario fact
  packs.
- **Backlog #129's queue gains a fourth named target**, sourced from real
  data this ADR's own items produce rather than proposed speculatively —
  consistent with #129's own bar that no article starts from a blank page.
- **#21b stays closed, on the record, for this milestone specifically** —
  a considered non-reopening with a stated reason, not a silent omission a
  future reader would have to reconstruct.
- **`docs/roadmap/backlog.md` and `docs/roadmap/milestones.md` are not
  edited by this ADR.** A follow-up PR adds M16's row to `milestones.md`
  (after M15, per §7) and mints the three items described in §2/§3/§5
  contiguously from the current backlog maximum, using this ADR's
  descriptions as their Purpose/Acceptance-Criteria source rather than
  restating them from scratch.
- **The known per-pod-scrape-isolation gap stays open, by design, and is
  expected to surface honestly in real drill write-ups** whenever it makes
  a result ambiguous — this ADR does not close that gap, and does not
  pretend M16's drills are immune to it.
