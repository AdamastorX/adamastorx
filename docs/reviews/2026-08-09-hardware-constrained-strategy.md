# Strategic direction under a real hardware ceiling — 2026-08-09

This is not a third health-check. The two prior reviews
(`2026-08-06-staff-engineer-review.md`, `2026-08-09-staff-engineer-review.md`)
audited what was built and what drifted; this one answers a different
question, triggered by two facts that arrived together: **the owner has
decided to stay on the current laptop for a meaningful stretch of time**,
and **a live capacity measurement has closed off the project's own planned
path for its next major milestone** (M7 as scoped by ADR 0035 and backlog
#48). The job here is to decide where the project goes instead.

The rubric is the owner's four standing objectives, verbatim:

1. An observability pipeline fed with real data
2. Microservices / distributed systems depth
3. A lab/playground for state-of-the-art and established technologies
4. Articles (blog/Medium) to grow a public SRE reputation

plus a fifth constraint, stated by the owner directly for this review:
**the project must keep being genuinely appealing and interesting to work
on.** A redirection that is correct on paper but boring to execute defeats
its own purpose for a portfolio/lab project — this constraint gets its own
section (§9), not a footnote.

Scope of evidence: all 39 ADRs, the full backlog (1,191 lines, every
milestone, not just M7), `docs/WHY.md`, both prior reviews,
`docs/architecture/overview.md`, `platform/argocd/apps/*.yaml` (36
Applications; 37 live including `root`), the chaos fact packs, the new
`observability/sre-agent/` harness, and — because every load-bearing number
here is a resource number — live re-measurement of the cluster and host
(`kubectl describe node`, `kubectl top`, `free -h`, `lscpu`) and the real
upstream Helm charts (`helm show values` for `cilium/cilium`,
`istio/ztunnel`, `istio/istiod`), all re-run during this review rather than
inherited from the briefing that seeded it (§10).

---

## 1. The finding: M7 as planned does not fit this machine, and no scoping pass fixes that

The hardware, measured live: an i7-6600U with **2 physical cores / 4
hyperthreads** (`lscpu`: 2 cores, 2 threads/core; `nproc` = 4), ~19Gi RAM.
The single k3s node's CPU requests sit at **3745m of 4000m allocatable —
93%**, leaving ~255m of schedulable headroom. The host itself — which is
also the operator's daily driver — shows **5.1Gi of 8Gi swap in use** and
~7.7Gi genuinely available RAM (`free -h`), with real usage at 2223m CPU /
11.2Gi memory (`kubectl top node`). Roughly 30 real components run on this
today.

Against that, the real cost of #48/#49/#59–#62 as planned (one additional
VM agent — already scaled down from ADR 0035's two — plus the
Cilium+Hubble and Istio-ambient tracks), from the actual charts:

| Component | Requests (source) |
|---|---|
| Cilium agent, per node ×2 | 100m / 512Mi each (chart's own reference sizing; see §10.2) |
| Istio ztunnel, per node ×2 | 200m / 512Mi each (real chart default) |
| Istio istiod | **500m / 2048Mi** (real chart default) |
| VM's own OS/kubelet/containerd | ~300m / ~750Mi (estimate, stated as such) |

Total: roughly **+1550m CPU / +5.2Gi RAM** before any workload is
scheduled onto the new node for actual work. Added to today's 3745m:
**~5295m against a 4000m ceiling — about 132% of the machine**. The
conclusion survives its own error bars: with the VM overhead estimate set
to zero, the charts alone are ~+1200m → **~124%**. And the deeper point is
not arithmetic but physics: **a VM does not add cores.** It re-partitions
the same 4 hyperthreads on the same 2 physical cores. Total real demand
across "the cluster" can never exceed what this one machine has, no matter
how many virtual nodes divide it — and istiod alone (2Gi) is larger than
almost any single component already running.

One variant deserves an honest look before being rejected, because #48's
own pre-flight gate names it: **a maximally-trimmed, Cilium-only, one-VM
build** (no Istio). On paper, a #77-style re-trim (requests 3745m against
2223m real usage — the five M13 services alone hold 1250m of requests)
could plausibly free ~700–1000m, and +VM(~300m) +Cilium(×2, ~250m with
Hubble) might squeeze under 4000m of *requests*. It still fails, twice
over. First, on RAM: a VM's memory is a reserved carve-out, not a
schedulable promise — 2–3Gi taken whole from a host already 5.1Gi into
swap with the IDE and browser running. Second, on what it buys: a second
"node" on the same disk, same kernel, same power button proves scheduling
mechanics only. #51's headline test (a pod rescheduled to a different node
still sees its replicated data) would replicate between two directories on
the same physical disk; #52's "node loss" would be killing a process on
the same machine that keeps running. The learning-per-cost is poor even
where the arithmetic is arguable.

