# 0024. Adopt Istio (ambient mesh) for mTLS and traffic control, overturning ADR 0023's service-mesh exclusion

Status: Proposed

## Context

ADR 0023 adopted Cilium and, in the same pass, re-examined the other four
excluded tools and kept them excluded — service mesh among them. It set an
explicit rule for reopening any of them: *anything reopening one of those
four cites this ADR's specific argument against it.* This ADR does exactly
that, for the mesh. It is a separate ADR rather than an edit to 0023 on
purpose: 0023 is the record of a CNI adoption and its title says so;
folding a second, unrelated technology adoption into it would muddy both.
0023's mesh bullet stays as the honest record of what was decided then, now
carrying a forward-reference to here.

ADR 0023's argument against a mesh had three parts. Each is answered below
by something 0023 did not weigh, not by disagreeing with what it did weigh.

1. **"Retries/timeouts are a handful of lines in two clients."** True as
   far as it goes, and it misses the actual gap. Two chaos scenarios this
   project ran live found the same failure shape in writing: a downstream
   outage does not fail fast, it *hangs the calling HTTP thread* for tens
   of seconds before erroring — ~60s on Kafka's producer `max.block.ms`
   (`observability/chaos/01-kafka-broker-unavailable.md`, backlog #43) and
   ~30s on HikariCP's connection-acquisition timeout
   (`observability/chaos/02-postgresql-unavailable.md`). That is traffic
   *control* — circuit breaking, outlier detection, a real timeout budget —
   not traffic *visibility*, which is the one thing OTel/Prometheus already
   give. It is also the **same problem in two languages** (Java `api`,
   Python `clinvar-service`); a per-client fix solves it once per language
   and never uniformly, while the mesh solves it in one place at the
   dataplane for every service regardless of language. 0023 costed the
   easy version of this problem and priced the mesh against it.

2. **"mTLS between four pods secures nothing against a real threat."** The
   reason to want it here is not the threat model — it is that **ADR 0010
   states plainly "no auth between in-cluster services" as a deliberate
   simplification**, and nothing has revisited that since. Closing a
   gap the project stated in writing and then learning the pattern that
   closes it is squarely this project's content goal (ADR 0022); in ambient
   mode mTLS is close to free once the mesh is present, so the objection
   ("a sidecar per pod to encrypt localhost") no longer holds either.

3. **The friction is the point, not a cost.** Running Cilium and Istio
   together has real, non-obvious edges — who owns kube-proxy replacement,
   how ambient's ztunnel/waypoint dataplane sits on top of Cilium's eBPF
   datapath, ambient vs. classic sidecar. ADR 0022's stated content goal
   values real lived friction over clean tutorials; this is exactly that
   kind of material, and 0023 treated it purely as risk.

What a mesh is **not** bought for here, so the boundary with 0023 stays
clean: **not** L7-aware network policy — Cilium already provides that below
(ADR 0023, backlog #50), and Istio does not replace it. Cilium owns L3/L4
identity and policy; Istio owns application-layer traffic *behaviour*
(retry/timeout/circuit-breaking/outlier-detection), mTLS identity, and
fault injection. Two layers, two jobs, stated so neither is bought twice.

## Decision

**Adopt Istio in ambient mode — not the classic sidecar model — as a
separate, later change after Cilium (backlog #49) is in and proven.**
Ambient is chosen deliberately: no per-pod sidecar, a lighter per-node
ztunnel plus waypoints only where L7 policy is actually needed, and it is
the newer, more-interesting-to-write-about mode.

**Sequence Cilium first, then Istio as its own change — for failure
attribution.** Cilium rides along with the M7 cluster rebuild because it
*is* the CNI (ADR 0023); Istio is layered on afterward, on its own, so
that if the dataplane breaks it is possible to say which layer caused it.
Doing both in one rebuild would make every failure ambiguous.

Istio adoption is structured as **three sprints** (backlog #59–#61):

- **Sprint 1 (#59) — ambient + mTLS + gateways.** Install ambient Istio on
  the Cilium cluster; bring the existing workloads into the mesh; enforce
  STRICT mTLS (closing ADR 0010's stated gap); stand up an ingress/egress
  gateway. The Cilium↔Istio integration edges are worked and documented
  here, not glossed.
- **Sprint 2 (#60) — traffic control.** The direct fix for the two real
  incidents: per-route timeouts, retries, circuit breaking, and outlier
  detection, verified by re-running scenarios 01/02 and confirming the
  caller now fails fast instead of hanging ~30–60s.
- **Sprint 3 (#61) — fault injection.** Istio delay/abort fault injection
  as its own deliberate chaos-adjacent exercise, producing a fact pack in
  `observability/chaos/` per the existing convention.

**Resolve the Argo Rollouts / Istio traffic-splitting overlap explicitly.**
Argo Rollouts (backlog #46) stays the progressive-delivery *controller* and
keeps owning the SLO-analysis gate. Once Istio is present, Argo Rollouts
uses **Istio as its traffic-management provider** (a real, supported
integration — Rollouts drives `VirtualService` subset weights) rather than
both tools independently implementing traffic splitting. Backlog #62 makes
this migration a stated decision, not an overlap left to be discovered.

## Consequences

- The excluded-tools list in `.claude/PROJECT.md` is amended again:
  **service mesh is removed**; Vault, Crossplane, and Backstage remain,
  still on ADR 0023's reasoning. ADR 0023's mesh bullet gets a
  forward-reference note here so the record reads honestly — 0023 was right
  for the argument it made and it named the argument this ADR had to beat.
- Ambient Istio adds a control plane (istiod) and a per-node ztunnel to the
  dataplane. Unlike a sidecar mesh this is not per-pod overhead, but it is
  another component whose failure degrades traffic for every meshed
  service — accepted knowingly, sequenced after Cilium precisely so its
  blast radius is separable from the CNI's.
- M7's scope grows: the dataplane is now "Cilium for identity/policy, Istio
  for traffic behaviour/mTLS." `docs/architecture/overview.md`'s
  network-dataplane section (added by ADR 0023) gains the mesh layer.
- **Two other tools from the same external second-opinion review are
  rejected here rather than silently dropped:**
  - **Swapping Traefik for ingress-nginx** — rejected. Traefik already
    works, already has the local CA and six live Ingress hostnames wired up
    (ADR 0021's fixed-local-addresses work), and Istio's ingress gateway
    now covers the mesh-facing edge. Swapping ingress controllers teaches
    no new lesson; it is pure churn.
  - **ExternalDNS** — rejected as premature. No public DNS exists yet (ADR
    0004 deferred Let's Encrypt / public addressing deliberately); there is
    nothing for it to manage until that premise changes.
</content>
</invoke>
