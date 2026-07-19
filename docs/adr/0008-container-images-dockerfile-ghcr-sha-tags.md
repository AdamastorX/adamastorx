# 0008. Container images: Dockerfile builds, GHCR, immutable SHA-only tags

Status: Accepted

## Context

platform#5 wants an image built and pushed to a registry on every merge to
`main`, tagged with the commit SHA; Trivy scanning (platform#6) hooks in
right after; the images feed the GitOps deploy (ADR 0003). Three coupled
decisions: how images get built, where they live and how they're tagged,
and where the workflow file lives — the boundary says "platform owns CI
pipeline definitions", but a GitHub Actions workflow can only run in the
repo whose events trigger it, i.e. with the code.

## Decision

- **Plain multi-stage Dockerfile.** One shared Dockerfile at the
  `services` repo root taking the module name as a build arg (the three
  images differ only in which jar they carry); runtime base is a
  digest-pinned `eclipse-temurin` JRE image. Rejected buildpacks
  (`spring-boot:build-image`): no Dockerfile to maintain, but slow builder
  pulls in CI and opaque layers that make Trivy findings hard to attribute
  to a line we control. Rejected Jib: daemonless and fast, but container
  concerns move into pom XML — a second place to look; a Dockerfile is the
  artifact every tool and every future engineer already understands.
- **GHCR: `ghcr.io/adamastorx/<service>`.** The project is already all-in
  on GitHub; `GITHUB_TOKEN` pushes with zero secret management; free for
  public images. Rejected Docker Hub (separate credentials, pull rate
  limits) and an in-cluster registry (a new stateful service to operate —
  exactly the un-boring thing).
- **Tags: the full commit SHA, nothing else.** Every merge to `main`
  builds and pushes all three images tagged with that SHA — no `latest`,
  no `main`, no semver. Immutable tags mean a manifest pins exactly what
  runs and rollback is "previous SHA". Rejected `latest` (a mutable
  pointer that invites drift and defeats GitOps pinning); rejected
  per-service change detection (three small builds cost minutes, and a
  uniform per-SHA image set keeps "what is deployable" trivially
  answerable — every main SHA has all three images).
- **The workflow file lives in `services`**
  (`.github/workflows/build-publish.yml`, push-to-`main` trigger; PR-time
  compile/test stays in the existing `ci` workflow per ADR 0006). This is
  mechanics, not an ownership transfer: platform keeps owning the pipeline
  *contract* — this ADR (build method, registry, naming, tag scheme, the
  Trivy insertion point) — and the YAML in `services` is its
  implementation, exactly as `ci.yml` already is under ADR 0006.

## Consequences

- Trivy (platform#6) slots into this workflow: scan the built image, gate
  the push. The digest-pinned base makes scan results reproducible; base
  bumps are visible PRs.
- Humans can't `docker pull <service>:latest`; you look the SHA up.
  Accepted — the cluster, not humans, is the consumer.
- Docs-only merges to `main` still build and push. Accepted cost for the
  invariant that every main SHA is fully deployable.
- Two independent revisit triggers: registry/auth if images must go
  private or the project leaves GitHub; build method if the shared
  Dockerfile grows per-service conditionals.
