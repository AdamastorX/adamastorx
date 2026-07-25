# 0015. Loki + Tempo + Alloy: log/trace centralization, single-binary charts, filesystem storage

Status: Accepted

## Context

observability#3 (backlog #19): "Logs from all services in Loki; traces
from #17 in Tempo; Grafana can pivot from a metric to a trace to a log
line." ADR 0013 (OpenTelemetry) already left the Collector's traces
pipeline on a `debug` (stdout) exporter as a placeholder, explicitly
noting "revisit the exporter (add OTLP-to-Tempo) as a small diff when
#19 lands." ADR 0013 also left logs as structured console output only,
deferred to this issue. Nothing existed yet: no log shipping, no trace
backend, only the Collector's stdout dump.

## Decision

- **`grafana-community/helm-charts`, not `grafana/helm-charts`, for
  both Loki and Tempo.** Same finding as ADR 0014's Grafana chart: the
  original repo's `tempo` and `promtail` charts are `deprecated: true`
  outright, and its `loki` chart's README states OSS users have been
  redirected to `grafana-community` (the original repo is now
  GEL-enterprise-only) since March 2026 — verified by downloading both
  repos' actual `Chart.yaml`/`README.md`, not assumed from a chart name
  still being reachable. `grafana-community` publishes newer, actively
  maintained versions of both.
