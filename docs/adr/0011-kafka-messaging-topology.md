# 0011. Kafka messaging: workers module, spring-kafka, work-items topic, single-broker KRaft deployment

Status: Accepted

## Context

services#3 needs an async path so a message produced by `api` is consumed by
a new `workers` service — the project's core "distributed systems" exercise
(M2). Kafka (KRaft) is already on the approved stack (`.claude/PROJECT.md`),
so the tool choice itself needs no ADR; per `WORKFLOW.md`, what does need
deciding is the topology/pattern used while adopting it. The `workers`
Maven module does not exist yet — `services/pom.xml` still only reactors
`gateway` and `api`, with `<!-- workers module arrives with services#3 -->`
— so its scaffold shape is in scope here too, to keep it consistent with
ADR 0007's gateway/api pattern before backend-engineer builds it. Dependency
services#2 (API) is done and deployed per ADR 0010.

## Decision

- **`workers` is a new Maven module in the same reactor**, same parent POM
  and version pins as `gateway`/`api` (ADR 0007: Java 25, Spring Boot 4.1
  line, `spring-boot-maven-plugin`). Dependencies: `spring-kafka`,
  `spring-boot-starter-actuator`, and — despite `workers` having no business
  HTTP API — `spring-boot-starter-webmvc` too, solely to give actuator an
  embedded servlet container so `/actuator/health/liveness` and
  `/readiness` exist over HTTP for the kubelet probes, exactly like
  `gateway`/`api` already do (`probes.enabled: true`). Rejected actuator
  without a web starter: it falls back to JMX-only endpoints, no HTTP
  surface for kubelet to probe, which would make `workers` the one module
  in the repo using an unproven, bespoke liveness mechanism to save a few
  MB of Tomcat that's already paid for and working twice over. `workers`
  still gets no Kubernetes `Service` (ADR 0009 already anticipated this) —
  the web starter is for the probe port only, not for exposing the module
  to any caller.
