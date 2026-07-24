# Session state (agent handoff notes)

Working notes for picking up where the last Claude Code session left off.
Not a design doc, not an ADR — a scratch log of in-flight work, open
threads, and things the next session shouldn't have to re-discover the
hard way. Prune/rewrite freely as work completes; this file describes
*current* state, not history (git history is the record of the past).

Last updated: 2026-07-24.

## What's done (services#3: Kafka messaging, ADR 0011) — AC fully met

- `services`: `api` (Kafka producer) + `workers` (new module, consumer)
  merged to main. Full path proven end to end against the **real**
  cluster, not just the embedded-Kafka unit tests: `POST /work-items` on
  `api` → consumed and logged by `workers`.
- `platform`: `workers` deployed (own ArgoCD Application, no k8s
  `Service` per ADR 0011), `api` wired with `KAFKA_BOOTSTRAP_SERVERS`,
  broker's internal-topic replication factor fixed for the single-broker
  cluster.
- `adamastorx`: ADR 0011 corrected (ack mode — see bugs below).
- **Consumer-group rebalance across replicas — captured** (platform
  #17/#18): scaled `workers` to 3 against the real cluster; each replica
  picked up exactly one of `work-items`' 3 partitions:
  ```
  Finished assignment for group at generation 6:
    {consumer-1=Assignment(partitions=[work-items-2]),
     consumer-2=Assignment(partitions=[work-items-1]),
     consumer-3=Assignment(partitions=[work-items-0])}
  ```
  Reverted back to 1 replica afterwards (steady state for this small dev
  cluster). services#3's AC ("a message produced by API is consumed by a
  worker; consumer group behaviour documented") is now fully satisfied —
  **the GitHub issue itself is still open and worth closing** next time
  someone's in there.

Three real bugs were found and fixed along the way (not hypothetical —
each one broke something concrete):

1. **Boot 4.1 / Jackson 2 vs 3** — `spring-kafka`'s `JsonSerializer`/
   `JsonDeserializer` need classic Jackson 2
   (`com.fasterxml.jackson.core:jackson-databind`), which Boot 4.1's
   default `spring-boot-starter-jackson` (Jackson 3,
   `tools.jackson.core`) doesn't provide. Fixed: declared explicitly in
   `api`/`workers` poms. Compile-time failure, easy to hit again if a
   new module adds `spring-kafka` without copying this.
2. **`AckMode.RECORD` + manual `Acknowledgment.acknowledge()`** — `RECORD`
   is an automatic-commit mode; it doesn't support an explicit
   `acknowledge()` call from `@KafkaListener`. Every message was
   "failing", retrying, and landing on the DLT. Fixed to
   `AckMode.MANUAL_IMMEDIATE` in `workers`' `WorkItemConsumerConfig` +
   corrected in ADR 0011's text (the ADR itself had the wrong enum name).
3. **Kafka single-broker internal-topic RF (the big one)** —
   `offsets.topic.replication.factor` (and the transaction-log
   equivalents) default to 3 regardless of actual broker count. With one
   broker, `__consumer_offsets` could never finish auto-creating, so
   every consumer group's `FIND_COORDINATOR` timed out and no
   `@KafkaListener` could ever join a group. Fix went through two
   iterations:
   - First attempt (platform PR #15) used the Bitnami kafka chart's
     `config:` values key, which **replaces** the chart's entire
     generated `server.properties` instead of merging into it (learned
     the hard way, by crash-looping the broker: `kafka-storage.sh format`
     died with `Missing required configuration "process.roles"`).
   - Corrected (platform PR #16): use `overrideConfiguration:` instead,
     which merges on top of the chart-generated base. This is the
     chart-specific gotcha to remember if anyone touches
     `argocd/apps/kafka.yaml` again — `config`/`controller.config` is an
     all-or-nothing replacement, `overrideConfiguration`/
     `controller.overrideConfiguration` is an additive merge.

Root-cause debugging path for #3 (useful if something similar recurs):
temporarily set `BITNAMI_DEBUG=true` directly on the live `StatefulSet`
(`kubectl set env statefulset/kafka-controller -n kafka BITNAMI_DEBUG=true`)
to defeat the Bitnami image's silent `debug_execute` wrapper, which
otherwise swallows the real command stderr on failure — `kubectl logs
--previous` was showing nothing but "Formatting storage directories..."
with no error before that.

## Known gremlin: ArgoCD stuck-operation cache

While fixing #3, an ArgoCD `Application`'s `.operation` field (the
in-flight sync request) got stuck holding a **stale** values snapshot
from an earlier commit (with the broken `config:` key) and kept
re-applying it on every retry, ignoring that `.spec.source` had since
been corrected. Neither `argocd.argoproj.io/refresh: hard` annotations,
restarting `argocd-repo-server`, nor restarting
`argocd-application-controller` cleared it. What worked:

```
kubectl patch application <name> -n argocd --type merge -p '{"operation":null}'
```

If an Application ever seems to be "reapplying the wrong thing no matter
what", check `kubectl get application <name> -n argocd -o
jsonpath='{.operation}'` before assuming it's a caching/chart problem —
it might just be a stuck operation with its own frozen copy of the sync
source.

## In progress / left open

- **Live cluster drift not yet reconciled through git**:
  - `work-items` topic currently has 3 partitions because it was fixed
    **manually** (`kafka-topics.sh --alter --topic work-items
    --partitions 3`) after the chart's provisioning Job lost a race
    against `api`/`workers`' own `allow.auto.create.topics=true`
    auto-creating it with 1 partition first. This isn't tracked in git —
    it'll silently regress to 1 partition if the broker ever gets
    reformatted again (pod recreation on an `emptyDir`, no persistence,
    ADR-accepted trade) unless the race itself gets fixed.
  - **Not yet done**: add `auto.create.topics.enable: false` to
    `argocd/apps/kafka.yaml`'s `overrideConfiguration` in `platform`, so
    only the provisioning Job (which sets the correct 3
    partitions/RF 1) can ever create `work-items` — closes the race
    permanently instead of relying on a manual fix that doesn't survive
    a broker restart.
- **Dangling doc reference**: `platform/argocd/apps/kafka.yaml`'s header
  comment says "Config rationale: ../README.md#kafka" — that section
  doesn't exist in `platform/README.md` (which currently has no
  per-component sections at all). Low priority, but worth fixing next
  time that file is touched.

## Cluster access (this machine)

k3s kubeconfig copied to `~/.kube/config` (owned by the normal user, not
root-only `/etc/rancher/k3s/k3s.yaml`). `kubectl` here does **not**
default to `~/.kube/config` on its own (something on this box makes it
fall back to the root-owned path) — always run with `KUBECONFIG` set
explicitly:
```
export KUBECONFIG=~/.kube/config
```
This export isn't persisted in `~/.bashrc` (that edit was blocked by the
permission classifier) — set it per session.

## Where to look next

- Close `services` issue #3 (see above — its AC is met, the issue just
  hasn't been closed yet).
- `services` issues #4 (PostgreSQL) and #5 (Redis) are the next
  milestone items (see `docs/roadmap/backlog.md`).
