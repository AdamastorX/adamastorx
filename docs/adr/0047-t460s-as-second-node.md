# 0047. The T460s joins as a tainted agent: one server on Wi-Fi, an asymmetric second node

Status: Proposed

## Context

ADR 0045 (2026-08-30) moved the platform from the Lenovo T460s to the
NucBox and called the new host "a genuine multi-node substrate". In
practice the cluster has been one node (`adamastorx`) since the cutover.
The owner has now decided (2026-10-09) that:

- the T460s becomes the second k3s node;
- the NucBox stays on its USB Wi-Fi dongle with a DHCP address (no cable,
  no router reservation), so its LAN IP can change (it moved from
  `192.168.1.10` to `192.168.1.7`, backlog #162).

The two machines are very unequal. NucBox: 16 CPU, ~58.7GiB RAM,
k3s v1.36.4+k3s1 (`kubectl describe node adamastorx`). T460s: i7-6600U,
2 cores / 4 threads, ~19.5GB RAM, 233GB disk (backlog #48, measured
2026-08-09), historically the operator's daily laptop. Every PVC is
`local-path` (14 of them), nothing in the repo sets `nodeSelector`,
affinity or tolerations, and Cilium is configured for one node
(`k8sServiceHost: 127.0.0.1`, `argocd/apps/cilium.yaml:81`). Evidence:
`docs/reviews/2026-10-09-project-review-opus.md` §6.

## Decision (proposed)

1. **One server, one agent.** The NucBox stays the only k3s server. No HA
   control plane: an embedded-etcd quorum needs three servers, and a
   two-server setup is less available than one.
2. **The agent joins over the NucBox's Tailscale address**
   (`100.69.223.105`, already a `--tls-san`), not the DHCP LAN address.
   Cilium's `k8sServiceHost` moves to an address both nodes reach. The
   agent sets its node IP explicitly. Both nodes pin the same k3s version.
3. **The T460s is tainted (`NoSchedule`) and labeled.** Workloads opt in
   through an explicit, short allowlist of stateless services. Everything
   with a PVC, every memory-heavy component (Kafka, Prometheus, Tempo,
   Mimir, Loki, Pyroscope, the Postgres instances) and Traefik (hostPort,
   and operator `/etc/hosts` point at the NucBox) are pinned to the NucBox
   with node affinity, checked at render time in CI.
4. **Roles for the second node**: drain and node-loss target for #52,
   reschedule target for #51's capability test, and an off-node (not
   off-site) backup disk (#176). Not a compute expansion: #69 stays
   blocked, Istio (#59-#62) stays superseded under ADR 0040.
5. **Pre-join gate**: the T460s's old k3s server install and old
   `local-path` data are removed, power policy set (no suspend on lid
   close), and current measurements recorded before the join (#171).
   If the laptop is still the operator's daily machine, this ADR is
   revisited before it is Accepted.

## Alternatives considered

- **Join over the LAN address.** Rejected: the server's LAN address is
  DHCP on Wi-Fi and has already changed once under a running cluster.
- **Promote the T460s to a second server.** Rejected: no quorum gain and
  a weaker machine in the control plane.
- **Leave scheduling untainted and rely on requests.** Rejected: requests
  are 21%/16% of the NucBox while limits are 110%/44%, so the scheduler
  would happily place limit-heavy pods on the laptop.
- **Do not add the node.** Possible; it keeps #51/#52 blocked indefinitely.
  The owner chose to add it.

## Consequences

- New milestone M19 carries the work (#171-#176), and #51/#52 depend on
  #174 instead of the superseded #48.
- Overlay traffic between nodes runs VXLAN inside WireGuard over Wi-Fi;
  MTU must be set explicitly and tested with full-size packets (#173).
- Policies that use `toEntities: host` for API-server or node targets must
  be rewritten for two nodes (#168, #173).
- ADR 0045's "multi-node substrate" statement becomes true only when #174
  lands; ADR 0045 gets an addendum saying so (#167).
- M19 does not start until #163 and #165 are done.
