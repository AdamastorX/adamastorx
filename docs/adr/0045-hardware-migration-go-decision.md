# 0045. Hardware migration: go decision, multi-node substrate, carry-PVC history preservation

Status: Accepted

## Context

Backlog #152 named this an owner decision, not pure engineering: the owner
has new hardware, and the 2026-08-21 staff-engineer audit
(`docs/reviews/2026-08-21-staff-engineer-full-audit.md`, ADR 0044's own
response to it) recommended migrating the live platform off the T460s and
keeping the single-node constraint as documented history rather than an
ongoing cost. The audit's live-checked numbers, carried into ADR 0044:
memory 111% overcommitted, 4-5Gi swap at rest, Mimir OOMing roughly every
6 hours, and #69's real Nextflow pipeline permanently blocked under the
current ceiling. ADR 0040/0041 already banked the single-node story's
narrative dividend; its operational cost keeps growing, not shrinking.

This is the successor to #104 (Done, ADR 0035 — the VM-interim decision),
which PROJECT.md itself records as "open again in practice" once ADR
0040's capacity math superseded it: no VM agent ever fit this machine at
any trim level checked, so #104's decision was correct for what it
answered but the question re-opened as soon as ADR 0040 landed.

**Owner decision, recorded here (2026-08-30)**:
- **Go.** Migrate off the T460s.
- **New host is a genuine multi-node substrate** — not a single beefier
  node. This unblocks #51/#52 as well as the migration itself, not just
  one or the other.
- **Hardware is already physically available** — no further gating date
  needed before #153 starts.
- **#94's 30-day Prometheus history-preservation precondition**: the
  retention window (started 2026-08-07 per #94's own status note) has not
  closed as of this ADR — about a week remains, target ~2026-09-06. The
  owner chose not to wait: carry the Prometheus PVC across now using the
  same PVC-copy discipline #49's single-node rebuild already proved live
  (copy `/data` out via a temporary pod, restore it onto the new host's
  equivalent PVC via a temporary pod), rather than block the whole
  migration on the clock. This repeats a pattern this project has run
  before, not a novel one — but #94's own 2026-08-09 follow-on incident is
  the reason the restore step below is spelled out explicitly rather than
  assumed to just work.

A cloud annex was considered and stays rejected, unchanged from ADR 0040
§6: this is a move to owned, physical hardware, not a pivot to cloud. ADR
0040 §6's own stated trigger for revisiting the annex ("no dedicated-host
date exists yet, once the queue drains") is now moot — a dedicated-host
date exists as of this decision.

This session could not re-verify current live cluster numbers directly
(cluster access is permission-gated in this environment) — the figures
above are carried from ADR 0044's own live-checked audit response, not
re-measured today. **#153's restore drill is where these get re-measured
against the new host for real**, not assumed still current from this
ADR's text.

## Decision

1. **Go.** The platform migrates off the T460s to the owner's new,
   already-available hardware.
2. **The new host is confirmed as a genuine multi-node substrate.** This
   retires the ADR 0041 memory-ceiling class, unblocks #69 (Nextflow), and
   re-opens #51/#52 (cross-node reschedule proof, drain/node-loss/
   rolling-upgrade drills) — real work again, not "Blocked (hardware)."
   The Istio ambient-mesh track ADR 0040 §4 superseded is **not**
   automatically restored by multi-node alone; if picked back up, it gets
   its own re-litigation ADR against the new host's real headroom, not an
   assumption that more nodes alone re-justifies it.
3. **#94's history-preservation method: carry the PVC across now**, via
   #49's proven pattern — copy the live Prometheus `/data` out via a
   temporary pod, restore it onto the new host's PVC via a temporary pod,
   with an **explicit `chown` to the Deployment's real
   `runAsUser`/`runAsGroup` (65534)** as a named step, not an assumption —
   `local-path`'s `hostPath`-backed PVCs do not get `fsGroup` correction
   from the kubelet, the exact gap that caused #94's 2026-08-09
   `CrashLoopBackOff`. This is executed and proven as part of #153's
   restore drill, before #154 touches the real live data — not assumed to
   work from this ADR's text alone.
4. **Cloud annex stays rejected**, unchanged from ADR 0040 §6.
5. **Execution path, in order, no step skipped or reordered**: #153
   (restore drill on the new host, using #23a and the #123 acceptance
   checklist, must pass before cutover) → #154 (the actual cutover) →
   #155 (post-migration acceptance, RTO and what-didn't-come-back
   writeup). This is the same execution-vs-proof separation this project
   already used for #49-then-#123.
6. **Terraform is re-targeted at the new host as part of #153/#154.** The
   single-node path stays supported as a variable, not forked — the same
   discipline ADR 0035/0040 already established.
7. **#99 (off-node backup: restic/rclone, including Terraform state)
   stays deferred, unchanged by this ADR.** It remains a real, open DR
   gap for the old host in the meantime — this migration does not
   silently resolve it, and #99 is not a precondition for #153/#154 to
   proceed.

## Consequences

- #152 → **Done**, this ADR. #153 is unblocked and can start immediately
  — hardware is available, the go decision and the history-preservation
  method are both recorded above.
- #51/#52 → move from "Blocked (hardware)" (ADR 0040 §Decision.3) to real,
  executable multi-node drills, gated only on #154 actually landing — not
  reworded as unblocked until the cutover is real.
- ADR 0041 (node memory ceiling) is **not** superseded by this ADR alone —
  it stays `Accepted` until #154 completes and the old host is actually
  decommissioned, so nothing here claims the constraint is gone before it
  is.
- Risk accepted explicitly, stated rather than glossed: carrying the PVC
  now instead of waiting for #94's window to close means if the
  copy/restore step has any gap, the in-flight partial history is what is
  at stake, not a fresh, already-complete 30-day dataset. #153's drill is
  the point where this is proven correct or a gap is found — before #154
  touches the real, live data.
- #94 itself stays open (not Done) until its 30-day report is actually
  published — the migration changes *where* that clock's data lives, not
  whether the report still needs writing.
