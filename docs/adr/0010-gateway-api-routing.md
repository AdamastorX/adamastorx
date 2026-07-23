# 0010. Gateway → API routing: application-level forwarding, Service DNS, env-injected address

Status: Accepted

## Context

services#2 (Scaffold Spring Boot API service) requires the new `api` service
be "reachable through the gateway." The `gateway` module exists today
(services#1) as a bare Spring Boot app on `spring-boot-starter-webmvc`
(servlet/Tomcat stack) with only actuator endpoints — no routing logic.
Needed before `api` is scaffolded: where routing happens, how the gateway
finds `api`'s address, and how that address is configured. Service mesh is
already banned (existing stack decision) — no Envoy-sidecar transparent
proxying was considered; noted here only for completeness.

## Decision

- **Routing happens inside the `gateway` app, via a hand-rolled forwarding
  controller using Spring's blocking `RestClient`** (part of `spring-web`,
  already on the classpath through `spring-boot-starter-webmvc` — zero new
  dependency). Rejected **Spring Cloud Gateway** (classic,
  `spring-cloud-starter-gateway`): it is built on WebFlux/Reactor Netty and
  requires the reactive stack, which directly conflicts with the
  servlet/Tomcat (`webmvc`) starter services#1 already locked in — adopting
  it means ripping out `webmvc` for `webflux` to gain a routing library, the
  opposite of boring. Rejected **Spring Cloud Gateway Server MVC** (the
  servlet-compatible variant introduced in Spring Cloud 2023.0): it avoids
  the stack conflict, but for exactly one downstream route today (gateway →
  api) it brings a route-config DSL and a newer, less-battle-tested
  dependency that buys nothing a two-method controller doesn't already do.
  Revisit if gateway ever needs to route to several backends or wants
  retries/circuit-breaking/rate-limiting that get painful to hand-roll —
  Gateway Server MVC is the fallback then, not `webflux`. Rejected
  **Traefik-only routing** (host/path rules sending external traffic
  straight to `api`'s Service, bypassing `gateway` entirely): simplest
  option, but the backlog's stated purpose for gateway is "a single
  entrypoint for external traffic," implying future auth/aggregation/
  rate-limiting work belongs there, and ADR 0009 already committed `api` to
  ClusterIP-only (no Ingress) — `api` was never meant to be reachable
  directly through Traefik, so routing external traffic to it directly
  would contradict a decision already made.
- **Service discovery: Kubernetes Service DNS.** `api` gets its own
  namespace (`api`), mirroring the existing per-service pattern (`gateway`
  Application → `gateway` namespace, `whoami` → `whoami` namespace; ADR
  0009's per-service manifest/Application layout). In-cluster address:
  `http://api.api.svc.cluster.local` (Service named `api` in namespace
  `api`, port `80` → container port `8080`, same shape as
  `platform/kubernetes/gateway/service.yaml`). Rejected sharing the
  `gateway` namespace: breaks the one-namespace-per-service boundary
  already established and blurs blast radius between the two services'
  resources for no benefit at this scale.
- **Config mechanism: environment variable injected via the gateway
  Deployment manifest**, with an in-repo default in `application.yml`, e.g.
  `api.base-url: ${API_SERVICE_URL:http://api.api.svc.cluster.local}`.
  Rejected a ConfigMap: one more resource to create and sync for a single
  string value; a ConfigMap earns its keep once there are several related
  settings or something needs updating independent of a redeploy — today
  it's one URL, versioned in `platform` per ADR 0009 either way. Rejected
  hardcoding with no override: couples the deploy-time address to the
  compiled jar, when `platform`, not `services`, should own the runtime
  address per ADR 0009's boundary.

## Consequences

- `gateway` gains a real dependency on `api` being up at request time — no
  new infra, but a new failure mode (timeouts/5xx from `api` need to be
  handled in the forwarding controller, not just proxied raw).
- Open question for the backend engineer to verify during implementation:
  confirm `RestClient` (blocking) is sufficient for the forwarding
  controller without adding `spring-webflux`/`reactor-netty`; if gateway
  ever needs streaming or reactive proxying, that's a bigger stack decision
  to revisit deliberately, not a side effect of this ADR.
- `api`'s manifests follow the same shape as `gateway`'s
  (`platform/kubernetes/api/` + `argocd/apps/api.yaml`, ClusterIP-only per
  ADR 0009, its own namespace) — no Ingress for `api`, consistent with it
  never being externally reachable except through `gateway`.
- Adding a second backend later (or wanting retries/circuit-breaking) is the
  trigger to revisit Spring Cloud Gateway Server MVC; needing a reactive
  stack for unrelated reasons is the trigger to revisit `webflux` — neither
  is a reason to preemptively adopt either now.
