# 0013. OpenTelemetry instrumentation: Micrometer Tracing + OTLP, Collector via Helm

Status: Accepted

## Context

observability#1 (backlog #17): "Every service emits traces, metrics, and
logs in a consistent format" / AC: "Gateway, API, workers all export OTel
data; a single trace can be followed across all three." OpenTelemetry is
already on the approved stack (`.claude/PROJECT.md`), so the tool choice
needs no ADR; per `WORKFLOW.md`, what does need deciding is the
instrumentation approach, what's actually in scope for this first issue
(vs. deferred to later observability backlog items), and where the
Collector's config lives given the repo-boundary split between
`observability` ("owns... OTel config") and `platform` (sole ArgoCD
entrypoint, ADR 0003). Nothing existed yet: no OTel dependency in
`services`, no Collector anywhere in `platform`.

## Decision

- **Micrometer Tracing (OTel bridge via `micrometer-tracing-bridge-otel`
  + `opentelemetry-exporter-otlp`), not the OpenTelemetry Java agent.**
  All three services already depend on `spring-boot-starter-actuator`
  (Micrometer's home in Boot); Spring for Apache Kafka's built-in
  Micrometer Observation support for `KafkaTemplate`/`@KafkaListener`
  auto-propagates trace context through record headers (W3C
  `traceparent`) once an `ObservationRegistry` bean exists, and Boot's
  observability autoconfiguration does the same for `RestClient` — both
  hops that matter here (`gateway`→`api` HTTP, `api`→Kafka→`workers`)
  get traced with dependency + config changes only, no code changes to
  `WorkItemProducer`/`WorkItemListener`/the gateway's forwarding
  controller. Rejected the OTel Java agent (`-javaagent` bytecode
  auto-instrumentation): it works around frameworks instead of using
  their native support, and would need bundling/updating an agent jar
  and modifying the shared `Dockerfile`'s `ENTRYPOINT` — real added
  complexity for no gain when the Spring-native path already covers
  both hops.
- **Traces**: OTLP HTTP push to a Collector
  (`management.otlp.tracing.endpoint`), **100% sampling**
  (`management.tracing.sampling.probability: 1.0`) — a single-node dev
  cluster with low traffic has no cost reason to sample down, and full
  sampling is what actually proves the AC.
- **Metrics stay on Boot's existing `/actuator/prometheus`** (Micrometer
  Prometheus registry, pull/scrape), **not routed through the
  Collector.** Backlog #18 (Prometheus/Grafana) scrapes services
  directly regardless of what this issue does, so pushing metrics
  through an OTLP pipeline first would add a hop this project never
  actually uses. Keeps the Collector scoped to traces only, for now.
- **Logs are out of scope for this issue.** Structured console output
  (already Spring Boot's default) is enough until backlog #19 (Loki)
  does centralized collection — a separate deliberate step per this
  project's own roadmap, not something to reach ahead of.
- **Collector: official `opentelemetry-collector` Helm chart**
  (`open-telemetry/opentelemetry-helm-charts`, not Bitnami — no
  registry-migration workaround needed here, verified the core image
  tag exists on Docker Hub directly), deployed via an ArgoCD Application
  in `platform` (`argocd/apps/otel-collector.yaml`), same inline-
  `valuesObject` pattern as Kafka/Postgres. `mode: deployment` (a single
  central collector fits a single-node cluster; `daemonset` is for
  per-node collection this project doesn't need). `image.repository:
  otel/opentelemetry-collector` + `command.name: otelcol` — the *core*
  distribution, not `-contrib`: the only components this needs (`otlp`
  receiver, `batch`/`memory_limiter` processors, `debug` exporter) are
  all in core, and the chart's default `config` already wires exactly
  that trace pipeline (`otlp` → `memory_limiter`,`batch` → `debug`) —
  verified by rendering the chart locally against these exact values,
  not assumed from the values.yaml comments alone. Left the chart's
  other default receivers (`jaeger`, `zipkin`) and its unused
  `metrics`/`logs` pipelines in place rather than fighting Helm's
  null-based config trimming for a marginal cleanup — they're inert
  (ClusterIP only, nothing sends to those ports) and not worth the
  values-file complexity to remove.
  - `debug` exporter (verbose stdout), not a real trace backend yet —
    proves "a single trace can be followed across all three" via
    correlated trace IDs in the Collector's own logs, without needing
    Tempo (#19) built first. Revisit the exporter (add OTLP-to-Tempo)
    as a small diff when #19 lands.
- **Its own `otel` namespace** (ADR 0009's per-component pattern, same
  reasoning as Kafka not Postgres): three consumers (`gateway`, `api`,
  `workers` all push to it), and no credential to worry about —
  `secretKeyRef` cross-namespace was Postgres's specific blocker, and
  doesn't apply here (OTLP receiver is open to the cluster, like
  Kafka's PLAINTEXT; nothing outside the cluster reaches it).
- **Repo-boundary resolution for "OTel config"**: the actual deployable
  Collector manifest (the ArgoCD Application + its inline pipeline
  config) lives in `platform` — ArgoCD can't read a second git repo for
  a ConfigMap's data without extra tooling, and ADR 0009 already
  decided manifests live in `platform` for exactly this reason.
  `observability/otel/README.md` documents the pipeline *design* (why
  these receivers/processors, what's deliberately deferred) and points
  at `platform/argocd/apps/otel-collector.yaml` as the deployed source
  of truth — same "pointer, not a second copy" pattern this session's
  `.claude/` cross-repo context already uses.

## Consequences

- `gateway`/`api`/`workers` each gain a new outbound dependency (the
  Collector) and two new Maven dependencies apiece; the OTLP exporter is
  fire-and-forget like the Kafka producer, not fail-fast like Flyway, so
  this shouldn't need the same "give CI a live dependency" treatment
  Postgres needed — to be confirmed empirically during implementation,
  not assumed, given how many Boot-4-modularized-autoconfiguration
  surprises this session already hit for seemingly-similar assumptions.
- The Collector's `debug` exporter is genuinely a placeholder: nothing
  persists trace data yet, so "follow a trace" today means reading
  Collector pod logs, not clicking through a UI. That gap closes with
  #19 (Tempo), tracked, not fixed speculatively here.
- Metrics deliberately do NOT flow through this Collector. If a future
  signal needs push-based metrics (e.g. a short-lived batch job that
  can't be scraped), that's the trigger to revisit, not a reason to
  route everything through OTLP now.
