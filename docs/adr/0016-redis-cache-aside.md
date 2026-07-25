# 0016. Redis cache-aside for `GET /work-items/{id}`: hand-rolled RedisTemplate, standalone chart, no PVC, api's namespace

Status: Accepted

## Context

services#5 (backlog #15): "Reduce load on PostgreSQL for hot-path reads —
*only if a concrete hot path actually needs it*." Redis is on the
approved stack (`.claude/PROJECT.md`), so the tool choice itself needs no
ADR; per `WORKFLOW.md`, what needs deciding is the pattern/topology while
adopting it — the same split ADR 0011/0012 already drew for Kafka/
Postgres. The issue was deliberately rewritten before this session picked
it up to require a written hypothesis *before* any cache code, and to
flag explicitly that `GET /work-items/{id}` — the only realistic
candidate read that exists in `api` today — may be a poor choice for
demonstrating invalidation, since `work_items` rows are immutable once
created (services#4/ADR 0012: `POST` creates, `GET`/`GET` list read,
nothing updates). This ADR is that hypothesis plus the implementation
decisions, written together because the honesty the issue asks for only
makes sense read against the actual design that followed from it.

## Hypothesis (written before any cache code)

- **Expected read volume/pattern.** This is a personal sandbox, not a
  service under real load — there is no organic hot path to point at
  honestly. The prediction being written down here to check later (the
  issue's actual ask) is modest: a handful of repeated `GET`s per work
  item per session (manual `curl`/demo traffic hitting the same id more
  than once), not sustained high-QPS traffic. The value of this issue
  isn't "prove Redis was needed" — the Purpose section is explicit that
  it wasn't measured as needed — it's "prove the hit/miss metric is real
  and the fail-open behaviour actually works," which doesn't require
  organic load to demonstrate.
- **Hit/miss as a metric, from day one.** `cache.gets{cache="work-items",
  result="hit"|"miss"|"error"}` (Micrometer counters, see Decision below)
  ship in the same PR as the cache logic, not after. A demo run's minimum
  bar to call the hypothesis checked: at least one `hit` after a `miss`
  for the same id, visible on `/actuator/prometheus`.
- **Staleness tolerance.** This is the honest part the issue asked to
  state plainly, regardless of which way it landed: `work_items` rows are
  immutable post-creation (no `PUT`/`PATCH` exists, ADR 0012 never added
  one), so a cached value can *never* diverge from PostgreSQL once
  written — staleness tolerance is effectively unbounded for this read.
  That is exactly why the issue flagged this candidate as weak for
  demonstrating *invalidation*: there is nothing to invalidate against,
  because nothing mutates. The TTL this ADR adds (Decision below) is a
  memory/key-count hygiene bound, not a correctness mechanism — stated
  explicitly so nobody mistakes it for the interesting kind of
  invalidation later.

## Is `GET /work-items/{id}` actually a good candidate? (the issue's honesty ask)

Landed on: **yes for what this issue's AC actually requires, no for
invalidation specifically — and that's fine, stated plainly rather than
picked around.**

- The AC's two hard requirements — an observable hit/miss metric, and
  *tested* fail-open behaviour on a Redis outage — are both entirely
  exercisable on an immutable read. Neither needs a write to invalidate
  against. This candidate proves both cleanly.
- What it cannot demonstrate is event-driven invalidation (evict-on-write,
  the genuinely interesting failure mode where a stale cache silently
  serves wrong data after a mutation) — because there is no mutation path
  for `work_items` to exercise it against. Any invalidation strategy here
  is necessarily time-based (TTL), not event-based.
- The alternative that *was* considered: `GET /work-items` (the unpaginated
  list). Every `POST` genuinely changes its contents, so caching it would
  give a real evict-on-write case to exercise. Rejected anyway — caching
  an unbounded, ever-growing "select *" is a different and weaker pattern
  than per-entity cache-aside (one global key, not keyed by entity id — not
  what the issue's own draft names, and not what a real service would
  actually do for a list endpoint without pagination first). Not
  building this now; noted here as the trigger if a future issue adds
  pagination and per-page caching becomes worth exploring.
- No update endpoint was added to `work_items` just to manufacture an
  invalidation demo. That would be building product surface backwards
  from a testing need, the opposite of `PROJECT.md`'s "no framework for a
  problem you don't have yet."
- Net: this PR ships a real, working cache-aside path with a real metric
  and a real, tested outage behaviour — genuinely useful evidence for the
  AC — while being explicit that it does not, and structurally cannot,
  prove invalidation-on-write. A future issue that gives `work_items` a
  mutable field (or a second, genuinely mutable entity) is the actual
  trigger to build and prove that half, not this one.

## Decision

- **Cache-aside, read path only — no write-through.** `WorkItemController`
  checks the cache first on `GET /work-items/{id}`; a miss reads
  PostgreSQL and then fills the cache. `POST /work-items` never writes to
  Redis. This is the textbook definition of the pattern the issue names,
  not a shortcut — a write-through variant was briefly considered and
  rejected as unnecessary complexity for what the AC actually asks for.
- **Hand-rolled `RedisTemplate`-based service, not Spring's declarative
  `@Cacheable`/`RedisCacheManager`.** Two concrete reasons, not a style
  preference:
  1. Boot's built-in cache-metrics binder
     (`CacheMeterBinderProvider`/`CacheMetricsRegistrar`) has no Redis
     support — it only auto-binds for Caffeine/EhCache2/Hazelcast/JCache.
     `@Cacheable` + `RedisCacheManager` alone would implement the caching
     but not the AC's "hit/miss ratio is an observable metric" — a custom
     Micrometer binder would still need writing, at which point the
     declarative layer adds indirection without saving the actual work.
  2. The AC's other hard requirement — a Redis outage fails the read
     *open* to PostgreSQL, not the request — needs a custom
     `CacheErrorHandler` bean with the declarative approach (the default
     `SimpleCacheErrorHandler` rethrows). A plain try/catch around two
     Redis calls is more direct to write, read, and test than reasoning
     about `@Cacheable`'s AOP proxy + a custom error handler bean
     interacting correctly, especially with a Testcontainers-based test
     that has to prove it (see Testing below).
  - `WorkItemCacheConfig` builds a typed `RedisTemplate<String, WorkItem>`
    (`StringRedisSerializer` keys, `JacksonJsonRedisSerializer` values on
    the shared Jackson 3 `JsonMapper` — the same Jackson stack already on
    the classpath for this app's REST responses, no new dependency) —
    same reasoning `WorkItemProducerConfig` already used to hand-build a
    typed `KafkaTemplate` instead of trusting Boot's untyped
    auto-configured one (ADR 0011).
  - `WorkItemCacheService.get`/`.put` wrap Redis calls in
    `try { ... } catch (DataAccessException ex)` — Spring Data Redis's
    common exception base for connection failures, timeouts, and
    serialization errors alike. A `get` failure returns `Optional.empty()`
    indistinguishable from a plain miss (the controller falls through to
    PostgreSQL either way); a `put` failure just logs and skips caching —
    never allowed to fail a request that already has its answer.
- **Metric shape: `cache.gets{cache="work-items", result="hit"|"miss"|
  "error"}` and `cache.puts{cache="work-items", result="error"}`,**
  Micrometer `Counter`s registered directly against `MeterRegistry`
  (exposed automatically on the existing `/actuator/prometheus`, ADR
  0014 — no new scrape config needed). Deliberately named/tagged to match
  Micrometer's own `CacheMeterBinder` convention even though hand-rolled
  (see above), so a future Grafana panel (backlog #20) built against the
  standard Spring cache-metrics shape needs no special-casing for this
  one hand-rolled cache. **`error` is its own `result` value, not folded
  into `miss`** — an outage-driven fallback isn't a real cache miss
  against a healthy cache, and lumping it into `miss` would quietly
  pollute the hit-ratio metric this ADR's own hypothesis is meant to be
  checked against.
- **No negative caching.** A not-found id is never written to Redis.
  Simpler, and there's no abuse vector to defend against here worth the
  complexity (ClusterIP-only, single in-cluster consumer, no external
  traffic ever reaches this — unlike a public API where cache-penetration
  from an enumeration attack would be a real concern).
- **TTL: 5 minutes** (`app.cache.work-items.ttl`, `application.yml`), a
  memory-hygiene bound only — see Hypothesis above for why this isn't a
  correctness mechanism for this particular read.
- **Fail-open needs to fail *fast*, not just eventually.** `application.yml`
  sets `spring.data.redis.connect-timeout` and `.timeout` to `500ms`
  (Lettuce's own defaults are far longer) — otherwise "fail open" would
  still mean the caller waits out a long timeout before PostgreSQL ever
  gets a chance to answer, which defeats the point of caching for latency
  in the first place.
- **Deployment: Bitnami `redis` Helm chart** via an ArgoCD Application
  (`argocd/apps/redis.yaml`), same inline-`valuesObject` pattern as every
  other chart Application here. Chart version 23.1.1 confirmed **not**
  `deprecated: true` in its `Chart.yaml` before pinning it (same check
  ADR 0014/0015 already established for Grafana/Loki/Tempo). Same
  `bitnamilegacy/redis` registry override ADR 0011/0012 already needed
  for Kafka/Postgres — re-verified specifically for this chart/tag
  against Docker Hub's registry API (`bitnami/redis:8.2.1-debian-12-r0`
  404s, `bitnamilegacy/redis:8.2.1-debian-12-r0` exists) rather than
  assumed from precedent; unlike Kafka/Postgres, this chart's *current*
  version already defaults to a tag that exists in the legacy registry,
  so no need to hunt for an older chart version.
  - **`architecture: standalone`, not the chart's own `replication`
    default (3 replicas).** One consumer, single-node dev cluster —
    replicating a cache nothing else reads from is pure overhead, and
    opting out of the multi-replica architecture entirely sidesteps the
    same class of trap Loki's `replication_factor` default hit
    (observability#3: a single-instance chart silently misconfigured for
    a mode it wasn't built for) rather than trying to tune a
    multi-replica architecture down to one node.
  - **No `PersistentVolumeClaim`.** The one deliberate break from
    Postgres's "durable state gets a real PVC" precedent (ADR 0012), and
    on purpose: cache-aside means PostgreSQL is the only source of truth,
    and this issue's own AC (Redis outage fails open) requires being
    comfortable with Redis losing all state at any time. A PVC here would
    work against the exact behaviour this deployment exists to
    demonstrate. Confirmed via `helm template` that
    `master.persistence.enabled: false` renders no PVC and backs `/data`
    with `emptyDir` instead. The chart's own default `redis.conf` still
    turns on AOF file persistence regardless — harmless, since it writes
    into that same `emptyDir` and doesn't survive a pod restart either;
    not worth fighting the chart default to disable it for a cache that's
    ephemeral by design either way.
  - **Auth: kept at the chart's default (`auth.enabled: true`,
    `auth.password` left unset, chart-generated Secret).** The real
    design choice the issue asked to make deliberately, not default
    without reasoning: Redis here has exactly one consumer (`api`), the
    same shape ADR 0012 reasoned through for Postgres (own-namespace
    exception, not Kafka/OTel's shared-no-credential treatment) — so that
    reasoning applies again, and it's what's followed here. Rejected
    disabling auth (Kafka's `PLAINTEXT` treatment, ADR 0011): that was
    justified there by *two* consumers across two namespaces with no
    credential-sharing problem to avoid in the first place. Redis having
    only one consumer removes that justification entirely — there's no
    cross-namespace Secret problem to dodge by going PLAINTEXT, so
    fighting the chart's own default auth for a "it's just a cache"
    argument isn't a strong enough reason on its own. "Cache data is less
    sensitive than Postgres data" is true but irrelevant to *this*
    decision — the namespace/credential shape follows from consumer
    topology, not data sensitivity, exactly as ADR 0012 reasoned it for
    Postgres.
  - **Deployed into `api`'s namespace, not its own** — direct consequence
    of the auth decision above: the chart's generated Secret must live in
    the same namespace as the Deployment reading it via `secretKeyRef`
    (can't cross namespaces), and there's no syncing tool on the approved
    stack to make that work otherwise (same conclusion, same reasoning,
    as ADR 0012).
  - **ClusterIP only**, `resourcesPreset: small` — same trust model and
    dev-cluster sizing as every other in-cluster dependency here.
- **Client library: Lettuce via `spring-boot-starter-data-redis`.**
  Checked the starter's own published POM before assuming Boot 4.1's
  modularisation would need a second artifact the way Kafka/Flyway did
  (ADR 0011/0012's recurring gotcha, `SESSION_STATE.md`) — it doesn't:
  the starter already declares `spring-boot-data-redis` (the split
  autoconfiguration module) as a direct compile dependency, and pulls in
  `lettuce-core`/`spring-data-redis` transitively. One dependency line is
  enough here, unlike Kafka/Flyway's two.
- **Testing: Testcontainers, a plain `GenericContainer`, not
  `@ServiceConnection`.** No official `org.testcontainers:testcontainers-redis`
  module exists (checked Maven Central directly — zero results), and
  `spring-boot-testcontainers` ships no
  `RedisContainerConnectionDetailsFactory` either (checked the jar's
  contents directly), unlike Postgres's built-in JDBC service-connection
  support this repo already relies on. The third-party
  `com.redis:testcontainers-redis` artifact would restore
  `@ServiceConnection` convenience but isn't worth a new dependency for
  one test class — `GenericContainer("redis:8.2-alpine")` +
  `@DynamicPropertySource` wiring `spring.data.redis.host`/`.port` is a
  few extra lines, no new dependency, same "explicit over magic"
  preference this repo already leans on (ADR 0014's scrape config).
  `WorkItemCacheIntegrationTest` proves both AC halves:
  1. A first `GET` records a `miss`, a second records a `hit` (the
     hypothesis's minimum bar, checked against a real metric read from
     `MeterRegistry`, not asserted from the implementation).
  2. **The Redis-outage test the AC requires explicitly**: after warming
     the cache, the test calls `redis.stop()` on the running Testcontainers
     container mid-test, then issues another `GET` for the same id and
     asserts it still returns `200` with the correct body — served from
     PostgreSQL, not failed — and that the `error` counter moved. This is
     the actual proof the "fail open, not fail the request" behaviour
     works, not just a description of intent.

## Consequences

- `api` gains a third external runtime dependency (after PostgreSQL,
  Kafka) — a Redis outage is now a new failure mode to reason about for
  `GET /work-items/{id}` specifically, though by design it degrades to
  "no worse than before this issue" (a PostgreSQL read) rather than a new
  way for the request to fail.
- The hit/miss metric only means something once real traffic exercises
  it — right now it will show whatever a demo/portfolio run against the
  real cluster produces, which is expected to be low-volume by the
  hypothesis above. That's the actual point: the metric now exists to be
  checked against reality, rather than assumed.
- Invalidation-on-write is explicitly *not* demonstrated by this issue,
  and structurally can't be by this read — flagged here as a known,
  reasoned gap rather than deferred silently. The trigger to build and
  prove it: a future issue that gives `work_items` (or a new entity) a
  genuinely mutable field.
- `platform` gains its first Redis Application and its second
  `standalone`-architecture single-instance chart deviation from a
  multi-replica default (after Loki's `replication_factor` fix,
  observability#3) — but this one avoids the trap by not opting into the
  multi-replica mode at all, rather than tuning one down.
- Rollout is deliberately split into two `platform` PRs, per
  `docs/runbooks/cross-repo-rollout.md`'s "a pure SHA bump and a new
  dependency's manifests can be separate PRs" guidance: `argocd/apps/redis.yaml`
  can merge and deploy independently of `api`'s code (Redis becomes
  available in-cluster, unused until `api` is updated); the
  `kubernetes/api/deployment.yaml` env-var change
  (`REDIS_HOST`/`REDIS_PASSWORD` via `secretKeyRef`) plus the image SHA
  bump can only happen once `services`' PR is merged and CI has published
  a real image SHA to bump to — not built speculatively against a SHA
  that doesn't exist yet.
