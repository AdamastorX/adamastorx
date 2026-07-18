# 0006. Per-repo CI workflows with a single required `ci` check

Status: Accepted

## Context

platform#4 wants every PR in `platform` and `services` to get automated
build/test/lint feedback, with a failing check blocking merge. Neither repo
has application code (`services` is empty until M2; `platform` is Terraform,
ArgoCD Applications, k8s manifests, one shell script), and later issues
(platform#5 image build, platform#6 Trivy, M2 Spring Boot) will add jobs.
The shape decisions — not the tool picks — are what future-us will ask
about.

## Decision

- **Self-contained `.github/workflows/ci.yml` per repo.** Rejected: one
  reusable workflow in `adamastorx` called cross-repo — the two repos share
  zero jobs (HCL/manifests vs. future Java), so the abstraction would exist
  before any duplication does, and cross-repo `uses:` adds ref-pinning
  ceremony. Revisit only when a third repo needs an identical job.
- **One stable required check named `ci`.** Each workflow ends in an
  aggregator job `ci` that fails unless every real job succeeded; branch
  protection on `main` requires exactly that one context (strict — branch
  up to date). #5/#6/M2 add or rename jobs without ever touching branch
  protection. Rejected: requiring individual job names (protection churn on
  every job change); path-filtered jobs (a skipped required check blocks
  merge forever).
- **CI validates only what exists.** `platform`: `terraform fmt`/`validate`,
  kubeconform over all manifests (CRD schemas from the datreeio
  CRDs-catalog for cert-manager/Argo kinds), shellcheck. Rejected:
  `kubectl --dry-run=server` (needs the live home cluster reachable from a
  GitHub runner), yamllint (style noise; kubeconform already fails on
  unparseable YAML), helm-template-rendering the ArgoCD Helm apps
  (re-implements ArgoCD's render and drifts from it).
- **`services` gets an honest placeholder**: a single trivially-green `ci`
  job stating there is nothing to build until M2, which replaces the job
  body but keeps the `ci` name. Rejected: no workflow (violates the
  acceptance criteria); invented "structural checks" over READMEs (fake
  signal).
- **`adamastorx` gets no CI.** Docs plus one manually-run bootstrap script
  break nothing when wrong. Add it when the repo grows something executable
  that CI could actually catch.

## Consequences

- The `ci` context name is a contract: every future workflow revision in
  these repos must keep a job with that exact name, or merges silently
  stop being gated the way we think they are.
- Merge on green `ci` still proves nothing about runtime behaviour in
  `platform` — ArgoCD applying `main` remains the real test (ADR 0003);
  CI only catches syntax/schema/format breakage before review.
- The services placeholder means a green check on `services` PRs carries
  no information until M2 replaces it. Accepted as the honest reading of
  "a workflow runs on PR" while there is nothing to run.
