# 0027. Per-tenant API keys and rate limiting at the edge: satisfying ADR 0021's reintroduction condition via Traefik middleware

Status: Accepted

## Context

ADR 0021 removed `gateway` and, in the same decision, stated exactly what
would justify bringing an edge layer back: "if a real cross-cutting
concern (auth, rate-limiting across several backends) ever arrives,
reintroducing an edge service — or using Traefik middleware — is a
deliberate future decision, not a reason to keep an empty one now." That
condition was deliberately left open, not closed — ADR 0021 removed
`gateway` because it had never carried real traffic or a real function,
not because auth/rate-limiting would never matter.

Backlog #56 is that condition arriving for real. By the time this item
was implemented, `api` had three real public callers with no
authentication of any kind and no per-caller quota: `clinvar-viewer`
calling `/variants/lookup` from a browser (ADR 0021/#S1), `#53`'s
watchlist subscriber-facing endpoints, and `#45`'s workload-generator
producing continuous synthetic load. There was no way to tell one
caller's traffic from another's at the edge, and no way to stop a caller
(malicious or just buggy) from consuming the whole node's capacity.

This ADR records the decision this item made and proves it satisfies
ADR 0021's condition on its own terms, so the decision trail stays
intact — a short note per that condition's own request, not a full
redesign document.

## Decision

**Enforce auth and per-key rate limiting via Traefik middleware on api's
existing Ingress. Do not reintroduce `gateway` or any new service.**

ADR 0021 explicitly offered two paths ("reintroducing an edge service —
or using Traefik middleware"). This picks the second, for the same reason
ADR 0021 removed `gateway` in the first place: `gateway` carried exactly
one placeholder route and no real function of its own — a forwarder with
nothing to forward is not made worthwhile by giving it a job it never
had. An auth-checking, rate-limiting service built specifically to sit in
front of `api` today would be a new thing built to solve a problem
Traefik — the ingress controller this cluster already runs in front of
every public path — already solves natively, at the cost of a new image,
CI pipeline, namespace, and failure mode for zero functional gain over
the middleware path. Traefik middleware CRDs (`middlewares.traefik.io/
v1alpha1`) were confirmed already registered and usable on the real
cluster (chart `traefik` 41.0.2, image `v3.7.6`) before any manifest
assuming they existed was written.

Concretely (`platform#<PR>`, `kubernetes/api/middlewares.yaml`):

- **Auth mechanism: HTTP Basic auth, the AC's "or equivalent."** Vanilla
  Traefik (no Traefik Hub, no plugin) has no CRD-native "check this
  custom header against a set of values" middleware — the only ways to
  validate a caller-supplied credential without writing a new backing
  service are `basicAuth`/`digestAuth` (self-contained) or `forwardAuth`
  (delegates the check to an external service, which reintroduces
  exactly the "new service" this decision rejects). `basicAuth`, backed
  by a real Kubernetes Secret holding one `tenant:apr1-hash` htpasswd
  line per caller, is the API-key mechanism here: username is the
  tenant name, password is the tenant's key.
- **Per-key rate limiting**: Traefik's native `rateLimit` middleware,
  `sourceCriterion.requestHeaderName: Authorization` — each distinct
  tenant:key pair gets its own token bucket. 5 req/s average, burst 10,
  documented in `middlewares.yaml` against this project's actual traffic
  (workload-generator's peak is 0.5 req/s; clinvar-viewer is one manual
  browser tab), not derived from a real distribution this project
  doesn't have — same "simple v1 pick, stated as such" precedent ADR
  0020's alert thresholds already set.
- **CORS preflight, the real gotcha found live**: a browser's OPTIONS
  preflight for a cross-origin request carrying a custom `Authorization`
  header never carries credentials, by spec. Applying `basicAuth`
  unconditionally would reject every preflight with 401, breaking
  `clinvar-viewer` regardless of whether its real request carries a
  valid key. Fixed with a `headers` middleware (`api-cors`) placed first
  in the chain: Traefik answers a matching OPTIONS preflight directly
  from that middleware, before `api-key-auth` ever runs. Confirmed live,
  not assumed from docs.
- **Keys as real Kubernetes Secrets, provisioned the established way**:
  `bootstrap/create-stateful-secrets.sh` (platform#36's pattern) gained a
  new section generating `api-tenant-keys` (the htpasswd Secret Traefik
  reads) and each tenant's own consuming Secret
  (`workload-generator-api-key`, `clinvar-viewer-api-key`) — the same
  out-of-band, idempotent, never-committed-to-git mechanism every other
  credential in this cluster already uses, not a second competing one.

## What this does *not* claim

- **`clinvar-viewer`'s key is not a confidentiality boundary.** It is a
  static page with no backend of its own; whatever config.js ships to
  the browser is readable via view-source by anyone who loads the page.
  Stated plainly in three places (`services/clinvar-viewer/app.js`,
  `platform/kubernetes/clinvar-viewer/deployment.yaml`,
  `bootstrap/create-stateful-secrets.sh`) rather than glossed over: the
  key still does real, honest work — per-tenant attribution and rate
  limiting at the edge, this item's actual AC — it just isn't, and
  structurally cannot be, a secret an attacker is prevented from
  reading. A real confidentiality boundary for a browser-originated
  caller would need a backend-for-frontend proxying the request (a
  legitimate future edge-service reason of its own, not needed for this
  item's stated goal).
- **Per-key rate-limit rejections are visible on the shared `websecure`
  entrypoint, not yet a dedicated per-router label.** Traefik's
  `metrics.prometheus.addRoutersLabels` was flipped on
  (`argocd/apps/traefik.yaml`) so router-level attribution is now
  possible, but the alert rule and dashboard shipped with this item
  still query the entrypoint-wide counter (the one independently proven
  live during development) rather than the router-level one (schema-
  correct but not live-verified this session) — today api is the only
  rate-limited route, so in practice this is already api-specific; that
  stops being true the moment a second Ingress gets its own limit, at
  which point the queries should move to the router-level metric.
- **Per-key request-rate visibility comes from Loki access logs
  (`ClientUsername`), not a Prometheus label** — a deliberate choice, not
  an oversight: an unbounded per-tenant Prometheus label is a real
  cardinality risk Traefik itself avoids by design. `accessLog.enabled`
  was added to the real chart's schema-confirmed field
  (`argocd/apps/traefik.yaml`) but its live behaviour (the JSON log
  actually carrying `ClientUsername`, actually reaching Loki, the
  dashboard panel actually rendering data) was not independently
  re-verified against a populated Loki this session — see the platform
  PR description for the exact split.

## Consequences

- ADR 0021's reintroduction condition is satisfied via its own
  explicitly-offered second path. No new service, image, namespace, or
  ArgoCD Application was added to satisfy it.
- `api`'s Ingress gains a real new failure mode of its own: a
  misconfigured middleware chain can lock out all public traffic to
  every real caller at once (this was exercised carefully and reverted
  between tests during this item's own live verification — see the
  platform PR for the full record). This is the same category of
  tradeoff ADR 0021 already accepted when it gave `api` its own Ingress
  in the first place ("a new failure mode to own, but it replaces two it
  removes") — extended, not newly introduced, by this item.
- `workload-generator` now reaches `api` via the public Ingress hostname
  instead of in-cluster Service DNS, specifically so its synthetic
  traffic is subject to the same edge enforcement as everything else —
  a deliberate behavioural change from backlog #45's original design,
  recorded here rather than left as a silent diff between that item's
  stated intent and the code.
- If a second cross-cutting concern ever needs more than Traefik's native
  middleware set can express (e.g. a check that genuinely needs
  application logic — not just "a plugin doesn't exist for X"), that is
  the point at which ADR 0021's *first* offered path — a real edge
  service with an actual function — becomes the right call, not this
  one stretched further than it should go.