- **Client library: `spring-kafka`**, not raw `kafka-clients`. It is the
  Spring-idiomatic, most-documented option for a Boot app (matches "boring,
  well-understood tools"), gives declarative `@KafkaListener` consumption,
  and its `KafkaTemplate`/error-handling/serialization support avoids
  hand-rolling what the library already solves. Raw `kafka-clients` was
  rejected: it would mean reimplementing consumer-loop, offset-commit, and
  retry/DLT plumbing that `spring-kafka` provides out of the box, for no
  gain at this scale.
- **Topic: `work-items`, 3 partitions, replication factor 1.** One topic —
  there is exactly one producer→consumer relationship to prove today;
  splitting topics by message type is a decision for when a second, truly
  distinct message type exists, not speculatively. 3 partitions (not 1): the
  AC explicitly asks for consumer-group behaviour to be documented,
  including multiple worker replicas — 1 partition would make replica
  count > 1 pointless to demonstrate, and this is a single-node dev cluster,
  so provisioning stays low (not 6, not 12). RF=1 is not a preference, it's
  forced by the single-broker KRaft deployment below — recorded here as a
  current constraint to revisit if the broker ever becomes multi-node, not
  a durability decision made on purpose.
- **No partition key yet — messages publish with a `null` key** (round-robin
  partitioning). There is no domain entity yet (the API is still a
  placeholder `HelloController`) that would give a natural ordering key,
  and nothing in the AC requires per-entity ordering. Once a real entity ID
  (e.g. an order/user ID) exists and ordering across its events matters,
  that ID becomes the key — noted here as the trigger, not implemented
  speculatively now.
- **Consumer group id: `workers`**, matching `spring.application.name`
  (same convention `gateway`/`api` use for their app name). Ack strategy:
  **manual acknowledgment, `AckMode.RECORD`** (`enable.auto.commit: false`)
  — offset commits after a record is successfully processed, giving
  **at-least-once** delivery. Rejected auto-commit: its time-based commit
  can advance the offset before processing finishes, so a crash there loses
  the message (at-most-once) — an outcome that undermines the entire point
  of exercising Kafka's delivery guarantees for the project's mission.
  At-least-once means a consumer restart can redeliver an already-processed
  record; `workers` has no persistent state yet, so idempotency isn't
  implemented now, only flagged as a requirement once it does. Consumer
  group behaviour to prove and document at implementation time: with 3
  partitions, up to 3 `workers` replicas get parallel assignment via normal
  Kafka group rebalancing (`spring-kafka`'s default `CooperativeStickyAssignor`);
  a 4th+ replica sits idle until a partition frees up — scale replicas and
  capture the rebalance/assignment logs as the AC's "consumer group
  behaviour" proof.
- **Message format: JSON**, via `spring-kafka`'s `JsonSerializer`/
  `JsonDeserializer` (Jackson — already a transitive dependency through the
  Boot web starters, zero new dependency). Rejected Avro/Protobuf with a
  schema registry: schema registry is new infra not on the approved stack,
  unjustified for one topic with one producer and one consumer both owned
  in this same repo. Rejected plain strings: JSON costs nothing extra over
  a bare string once `JsonSerializer` is in play, and avoids a migration
  the moment the message needs a second field. Implementation note for
  backend-engineer: `spring.kafka.consumer.properties.spring.json.trusted.packages`
  needs to be set to the message DTO's package — producer and consumer
  share a trust boundary (same repo, same reactor) so this is a config
  line, not a design question.
- **Error handling: `DefaultErrorHandler` with a small fixed retry (e.g. 3
  attempts, short fixed backoff) then a dead-letter topic** via
  `DeadLetterPublishingRecoverer` (Spring Kafka's default naming:
  `work-items.DLT`). Rejected log-and-drop on failure: it silently loses
  messages, which defeats the AC's purpose of exercising a real delivery
  guarantee, and gives observability nothing to alert on later. Rejected
  Spring Kafka's non-blocking `@RetryableTopic` cascade (multiple
  auto-created retry topics with escalating backoff): that's
  disproportionate machinery — several extra topics and consumer groups —
  for one dev topic; a bounded retry + single DLT gets the same "don't
  lose it, make it visible" outcome with a few lines of config, no new
  topics beyond the one DLT.
- **Broker deployment shape (for platform-engineer): single-broker Kafka in
  combined controller+broker KRaft mode**, deployed the same way Traefik
  and cert-manager already are — a **Helm chart Application** in
  `platform/argocd/apps/` (chart source + inline `valuesObject`, no local
  templating), its **own `kafka` namespace** (per-service/per-component
  namespace pattern, ADR 0009), **ClusterIP only** (in-cluster clients via
  Kubernetes Service DNS, same discovery mechanism as ADR 0010's
  `api.api.svc.cluster.local` — no external exposure, nothing outside the
  cluster talks to Kafka). Single replica, modest CPU/memory
  requests/limits sized for a dev laptop, not production; storage can be a
  small PVC or emptyDir — this is a single-node dev cluster with no
  durability requirement yet, so losing topic data on a broker restart is
  an accepted trade, not a gap to fix. Exact chart source/version is
  platform-engineer's implementation call (mirrors how Traefik/cert-manager
  each pin their own chart+version). Rejected the **Strimzi operator**:
  it adds an operator + CRD surface (a new kind of tool, not just a new
  chart) to manage a single broker for one topic — disproportionate here,
  and adopting an operator is itself the kind of tool decision that would
  want its own ADR, not a side effect of this one. Revisit if the project
  ever needs multiple Kafka clusters, topics-as-code across several teams,
  or in-cluster user/topic self-service — that's Strimzi's actual value
  proposition. Rejected hand-written raw StatefulSet manifests: reinvents
  what a maintained chart already gets right (KRaft cluster-id bootstrapping,
  listener config), and this repo already established "Helm chart for infra
  components, raw manifests for our own services" via Traefik/cert-manager
  vs. gateway/api (ADR 0009) — this follows the existing split, it doesn't
  create a new one.

## Consequences

- `services/pom.xml` gains a `workers` module entry; `workers` ships with
  an embedded Tomcat it never uses for business traffic, purely to host
  actuator's HTTP probes — a small, consistent cost paid to avoid a
  bespoke probing mechanism for one module.
- `api` gains a new runtime dependency: it must reach the `kafka` Service
  to produce; a Kafka outage turns `api`'s produce path into a new failure
  mode to handle (this ADR does not decide `api`'s producer-side error
  handling — that's part of the services#3 implementation, informed by the
  consumer-side error handling decided here).
- Consumer-group behaviour (rebalance across replicas, at-least-once
  redelivery) must actually be exercised and captured (logs/description) at
  implementation time to satisfy the AC — this ADR decides the mechanism,
  not the proof.
- RF=1 is a single point of data loss for in-flight topic data if the sole
  broker is lost; acceptable for a dev cluster today, and explicitly called
  out above as a constraint to revisit, not a permanent design choice.
- A second topic or a second distinct message type is the trigger to
  revisit "one topic"; a second Kafka client needing ordering guarantees
  is the trigger to revisit "no partition key"; multi-cluster or
  topic-self-service needs are the trigger to revisit Strimzi — none of
  these are reasons to build toward now.