**What this kills, precisely:** #48 (the VM agents), and the *sequencing*
that chained #49/#50/#59–#62 behind it. **What it does not kill:** Cilium
and NetworkPolicies are not multi-node technologies — they were bundled
into M7 only because a CNI swap needs a cluster rebuild and #48 was doing
one anyway (backlog #49's own Purpose says exactly this). That reasoning
now runs in reverse: the rebuild is the only remaining cost, and it is
payable on one node. **What is genuinely, definitionally impossible
without 2+ real nodes:** #51's cross-node reschedule proof and #52's
drain/node-loss/rolling-upgrade drills — there is nowhere to reschedule
to. Those stay blocked on hardware, and should say so.

## 2. Verdict

The project is not blocked; its most expensive plan is. Of the four
objectives, only a *fraction of one* (the multi-node slice of objective 2)
actually needs hardware this machine doesn't have. Objectives 1, 3, and 4
— and most of 2 — have a deep, already-scoped queue of single-node work,
and the highest-value items in the entire backlog (the sre-agent, the
SLO-over-time report, publishing anything at all) need **less** hardware
than what's running today, not more. The redirection, in one line:

**Rescope M7 to the network dataplane on one node (Cilium/Hubble/
NetworkPolicies, via a deliberate, measured full-cluster rebuild), answer
the fail-fast problem at the application layer instead of with a mesh,
mark #51/#52 blocked-on-hardware honestly, and spend the freed attention
on the three things that convert this project's existing evidence into
reputation: the sre-agent, the SLO report, and actually publishing.**

## 3. What M7 becomes

### 3a. Keep: Cilium + Hubble + first NetworkPolicies, on one node (#49, #50)

The single most valuable un-built platform work that *fits*. The case is
unchanged from ADR 0023 — this project has metrics, logs, traces, and
profiles, and zero visibility into what talks to what; #50 calls the
absence of any NetworkPolicy "the largest remaining unaddressed gap in the
platform" — and none of it needs a second node. Hubble flow maps,
default-deny-per-namespace with allows derived from *observed* flows, the
DNS footgun, L7 visibility on the `api`→`clinvar-service` path: all fully
exercisable between pods on one node. What a single node cannot show
(cross-node routing, WireGuard node-to-node encryption, multi-node
identity propagation) is real but small, and stated rather than glossed.

Cost, measured against the real headroom: Cilium agent (~100m/512Mi, one
node now, not two) + operator + Hubble relay/UI ≈ **~200m / ~0.7Gi of
requests** — affordable *after* the reclaim pass in §4, not before.

Risk, stated plainly: a CNI swap on the only node is the one failure
ArgoCD cannot recover from, with no second node to retreat to. #49's own
AC already demands the mitigation — a rehearsed flannel-restore runbook
*before* the attempt — and the swap itself is a Terraform-driven rebuild
(`--flannel-backend=none --disable-network-policy --disable-kube-proxy`)
on a destroy/recreate path proven since #5, with #23a's restore proven and
#94's PVC-copy pattern (used successfully today, zero data loss) covering
the stateful data. Do not treat the rebuild as overhead to minimize:
**"rebuild the entire platform from git + backups, with measured RTO" is
the strongest available test of ADR 0003's GitOps claim and a first-class
fact pack in its own right** — the closest thing to a DR drill a single
node can honestly produce, and a partial substitute for the *spirit* of
#52 while its letter stays blocked.

### 3b. Replace: the Istio track (#59–#62) with application-level fail-fast (#43/#105, un-deferred)

The problem #60 exists to solve is real and precisely documented: a
downstream outage hangs the caller instead of failing fast — ~60s on
Kafka's `max.block.ms` (`observability/chaos/01-*.md`, #43), ~30s on
HikariCP acquisition (`observability/chaos/02-*.md`, #105). ADR 0024's
argument for solving it at the dataplane was "the same problem in two
languages — solve it once for every service." That argument had a price
tag nobody had measured: **istiod's 500m/2Gi + ztunnel's 200m/512Mi per
node is roughly ten times the entire remaining headroom of this machine**,
for a cluster of ~8 application services. At this capacity, ADR 0023's
original position — "retries/timeouts are a handful of lines in two
clients" — is no longer the argument the mesh beat; it is the only answer
that fits.

So: un-defer the per-client fix that ADR 0024's addendum explicitly parked
("neither #43 nor #105 gets an independent per-client fix... both stay
open, gated on M7"). Concretely: a stated timeout budget well under the
current 30–60s hangs — `max.block.ms` tuned on `api`'s Kafka producer,
HikariCP `connectionTimeout` tuned with a fail-fast path, and a
Resilience4j circuit breaker on `api`'s outbound `clinvar-service`/lookup
path (Java first: **both documented hangs are in `api`** — the "two
languages" cost is deferred until a Python-side hang is actually
documented, honestly, rather than paid speculatively). Proven the way #60
would have been: re-run chaos scenarios 01 and 02, before/after latency as
dated postscripts in the existing fact packs. Same evidence, ~zero
resource footprint.

The tradeoffs are stated, not glossed: no free per-language win, no
unified L7 policy, no mesh mTLS. On mTLS specifically: the gap ADR 0024
attributed to ADR 0010 (see §10.4 — the citation is loose, the gap itself
is real: ADR 0012 records Kafka as "PLAINTEXT, no auth", and every
in-cluster call is unauthenticated plaintext) was worth closing when
ambient made it *nearly free*. At 2.5Gi+700m it is not nearly free, and
ADR 0023's original threat-model point stands on one physically-owned
node: mTLS between pods on the same host, against this project's actual
threat model, defends approximately nothing. The gap stays open, named,
with the mesh as its future answer *when hardware exists*.

#61 (Istio fault injection) loses nothing real: Chaos Mesh (#64, already
in the backlog, single-node-feasible) covers deliberate fault injection —
including network-layer faults Istio couldn't do — see §5. #62 dissolves
with #59.

### 3c. Mark blocked-on-hardware, honestly: #51 and #52

Both stay in the backlog, re-labeled **Blocked (hardware)** with one line
each stating the definitional dependency (nowhere to reschedule to;
nothing to drain to). No forced substitute, no quiet deletion. This is the
same honesty the project already practices for #99 (owner credential) and
#89's retroactive captures (no browser): a real, stated gap beats a faked
version of the exercise.

### 3d. Evaluated and not adopted (for now): a cheap cloud annex

A few dollars a month buys two real small VMs (e.g. 2× Hetzner
CAX11-class, ~€4/mo each) and with them the *only* honest route to #51/#52
without buying hardware: a short-lived 2–3 node cloud cluster, built by
the same Terraform pattern, used to produce the drain/replication/
node-loss fact packs, then torn down. It is worth naming because it is the
one option that actually delivers the blocked content. It is not adopted
now, for three reasons. First, ADR 0035 states an explicit "owned
hardware, not cloud" story; even a bounded annex dilutes it, and the
dilution should be a deliberate ADR-recorded trade, not a side effect.
Second, the fidelity is imperfect anyway — a cloud "hard power-off" is an
API stop, not #52's physical power-loss. Third, and decisively: the
single-node queue in §5–§6 is already 60–90 days deep with higher-value
work. **Recorded as a trigger, not a rejection**: if, when that queue
drains, the dedicated-host date still doesn't exist, a one-month cloud
annex for #51/#52's fact packs is the honest fallback — its own ADR then.

## 4. The capacity ledger: what gets reclaimed before anything gets added

The project already holds its levers; it just hasn't pulled them since the
constraint became binding. Measured live this review:

- **Decommission the Mimir experiment** (100m/256Mi requested, 73m/401Mi
  real). ADR 0038's own conclusion is "not yet worth it as a standing
  piece of this cluster's real architecture" — it was kept deployed as the
  completed experiment. That was defensible at the 91% ADR 0038 itself
  recorded; at 93% with new tenants (Cilium) queued, the ADR and write-up
  are the artifact, the pod is just rent. Rollback path is already stated in #108
  (removing remote-write leaves Prometheus standing alone).
- **Decommission Beyla** (100m/256Mi requested — but 797Mi *real* RAM, the
  third-largest memory consumer measured, on a host in swap). The A/B
  write-up, dashboard evidence, and the OOM incident (ADR 0036, #102) are
  complete and captured. Same principle: experiment concluded, record
  stands, capacity returns.
- **A #77-style re-trim** of the M13 services' 250m-each requests against
  their real usage, same measured-not-guessed discipline as before.

Together: **~200m of requests and ~1.2Gi of real RAM back** before the
trim, comfortably covering Cilium's ~200m/0.7Gi with margin restored —
the ledger balances *without* touching anything load-bearing. Each
teardown gets a one-paragraph ADR addendum (0036/0038) so "kept deployed
as the completed experiment" doesn't silently become "torn down without a
record" — the project's own correction pattern (ADR 0037) applied to
itself.

## 5. What gets built that needs no new hardware — by objective

**Objective 4 (articles) — the binding gap, and now the cheapest to
close.** Both prior reviews said it; this one says it harder because
writing is the one activity with zero CPU cost. Concretely, two changes:
(a) **make "publish article #1" a first-class backlog item with a named
target** — the Mimir three-bug series or the outbox force-kill are both
~90% written already; every week of engineering-first sequencing has been
a choice against this objective, and under a hardware ceiling that choice
loses its last excuse. (b) **Re-decide #88 Phase 1** (cloudflared →
`visualizer`, ~10m CPU). The owner descoped it on 2026-08-06 — a real
decision, respected — but the pile behind the door has grown again since
(sre-agent harness, the freshness SLO, today's zero-loss PVC migration),
#107 (the ntfy exposure, Phase 2's stated precondition) is closed, and an
article that links a live artifact is worth a multiple of one that links a
screenshot. This review's ask is a fresh go/no-go on Phase 1 alone, not a
reversal by default.

**Objective 1 (observability, real data) — one item, mostly patience.**
#94's clock is real and running: retention raised 2026-08-07, the PVC
recreated today with zero data loss, report due when 30 real days elapse
(~2026-09-06, ~28 days out). The SLO-over-time report is still the most
differentiated article this project can produce — almost nobody has the
data — and its cost is a writing day. Small tail: #91's and #118's
positive-case verifications, #19a exemplars, #21e's lookup counter.

**Objective 2 (distributed-systems depth) — deeper, not wider.** The
multi-node slice is blocked; the rest of the objective isn't:

- **Chaos Mesh (#64)** is the single best fit for this stretch: declarative
  re-runs of the existing scenarios, plus fault types the manual method
  could never safely reach — a real **network partition or injected
  latency between `api` and `clinvar-service`**, on one node. Partial
  failure (a reachable-but-slow dependency) is a genuinely different
  failure class from the process-kills all three existing fact packs used,
  and it is exactly what exercises §3b's new timeouts/circuit breakers.
- **The fail-fast work itself (§3b)** *is* distributed-systems depth: a
  measured timeout budget, a circuit breaker proven to open under a real
  injected fault, before/after fact packs.
- **Kyverno (#58)** stays a good P2: the webhook-as-SPOF failure mode is a
  real, new distributed-systems lesson, exercised deliberately, single-node.
- The correctness tail (#38's rsID `LIMIT 1` bug — a real P1 bug open
  since M5 — and #39's indel normalization) costs nothing and closes real
  gaps.

**Objective 3 (lab/playground) — the flagship is already scaffolded.**
`observability/sre-agent/` is real: a 141-line harness, three graded Mimir
bundles, a CI job proving `reference_answer` never leaks into the prompt —
and it has **never been run against the real API** (no key in the build
environment; an owner-only step, same class as #99). The sequence is
obvious and cheap: (1) the owner runs v1 and the human grading gets
written up honestly — that write-up is itself the article ("what my AI SRE
caught, missed, and hallucinated about my own real incidents"); (2) v1.5
adds bundles from the incidents ADR 0039 explicitly deferred (Beyla's
red-herring OOM, chaos 01/02); (3) v2 goes live-triggered against
Loki/Tempo/Prometheus per #66's full AC — with #64 as the re-trigger
mechanism #66's own AC already names. Note what this makes Chaos Mesh: not
a checkbox, but **the evaluation harness for the sre-agent** — the two
items compose into one storyline. Cilium/Hubble (§3a) is the other
objective-3 anchor: eBPF is the most state-of-the-art thing this machine
can run, and it fits.

## 6. The sequence (next ~90 days)

Ordered, with dependencies respected; same style as the 2026-08-09
review's §8, but this is a redirection map, not a punch list:

1. **sre-agent v1 real run + graded write-up** — days, owner supplies the
   API key, highest novelty-per-effort in the backlog. (Objectives 3, 4)
2. **Publish article #1** (Mimir series or outbox force-kill — pick one,
   ship it), with the **#88 Phase 1 go/no-go** decided alongside so the
   article can link something live. (Objective 4)
3. **Capacity-reclaim pass**: Mimir + Beyla teardown (ADR 0036/0038
   addenda), M13 request re-trim. Frees §4's ledger; nothing new deploys
   before this. (Enables 4–5)
4. **M7-rescoped stage 1 — Cilium + Hubble via the single-node rebuild**,
   flannel-restore runbook rehearsed first, full-restore RTO measured and
   fact-packed. (Objectives 2, 3; ADR 0023 finally lands)
5. **M7-rescoped stage 2 — #50 default-deny NetworkPolicies from observed
   Hubble flows**, denied-flow verification live. (Objectives 2, 3)
6. **App-level fail-fast (#43/#105)**: timeout budget + circuit breaker in
   `api`, chaos 01/02 re-run, before/after postscripts. (Objective 2)
7. **~2026-09-06: the SLO-over-time report (#94)** — write and publish it
   the week the window closes; article #2 or #3. (Objectives 1, 4)
8. **Chaos Mesh (#64)**: scenarios as code, first real network partition,
   then wired in as sre-agent v2's live re-trigger mechanism. (Objectives
   2, 3)
9. **sre-agent v2** (live queries, own Application — #66's real AC), once
   8 gives it something to be triggered by. (Objectives 3, 4)
10. **The tail, as one batch, capped**: #91/#118 positive cases, #98's
    last setting, #117, #84, #21e, #38/#39. Hygiene is a batch here, not
    a phase — see §9.

## 7. ADR changes

1. **ADR 0035 — addendum required** (the ADR 0037 honest-correction
   pattern, applied again): the interim-VM decision was made before this
   capacity math existed; the math falsifies it (§1), including the
   trimmed one-VM variant its own pre-flight gate anticipated. The
   addendum records the measurement, states that no VM agents run on this
   laptop, and points to the rescope ADR below. #48 closes as
   **superseded**, not Done.
2. **A new ADR (0040): M7 rescoped under the hardware ceiling** — the
   decision record for §3 as a whole: Cilium/Hubble/NetworkPolicy
   unbundled from multi-node and executed on one node via deliberate
   rebuild; #51/#52 re-labeled Blocked (hardware); the Istio track
   deferred with the mesh's benefits re-priced honestly; the per-client
   fail-fast fix un-deferred; the cloud-annex option recorded with its
   trigger (§3d). One ADR, because these are one decision — the parts
   only make sense together.
3. **ADR 0024 — addendum**: status effectively Deferred (blocked on
   hardware); its 2026-08-08 addendum ("neither #43 nor #105 gets an
   independent per-client fix") is reversed by 0040 with the reasoning in
   §3b — the "handful of lines in two clients" answer it beat is the
   answer that fits the machine. Also correct the loose ADR 0010 citation
   (§10.4) while touching the file.
4. **ADR 0023 — no change needed.** The Cilium decision stands entirely;
   only its transport (the #48 rebuild) changes, which 0040 records.
5. **ADR 0025 / M12 — one honest line**: "lands after M7's multi-node/
   replicated-storage substrate" now means blocked-on-hardware with no
   date. Same for ADR 0029's FinBERT-v2 trigger ("once M7's hardware
   exists") — both now reference the real dedicated host, not the dead VM
   interim. ADR 0031's "M12 stays gated on M7" inherits the same meaning.
6. **Consequential doc updates, not ADRs**: `WHY.md`'s M7 row and
   `overview.md`'s "Still not yet built" paragraph both describe M7 as
   gated on a hardware move — true again, but the *shape* changes with
   0040. And one live drift to fix while there: `overview.md` still says
   #94 is "blocked on a declined PVC resize" — false since this morning
   (16Gi PVC bound, zero data loss; §10.5).

## 8. What *not* to do

- **Don't build #48 in any form on this laptop** — not two VMs, not one,
  not "just to try it." The requests arithmetic is refutable only by
  ignoring the RAM carve-out and the hyperthread reality, and the
  cluster's own KEDA drill already demonstrated what 93%-requested looks
  like when something real asks for more (`Insufficient cpu`, #63).
- **Don't adopt the cloud annex now** (§3d) — the trigger is stated;
  pulling it early buys fact packs at the cost of the narrative while
  higher-value single-node work sits queued.
- **Don't keep concluded experiments deployed as trophies.** ADR 0038's
  own verdict argues for Mimir's teardown now that capacity is the binding
  constraint; the write-up is the asset. Same for Beyla.
- **Don't start M12 or any new application service.** The ADR 0031 gate
  (#90–#97) is anyway not fully cleared — #91's positive case and #94's
  report are still pending — and the marginal-shape-vs-tax reasoning both
  prior reviews upheld only tightens at 93%.
- **Don't respond to the ceiling by micro-optimizing the cluster as a
  hobby.** One reclaim pass (§4), sized to what §3a needs, then stop —
  endless request-shaving is the boring failure mode of a
  hardware-constrained lab, and §9 exists to prevent exactly that.

## 9. The appeal test (the fifth constraint, applied)

A redirection that reads as "you can't have the fun milestone, here's
hygiene instead" would fail the owner's own stated constraint even if
every line above is technically right. Checked deliberately:

- **The most novel thing in the backlog survives and moves first** — the
  sre-agent was never hardware-gated, and steps 1/8/9 make it this
  stretch's through-line, not a leftover.
- **The state-of-the-art itch keeps a real outlet**: eBPF/Cilium/Hubble is
  arguably the most modern technology this project has ever deployed, and
  it lands *sooner* under this plan than under the old sequencing (no
  longer queued behind VM provisioning).
- **The rebuild is an event, not a chore**: tearing the only node down to
  `--flannel-backend=none` and watching 36 Applications reconcile from git
  against a measured clock is the highest-stakes exercise this project has
  ever run on purpose.
- **Chaos Mesh partitions are new physics** for this cluster — every fault
  so far has been a kill; a slow, reachable dependency is a different and
  more interesting enemy.
- **Publishing closes the loop that makes lab work feel real**: external
  readers, for the first time, with live links if #88 Phase 1 goes ahead.
- **Hygiene is explicitly capped** (§6 step 10): one batch, at the end,
  never the identity of the phase.

What's honestly lost for this stretch: the multi-node substrate itself,
and the mesh. Both are recorded as blocked, not abandoned — and the boring
version of this review (do nothing until hardware arrives) was the one
outcome ADR 0035 already ruled out once: "blocked indefinitely is how a
solo lab actually stalls."

---

## 10. Review of this review (2026-08-09, before merge)

Every load-bearing claim — especially every resource number — was
re-verified against the live cluster, the real charts, and the real repos
during this review, not carried from the briefing that seeded it. Findings
from that pass, including corrections to this review's own inputs:

1. **The capacity numbers held on re-measurement.** `kubectl describe
   node`: 3745m/4000m (93%) requested, memory requests 7654Mi (38%);
   `kubectl top node`: 2223m (55%) / 11189Mi (56%) real; `free -h`: 5.1Gi/
   8Gi swap used, ~7.7Gi available; `lscpu`: 2 cores, 2 threads/core.
   All consistent with backlog #48's own 2026-08-09 pre-flight note.
2. **One chart-default claim in the briefing was imprecise, and is
   corrected here rather than repeated**: `helm show values cilium/cilium`
   shows the agent's default is actually `resources: {}` — 100m/512Mi is
   the chart's own *commented reference sizing*, not an enforced default.
   The correction changes nothing material: this project's own #114
   convention forbids deploying unconstrained containers, so real requests
   would be set at approximately those values anyway, and the §1 math is
   dominated by ztunnel (200m/512Mi) and istiod (500m/2048Mi), both
   confirmed as real, uncommented chart defaults.
3. **The briefing's ADR count was off by one, again in the same direction
   as last time**: it said 38; the real count is 39 (`0001`–`0039`,
   ADR 0039 being the sre-agent v1 scope). Corrected in the scope line.
   Two briefs in a row have miscounted this — the number is one `ls` away.
4. **A citation this review initially planned to repeat does not check
   out, and the plan §3b was adjusted to say so**: ADR 0024 and backlog
   #59 both quote ADR 0010 as stating "no auth between in-cluster
   services." Grepped directly: **that phrase does not appear in ADR
   0010**, whose actual subject is gateway routing (a component ADR 0021
   later removed). The nearest real in-repo statement is ADR 0012's
   "(PLAINTEXT, no auth)" for Kafka. The *gap* — unauthenticated plaintext
   in-cluster traffic — is real and unchanged; the attribution is loose
   and should be corrected in ADR 0024's next addendum (§7.3) rather than
   propagated a third time.
5. **The state this review was briefed on had already moved by the time it
   was written — verified live rather than inherited**: #94's PVC
   recreation, described in the 2026-08-09 staff review (§7.8) as declined
   and standing drift, was executed today with zero data loss (16Gi PVC
   `Bound`, 46 minutes old at check time; retained history verified by
   real `/api/v1/query` offsets per the backlog note). Consequence:
   §7.8's `OutOfSync` finding is resolved, #118's alert now guards the
   class, and `overview.md` carries a fresh one-line drift (§7.6) — the
   same prose-staleness class #97's checker was explicitly scoped not to
   catch, recurring for a fifth time, right on schedule.
6. **Checked whether unbundling Cilium from the multi-node rebuild
   contradicts ADR 0023 before recommending it**: it doesn't. 0023's
   decision is the CNI adoption; the multi-node coupling lives only in
   backlog sequencing ("a cluster rebuild — which #48 is doing anyway",
   #49's Purpose) and in ADR 0024's sprint ordering. The rebuild
   requirement is honored on one node; only the "#48 first" chain breaks,
   which is §7.2's ADR to record.
7. **Checked the ADR 0031 gate before recommending "no new services"**:
   the gate (#90–#97) is not fully cleared — #91 is "built, live proof
   pending" (positive case needs US market hours) and #94's report needs
   ~28 more days — so §8's prohibition is the project's own standing rule
   restated, not a new constraint this review invents.
8. **What this review looked for and did not find**: any open backlog item
   that is both hardware-blocked and *not* covered by §3's disposition —
   checked every `Dependencies: #48` chain: #49–#52 and #59–#62 are
   rescoped/substituted/blocked per §3; #67–#72 (M12) per §7.5/§8;
   #78/#79 were already Done under the owner's M13 override; the one
   remainder is **#65 (Kubecost)**, whose #48 dependency was always the
   soft one ("gains value once M12's workload diversity exists") — its
   disposition is: dependency rewritten to that real question, stays P2,
   not picked up this stretch (another always-on component is the wrong
   purchase on a capacity-bound node). Also looked for any prior ADR whose
   *resource*
   assumptions (as opposed to sequencing assumptions) the ceiling
   invalidates — none found: every deployed component already carries
   measured, explicit requests (#114), which is precisely why the 93%
   figure can be trusted enough to plan against.
