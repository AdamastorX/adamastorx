# 0009. Service deployment: manifests in platform, manual SHA-bump PR, raw manifests

Status: Accepted

## Context

Gateway/API/workers must deploy "via the M1 pipeline" (services#1 AC),
meaning ArgoCD app-of-apps over the `platform` repo (ADR 0003, sole GitOps
entrypoint). Needed: where the services' k8s manifests live, how a freshly
pushed image SHA (ADR 0008) reaches the cluster, and Helm chart vs. raw
manifests.

## Decision

- **Manifests live in `platform`** — `kubernetes/<service>/` plus one
  Application each in `argocd/apps/`, same pattern as `whoami`. Rejected:
  manifests in `services` with ArgoCD watching a second repo — that splits
  the "one place tells the cluster what runs" property ADR 0003 bought,
  and blurs the boundary: platform owns GitOps delivery, services owns the
  code that becomes images. The image at a SHA is the interface between
  the two repos.
- **A new image SHA reaches the cluster via a manual bump PR** to
  `platform` (edit the image tag, review, merge, ArgoCD syncs). Rejected:
  ArgoCD Image Updater — a new tool watching registries and writing to Git
  (plus write-back credentials) to save a one-line PR. Rejected: CI in
  `services` opening cross-repo bump PRs — cross-repo tokens, and services
  automation writing into platform crosses the ownership boundary. The
  friction is deliberate: every deploy is a reviewed, revertible commit.
  Revisit trigger: when bump PRs are demonstrably rote toil (several per
  week), automate the PR *creation* first — still human-merged — before
  ever considering Image Updater.
- **Raw manifests per service, no Helm chart.** The three services are not
  clones: gateway has an Ingress (TLS via `adamastorx-ca`, ADR 0004), api
  is ClusterIP-only, workers has no Service at all — a shared chart would
  spend its life in `{{ if }}` branches. Rejected: per-service charts
  (templating with exactly one values consumer is ceremony); one shared
  chart now (abstraction before duplication has demonstrated drift — ADR
  0006's own rule). Revisit trigger: the same cross-cutting edit (OTel
  env, probes, resource defaults) hand-repeated across all services more
  than a couple of times.

## Consequences

- Shipping a code change is two PRs: merge in `services` (builds and
  pushes images), bump PR in `platform` (deploys). Slower than
  push-to-deploy; the audit trail and the boundary are the point.
- Runtime configuration (replicas, resources, env) is versioned in
  `platform`, separate from application code — environment changes and
  code changes never share a diff.
- New service manifests get kubeconform validation in platform CI (ADR
  0006) for free, and appear/disappear with their Application file per ADR
  0003's prune semantics.
