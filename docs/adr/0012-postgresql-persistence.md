# 0012. PostgreSQL persistence for `api`: Spring Data JPA, Flyway, single-instance chart with a real PVC

Status: Accepted

## Context

services#4 needs `api` to actually persist state — "durable state for the
API service," AC: "API reads/writes to PostgreSQL; schema migrations are
versioned and repeatable." PostgreSQL is already on the approved stack
(`.claude/PROJECT.md`), so the tool choice itself needs no ADR; what does
need deciding, per `WORKFLOW.md`, is the app-side data-access/migration
tooling and the deployment shape — neither is named anywhere in the
roadmap docs, so both are open implementation choices recorded here.
services#2 (API) and services#3 (Kafka) are done; `api` already has a
`work-items` concept (an in-memory-only proof from ADR 0011's Kafka
scaffold) that this extends rather than duplicates.

This is also the first genuinely stateful workload in the cluster.
Kafka (ADR 0011) deliberately chose `emptyDir` over a PVC and accepted
topic data loss on broker restart — a reasonable trade for a dev message
broker, explicitly reasoned through there. Nothing in `platform/` today
configures or even references a `StorageClass` or `PersistentVolumeClaim`
for anything. Calling Postgres "durable state" while also losing it on
every pod restart would contradict the entire point of this issue, so
this ADR makes the one deliberate deviation from that emptyDir precedent.

## Decision

- **Spring Data JPA + Hibernate** for data access, not plain JDBC. It's
  the standard, most-documented pairing for "Spring Boot + Postgres" —
  boring in the sense that matters here (what the overwhelming majority
  of real Spring Boot services actually use), and needs less boilerplate
  than hand-rolled `JdbcTemplate`/`JdbcClient` code for the AC's scope
  (a single entity, basic create/read). Rejected plain JDBC: more code
  for no real gain at this scale, and it would be the less-standard
  choice here, not the more conservative one.
- **Flyway** for schema migrations — Spring Boot-native support (own
  autoconfiguration, runs at startup by default), and its `V1__`,
  `V2__`... file-naming *is* the "versioned and repeatable" the AC asks
  for, not something bolted on separately. Rejected Liquibase: heavier
  (XML/YAML changelog format vs. plain SQL files), no capability this
  project needs that Flyway lacks.
- **Extends the existing `work-items` concept, not a new throwaway
  entity.** `api`'s `POST /work-items` now persists a `work_items` row
  (via a new `WorkItemEntity`/JPA repository, kept as a distinct class
  from the existing `WorkItem` Kafka-payload record — same
  producer/consumer decoupling precedent ADR 0011 already established,
  applied here to REST/Kafka-DTO vs. JPA-entity layering) *before*
  publishing to Kafka, and adds `GET /work-items/{id}` and
  `GET /work-items` to prove the read side. This is a more coherent
  story than a disconnected dummy table: a work item now gets durably
  recorded, then handed off for async processing — closer to how a real
  service would actually use both together.
  - **Explicitly not addressed, flagged for later:** dual-write
    consistency between the Postgres save and the Kafka publish (a
    proper outbox pattern). If the DB write fails nothing gets
    published (acceptable ordering for now), but a Kafka publish failure
    after a successful save isn't compensated. Noted here as a real gap,
    not built speculatively before an issue actually needs it.
