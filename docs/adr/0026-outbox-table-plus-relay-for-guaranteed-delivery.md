# 0026. Outbox-table-plus-relay for guaranteed delivery: watchlist-service's design, and #16's deferred decision made for real

Status: Accepted

## Context

Backlog #16 named a real, deliberately deferred gap: `api` persists a
`work_items` row to PostgreSQL, then calls `KafkaTemplate.send()` as two
independent operations (ADR 0012's own stated consequence, not an
oversight). A publish failure after a committed save silently drops the
Kafka side — a broker hiccup, not a code bug, is enough to trigger it.
#16's AC asked for a design decision between an outbox-table-plus-relay
approach and an idempotent-consumer-plus-retry approach, with the rejected
alternative recorded — but nothing forced that decision to be made for
real: `work_items` could tolerate the loss (nothing downstream depended on
a specific publish arriving), so the gap sat open, correctly deprioritised
(P2), for several milestones.

Backlog #53 (`watchlist-service`) is the item that finally makes the
decision matter. A subscriber registers interest in a ClinVar variant or
gene; when `clinvar-service` publishes `clinvar.ingestion.completed`
naming a changed variant, every matching subscriber must be notified
**exactly once, eventually, even across a pod restart**. Unlike
`work_items`, a missed or duplicated notification here is a silently wrong
answer to a real user, not a tolerable gap — and the AC names the actual
proof required: a deliberately-induced crash between "event consumed" and
"notification sent" must not lose the notification, verified live.

## Decision

**Outbox-table-plus-relay**, for both `watchlist-service`'s new delivery
problem and, retrofitted, `api`'s original `work_items` gap.

### The mechanism (watchlist-service)

