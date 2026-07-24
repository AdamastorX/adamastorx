# Session state (agent handoff notes)

Working notes for picking up where the last Claude Code session left off.
Not a design doc, not an ADR — a scratch log of in-flight work, open
threads, and things the next session shouldn't have to re-discover the
hard way. Prune/rewrite freely as work completes; this file describes
*current* state, not history (git history is the record of the past).

Last updated: 2026-07-24.

## Where things stand

M2 Distributed Application: services#1 (gateway), services#2 (API),
services#3 (Kafka, ADR 0011), and services#4 (PostgreSQL, ADR 0012) are
all done and closed — both proven end to end against the **real**
cluster, not just unit tests. **services#5 (Redis) is the next open
item.** Nothing started on it yet.

## Recurring gotcha worth knowing before touching this stack again

**Boot 4.1 modularized its autoconfiguration**: the client library
(`spring-kafka`, `flyway-core`, classic Jackson 2) and the
`FooAutoConfiguration` classes that actually wire it into a Spring
context now live in *separate* artifacts (`spring-boot-kafka`,
`spring-boot-flyway`, `jackson-databind` needing `spring-boot-webmvc`'s
replacement). Adding the client library alone compiles fine and then
silently doesn't work at runtime (no error — Flyway just never ran, the
app booted straight into "relation work_items does not exist" the first
time this bit). Hit this three separate times across services#3 and
services#4. If a future integration (Redis, anything else) compiles
clean but a Boot feature just isn't activating, check for a matching
`spring-boot-<name>` artifact before assuming the library itself is
broken.

Also: **major-version library bumps rename Maven artifacts without
renaming Java packages.** Testcontainers 2.x (which Boot 4.1 pins)
renamed `org.testcontainers:postgresql`/`junit-jupiter` to
`testcontainers-postgresql`/`testcontainers-junit-jupiter` — the classes
(`org.testcontainers.containers.PostgreSQLContainer`, etc.) didn't move.
Verify actual current artifact coordinates by compiling, not from
memory/old docs — this and the Jackson 2/3 split both looked "obviously
right" from familiarity and were wrong.

## Cluster access (this machine)

k3s kubeconfig at `~/.kube/config`. `kubectl` here does **not** default
to it on its own — always run with `KUBECONFIG` set explicitly:
```
export KUBECONFIG=~/.kube/config
```
Not persisted in `~/.bashrc` (blocked by the permission classifier) —
set it per session.

## ArgoCD stuck-operation gremlin (if it recurs)

An `Application`'s `.operation` field (the in-flight sync request) can
get stuck holding a **stale** values snapshot from an earlier commit and
keep re-applying it on retry, ignoring that `.spec.source` has since
changed. Refresh annotations and restarting `argocd-repo-server`/
`argocd-application-controller` don't clear this. What works:
```
kubectl patch application <name> -n argocd --type merge -p '{"operation":null}'
```
Check `kubectl get application <name> -n argocd -o jsonpath='{.operation}'`
before assuming a "keeps reapplying the wrong thing" symptom is a
caching/chart problem — it might just be a frozen operation.

## Namespace-per-component isn't absolute

Established pattern: each service/infra component gets its own
namespace (gateway, api, workers, kafka). PostgreSQL broke that pattern
deliberately (ADR 0012) — it lives in `api`'s namespace, not its own,
because `secretKeyRef` can't cross namespaces and Postgres has exactly
one consumer here (unlike Kafka's two, which also sidesteps the whole
problem via PLAINTEXT/no-auth). If Redis also ends up needing
credentials and has a single consumer, the same reasoning likely
applies — don't assume it needs its own namespace by default.

## Where to look next

- services#5 (Redis) is the next milestone item — same shape of
  decisions likely needed as Postgres: client library choice (Lettuce is
  Boot's default and already pulled in by `spring-boot-starter-data-redis`,
  no real alternative worth considering here), deployment (Bitnami
  `redis` chart following the same pattern), and a namespace call using
  the reasoning above.
- After that, M2 is complete and M3 (Observability) starts — see
  `docs/roadmap/milestones.md`.
