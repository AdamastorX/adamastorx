# 0021. Simplification pass: remove `gateway` and `whoami`, ClinVar-only annotation, close M6

Status: Proposed

## Context

Every prior review of this project was additive — five repo-persona
reviews, an independent staff-engineer audit, three staff-level SRE/
platform/bioinformatics reviews — and each one found gaps and added
backlog. That was valuable, but nobody had been asked the opposite
question the owner explicitly set for this pass: for a personal
SRE/platform *portfolio* (no real users, no revenue), what should this
project **stop doing, remove, or never have built** because it doesn't
serve that goal? Sunk cost is not a reason to keep anything.

Four things were found that carry real, ongoing complexity while
returning little or nothing for that specific audience. Removing a whole
service, deleting the last public entrypoint, cutting a data domain, and
closing a reserved milestone are exactly the "significant, hard-to-reverse,
worth defending later" decisions ADRs exist for — hence this one, rather
than only backlog items.

Load-bearing facts (confirmed live, not assumed):

- **`gateway` has exactly one business route** — `GET /api/hello` →
  `api`'s `GET /hello` — a placeholder from M1 bring-up (ADR 0010). It was
  never wired to proxy any real traffic; `work-items` and
  `/variants/lookup` all reach `api` directly. `api` has no public
  Ingress, so `gateway`'s Ingress is the *only* public application path,
  and it exposes a stub. Zero real requests since last restart. It carries
  a full tax: its own Spring Boot module, CI build/scan/publish matrix
  entry, Kubernetes namespace/Deployment/Service, ArgoCD Application,
  Traefik Ingress, TLS certificate.
- **`whoami`** (`traefik/whoami`) was M1's end-to-end proof that Traefik +
  cert-manager issue and serve TLS. Real services now exist; that proof no
  longer needs a dedicated app, its own namespace, `ResourceQuota`,
  `LimitRange`, Ingress, certificate, and ArgoCD Application.
- **gnomAD enrichment was never built.** Its real footprint (~7.7GB, per
  `SESSION_STATE.md`) does not fit this single-node cluster, and it adds a
  *second* data source that introduces no operational signal ClinVar does
  not already provide. Backlog #24a already concedes deprioritising it is a
  valid outcome.
- **M6 (backlog #30)** reserves a real FASTQ/alignment pipeline on
  self-hosted MinIO + Kubernetes Jobs — a whole new object-storage/batch
  data plane. That is bioinformatics depth for a bio audience, not
  SRE/platform depth. The project's genuinely distinctive portfolio
  asset — the polyglot judgement call and data-provenance story — is
  already delivered by `clinvar-service`; M6 extends the "bio coat of
  paint," which is the failure mode #30 itself was meant to guard against.

## Decision

1. **Remove `gateway` entirely** and expose `api` directly. Delete the
   `services/gateway` module (and its CI matrix entries and
   `GatewayMetricsHistogramTest`), `platform/kubernetes/gateway/`, and
   `argocd/apps/gateway.yaml`. Give `api` its own Ingress + cert-manager
   certificate so a real service is the live Traefik+TLS+service path. This
   supersedes **ADR 0010** (gateway→api routing): the "single entrypoint
   for future auth/aggregation/rate-limiting" that ADR reasoned toward
   never materialised, and a two-method forwarder in front of one backend
   is not worth its own service, image, pipeline, and cert. If a real
   cross-cutting concern (auth, rate-limiting across several backends) ever
   arrives, reintroducing an edge service — or using Traefik middleware — is
   a deliberate future decision, not a reason to keep an empty one now.

2. **Remove `whoami`.** Delete `platform/kubernetes/whoami/` and
   `argocd/apps/whoami.yaml`. `api`'s new Ingress (decision 1) is the
   standing ingress+TLS proof.

3. **ClinVar-only annotation; drop gnomAD.** `clinvar-service`, the
   two-Postgres split (ADR 0019's load-bearing lesson), the release
   provenance story, and invalidation-on-write all **stay** — they are the
   project's most defensible portfolio content. gnomAD is cut from backlog
   #24's acceptance criteria, from ADR 0018's scope, and from
   `docs/data-sources.md`; backlog #24a is closed (its question is
   answered: no gnomAD).

4. **Close M6 (backlog #30).** Mark it won't-do with this reasoning rather
   than leaving it reserved. ADR 0018's and ADR 0019's forward references
   to #30 are annotated accordingly. `clinvar-service` remains the polyglot
   foothold; nothing commits to building on it into a batch/object-storage
   milestone.

This ADR does not itself delete any code or infrastructure. Each removal
is a separate, explicitly-confirmed decision the owner makes later, one at
a time, tracked as the Simplification backlog items (S1–S5).

## Consequences

- The public surface shrinks to exactly the services that do real work.
  `api` gains an Ingress (a new failure mode to own, but it replaces two
  it removes). ADR 0010 becomes `Superseded by 0021`.
- Backlog #21/#21a (SLO + histogram tables), #35 (per-namespace CPU
  limits), and any dashboard/runbook that enumerates `gateway` drop its
  rows in the same change that removes the service — reconciled via
  Simplification #S1, not left dangling.
- The annotation domain is single-source (ClinVar). The provenance and
  invalidation-on-write stories are unaffected; only the optional
  second-source breadth is gone.
- M6 is closed, not reserved. If a real batch/object-storage need ever
  appears from an SRE angle (not a bio one), it earns a fresh ADR then.
- The bioinformatics-depth enhancements that only serve a clinical-genomics
  audience (backlog #40 HGVS, #41 liftover) are cut alongside this (see
  Simplification #S5); the real correctness items (#38 bug, #39
  normalization) stay.