- **Deployment: Bitnami `postgresql` Helm chart** via an ArgoCD
  Application (`argocd/apps/postgresql.yaml`), same inline-`valuesObject`
  pattern as every other chart-based Application in this repo
  (Traefik, cert-manager, Kafka) — single instance (no read replicas,
  no HA), **ClusterIP only** (same trust model as Kafka and
  `gateway`↔`api`: nothing outside the cluster talks to it, no service
  mesh). Same `bitnamilegacy/postgresql` registry override ADR 0011
  already needed for Kafka — confirmed the chart's default
  `docker.io/bitnami/postgresql` tag 404s the same way (verified against
  Docker Hub's registry API, not assumed from precedent alone).
- **Deployed into `api`'s own namespace, not a separate `postgresql`
  one** — the one deliberate deviation from Kafka's per-component
  namespace. Kafka has two consumers across two namespaces (`api`
  produces, `workers` consumes) and sidesteps credentials entirely
  (PLAINTEXT, no auth), so its own namespace was free. Postgres has
  exactly one consumer (`api`) and *does* need a password: the chart's
  auto-generated Secret (see below) lives in the same namespace as the
  release, and `secretKeyRef` cannot cross namespaces in Kubernetes.
  Making that work across namespaces needs a syncing tool (Reflector,
  External Secrets Operator) that isn't on the approved stack — clearly
  disproportionate machinery to keep a single-consumer dependency
  symmetrical with a genuinely-shared one. Revisit if a second consumer
  for this Postgres instance ever shows up.
- **A real PVC, not `emptyDir`** — the one deliberate break from the
  Kafka pattern. The chart's own default (`primary.persistence.enabled:
  true`) already does this; the only change from chart defaults is
  sizing it down (e.g. 2Gi vs. the chart's 8Gi default) to match "small
  dev cluster, not production," same sizing philosophy as Kafka's
  `resourcesPreset: small`. `storageClass` is left at the chart's empty-
  string default, which resolves to the cluster's default
  `StorageClass` — k3s ships `local-path` (its bundled Local Path
  Provisioner) as that default already, so no new provisioner needs
  installing to get a working PVC.
- **Credentials: the chart's own auto-generated Secret, not a
  hand-rolled one.** `auth.username`/`auth.database` are set to `api`
  (a dedicated least-privilege user + database, not the `postgres`
  superuser) with `auth.password` left unset — the chart generates a
  random password into a Secret (`common.secrets.passwords.manage`,
  confirmed by reading the chart's own `templates/secrets.yaml`, the
  same way Kafka's KRaft cluster ID is chart-generated rather than
  hand-written) under key `password`. `api`'s Deployment reads
  `SPRING_DATASOURCE_USERNAME`/`SPRING_DATASOURCE_PASSWORD` from that
  Secret via `secretKeyRef` — no credential ever lives in git, matching
  how nothing else in this repo hand-rolls one either.
- **Connection string follows the existing env-var-with-in-cluster-
  default pattern**: `spring.datasource.url` defaults to
  `jdbc:postgresql://postgresql.api.svc.cluster.local:5432/api` (same
  same-namespace reasoning as above — mirrors `KAFKA_BOOTSTRAP_SERVERS`'s
  `api.api.svc.cluster.local`-style default from ADR 0010), overridable
  via `SPRING_DATASOURCE_URL` at deploy time. Username/password get no
  baked-in default — unlike a Service DNS name, a real password has no
  sane public one.

## Consequences

- `api` gains its first real dependency on cluster storage — a Postgres
  outage or PVC issue is a new failure mode for both the read and write
  paths of `/work-items`, not just the async Kafka side ADR 0011 already
  introduced.
- `platform` gains its first `PersistentVolumeClaim`/`StorageClass`
  usage. If the cluster is ever rebuilt or the node's local-path storage
  is lost, Postgres data goes with it — acceptable for a single-node dev
  cluster (same "not production" framing as everything else here), but
  a real durability gap worth knowing about, unlike Kafka's *deliberately
  accepted* ephemerality.
- CI's image smoke-test (`services/.github/workflows/ci.yml`) needs a
  live, reachable Postgres for the `api` job specifically, not just a
  resolvable hostname the way Kafka's client tolerated — Flyway migrates
  at application startup and fails fast if the database is unreachable,
  aborting `SpringApplication.run()` entirely (Spring Data JPA's
  connection-pool initialization is similarly eager). An ephemeral
  `postgres:16-alpine` container on the same Docker network as the
  smoke-test container is required for that job going forward.
- The outbox-pattern gap above is the trigger to revisit dual-write
  consistency, if/when a future issue's correctness requirements
  actually need it — not a reason to build it now.
