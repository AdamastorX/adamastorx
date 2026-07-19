# 0007. Services build: Maven multi-module reactor, Java 25, Spring Boot 4.x

Status: Accepted

## Context

M2 starts with services#1/#2: Spring Boot gateway and API services (workers
follow) in the existing `services` repo, which today holds only placeholder
dirs (`gateway/`, `api/`, `workers/`, `shared/`). Needed: build tool, repo
layout, whether `shared/` becomes a real module, and the Java/Spring Boot
versions. Constraint from ADR 0006: one required `ci` check, no
path-filtered required jobs — every PR builds the whole repo.

## Decision

- **Maven, wrapper committed (`./mvnw`).** Rejected Gradle: faster
  incremental builds and a richer DSL, but that DSL is a programmable
  surface inviting clever build logic, and build speed is irrelevant at
  three small services. Maven's rigid lifecycle is the boring default the
  Spring ecosystem documents first.
- **Single multi-module reactor.** Root aggregator `pom.xml` (parent of all
  modules; Spring Boot version, Java version, plugin versions pinned
  exactly once) with `gateway`, `api`, `workers` modules. `./mvnw verify`
  at the root builds and tests everything — exactly the shape ADR 0006's
  no-path-filter rule wants CI to have. Rejected: independent per-service
  builds in the one repo — three places to pin the Boot version, drift
  guaranteed, and it buys nothing until a service needs divergent versions
  (which would be a repo-split conversation, not a layout tweak).
- **No `shared/` module yet.** The dir stays a placeholder. Extract a
  module only when the same non-trivial code exists in ≥2 services and its
  duplication has actually caused a bug or repeated fix — not
  speculatively for DTOs. Adding it later is one ordinary module in the
  same reactor, no restructuring.
- **Java 25 (current LTS, GA 2025-09), Spring Boot 4.1 line.** Verified
  2026-07: Spring Boot 3.5 reached OSS EOL 2026-06-30, so 4.x is the only
  OSS-supported choice; 4.1 is the current GA line (OSS support into
  mid-2027) vs. 4.0's end-2026. Engineer pins the exact latest 4.1.x patch
  at implementation time.

## Consequences

- Every services PR compiles and tests all modules. Accepted cost — small
  services, cached dependencies; it also keeps the single `ci` check
  honest.
- One Boot/Java version across all services, by construction. A service
  that genuinely needs to diverge is a signal to re-examine the repo
  boundary, not to fork version pins inside the reactor.
- Extracting `shared/` later needs no ADR; abandoning the single reactor
  for per-service builds would.
