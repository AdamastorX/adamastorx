# 0005. Traefik exposure via hostPort 80/443

Status: Accepted (retroactive — decision shipped in platform PR #9 before
this ADR was written)

## Context

Traefik (the GitOps-managed replacement for k3s's disabled bundled one)
needs traffic to reach it on ports 80/443. k3s runs with
`--disable servicelb` and there is no cloud load balancer, so a
`type: LoadBalancer` Service would sit `<pending>` forever. Remaining
options: NodePort (works, but exposes `:3xxxx` ports — real 80/443 would
still need something in front), re-enabling ServiceLB (adds a component
solely to simulate an LB on one machine), or hostPort (binds 80/443
directly on the node).

## Decision

hostPort 80/443 on the Traefik pod, with the Service kept ClusterIP for
in-cluster use. Single node, ports 80/443 free on the host: hostPort gives
real ports with zero extra moving parts. Revisit if the cluster ever gains
more nodes or a real load balancer.

## Consequences

- Upgrade strategy must be `maxSurge: 0` / `maxUnavailable: 1`: a surge
  pod can never bind the already-bound hostPort on the only node, so the
  chart's default RollingUpdate would deadlock every Traefik upgrade.
  Accepted cost: brief ingress downtime during upgrades.
- Ingress status needs `ingressEndpoint.ip` (the node IP) instead of
  `publishedService`, since a ClusterIP Service has no LB status to copy —
  without it every Ingress-owning ArgoCD app sits Progressing forever.
  Status-cosmetic only; traffic hits the hostPort regardless.
- The decision is explicitly single-node-shaped. Multi-node or an LB in
  front invalidates it — that revisit supersedes this ADR rather than
  patching it.
