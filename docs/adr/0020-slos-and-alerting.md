# 0020. SLOs and alerting: real histograms/lag first, Alertmanager with no external channel yet, one runbook per alert

Status: Accepted

## Context

M4 Reliability (backlog #21/#22/#23) has not been started since M3's
dashboards (#20, ADR 0017) shipped. ADR 0017 itself named the gap
directly rather than hiding it: golden-signal dashboards for
`gateway`/`api`/`workers` ship with **no true latency percentiles**
(Boot's histogram buckets aren't enabled — only average/max) and no
Kafka consumer-lag metric for `workers` (a thread-pool-usage panel
stands in as a stated proxy), both flagged as "the trigger for a
follow-up," not silently absorbed. That follow-up is due now — writing
SLOs against average/max instead of a real p95, or a saturation proxy
instead of the textbook consumer-lag signal, would produce alert
thresholds picked against the wrong number.

Since ADR 0017, M5 (ADR 0018/0019) added `clinvar-service`, a fourth
component with **zero** Prometheus metrics today (OTel tracing only,
`app/telemetry.py`) and a real, live incident behind it: two
overlapping manual ingestion triggers ran two full VCF scans
concurrently, invisible in logs for the ~90 real-data seconds their
slowest step normally takes, ending in a SIGKILL with no OOM evidence
anywhere in kernel or kubelet logs (checked `dmesg -T`,
`journalctl -k`, `journalctl -u k3s.service` — all clean). A lock
(services#36) now prevents the recurrence, but nothing here is
observable as a metric — only as a log line, read after the fact.

A cross-persona survey (architect, backend-engineer, platform-engineer,
observability-engineer, documentation-engineer — five independent
reviews of current state) converged on the same conclusion
independently: M4 is the most overdue milestone in the project, and
starting a sixth milestone or gnomAD enrichment before it would be
optics over substance for this project's actual purpose (an SRE
portfolio demonstrating operability, not just feature surface).

## Decision

### Metrics prerequisites ship as part of M4, not deferred again

- **`management.metrics.distribution.percentiles-histogram.http.server.requests`
  and the equivalent `spring.kafka.listener` timer property, set `true`
  on `gateway`/`api`/`workers`.** This is the direct, named follow-up
  ADR 0017 flagged — a real `histogram_quantile(0.95, ...)` p95 replaces
  the average/max stand-in on all three golden-signal dashboards once
  this lands.
- **`workers` gets a real Kafka consumer-lag metric**, not the
  thread-pool proxy. Boot's auto-configured Kafka metrics binder
  doesn't apply here — `workers` uses hand-built
  `ConsumerFactory`/listener-container-factory beans (ADR 0011,
  documented reason: Boot's auto-configured ones are untyped), the same
  reason `spring.kafka.listener.observation-enabled` was already a
  silent no-op for this service (see `docs/SESSION_STATE.md`'s
  recurring-gotcha log). Same fix shape: explicit
  `KafkaClientMetrics(consumer).bindTo(meterRegistry)` registered
  directly against the hand-built consumer, not a property that
  assumes an auto-configured bean underneath.
- **`clinvar-service` gets Prometheus metrics from zero**:
  `prometheus_client` + `GET /metrics`, with an ingestion-duration
  histogram, an `in_progress` gauge, a counter for the 409
  concurrent-rejection path (a rejection is itself a signal, not just
  a defensive no-op), and a lookup-latency/count histogram split by
  cache outcome is *not* this service's job (that's `api`'s Redis
  layer, ADR 0016) but the raw HTTP-call latency/error rate from
  `api`'s perspective is. This is the metric surface the
  double-ingestion incident needed and didn't have.

### SLOs (backlog #21)

One SLO per service, defined against the metric that's now real, not
guessed against a stand-in:

| Service | Availability SLI | Latency SLI |
|---|---|---|
| `gateway` | non-5xx rate on `http_server_requests_seconds_count` | p95 via the new histogram buckets |
| `api` | non-5xx rate, plus `GET /variants/lookup` success rate specifically (its own external dependency on `clinvar-service`, a distinct failure mode from the rest of `api`) | p95, same split |
| `workers` | listener timer's own `error` label (`!= "none"`) rate | consumer-lag threshold (the new real metric), not latency — a queue consumer's saturation signal is backlog, not per-message latency |
| `clinvar-service` | `GET /internal/clinvar/lookup` non-5xx rate (as called by `api`) **and** ingestion freshness — time since last *successful* ingestion exceeding the scheduled cadence, since a silently-failing weekly job is a real, already-demonstrated failure mode | p95 on the lookup path; ingestion duration anomaly (a run taking several multiples of the ~90s real-data baseline is itself alert-worthy, the exact signal that would have made the double-ingestion incident visible as a metric instead of a log line read after the fact) |
| `watchlist-service` (backlog #53, added by ADR 0026) | **Delivery success rate** — `watchlist_delivery_attempts_total{outcome="sent"}` over `{outcome="sent"}+{outcome="dead_lettered"}` resolved attempts, not a request-count SLI: subscription CRUD is low-volume admin traffic, the real subscriber-facing promise is "did the notification actually arrive," which this metric answers directly (`WatchlistDlqDepthHigh` alerts on the same underlying signal, ADR 0026) | **Delivery latency** — p95-equivalent stand-in via `watchlist_delivery_latency_seconds`'s sum/count average (no `_bucket` histogram wired for this custom Timer yet, same stated gap ADR 0017 once had for `http.server.requests` before #21a closed it — a real follow-up here, not silently presented as a percentile it isn't) |
| `market-data-ingestor` (backlog #78, added by backlog #90/ADR 0031) | **Tick publish success rate** — `market_data_ticks_published_total` over `{published}+{publish_failed}`; no business HTTP API (ADR 0009/0011) so no request-count SLI applies. Freshness (`market_data_seconds_since_last_tick`/`market_data_stale_feed`, already alerted since #78) is a separate, already-real signal, not duplicated into this row | p95 via `market_data_tick_publish_latency_seconds`'s real histogram buckets (the AC #78 already required, under 2s receipt-to-publish) |
| `news-ingestor` (backlog #79, added by backlog #90/ADR 0031) | **Feed poll success rate** — `news_ingestor_feed_poll_total{outcome="succeeded"}` over total poll cycles; no business HTTP API, same reasoning as `market-data-ingestor` above | Poll-cycle duration via `tasks_scheduled_execution_seconds` (Boot's own `@Scheduled` instrumentation) — no custom histogram needed, the framework's own timer already covers "how long did one poll cycle take" |
| `sentiment-analyzer` (backlog #80, added by backlog #90/ADR 0031) | **Consume/publish success rate** — `1 - (sentiment_analyzer_consume_errors_total + sentiment_analyzer_publish_errors_total) / sentiment_analyzer_articles_consumed_total`, the two real, distinct failure modes that service's own `metrics.py` docstring names | p95 via `sentiment_analyzer_scoring_duration_seconds`'s real histogram (VADER scoring latency, the AC's own stated minimum metric) |
| `aggregator` (backlog #81, added by backlog #90/ADR 0031) | non-5xx rate on `GET /aggregates`/`GET /aggregates/{ticker}` (`http_server_requests_seconds_count{uri=~"/aggregates.*"}`, excluding `/actuator/*` same as every other service's own row) **and** the pipeline freshness SLO backlog #91 adds on top of this row once built (event-time→serve-time lag, not covered here — this row is aggregator's own request-serving health, a different question) | p95 via `http_server_requests_seconds_bucket`; state-restore duration (`aggregator_state_restore_duration_seconds`, already real, the metric #81's own AC required) is the saturation-adjacent signal for the ~45s restart window, not a latency SLI in the request sense |

Error budgets and exact thresholds are set from each service's real
current traffic/latency distribution once the histogram/lag metrics
are live — not picked in the abstract in this ADR.

### Alerting mechanism

- **Prometheus's own `serverFiles.alerting_rules.yml` values key, not a
  `PrometheusRule` CRD.** Consistent with ADR 0014's rejection of the
  Prometheus Operator for the same reason: no Operator-managed CRD
  surface for a single static Prometheus instance.
- **Alertmanager is enabled** (`argocd/apps/prometheus.yaml`'s
  `alertmanager.enabled` flips from `false` to `true`) with a minimal,
  default receiver — **no external notification channel (Slack, email,
  PagerDuty) is wired up yet**, stated openly rather than assumed away.
  Alerts are visible in Alertmanager's own UI and Grafana's alerting
  view; a real notification channel is real, useful follow-on work but
  isn't what makes an alert exist or a runbook meaningful, and nothing
  here should block on picking one. Revisit when there's an actual
  destination (a Slack workspace, a personal on-call phone) worth
  wiring up.
  - **Correction, found implementing #21/#21c for real**: that
    "revisit" trigger came due almost immediately — an Alertmanager
    with no receiver notifies no one, which is a real, avoidable gap
    for a single-operator project, not a hypothetical one. `ntfy.sh`
    was picked over Slack/Discord/Telegram/PagerDuty specifically
    because it needs zero account/credential setup (a random,
    never-registered topic name is the entire "auth" model) — every
    alternative above requires creating an account or an app/bot
    first. Alertmanager has no native `ntfy` receiver type; wired via
    a plain `webhook_configs` entry pointed at
    `https://ntfy.sh/<topic>`. Verified live before committing to this
    shape (not assumed from ntfy's docs): POSTing an
    Alertmanager-shaped JSON blob to a topic-suffixed ntfy URL returns
    `200` and delivers a real push notification whose body is that raw
    JSON — readable, not prettified; a templating relay in front of
    ntfy for nicer formatting is real, useful follow-on work, not
    needed for the "does a real notification arrive" bar #21c sets. A
    minimal severity-routing tree exists (a `critical` route with
    tighter `group_wait`/`repeat_interval`) but shares the same single
    receiver for v1, per backlog #21c's own "don't over-engineer
    routing #21b's burn-rate work will refine later" scope.
  - **Second correction, found writing #21's actual alert rules**:
    two of the SLO table's clinvar-service rows needed a metric
    dimension #21a's shipped metrics don't have.
    `clinvar_lookup_duration_seconds` (latency only, no status label)
    can't support a non-5xx-rate alert — shipped without one rather
    than alerting against a signal that isn't there, tracked as
    backlog #21e. `clinvar_ingestion_duration_seconds_count`
    increments on both success and failure (its `.time()` wrapper
    sits around `_do_ingest` regardless of outcome), so the freshness
    alert that did ship (`ClinVarIngestionFreshnessBreach`) can only
    detect "no attempt in 8 days", not this section's own "time since
    last *successful* ingestion" — also tracked as #21e, not silently
    passed off as the real thing.

### Runbooks (backlog #22)

One Markdown file per alert in `observability/runbooks/`, named after
the alert (`observability/runbooks/<AlertName>.md`), each documenting:
what fired, what it means, first response steps, and how to confirm
resolution. `ClinVarInvalidationLag` (backlog #29, already named)
becomes the first of these; every alert from #21's table above gets
one at ship time, matching the `observability-engineer` persona's own
rule ("never ships ... an alert without a runbook") literally, not just
in spirit this time.

### Backlog #27/28/29 reconciliation (ADR 0018 → ADR 0019 drift)

- **#27** ("shared RWX PVC, `workers` becomes stateful") is fully
  superseded by ADR 0019 — `clinvar-service` got its own PVC/namespace/
  Postgres instead, and `workers` was reverted to stateless. Closed as
  superseded, no replacement item; the actual provisioning already
  shipped in a different shape (platform#36/#38).
- **#28** (release-ID trace propagation) stays open, rescoped: the
  release ID now needs to ride the HTTP boundary between `api` and the
  separate `clinvar-service` Python/FastAPI process (the project's
  first Java↔Python trace stitch), not a shared in-process read. Verify
  live, not assumed, that FastAPI's OTel instrumentation actually
  propagates W3C `traceparent` end to end before declaring this done.
- **#29** (dashboard + `ClinVarInvalidationLag` alert) stays open,
  rescoped: needs `clinvar-service`'s own new golden signals (above)
  alongside `api`'s existing Redis cache view — two separate signal
  sources, not one — and the alert's failure surface is "did
  `clinvar-service`'s Kafka publish happen, did `api`'s consumer drain
  it," since `clinvar-service` now owns the diff/publish step
  end-to-end (ADR 0019), not `api` recomputing anything.

### Seventh chaos scenario (backlog #23)

`clinvar-service`'s dedicated Postgres/PVC (own namespace, node-pinned
`local-path` volume, ADR 0019) is a failure domain none of the original
six scenarios touch. Added as scenario 7: `clinvar-service`'s Postgres
or PVC made unavailable during a live `/variants/lookup` call, proving
the failure degrades that path only (`work-items` unaffected) and that
the node-pinned PVC's known consequence — it cannot be rescheduled onto
another node — is observed directly, not assumed.

## Consequences

- Three `services`-repo PRs land before any alert rule references a
  percentile or a lag value: histogram buckets + consumer-lag metric
  (Java, `gateway`/`api`/`workers`), and `clinvar-service`'s metrics
  module from scratch (Python). Dashboards (ADR 0017) get updated in
  the same wave to plot the real values instead of the stated
  average/max and thread-pool proxies.
- Alertmanager exists with no real destination for a notification yet
  — an accepted, explicit gap for a single-operator home-lab project,
  not a silently incomplete rollout.
- `observability/runbooks/` stops being an empty scaffold; each new
  runbook is written against a real, already-firing alert, not
  speculatively ahead of one.
- #27 closes; #28/#29 continue under ADR 0019's actual architecture
  instead of ADR 0018's superseded one.
- gnomAD enrichment, the ClinVar ingestion endpoint's synchronous
  request shape, and Cloudflare Tunnel/public DNS exposure are all
  explicitly parked behind this milestone — real, tracked, not
  forgotten, but M4 goes first per the converged five-persona survey.