1. `ClinVarIngestionListener` (a second, independent Kafka consumer group
   on `clinvar.ingestion.completed` — the topic's first and only other
   consumer is `api`'s Redis cache-invalidation listener, ADR 0019, and
   the two share nothing) resolves every subscription matching a changed
   variant and inserts one `PENDING` row per match into a `deliveries`
   table (`services/watchlist-service`'s V2 migration), all in one
   transaction. **The Kafka offset is only acknowledged after that
   transaction commits.** This is the entire "event consumed" checkpoint.
2. `NotificationRelay` is a fully independent `@Scheduled` poll loop —
   not triggered by, not blocked on, the Kafka listener — that reads
   `PENDING` rows and actually calls ntfy, marking each `SENT` on success.
3. **Idempotency**: a `UNIQUE (subscription_id, release_id, variant_key)`
   constraint on `deliveries`, inserted with `ON CONFLICT DO NOTHING`. A
   real Kafka redelivery of the same message (a rebalance, a manual
   offset reset, or exactly the crash-before-ack window this design
   exists to close) re-resolves the same matches and no-ops on the
   already-inserted rows — proven by `DeliveryIdempotencyIntegrationTest`,
   which publishes the identical event twice against a real embedded
   Kafka broker and asserts a real fake-ntfy HTTP server receives exactly
   one POST.
4. **Dead-lettering**: a row that fails `app.delivery.max-attempts` times
   moves to `DEAD_LETTERED` and stops being polled — one permanently
   broken subscriber's target never blocks any other subscriber's
   fan-out, because every subscriber's delivery is its own row, processed
   independently. Proven by `NotificationRelayDeadLetterIntegrationTest`.

**Why the crash-mid-delivery AC holds**: the row survives a crash in
Postgres regardless of which side of the split dies. A crash after Kafka
offset acknowledgment but before the relay's next tick leaves the row
`PENDING` — the next tick (on this pod or its replacement after a
restart) finds it and completes delivery, with no dependency on a fresh
Kafka message ever arriving again. See the services repo's PR description
for what was proven live on the real cluster versus what still needs a
human check.

**Stated residual gap**: a crash between a row being claimed (`PENDING` →
`SENDING`) and the ntfy call actually completing leaves that one row
stuck `SENDING` forever — nothing currently reclaims it. A stuck-`SENDING`
reaper is real, valuable follow-on work, not built here; the AC's own
crash test targets the much larger and more likely window (kill between
Kafka-ack and the relay's next tick even starting), which this design
closes completely. Recorded in `NotificationRelay`'s own javadoc, not
silently assumed away.

### Rejected alternative: idempotent-consumer-plus-retry

Deliver inline inside the Kafka listener (call ntfy directly), track a
dedupe key in Postgres, and rely on not acknowledging until delivery
succeeds — Kafka's own redelivery-on-crash plus the dedupe check would, in
principle, give the same guarantee.

Rejected for watchlist-service specifically because it does not support
the AC's other hard requirement, per-subscriber dead-lettering without
blocking the fan-out: a single Kafka message's listener invocation would
have to fan out to every matching subscriber inline, and one subscriber's
ntfy target being permanently down would either block the whole
invocation (and therefore the offset commit, and therefore every other
subscriber's delivery for that message) or need its own separate
tracking table anyway — at which point it has quietly become the outbox
approach with extra steps. The outbox table's rows are already the unit
of per-subscriber state the dead-lettering AC needs; building that table
and then still doing inline delivery would be strictly more code for a
worse guarantee.

### Addendum — found live, not in a unit test

The crash-mid-delivery proof this ADR exists for was run for real against
the live cluster (kill the pod, confirm the notification survives — see
the services PR for the full transcript), and it caught something a
written-but-mocked unit test would not have: `NotificationRelay`'s first
implementation put `@Transactional` on private helper methods
(`claim()`/`markSent()`/etc.) that `attemptDelivery` called as plain
internal method calls on `this`. That compiles clean and looks correct,
but it's Spring AOP self-invocation — calling a method on the same bean
bypasses the CGLIB proxy `@Transactional` is implemented through entirely,
so no transaction was ever actually opened. It surfaced as
`jakarta.persistence.TransactionRequiredException` the instant a real pod
restart exercised the relay's very first tick against a real Postgres.
The fix (`TransactionTemplate`, a programmatic API with no proxy to
bypass) was verified by re-running the exact same live crash sequence a
second time, not assumed correct because it compiled — the delivery row
that survived the first crash was still sitting `PENDING` in Postgres and
became the live test case for the fix. The identical latent bug existed
in `api`'s own `OutboxRelay` (same shape, same ADR) and was fixed there
proactively once recognized, before it could fail live separately. This
is exactly the class of bug this project's "verify against real, live
behavior" discipline exists to catch — recorded here rather than only in
a commit message.

### Retrofit: api's `work_items` gap (closing #16 for real)

The same split is applied, minimally, to `api`'s original gap:
`WorkItemOutboxService` now persists the `work_items` row and an
`outbox_events` row (topic, key, JSON payload) in one transaction;
`OutboxRelay` is the independent poll loop that actually publishes to
Kafka and marks the row `PUBLISHED`. `WorkItemController` no longer calls
`KafkaTemplate.send()` directly at all — see that class's updated javadoc.

`WorkItemOutboxFailureIntegrationTest` is #16's own literal AC: with
`spring.kafka.bootstrap-servers` pointed at an address nothing listens on
(so every publish attempt genuinely fails, repeatedly), the test proves
the `work_items` row and its `outbox_events` row both survive — durably,
in Postgres — rather than either being rolled back or silently dropped,
which is exactly what the old direct-publish code could not guarantee.

`api`'s relay does not need per-recipient dead-lettering (`work_items` has
one publish target, not N subscribers), so its `OutboxEventJpaRepository`
skips the claim-then-act two-phase `deliveries` needs and instead does a
plain "mark published only if still `PENDING`" update — a rare double
publish on a relay-tick/pod race is accepted here (work-items' consumer
already tolerated at-least-once before this change; nothing about this
retrofit makes that weaker), unlike watchlist-service's stricter
per-subscriber dedupe requirement.

## Consequences

- `services/api` gains its first background poll loop (`OutboxRelay`,
  `@Scheduled`) and a new table (`outbox_events`, V2 migration) — a small,
  bounded addition to close a gap ADR 0012 named on day one rather than a
  redesign; `WorkItemController`'s HTTP contract (`202`, same `WorkItem`
  response shape) is unchanged.
- `services/watchlist-service` is a new component whose entire delivery
  guarantee rests on this pattern — see its own README for the schema and
  metric surface.
- **Known, stated gap carried over from `services/watchlist-service`'s own
  README**: subscription matching only resolves `variantKey`, not
  `geneSymbol` — no component in this project extracts or indexes a gene
  symbol from ClinVar's VCF `GENEINFO` field today (confirmed against
  `clinvar-service/app/schemas.py` and `api`'s `VariantAnnotation.java`
  before this ADR was written, not assumed). `gene_symbol` is schema-ready
  in `subscriptions` but unresolved against real events — a real
  prerequisite change to `clinvar-service`'s own ingestion pipeline, out
  of scope here per ADR 0021's "don't build ahead of need" discipline.
- ADR 0012's own "explicitly not addressed, flagged for later" consequence
  (dual-write consistency between the Postgres save and the Kafka
  publish) is now closed — see that ADR's updated Consequences section.
- Backlog #16 is closed by this ADR plus the services PR it accompanies;
  backlog #53 depends on it and is otherwise built out in full (subject to
  the services/platform PRs' own stated live-verification status).
