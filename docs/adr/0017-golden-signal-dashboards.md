# 0017. Golden-signal dashboards: file-based provisioning, dashboards-before-alerts as a declared stepping-stone

Status: Accepted

## Context

observability#4 (backlog #20): "One dashboard per service covering the
four golden signals (latency, traffic, errors, saturation); dashboards
are code (provisioned, not click-built)." Dependency: observability#3
(backlog #19, Loki/Tempo/Alloy — done, ADR 0015). Grafana has had a
provisioned Prometheus/Loki/Tempo datasource trio since ADR 0014/0015
but zero dashboards — deliberately, per ADR 0014's own decision record:
"No dashboards, no alerts, built now… Backlog #20 is the
dashboards-as-code deliverable." Nothing existed yet: no
`dashboardProviders`/`dashboards` values on the Grafana chart, no
dashboard JSON anywhere in either repo.

## A tension worth resolving explicitly, not silently

The `observability-engineer` persona (`observability/.claude/agents/observability-engineer.md`)
states a rule under "Never": *"Ships a dashboard without the alert/SLO
it's meant to support, or an alert without a runbook."* Taken literally,
this issue violates that rule — backlog #20 (this issue) and #21
("Define SLOs and alerting rules") are explicit, sequential backlog
items, with #21 *depending on* #20, not the other way around. Building
#21 first isn't an option: an SLO needs an error budget computed from
something, and alert thresholds need to be picked with real signal
shapes in front of you, not guessed blind.

**Resolution reached here**: build the dashboards now, but treat them
explicitly as a declared stepping-stone toward #21, not as a
finished, standalone deliverable — and say so loudly rather than
pretending the persona rule doesn't apply:

- The four golden signals (latency, traffic, errors, saturation) are
  themselves the textbook precursor to SLO definition (the SRE
  workbook's own framing) — this issue's AC is, in substance, "build
  the inputs #21 needs," not "add unrelated dashboard sprawl no alert
  will ever reference." Every panel here is a direct candidate SLI.
- Every dashboard's JSON carries a visible marker of the gap rather
  than hiding it: the `description` field on each saturation panel
  states its known limitation in the UI itself (see below), and
  `observability/grafana/dashboards/README.md` states in its opening
  paragraph that these dashboards ship with **no alerts and no SLOs
  yet — backlog #21 is next, not deferred indefinitely**. A human
  looking at any of these dashboards in Grafana, or at the design doc,
  sees the gap without needing to already know this ADR exists.
- This is the same call ADR 0014 already made for Prometheus/Grafana
  itself (deploy the platform now, dashboards later, explicitly
  citing this same persona rule as the reason *not* to rush a
  half-built dashboard into that issue) — consistent reasoning applied
  one step further down the same dependency chain, not a new
  precedent invented here.
- What this ADR explicitly does **not** do: add alert rules or SLO
  definitions to satisfy the letter of the persona rule by scope
  creep into #21's territory. That would blur two issues this
  project's roadmap deliberately kept separate and sequential, and
  would mean picking error-budget thresholds without the lived data
  these dashboards exist to surface first.

## Decision

- **Dashboard content lives in `platform`, not `observability` —
  same repo-boundary precedent as ADR 0013's OTel Collector config.**
  ArgoCD only watches `platform` (ADR 0003) and can't read a second git
  repo for a ConfigMap's/Helm-values' data without extra tooling, so
  the actual deployable dashboard JSON is embedded in
  `platform/argocd/apps/grafana.yaml`'s `helm.valuesObject` — the same
  inline-YAML-as-code pattern already used there for datasources.
  `observability/grafana/dashboards/README.md` documents the design
  (why these panels/queries, what's deliberately deferred) and points
  at that file as the deployed source of truth — "pointer, not a
  second copy," not a dashboard JSON independently hand-maintained in
  two places that can drift.
- **Provisioning mechanism: the chart's `dashboardProviders` +
  `dashboards` values keys (file-based provisioning), not the sidecar
  (`sidecar.dashboards.enabled`).** Verified by pulling
  `grafana-community/grafana` 12.8.0 (the exact chart/version
  `platform/argocd/apps/grafana.yaml` already sources) and rendering it
  locally with both mechanisms' templates open side by side, not
  assumed from the values.yaml comments:
  - `dashboards.<provider>.<name>.json` (a `json: |` block, inline
    dashboard JSON) makes `templates/dashboards-json-configmap.yaml`
    generate one ConfigMap per provider holding each dashboard's JSON
    as a data key, and `templates/_pod.tpl` mounts each key
    individually into the Grafana container at
    `/var/lib/grafana/dashboards/<provider>/<name>.json` via `subPath`
    — no extra container, no extra RBAC, no watch loop. Confirmed by
    rendering the real values (see below) and inspecting the resulting
    Deployment's `volumeMounts`/`volumes`.
  - The sidecar (`k8s-sidecar` container watching ConfigMaps labeled
    `grafana_dashboard` cluster/namespace-wide) is built for a
    different problem: dashboards owned and updated by *other*
    workloads/teams dropping labeled ConfigMaps independently of
    Grafana's own deploy, needing `rbac.create` for
    list/watch/get on ConfigMaps. Nothing here needs that — there is
    exactly one GitOps entrypoint (`platform`) and exactly one place
    these three dashboards are defined. Adding a sidecar container plus
    RBAC surface for content that's already fully known at Helm-values
    time would be exactly the kind of disproportionate machinery this
    project has consistently rejected elsewhere (ADR 0011's Strimzi
    rejection, ADR 0014's Prometheus Operator rejection) — same
    reasoning, applied to a third case.
  - Verified end to end: `helm template` against the exact chart/
    version with a `dashboardProviders`/`dashboards` values block
    holding the three dashboards below produced a `file`-type provider
    config at `/var/lib/grafana/dashboards/golden-signals` and a
    generated `grafana-dashboards-golden-signals` ConfigMap correctly
    mounted at that path — before writing the real `platform` manifest,
    not after.
- **One dashboard JSON per service** (`gateway-golden-signals`,
  `api-golden-signals`, `workers-golden-signals`), matching the AC
  literally, in a shared `Golden Signals` provisioning folder — not one
  parameterized dashboard with a `$service` template variable. Each
  service's signals come from genuinely different metric families (see
  below), so a shared template would either hide that difference behind
  variable substitution or force artificial symmetry.
- **Every panel's PromQL query is built from metric names/labels
  confirmed by querying the live Prometheus** (`kubectl port-forward`
  to `prometheus-server`, read-only), not assumed from Micrometer/
  Spring-Kafka documentation:
  - `gateway`/`api` (HTTP-facing, Boot's `http_server_requests_seconds_*`):
    - Traffic: `sum(rate(http_server_requests_seconds_count{uri!~"/actuator.*"}[$__rate_interval]))`.
    - Latency: `rate(_sum)/rate(_count)` (average) plus `max()` of
      `http_server_requests_seconds_max`. **Gap, stated openly**: Boot
      does not export `http_server_requests_seconds_bucket` here
      (`management.metrics.distribution.percentiles-histogram` isn't
      enabled) — confirmed by listing every series for both jobs and
      finding no `_bucket` suffix. There is no true p95/p99 to show,
      only average and max. Enabling histogram buckets is an
      app-level Micrometer config change in `services`, out of scope
      for a dashboard-only PR — flagged here as the trigger for a
      follow-up, not silently worked around by pretending average is
      "good enough" without saying so.
    - Errors: `outcome="SERVER_ERROR"` request-rate series plotted
      against total rate, plus a `stat` panel for the current ratio
      (`error rate / total rate`, thresholds at 1%/5%).
    - Saturation: JVM heap used/max ratio (`area="heap"`) for both;
      `api` additionally gets HikariCP pool usage
      (`hikaricp_connections_active/_max`) since `api` is the one
      service with a real connection-pool bottleneck (ADR 0012,
      Postgres) — `gateway` gets process CPU usage instead, since it
      has no comparable pool. Deliberately not copy-pasted identical
      panels across both services.
  - `workers` (no business HTTP API, ADR 0009/0011 — confirmed again
    live: its only `http_server_requests_seconds` series are
    `/actuator/health` and `/actuator/prometheus`, nothing business-
    facing): golden signals come from the `spring.kafka.listener`
    timer instead.
    - Traffic: `sum(rate(spring_kafka_listener_seconds_count[$__rate_interval]))`
      (messages processed/sec on the `work-items` topic).
    - Latency: `rate(_sum)/rate(_count)` plus `max()` of
      `spring_kafka_listener_seconds_max` — same "average/max only, no
      percentiles" gap as above, same reason.
    - Errors: the timer's own `error` label (`"none"` on success, the
      exception class name otherwise) — `error!="none"` rate plotted
      against total, plus a ratio `stat` panel.
    - Saturation: `applicationTaskExecutor` thread-pool usage
      (`executor_active_threads/executor_pool_max_threads`) and JVM
      heap, used as an explicit **proxy**, stated as such directly in
      the panel's own `description` field in the dashboard JSON: no
      `kafka_consumer_*` metric (e.g. `records-lag-max`) is exposed
      today — confirmed by listing every series `workers` exports and
      finding none. Consumer lag would be the textbook saturation
      signal for a Kafka listener; it isn't available without adding a
      Kafka client metrics binder in `services`, which is an app-level
      change this dashboard-only PR doesn't make. Flagged as a gap
      with a stated trigger to revisit (if the executor-pool proxy
      stops correlating with real backlog during a future chaos-test
      scenario, backlog #23), not quietly substituted without
      acknowledgment.

## Consequences

- `platform/argocd/apps/grafana.yaml` grows a `dashboardProviders` +
  `dashboards` block (~700 lines of inline dashboard JSON across three
  dashboards) alongside its existing `datasources` block — the same
  file, the same inline-values-as-code pattern, now covering all of
  Grafana's provisioned state (datasources + dashboards), still no
  PVC, still nothing to lose on pod restart.
- `observability/grafana/dashboards/README.md` stops being an empty
  scaffold and becomes the design record for these three dashboards —
  still not the deployable source of truth, same split ADR 0013
  established for OTel config.
- Backlog #21 (SLOs + alerting) is now unblocked and has real signal
  shapes to draw error budgets from instead of starting from nothing —
  the explicit reason this ADR treats #20 as a stepping-stone rather
  than pretending it's a complete, standalone deliverable.
- Two real gaps are now documented and trigger-tagged rather than
  silently absorbed: no true latency percentiles (needs a Micrometer
  histogram config change across all three services), and no Kafka
  consumer-lag metric for `workers` (needs a Kafka client metrics
  binder). Both are `services`-repo, app-level changes — explicitly
  out of scope here, not silently worked around.
- The sidecar dashboard-provisioning mechanism remains unused. If a
  future need arises for dashboards owned by a different workload/repo
  dropping ConfigMaps independently (the actual problem the sidecar
  solves), that's the trigger to revisit — not built ahead of it.
