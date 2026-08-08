# 0033. Event contracts: shared JSON Schema plus CI validation, not a schema registry

Status: Accepted

## Context

Every event on this project is unversioned JSON, and producer/consumer
shapes have already drifted independently across the Java↔Python
boundary at least once, silently: backlog #80's own implementation
found `news.article.published` has no `summary`/`description` field,
contradicting what its own AC text assumed — found by reading the
merged producer code directly, the exact class of failure contract
testing exists to catch before a human has to notice it by hand. Five
topics now span two languages (`stock.price.tick`,
`news.article.published`, `news.sentiment.scored`,
`clinvar.ingestion.completed`, `work-items`), and the drift surface
grows with every new topic — the same "growing surface, no mechanical
check" shape backlog #97 already found and fixed for this project's
own documentation.

## Decision

**Shared, versioned JSON Schema files (`services/schemas/*.schema.json`,
Draft 2020-12) plus a CI job that validates a real golden example
against each schema and a real, deliberately-broken example against
the same schema — the "lightest" option this item's own AC named.**

Each schema is built from the real producer's own current code, not
from the AC text or an assumed shape — every field, type, and enum
value in each of the five schemas shipped with this decision was
confirmed against the actual producer record/dataclass (`StockPriceTick.java`,
`ArticlePublishedEvent.java`, `events.py`'s `SentimentScoredEvent`,
`kafka_producer.py`'s `IngestionCompletedEvent`, `WorkItem.java`)
before being written, not inferred from documentation. One real,
already-known ambiguity is reflected honestly rather than resolved by
guessing: `news.article.published`'s `publishedAt` (and its pass-through
echo, `news.sentiment.scored`'s `articlePublishedAt`) accepts either a
JSON number or a string, because `sentiment-analyzer/app/events.py`'s
own docstring already states this encoding was never independently
re-verified against a live producer — the schema does not manufacture
a false certainty this project doesn't actually have.

**Rejected: Confluent Schema Registry.** Requires a new, always-on
runtime component (the registry itself) this single-node cluster would
need to operate, back up, and keep available for every producer/consumer
to even start — real, permanent operational weight for a drift-detection
problem a CI-time check answers just as well, the same "don't operate a
new component to answer a question a simpler mechanism already answers"
reasoning ADR 0014 (Mimir vs. a retention config value) and ADR 0032
(Strimzi vs. persistence) already applied to this project's other
tooling decisions.

**Rejected: Apicurio Registry.** Same operational-weight objection as
Confluent Schema Registry — a real, standalone service, not a CI-time
check — plus it solves a broader problem (schema evolution compatibility
rules enforced at publish time, multi-format support) this project does
not have yet: nothing here needs Avro/Protobuf, and compatibility-rule
enforcement at the moment of publish is a real capability gap this
decision leaves open, not silently claimed as covered.

## Consequences

- `services/schemas/` is the new, real source of truth for each covered
  topic's wire shape — a schema and its two example fixtures are the
  literal proof a reader can run, not prose describing intent.
- **Real, stated gap, not glossed over**: these schemas are validated
  against checked-in example payloads, not against each producer's own
  real serialized output at its own test time. The stronger half of
  "producer publishes the schema, consumers test against it" — wiring
  a JSON Schema validator into each producer's own test suite, asserting
  its actual live `ObjectMapper`/`json.dumps` output validates — is real,
  valuable follow-on work, not built in this pass (`schemas/README.md`
  states this explicitly). Until that lands, a producer's wire shape
  silently drifting from its own committed schema would not be caught
  by this CI job alone — only a schema silently drifting from what a
  *consumer* expects is what today's checked-in-example mechanism
  actually proves.
- No schema evolution/compatibility enforcement exists yet (a
  registry's other real capability, not adopted here) — a backward-
  incompatible field rename or type change is only caught if someone
  remembers to update the relevant `*.invalid.json` fixture to prove
  the old shape is now rejected, not enforced structurally. Revisit if
  this project ever needs to support two producer versions of the same
  topic live at once; not built ahead of that need.
- Coverage is the five topics backlog #96's own AC names — any future
  topic needs its own schema added deliberately, not automatically
  generated or inferred.
