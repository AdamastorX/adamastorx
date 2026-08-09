# 0040. M7 rescoped under the hardware ceiling

Status: Accepted

## Context

ADR 0035 chose an interim path for M7 (two local VM agent nodes on the
existing laptop) rather than an indefinite wait for dedicated hardware.
That decision was made before the capacity math to check it against
existed. A staff-engineer strategy review
(`docs/reviews/2026-08-09-hardware-constrained-strategy.md`), triggered by
the owner deciding to stay on the current laptop for a meaningful stretch,
re-measured the cluster and host live (`kubectl describe node`,
`kubectl top`, `free -h`, `lscpu`, and the real upstream Helm charts via
`helm show values`) rather than inheriting numbers from an earlier
briefing, and found: this node's CPU requests already sit at **93% of its
4000m allocatable** (3745m), and those 4 "vCPUs" are **4 hyperthreads on a
2-physical-core i7-6600U**, not 4 independent execution units. The real
cost of the planned path — a second VM node plus Cilium+Hubble plus the
Istio ambient-mesh track (backlog #48/#49/#59–#62) — totals roughly
**+1550m CPU / +5.2Gi RAM** before any workload is scheduled for actual
work: against today's 3745m, that is **~5295m against a 4000m ceiling,
about 132% of the machine** (~124% even with the VM overhead estimate
zeroed out). ADR 0035's own addendum records this falsification in full;
this ADR records the decision for where M7 goes instead — one decision,
because the parts (Cilium's unbundling, the mesh's replacement, #51/#52's
honest labeling, the capacity ledger, the cloud-annex non-adoption) only
make sense together.

A physical fact underlies the whole finding: **a VM does not add cores.**
It re-partitions the same hyperthreads the single node already saturates.
Total real demand across "the cluster" cannot exceed what this one machine
has, no matter how many virtual nodes divide it.

## Decision

**1. Cilium + Hubble + first NetworkPolicies (backlog #49, #50) unbundle
from multi-node and execute on one node**, via a deliberate, rehearsed
full-cluster rebuild. ADR 0023's own decision is unchanged — Cilium was
never bundled into M7 for a multi-node reason, only because a CNI swap
needs a cluster rebuild and #48 was doing one anyway (#49's own Purpose
says this explicitly). That reasoning now runs in reverse: the rebuild is
the only remaining cost, and it is payable on one node. A flannel-restore
runbook is written and rehearsed **before** the rebuild is attempted, not
after — a broken CNI on the only node is the one failure ArgoCD cannot
recover from, with no second node to retreat to. What a single node
genuinely cannot show (cross-node routing, WireGuard node-to-node
encryption, multi-node identity propagation) is real but small, and stated
rather than glossed. The rebuild itself is treated as a first-class fact
pack, not overhead to minimize: rebuilding the entire platform from git +
backups, with a measured RTO, is the strongest available test of ADR
0003's GitOps claim this project has ever run, and a partial substitute
for the *spirit* of #52 while its letter stays blocked.

**2. Backlog #48 closes as superseded, not Done.** The interim-VM path
ADR 0035 chose does not fit this machine at any trim level checked
(§Context; ADR 0035's own addendum has the full arithmetic, including the
maximally-trimmed Cilium-only variant). No VM agents run on this laptop.

**3. Backlog #51 and #52 are re-labeled Blocked (hardware), honestly.**
Both are definitionally impossible on one node — #51's cross-node
reschedule proof has nowhere to reschedule to; #52's drain/node-loss/
rolling-upgrade drills have nothing to drain to and nothing to lose that
isn't everything. This is the same honesty this project already practices
for #99 (owner credential) and #89's retroactive captures (no browser): a
real, stated gap beats a faked version of the exercise. Neither item is
deleted or reworded otherwise.

**4. The Istio ambient-mesh track (backlog #59–#62) is superseded, not
merely deferred, by app-level fail-fast.** istiod's 500m/2048Mi plus
ztunnel's 200m/512Mi per node is roughly ten times this machine's entire
remaining headroom, for a cluster of ~8 application services — a price tag
ADR 0024's original "same problem in two languages, solve it once" argument
did not have when it beat ADR 0023's "a handful of lines in two clients."
At this capacity, ADR 0023's original position is no longer the argument
the mesh beat; it is the only answer that fits the machine. Concretely,
this un-defers backlog **#43** (a stated timeout budget on `api`'s Kafka
producer `max.block.ms`, well under the current ~60s hang) and **#105**
(HikariCP's `connectionTimeout` tuned with a real fail-fast path, plus a
Resilience4j circuit breaker on `api`'s outbound `clinvar-service` call —
the traffic-control piece #60 would have provided at the dataplane).
**Java/`api` only, for now**: the "two languages" cost ADR 0024 originally
priced the mesh against is deferred until a Python-side hang is actually
documented, honestly, rather than paid speculatively — only `api`'s hangs
are documented today. Both proven the way #60 would have been: chaos
scenarios 01 and 02 re-run, before/after latency recorded as dated
postscripts in the existing fact packs. #61 (Istio fault injection) loses
nothing real — Chaos Mesh (#64, already in the backlog, single-node-
feasible) covers deliberate fault injection, including network-layer
faults Istio couldn't reach. #62 dissolves with #59.

The mTLS gap ADR 0024 wanted to close (every in-cluster call is
unauthenticated plaintext — see this ADR's correction to ADR 0024's own
citation of that gap, recorded in ADR 0024's own addendum, not here) stays
open, real, and named as a future mesh benefit **when hardware exists** —
not closed, not ignored. At 2.5Gi+700m it is not "nearly free" the way
ambient mode would have made it; ADR 0023's original threat-model point
stands on one physically-owned node: mTLS between pods on the same host,
against this project's actual threat model, defends approximately nothing
today.

**5. The capacity ledger for this rescope is the M13 request re-trim
only — explicitly, Mimir and Beyla are out of scope.** The strategy
review that surfaced this whole rescope also recommended decommissioning
the Mimir and Beyla experiments (~200m CPU / ~1.2Gi RAM combined) as part
of the capacity ledger. **The project owner has directly overridden that
recommendation**: both stay deployed, full stop, to keep testing those
technologies — a real, explicit, standing decision, not an oversight this
ADR is silently working around. This means the real reclaimable headroom
for #49's Cilium/Hubble addition (~200m/~0.7Gi) is **smaller** than the
strategy review's original math assumed, which counted on the Mimir+Beyla
teardown to cover it. The only lever actually pulled here is backlog
**#120**, a #77-style re-trim of the M13 services' requests (250m each)
against real measured usage — the same, already-proven method #77 used to
cut this cluster's CPU footprint 99%→63% once before. **Re-measure real
headroom immediately before attempting the Cilium rebuild** (#49) rather
than trusting this ADR's or the strategy review's numbers as still
current by then — the ledger is real but thinner than originally proposed,
and the point of measuring instead of assuming applies to this ADR's own
figures too.

**6. A cheap cloud annex (2-3 small VMs, e.g. Hetzner CAX11-class) for
#51/#52's fact packs is recorded as a future trigger, not adopted now.**
It is the one option that actually delivers #51/#52's blocked content
(a short-lived cloud cluster, built by the same Terraform pattern, torn
down after). Not adopted: ADR 0035 states an explicit "owned hardware, not
cloud" story that even a bounded annex dilutes, the fidelity is imperfect
anyway (a cloud "hard power-off" is an API stop, not #52's physical
power-loss), and the single-node queue ahead of it is already deep with
higher-value work. **Trigger, stated plainly**: pull this only if, once
that queue drains, no dedicated-host date exists yet — and only via its
own future ADR, not as a side effect of this one.

## Consequences

- Backlog #48 → **Won't do (superseded)**. #49/#50 → unbundled from
  multi-node, dependency rewritten to "a deliberate single-node rebuild,"
  not #48. #51/#52 → **Blocked (hardware)**, unchanged otherwise. #59–#62
  → **Won't do (superseded)**. #43/#105 → un-deferred, app-level fixes,
  no longer gated on M7. #65 (Kubecost) → dependency rewritten to its real
  soft dependency (M12's workload diversity), never actually #48. New
  backlog #120 (M13 request re-trim, Mimir/Beyla explicitly out of scope)
  added as the real capacity-ledger item.
- ADR 0025 (M12), ADR 0029 (FinBERT-v2 trigger), and ADR 0031 (M12 gate)
  each gain a line: "gated on M7's multi-node substrate" now means
  blocked-on-hardware with no date, referencing this ADR and the real
  dedicated-host trigger, not the superseded VM interim.
- `docs/WHY.md`'s M7 row and `docs/architecture/overview.md`'s "Still not
  yet built" paragraph are updated to describe the rescoped shape: Cilium/
  Hubble/NetworkPolicies now targeted single-node; the multi-node
  substrate itself (replicated storage, node-drain drills, the Istio mesh)
  stays blocked-on-hardware.
- Nothing here touches ADR 0023 (the Cilium adoption decision itself
  stands; only its transport — the rebuild path — changes) or ADR 0036/
  ADR 0038 (Beyla/Mimir stay exactly as they are, per the owner's explicit
  decision in §5 above).
- What's honestly lost for this stretch: the multi-node substrate itself,
  and the mesh. Both are recorded as blocked, not abandoned.
