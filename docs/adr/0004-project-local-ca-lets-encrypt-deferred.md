# 0004. TLS strategy: project-local CA now, Let's Encrypt deferred

Status: Accepted (retroactive — decision shipped in platform PR #9 before
this ADR was written)

## Context

Services behind Traefik need TLS with automatic issuance and renewal. The
obvious answer is cert-manager with a Let's Encrypt `ClusterIssuer` — but
the cluster currently runs on a NATed host with no public IP reachability
and no public DNS. Neither ACME challenge can complete: HTTP-01 requires
Let's Encrypt to reach the host over the internet, DNS-01 requires
publicly resolvable records for the hostnames. A Let's Encrypt issuer
configured today would be permanently-failing config pretending to work.

## Decision

Use cert-manager with the bootstrap-CA pattern
(`platform/kubernetes/cert-manager-issuers/`): a `selfsigned`
ClusterIssuer signs one 10-year `adamastorx-root-ca` Certificate, and the
`adamastorx-ca` ClusterIssuer signs all leaf certificates (90-day, renewed
automatically) off that root. Services request certs via the
`cert-manager.io/cluster-issuer: adamastorx-ca` Ingress annotation.

Let's Encrypt is deferred, not rejected. Explicit trigger for revisiting:
migration to a host with public DNS (already on the roadmap). At that
point an LE `ClusterIssuer` is added alongside this one and services
switch per-Ingress; the project CA can stay for internal-only endpoints.

## Consequences

- Issuance and renewal are fully automatic and real — only trust is
  project-local.
- Clients must trust the project CA until the migration: export the root
  from the `adamastorx-root-ca` Secret (`cert-manager` namespace) and use
  `curl --cacert` or a browser trust-store import. Anything that can't be
  told to trust a custom CA will show certificate warnings.
- The revisit is additive (new issuer, per-service switch), not a
  migration of this one — no cert downtime when the trigger fires.