- **Loki: `Monolithic` deployment mode (the chart's default), filesystem
  storage, no gateway/cache/canary subcharts.** `SimpleScalable` and
  `Distributed` modes require object storage (S3/GCS/etc) — standing up
  MinIO for a single-node dev cluster's log volume is exactly the kind
  of disproportionate machinery ADR 0011/0014 already rejected for
  Kafka/Prometheus. `storage.type: filesystem` needs an explicit
  `schemaConfig` (tsdb/v13, not the chart's `useTestSchema` shortcut,
  which the chart's own comments mark as "for testing or playing
  around" — this cluster's logs are real, not disposable). The chart's
  optional `gateway` (nginx front for routing to read/write/backend
  components), `chunksCache`/`resultsCache` (memcached), and
  `lokiCanary`/`test` (self-test smoke checks) are all disabled: with
  everything on one `singleBinary` pod, the gateway adds an nginx hop
  routing to itself, and memcached caching has no benefit at this
  traffic volume. `read`/`write`/`backend` (the `SimpleScalable`-mode
  components) must be explicitly zeroed (`replicas: 0`) even though
  `Monolithic` is selected — the chart's own validation rejects a
  values file that leaves both sets of replicas non-zero, confirmed by
  actually hitting that error locally before writing the final values.
  `auth_enabled: false` — no multi-tenant requirement here, and leaving
  it on would require every writer/reader to set an `X-Scope-OrgID`
  header for no benefit (same "don't build for a need that doesn't
  exist" reasoning as everywhere else in this project). A 2Gi PVC
  (`local-path`), same pattern as Prometheus/Postgres.
  - **Correction, found deploying this for real**: the chart's
    `common.replication_factor` defaults to 3, inherited from its
    multi-replica `SimpleScalable`/`Distributed` modes — with exactly
    one `singleBinary` replica, the ring permanently considered itself
    under-replicated and every query 500'd with "too many unhealthy
    instances in the ring." No startup error, `/ready` reported ready,
    the pod looked healthy — only actually querying surfaced it. Fixed
    with `commonConfig.replication_factor: 1`.
- **Tempo: the `tempo` (single-binary) chart, not `tempo-distributed`.**
  One binary handles ingest, storage, and query — the distributed chart
  splits this into separate scalable components, solving a scale
  problem this cluster doesn't have. Retention set to 72h to match
  Prometheus's 3-day metrics retention (ADR 0014) rather than the
  chart's 24h default, so a trace and the metrics/logs around it stay
  correlatable for the same window. 2Gi PVC, same reasoning as Loki —
  trace data has continuity value once persisted, an `emptyDir` would
  make the retention setting meaningless.
- **OTel Collector (ADR 0013) traces pipeline now exports to Tempo
  (`otlp/tempo`, its OTLP gRPC receiver), replacing the `debug`
  exporter** — the placeholder's job (proving spans exist by eyeballing
  Collector logs) is superseded by having a real, queryable backend.
  Confirmed the Collector chart's `config` values key deep-merges with
  its own defaults (only the `service.pipelines.traces.exporters` list
  is replaced, receivers/processors untouched) by rendering the chart
  locally before writing the change — same diligence as ADR 0011's
  `config:`-vs-`overrideConfiguration:` Kafka lesson, this time
  confirming the *opposite* behavior (merge, not replace) for this
  chart before relying on it.
- **Log shipping: `alloy` chart (Grafana's current agent), not
  `promtail`.** Promtail is the deprecated predecessor (see above) —
  Alloy is its intended replacement and still an actively-published,
  non-deprecated chart on `grafana.github.io/helm-charts`. Config is an
  explicit River pipeline (`discovery.kubernetes` role=pod →
  `discovery.relabel` to attach `namespace`/`pod`/`container` labels →
  `loki.source.kubernetes` → `loki.write` to
  `loki.loki.svc.cluster.local:3100`), written out plainly rather than
  reached for the `k8s-monitoring` meta-chart (a higher-abstraction
  wrapper over Alloy) — same "explicit config over a bundled black box"
  choice this project already made for Prometheus's scrape configs and
  the Collector's pipeline. `loki.source.kubernetes` (the API-based log
  read, introduced as Alloy's modern approach) was chosen over the
  traditional `loki.source.file` + hostPath-mount approach Promtail
  used: no `/var/log` hostPath mount or container-runtime-specific path
  assumptions needed, just `pods`/`pods/log`/`namespaces` RBAC — less
  host filesystem coupling for the same result. DaemonSet (the chart's
  default `controller.type`) — log collection is inherently per-node,
  unlike the Collector's centralized `mode: deployment` for OTLP push.
- **Grafana correlation: Loki `derivedFields` → Tempo (logs→trace) and
  Tempo `tracesToLogsV2` → Loki (trace→logs), both as code in
  `grafana.yaml`'s `datasources` values — no metric→trace pivot.** The
  services already emit a `[<traceId>-<spanId>]` bracket in every log
  line once a trace is active (Boot's default correlation pattern, on
  since ADR 0013) — confirmed by triggering a real request and reading
  the literal bracket format directly from `workers`' log output rather
  than assuming Boot's documented pattern matches this version. The
  `derivedFields` regex extracts the 32-hex traceId from that exact
  format. `tracesToLogsV2` filters by time window only
  (`filterByTraceID: false`) since Loki's labels here are
  `namespace`/`pod`/`container`, not a trace ID label — good enough at
  this log volume, matching the "static targets, no relabeling needed"
  reasoning ADR 0014 already used for `workers`' scrape config.
  **Metric→trace (the third leg of the issue's literal "metric to
  trace to log" AC) is out of scope here** — it needs Prometheus
  exemplars, which need native histograms/OpenMetrics scraping and a
  Micrometer exemplar bridge added to all three services, a separately-
  scoped app-level change bundled into #19 would gate a working
  trace↔log pivot on. Tracked as backlog #19a, same "split what the AC
  doesn't actually require yet" pattern as #18a (Mimir). `serviceMap`
  (Tempo's span-metrics-to-Prometheus feature) is left off `Tempo`'s
  datasource config for the same reason — it needs Tempo's
  `metricsGenerator`, deliberately left disabled (a `remote_write`
  dependency this issue doesn't need).
- **Separate `loki`, `tempo`, `alloy` namespaces**, matching this
  project's established per-component pattern (Kafka, Postgres, OTel
  Collector, Prometheus, Grafana are each their own namespace) rather
  than inventing a shared "logging stack" namespace for this trio.

## Consequences

- `platform` gains 3 more ArgoCD Applications (`loki`, `tempo`,
  `alloy`) and its first DaemonSet (`alloy` — everything else so far
  has been a `Deployment`/`StatefulSet`).
- The OTel Collector's `debug` exporter is gone from the traces
  pipeline — "follow a trace" now means Tempo (via Grafana or its own
  API), not reading Collector pod logs. The exporter definition itself
  is left in the rendered config unused rather than fought out of
  Helm's config-trimming, same precedent ADR 0013 already set for the
  chart's unused jaeger/zipkin receivers.
- Alloy tails every pod's logs cluster-wide via the Kubernetes API
  (`loki.source.kubernetes`, RBAC-scoped to `pods`/`pods/log`/
  `namespaces`) — this includes ArgoCD, Traefik, cert-manager, and
  every other system pod, not just the three application services. No
  scoping to a namespace allowlist was added since the AC only asks for
  the three services' logs and Loki has no query-time cost from extra
  labels/streams at this log volume — revisit if noise becomes a real
  problem, not before.
- Backlog #19a (Prometheus exemplars) is real, tracked, deliberately
  not built now — the trace↔log pivot this issue asked for works today;
  metric→trace does not yet.
- 72h retention on both Loki and Tempo means, like Prometheus's 3-day
  window (ADR 0014), incident-lab evidence (backlog #23) older than
  that won't be replayable from the live stack — acceptable for a dev
  cluster where labs are run and documented close to when they happen.
