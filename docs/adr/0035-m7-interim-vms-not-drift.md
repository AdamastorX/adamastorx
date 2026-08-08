# 0035. M7 gate decision: interim multi-node VMs on the existing laptop, not an indefinite wait for dedicated hardware

Status: Accepted

## Context

M7 (the dedicated-host migration) and everything gated behind it —
M12's reopened bioinformatics milestone, multi-node k3s (#48), Cilium
(#49), NetworkPolicies (#50), replicated storage (#51), real node-loss
drills (#52) — has sat blocked on one physical hardware move with no
date attached since it was first named. "Blocked indefinitely" is how
a solo lab actually stalls: not by a decision to stop, but by nothing
ever being decided at all. Backlog #104 named the three honest
outcomes ("dedicated host by a stated date, the VM interim, or
explicitly accept the gate with a review date — drift is the one
answer not allowed") and asked for one of them, for real.

## Decision

**The interim VM path**: two additional k3s agent nodes as local VMs
(multipass or lima) on the existing laptop, provisioned through the
same Terraform SSH remote-exec path #5 already proved for the current
single server node — not a new provisioning mechanism, an extension of
the one already trusted.

This is chosen over the other two real options:

- **Dedicated host by a stated date** — rejected for lack of an honest
  date to state. The real hardware move has no committed timeline;
  writing one down that isn't real would just be drift wearing a
  date, the exact failure mode this decision exists to avoid.
- **Explicitly accept the gate, with a review date** — rejected as the
  weaker answer available: it protects against silent drift but
  leaves #48–#52's real multi-node learning (Cilium, NetworkPolicies,
  node-loss drills — genuinely new Kubernetes operational skill this
  project hasn't exercised yet) blocked for no real reason when a
  cheap, honest interim exists.

The VM path doesn't betray the "owned hardware, not cloud" story this
project has told throughout — it's still the same laptop, still
Terraform-provisioned, still fully under the operator's own control.
The one thing it structurally cannot provide is a real, physical
power-loss test (#52's own hard-power-off AC) — a VM's own host is
still the single point of failure a physical multi-node cluster
wouldn't have. Stated here as a real, accepted gap, not glossed over:
if the dedicated host migration ever does happen, that specific test
becomes available for the first time, not before.

## Consequences

- **#48's own AC is adapted, not rewritten**: "multi-node k3s,
  provisioned from the existing Terraform" now means 2 local VM agent
  nodes plus the existing physical server node, not 2+ separate
  physical/dedicated hosts. The single-node path stays supported as a
  Terraform variable (matching this project's own existing pattern of
  keeping prior configurations reachable, not forking), not removed —
  a real regression to single-node remains one variable flip away if
  the VM approach ever needs to be backed out.
- **#49–#52 unblock on the same real timeline as #48**, not
  separately gated — Cilium, NetworkPolicies, replicated storage, and
  node-loss drills all need the multi-node substrate #48 provides,
  regardless of whether that substrate is VMs or physical hosts.
- **M11 (`sre-agent`) and M12 (reopened bioinformatics)** remain
  sequenced after this substrate work, unchanged — this decision
  unblocks the substrate, not the milestones stacked on top of it.
- If a dedicated host migration does become real later (a stated date
  actually arrives), that's a fresh, separate decision to make at that
  time — this ADR does not need to be revisited or reversed for that
  to happen; the VM interim and a later hardware move are additive,
  not competing.
