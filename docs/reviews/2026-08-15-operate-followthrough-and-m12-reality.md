# Operational follow-through, and what M12 is actually blocked on — 2026-08-15

Fourth in the review series (`2026-08-06-staff-engineer-review.md`,
`2026-08-09-staff-engineer-review.md`,
`2026-08-09-hardware-constrained-strategy.md`,
`2026-08-11-staff-review-differentiation-and-article-strategy.md`). The
first two audited what was built and what drifted; the third decided where
the project goes under a real hardware ceiling; the fourth found the
project alerting correctly on a 33-hour incident nobody answered, and
reframed the binding constraint as "build rate has outrun operate rate."

This one asks two questions the owner set for it: **is the project actually
healthy right now, verified against the live system rather than the
backlog's own prose**, and **is the roadmap still coherent — specifically,
is the M12 bioinformatics epic (#67–#72) really blocked, and if so, on
what?** The second question turns out to have a different answer than the
backlog currently gives, and that answer is the most important thing in
this document.

Scope of evidence: all 41 ADRs (0040/0041 are new since the last review),
the full 1,314-line backlog through #134, the four prior reviews, the M7
and M12 backlog sections read in full, `docs/architecture/overview.md`, and
— because this project's own culture is that "Done" claims get corrected
when live evidence contradicts them — a **read-only live inspection of the
running cluster and the four GitHub repos** performed during this review:
`kubectl describe node`/`top`/`get`, the live Prometheus `/api/v1/alerts`
and `/api/v1/rules`, real Kafka topic and blackbox-probe state, real pod
restart counts, the live `clinvar-service-refdata` volume, and `gh issue
list` across the `AdamastorX/adamastorx` repo. Nothing was mutated: no
`apply`, `patch`, `delete`, `scale`, or sync. Corrections to this review's
own briefing are recorded in §10.

---

## 1. The finding: the last four days fixed every interesting bug and deferred every unglamorous discipline

The 2026-08-11 review proposed nine items (#122–#129) and the project then
found four more live (#130–#134). Splitting that list by what actually
happened is the whole finding:

**Shipped, and shipped with genuinely exceptional rigor** — every one a
live-diagnosed, live-fixed, live-verified bug:

- **#122** (close the four-alert incident): three root causes fixed. Verified
  live this review — zero alerts firing, `clinvar.ingestion.completed`
  exists on the broker, `/data/clinvar/current/clinvar.vcf.gz` is back
  (370M, `Aug 14`), all seven `probe_success` series read `1`.
- **#130** (`GET /work-items` unbounded → OOM): the theoretical risk became
  a real 282-restarts-in-41-hours incident, root-caused to blackbox's own
  probe hammering the unbounded endpoint (not `workload-generator`, a
  misattribution review caught), fixed with real pagination. `api` now
  `0` restarts.
- **#131/#132/ADR 0041** (node-wide memory pressure): five real ingestion
  attempts across three days, two genuine application-memory bugs found by
  live-measuring where the trace peaked (streaming the index insert, then
  streaming the release diff), a 20,000-trial fuzz test on the diff
  refactor. `ClinVarIngestionFreshnessBreach` cleared for real.

That is the project's engineering culture — "re-test the fix live because it
compiled is not proof" — operating at its best. It is real and it is rare.

**Not shipped** — every process, discipline, and publishing item from the
*same* review, still open, confirmed against the live system:

| Item | What it is | Live status 2026-08-15 |
|---|---|---|
| **#125** | alert on restarts/OOMKills | **0** of 20 alert rules match restart/OOM/CrashLoop; `mimir` at **29** restarts, `market-data-ingestor` hit **34** |
| **#126** | NetworkPolicy past #50's 5-namespace floor | still **5 of ~28** namespaces (`api`, `clinvar`, `workers`, `alloy`, `prometheus`); `kafka` ingress still unrestricted |
| **#123** | post-rebuild business-path acceptance checklist | open |
| **#124** | standing operations log | open; `docs/operations/` does not exist |
| **#127** | component budget + decommission rule | open |
| **#128** | sre-agent v1 real run | open (owner key) |
| **#129 / #119** | publish article #1 | open; `docs/articles/` still holds exactly one unpublished draft |
| **#122's own fact pack** | the incident write-up | **not done** (the item says so honestly); `observability/chaos/` still has only `01/02/03` |

The pattern is not a criticism of any single decision — each fix was worth
doing and several were urgent. The pattern *is* the finding: **when a live
bug and a discipline item compete for the same hour, the bug wins every
time, and the discipline item does not get a later hour.** The 2026-08-11
review predicted this exact reversion ("adding more things to operate")
and recommended #124 specifically as the antidote. #124 is open. The
prediction has now become a measurement.

The sharpest instance is **#125 against ADR 0041**. ADR 0041 did the
honest, correct thing — it measured the node's memory ceiling and *accepted*
Mimir's chronic OOM-restarts as a known constraint rather than chasing them
as a bug. But "accept the restarts" and "have no alert on restarts" are two
different decisions, and only the first was made deliberately. The result:
`mimir` has climbed from 11 → 24 → **29** restarts across three
consecutive reviews with nothing watching it, and `market-data-ingestor`
silently reconnect-stormed to 34 restarts (#133) with, again, nothing
watching — a human had to notice the 29-hour-silent feed. The one alert
that would have caught both is the one that keeps getting deferred.

## 2. Verdict

**The project is genuinely healthy as a running system and genuinely
behind as an operated one — and the gap is now structural, not
incidental.** The live cluster is clean: no alerts firing, the biggest
incident in the project's history closed with real evidence, and the "Done"
markers I spot-checked hold up against live state (§3). That is a real pass
and should be said plainly.

But three of the four prior reviews have named operational follow-through
as the binding gap, and the response has been to fix the bugs those reviews
surfaced while leaving the *disciplines that would have caught the bugs
earlier* — restart alerting, a post-rebuild acceptance gate, a standing ops
log — unbuilt. The recommendation, in one line:

> **Do the four zero-CPU discipline items (#125, #123, #124, #127) as a
> single deliberate batch before any more bug-hunting or building, treat
> "publish something" (#129) and "run the sre-agent" (#128) as the two
> owner-gated items that convert all this evidence into the reputation
> that is the actual point — and correct the M12 dependency text, which is
> now factually wrong about what blocks it (§4).**

## 3. Overall health: what is actually real, verified live

The good, verified rather than recited:

- **The 2026-08-11 incident is genuinely closed.** Zero firing alerts;
  refdata restored; the missing Kafka topic present; blackbox green across
  all targets; `api` and `clinvar-service` both stable. This is a real
  recovery from a real three-root-cause outage.
- **The "Done" markers I sampled are honest.** #49 (Cilium), #50
  (NetworkPolicies), #53 (watchlist fan-out), #54 (async jobs), and all
  five M13 services (#78–#82) map to **CLOSED** GitHub issues *and*
  live-verified state. This is a real improvement over the pattern past
  reviews caught (things marked Done that were never synced) — for the
  items that pre-date #120, the backlog↔issue↔cluster chain is consistent.
- **The hardware ceiling is holding as ADR 0040/0041 describe it.** Live:
  CPU requests **3445m/4000m (86%)**, memory requests 46% but memory
  *limits* **114% overcommitted** and CPU limits 440%; `kubectl top node`
  2180m (54%) / 13490Mi (67%); one node, i7-6600U, rebuilt 5 days ago.
  Both ADRs' numbers reproduce.
- **The rebuild preserved history.** Prometheus `up` series exist back
  ~9 days; #94's 30-day SLO clock (started 2026-08-07) is intact and the
  report is on track for ~2026-09-06. This is the payoff of #49's PVC-copy
  discipline and remains the single most differentiated article the
  project can eventually publish.

The honest counterweight: the cluster being clean *today* is partly because
a reviewer found the incidents on 2026-08-11 and the owner fixed them. That
is exactly the loop #124 exists to make self-sustaining, and it isn't built
yet — so the next unattended incident has the same detection layer and the
same (absent) response layer as the last one.

## 4. M12 is not blocked on what its dependency text says it is blocked on

This is the centerpiece. The briefing for this review framed M12 (#67–#72)
as transitively blocked by the hardware ceiling through #48 and #51. That
is *directionally* right — M12 cannot proceed as scoped — but the specific
dependency chain the backlog records is **wrong about the mechanism**, and
the difference changes the recommendation.

What the backlog literally says today, confirmed live:

- M12 intro (line 588): *"Lands after M7's multi-node/replicated-storage
  substrate, which the data volume needs."*
- **#67** `metadata-service`: `Dependencies: #48 (multi-node substrate)`
- **#68** MinIO: `Dependencies: #51 (replicated storage), #67`
- **#69** Nextflow: `Dependencies: #67, #68`
- **#70/#71/#72**: chained behind #69/#68.

Both roots — **#48** (Won't do, superseded) and **#51** (Blocked,
hardware) — are dead. So on its face the whole epic is unstartable. But ADR
0040's own Consequences section already ordered the correction — *"ADR 0025
(M12) ... gains a line: 'gated on M7's multi-node substrate' now means
blocked-on-hardware with no date"* — and **that correction was never
applied to the backlog.** #67–#72 still cite #48/#51 verbatim with no dated
reassessment note. This is the same prose-staleness class the project has
now caught five times (#32/#83/#97), recurring in the roadmap's own
dependency graph.

Worse than stale: it is **misleading about what actually blocks the work.**
Read item by item, the multi-node dependency is largely spurious, and the
real blocker is different and more interesting:

- **#67 `metadata-service` is not multi-node-blocked at all.** It is a
  Spring Boot CRUD service with a namespace-local Postgres — the exact
  shape #53/#67 describe. Nothing in it needs a second node; the `#48`
  dependency was inherited from the milestone header, not from the item.
  What actually blocks it is (a) the CPU ceiling — a new always-on
  ~250m service against 555m of headroom — and (b) the **ADR 0031 gate**
  ("no new application services until #90–#97 close"), which #91 and #94
  keep open. Different blocker, different (and non-permanent) trigger.
- **#68 MinIO is not replication-blocked; its AC is over-specified.** MinIO
  runs fine on single-node `local-path`. The `#51` dependency exists only
  because the AC says *"backed by #51's storage layer"* — waive the
  replication clause and MinIO is deployable today, at the cost of yet
  another memory-hungry always-on component on a node already 114%
  overcommitted on memory limits and swapping at rest (ADR 0041). Capacity-
  blocked, not substrate-blocked.
- **#69 Nextflow is the item that genuinely does not fit — and not because
  of nodes.** Running *real* public pipelines (the line ADR 0025 draws for
  this to be worth doing) means real alignment/variant-calling compute:
  multi-gigabyte working sets and sustained CPU. This is a machine that
  **cannot complete a single ~900MiB ClinVar ingestion without three
  consecutive OOM kills** (ADR 0041) and needed two code-level memory
  refactors to get one run through. An nf-core pipeline's per-step
  footprint dwarfs that. #69 is blocked by the *same physics* as #48 —
  "this hardware does not have the resources" — but the dependency text
  points at the wrong cause (multi-node scheduling) instead of the real one
  (absolute compute/memory capacity).
- **#70 (Kafka saga) and #71 (`notification-service`) are pure
  messaging/CRUD shapes** — single-node-feasible in principle, blocked only
  transitively because they consume #69's events.
- **#72 (real datasets)** — disk has room (~160G free), but its value is
  feeding #69's real runs, so it inherits #69's block.

**The honest reframing:** M12 is blocked, but "needs the multi-node
substrate" is the wrong reason on record. The real reasons are three
distinct things the backlog should say separately: (1) the **CPU/memory
capacity ceiling** (ADR 0040/0041) — affects #67, #68; (2) **absolute
compute physics** for #69, which is the true hard block and the only one
that behaves like #48's; and (3) the **ADR 0031 no-new-services gate** —
affects #67 and is *not permanent*, it clears when #90–#97 do.

**Independent judgment on whether it could proceed at all:** a deliberately
de-scoped M12 *could* run a thin slice on this node — `metadata-service` +
MinIO-on-`local-path` + the #70/#71 saga/notification shapes, with a
*mocked or trivially small* pipeline standing in for #69. But that slice
deletes the one thing ADR 0025 said made M12 worth reopening: real public
pipelines on real data. A bio milestone whose pipeline is a stub is exactly
the "bio coat of paint" risk ADR 0021 named and ADR 0025 promised to avoid.
**So the recommendation is not "re-scope M12 to fit" — it is "state
honestly that its core (#69) is hardware-blocked in the same permanent way
#48 is, and stop pretending the block is about node count."**

**Recommended correction (append, don't rewrite — the project's own
convention):**

- *M12 intro* — append: *"**Reassessed 2026-08-15** — 'after M7's multi-node
  substrate' is superseded by ADR 0040: #48 is Won't-do and #51 is
  Blocked(hardware), so there is no multi-node substrate coming. The real
  block is single-node capacity (ADR 0040/0041), not node count. #67/#68
  are capacity- and ADR-0031-gate-blocked, not substrate-blocked; #69
  (real pipeline compute) is the genuine permanent hardware block — the
  same physics as #48 — and everything downstream inherits it. Re-scoping
  to a stub pipeline is explicitly rejected (revives ADR 0021's 'bio coat
  of paint' risk). Revisit only when a dedicated host or ADR 0040 §6's
  cloud annex exists."*
- **#67** — dependency rewritten from `#48` to: *"the ADR 0031 gate
  (#90–#97) plus real CPU headroom; not multi-node — Blocked(capacity/gate),
  reassessed 2026-08-15."*
- **#68** — *"Blocked(capacity), reassessed 2026-08-15 — MinIO runs on
  single-node `local-path`; #51's replication is the waivable clause, not
  the blocker. The blocker is memory headroom (ADR 0041)."*
- **#69** — *"Blocked(hardware), reassessed 2026-08-15 — real pipeline
  compute does not fit a node that OOMs on a single ClinVar ingestion; the
  same permanent block as #48, mislabeled as multi-node."*

## 5. Roadmap structure: otherwise coherent, two more stale edges

M1–M15 remains a coherent spine and the milestone framing still holds. The
M12 case above is the significant structural defect. Two smaller ones,
found while tracing dependency chains:

- **#78/#79 still read `Dependencies: #48 (multi-node substrate, M7)`**
  even though both are Done under the M13 owner-override. Harmless
  (historical), but it means a reader grepping `Dependencies: #48` finds
  four live-looking edges to a dead item; worth a one-line "(satisfied via
  M13 override)" so the graph is honest.
- **The #122–#134 block never entered GitHub Issues.** Confirmed live: the
  highest backlog item mirrored as an issue is **#120**. Items #121–#134
  — fourteen of them, including **five marked Done** (#121, #122, #130,
  #131, #132) — have **no issue at all**. The backlog is the stated source
  of truth (prior reviews are explicit that issues are secondary), so this
  is not drift in the authoritative record. But it means the GitHub issue
  tracker is now ~14 items and one major incident behind, and any tooling
  or human that reads issues for status is looking at a stale world. Either
  file the backlog since #120 as issues, or record explicitly (a one-liner
  in the backlog header or CONTRIBUTING) that issues stopped being mirrored
  at #120 — the current silent divergence is the worst of both.

## 6. The hardware ceiling's real, structural effect on what remains

Sorting the remaining roadmap by what this exact machine can and cannot do,
given ADR 0040 (CPU) and ADR 0041 (memory) both now measured:

**Achievable on this node, no infrastructure change:**
- Everything zero-CPU: #123, #124, #125 (rules only), #127, #129, #94's
  report, the #122 fact pack. This is where the highest-value remaining
  work lives, and it is *all* deferred.
- eBPF-datapath work: #126 (Cilium policies are datapath rules, not
  workloads — genuinely free).
- App-level fail-fast (#43, closed today — good) and its chaos re-runs.
- The sre-agent v1 grading (#128) — runs off-cluster.

**Achievable only by paying real capacity, one component at a time:**
- #67 `metadata-service`, #68 MinIO-on-`local-path` — each a real
  always-on tenant on a node at 86% CPU / 114% memory-limits. Possible,
  but every addition now trades against the memory pressure ADR 0041
  accepted, and the ADR 0031 gate says not yet anyway.

**Not achievable without a second physical machine or a cloud annex
(honestly permanent on this hardware):**
- #51, #52 (already correctly labeled).
- **#69 Nextflow real pipelines** — belongs in this bucket and currently
  isn't labeled as such (§4).
- The Istio mesh / mTLS gap (correctly deferred by ADR 0040, named as a
  "when hardware exists" benefit).

The ceiling's real effect is therefore *not* that the project is stuck —
the zero-CPU queue is deep and high-value. It is that the project's
**default activity (find and fix a live bug, or add a component) is exactly
the activity the ceiling most constrains**, while the activity the ceiling
does not constrain at all (writing, alerting rules, policy) is the activity
that keeps getting deferred. The hardware ceiling and the operate-gap are
the same problem viewed twice.

## 7. Concrete recommendations, ranked

Ordered by value-per-effort under the ceiling; every item through #6 is
zero added CPU.

1. **#125 — restart/OOMKill alert, first.** It is one rules file, it catches
   the class that produced two of the last three incidents, and its absence
   is the clearest live contradiction of the project's own "never ship a
   signal you don't consume" standard. Query it against live Prometheus so
   it returns `mimir`'s real 29-restart series before committing; triage
   Mimir as its first subject (accept-with-reason per ADR 0041, but *now
   with an alert*).
2. **Correct the M12 dependency text (§4)** and the two stale edges (§5).
   Pure honesty debt, costs an editing pass, and stops the roadmap from
   quietly lying about its own hardest block.
3. **#123 — post-rebuild business-path acceptance checklist.** The next
   rebuild is not hypothetical (the last one was 5 days ago and broke three
   business paths under all-green component checks). This is the
   generalization of #85/#86 the project keeps re-learning per-incident.
4. **#124 — stand up `docs/operations/`, cycle 1 = the #122 incident.** The
   antidote to §1's entire pattern. A read-only sweep plus a page; if it
   finds nothing that is a valid recorded outcome. Two consecutive cycles
   before it counts as a habit.
5. **#129 / #119 — publish the finished draft.** Zero published words after
   28 days and four reviews. The draft exists. This is an owner action, not
   an engineering task, and it is the single highest-leverage thing on the
   list for objective 4.
6. **#126 — NetworkPolicy past 5 namespaces, `kafka` ingress first.** Real
   security finding (PLAINTEXT broker, unrestricted ingress), free, and the
   method is fully proven by #50's five batches.
7. **#128 — sre-agent v1 real run.** Owner key. The corpus has roughly
   doubled (the #122/#130/#131/#132 saga is a genuinely hard multi-cause
   case with documented wrong turns) — the best grading material the
   project will build for a while.

**#127 (component budget)** folds naturally into whichever PR touches ADR
0022; it is the written rule that would have prevented §1's pattern in the
first place.

## 8. What not to do

- **Do not start M12 in any form**, including a de-scoped single-node slice
  — §4 explains why the stub-pipeline version defeats its own purpose, and
  the ADR 0031 gate is anyway not clear.
- **Do not add any new always-on component this stretch.** ADR 0041's
  memory ceiling is a harder "no" than ADR 0040's CPU one — the node OOMs
  under existing load. #67/#68 wait.
- **Do not fix another live bug before doing #125.** The next bug is better
  caught by the alert than by the next reviewer; build the net before
  chasing the next thing to fall through it.
- **Do not silently rewrite the M12 items** — append dated reassessment
  notes, matching the convention this backlog uses everywhere else.
- **Do not treat "issues stopped at #120" as fine because the backlog is
  truth** — decide it deliberately (mirror, or declare the mirror
  retired), don't leave it as accident.

## 9. The appeal test

The standing check (the owner's constraint that the project stay genuinely
interesting): does a plan that is 60% "do the unglamorous discipline items"
fail it? Checked honestly:

- The most novel item (**sre-agent**, #128) is #7 on the list and its
  grading corpus just got its best case ever — that is more interesting,
  not less, than another config-bug fix.
- **Publishing** (#129) is the loop-closer four reviews have begged for and
  is two hours of owner time.
- **#126** is real security work on a live eBPF datapath with a track record
  of hard upstream bugs — not hygiene.
- What is honestly imposed as a cost: the pleasure of finding-and-fixing the
  next live bug, and of installing the next component. That cost is
  deliberate, because §1 is the evidence that both have become the default
  reflex, and both are the activities the hardware ceiling most constrains
  while moving objective 4 the least.

---

## 10. Review of this review (2026-08-15, before merge)

Every load-bearing claim here was read off the live cluster or the real
repos during this review. Findings, including corrections to the briefing
that seeded it:

1. **The briefing's framing of M12 as "transitively blocked by #48/#51" is
   right in conclusion but wrong in mechanism, and §4 is written to the
   corrected version.** Read item-by-item, #67 needs no second node, #68's
   replication clause is waivable, and the genuine permanent block is #69's
   real pipeline *compute* — the same physics as #48, not the multi-node
   *scheduling* the dependency text names. The distinction is the whole
   recommendation, so it was checked against the item text directly, not
   inherited.
2. **The incident the last review found is genuinely closed — verified, not
   assumed.** Zero firing alerts via `/api/v1/alerts`; `du -sh /data/clinvar`
   → 370M with a real `clinvar.vcf.gz`; `kafka-topics.sh --list` includes
   `clinvar.ingestion.completed`; all seven `probe_success` = 1. The 2026-
   08-11 review's §1 findings are resolved.
3. **The restart-alert gap is real and current, not carried from the last
   review.** `/api/v1/rules` returns 20 alerting rules, **zero** matching
   restart/OOM/CrashLoop; `mimir` shows 29 restarts live (up from the 24 in
   ADR 0041 and 11 in the 2026-08-11 review). #125 is unbuilt.
4. **The issue-mirror gap was verified by enumeration, not inferred.**
   Parsed every `#N:`-titled issue across all states: 91 exist, max **#120**;
   none of #121–#134 is filed. Five of the unfiled items are marked Done in
   the backlog.
5. **One thing I could not fully verify live:** a `GET /variants/lookup`
   returning a real classification — the container has no `curl`, so I relied
   on #122's own recorded live check (`rs80357906` → `Pathogenic`) plus the
   independent proxies that the refdata file exists and the ingestion counter
   is `succeeded=1`. Stated as a proxy, not a direct confirmation, per this
   project's norm.
6. **What I looked for and did not find:** any pre-#120 "Done" item whose
   GitHub issue was still open or whose live state contradicted the marker —
   the sample I checked (#49/#50/#53/#54/#78–#82) was consistent across
   backlog, closed issue, and cluster. The "Done means done" discipline
   holds for the mirrored range; the gap this review found is a different
   one (unmirrored new items, deferred disciplines), not the "marked Done,
   never synced" class earlier reviews caught.
7. **Deliberately not re-verified exhaustively:** per the review's own
   budget, ~12 items across milestones were spot-checked live rather than
   all 134. #133 (market-data watchdog) is quiescent live (feed fresh, ticks
   flowing) but its backlog entry carries no Done marker and I did not read
   the code to confirm the watchdog fix landed — flagged as
   apparently-open, not asserted either way.
