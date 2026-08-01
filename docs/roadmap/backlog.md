# Backlog

Grouped by epic within each milestone. No implementation detail —
that's decided when the issue is picked up (Understand → Design in
`.claude/WORKFLOW.md`). Priority: P0 (blocking milestone), P1 (needed for
milestone), P2 (nice to have, can slip).

Labels shown are from `.github/labels.yml`.

---

## M0 Foundation

### Epic: Org & Repo Bootstrap

**1. Bootstrap GitHub organization structure**
- Purpose: Repos, labels, milestones, and project board exist and match this plan.
- Acceptance Criteria: 4 repos created; labels synced from `labels.yml`; 5 milestones created; 1 project board with 5 columns.
- Dependencies: none.
- Priority: P0. Labels: `epic`, `platform`.

**2. Define contribution guide and coding principles**
- Purpose: Contributors (human or agent) know the workflow and PR expectations before opening the first PR.
- Acceptance Criteria: `CONTRIBUTING.md` published; linked from every repo's README.
- Dependencies: #1.
- Priority: P0. Labels: `documentation`.

### Epic: Documentation Foundation

**3. Establish documentation structure and ADR process**
- Purpose: Every repo has a place for architecture notes, decisions, and runbooks before any code exists.
- Acceptance Criteria: `docs/` tree created in `adamastorx`; ADR template and seed ADR published; process documented in `docs/adr/README.md`.
- Dependencies: #1.
- Priority: P0. Labels: `documentation`, `architecture`.

**4. Write initial architecture overview**
- Purpose: A single diagram/doc anyone can read to understand the target shape of the system before M1 work starts.
- Acceptance Criteria: `docs/architecture/overview.md` reviewed and merged; covers repo boundaries and data flow at a glance.
- Dependencies: #3.
- Priority: P1. Labels: `architecture`, `documentation`.

---

## M1 Platform Bootstrap

### Epic: Cluster Foundation

**5. Provision k3s cluster via Terraform**
- Purpose: A running, reproducible cluster is the prerequisite for everything else in M1/M2/M3.
- Acceptance Criteria: `terraform apply` from `platform` repo produces a healthy k3s cluster; state is versioned; destroy/recreate is proven to work.
- Dependencies: #1.
- Priority: P0. Labels: `platform`.

**6. Bootstrap ArgoCD as GitOps entrypoint**
- Purpose: All further cluster changes flow through Git, not manual `kubectl apply`.
- Acceptance Criteria: ArgoCD installed and watching `platform` repo; an app-of-apps pattern documented; one trivial app synced end to end as proof.
- Dependencies: #5.
- Priority: P0. Labels: `platform`.

**7. Deploy Traefik ingress and cert-manager**
- Purpose: Services can be exposed with valid TLS without hand-rolled certs.
- Acceptance Criteria: Traefik routes external traffic to a test service; cert-manager issues and renews a certificate automatically.
- Dependencies: #6.
- Priority: P1. Labels: `platform`, `security`.

### Epic: CI/CD

**8. GitHub Actions CI pipeline skeleton**
- Purpose: Every PR gets automated build, test, and lint feedback before review.
- Acceptance Criteria: Workflow runs on PR for `services` and `platform`; failing build/lint blocks merge.
- Dependencies: #1.
- Priority: P0. Labels: `enhancement`.

**9. Container build and publish workflow**
- Purpose: Merged changes produce a deployable artifact automatically.
- Acceptance Criteria: Image built and pushed to a registry on merge to main, tagged with commit SHA.
- Dependencies: #8.
- Priority: P1. Labels: `enhancement`.

**10. Add Trivy security scanning to CI**
- Purpose: Known-vulnerable images/dependencies are caught before deploy, not after.
- Acceptance Criteria: Trivy scan runs in CI; build fails on critical/high CVEs with no override without explicit acknowledgement.
- Dependencies: #9.
- Priority: P1. Labels: `security`.

---

## M2 Distributed Application

### Epic: Core Services

**11. Scaffold Spring Boot gateway service**
- Purpose: A single entrypoint for external traffic into the application.
- Acceptance Criteria: Service builds, has a health endpoint, deploys via the M1 pipeline.
- Dependencies: #7, #9.
- Priority: P0. Labels: `backend`.

**12. Scaffold Spring Boot API service**
- Purpose: Core business-logic service the gateway routes to.
- Acceptance Criteria: Service builds, has a health endpoint, deploys via the M1 pipeline, reachable through the gateway.
- Dependencies: #11.
- Priority: P0. Labels: `backend`.

**13. Integrate Kafka (KRaft) messaging between services**
- Purpose: Async communication path between API and workers, the core "distributed systems" challenge of the project.
- Acceptance Criteria: A message produced by API is consumed by a worker; consumer group behaviour documented.
- Dependencies: #12.
- Priority: P1. Labels: `backend`. **Done** (services#3, ADR 0011) — produce/consume and multi-replica rebalance both proven against the real cluster.

**14. Integrate PostgreSQL persistence layer**
- Purpose: Durable state for the API service.
- Acceptance Criteria: API reads/writes to PostgreSQL; schema migrations are versioned and repeatable.
- Dependencies: #12.
- Priority: P1. Labels: `backend`. **Done** (services#4, ADR 0012) — JPA + Flyway, real PVC, proven against the real cluster.

**15. Integrate Redis caching layer**
- Purpose: Reduce load on PostgreSQL for hot-path reads — *only if a concrete hot path actually needs it*. Not a reason to add Redis by itself; the approved-stack list names the tool, not an obligation to use it without a measured need.
- Acceptance Criteria: A specific, measurable hypothesis is written *before* implementation (which read, expected hit ratio, staleness tolerance) — see services#5 for the current draft. Once implemented: a defined cache-aside path exists for that read; hit/miss ratio is an observable metric; invalidation strategy is documented; the read path's behaviour on a Redis outage (fail open to Postgres, not fail the request) is explicit and tested.
- Dependencies: #14.
- Priority: P2. Labels: `backend`.

**16. Transactional outbox / idempotent consumer for `work-items`** — Done (ADR 0026, decided and landed while building #53, which is the item that gave it a real reason). Outbox-table-plus-relay chosen over idempotent-consumer-plus-retry, with the rejected alternative's reasoning recorded in the ADR (an inline idempotent-consumer design can't cleanly support #53's own per-subscriber dead-lettering without becoming the outbox approach anyway). `WorkItemOutboxService` persists the `work_items` row and an `outbox_events` row in one transaction; `OutboxRelay` independently publishes and marks it published via `TransactionTemplate` (not `@Transactional` on a self-invoked helper method — the same Spring AOP self-invocation bug found live in watchlist-service's identical relay was fixed here proactively, see ADR 0026's addendum). `WorkItemOutboxFailureIntegrationTest` forces every publish attempt to fail (unreachable broker) and proves the work item and its outbox row both survive. ADR 0012's consequences section updated. Compiles clean; not executed locally this session (no Docker available in the agent's environment) — CI's real Testcontainers run is what actually proves it on merge, see the services PR.
- Purpose: Close a known consistency gap — `api` currently persists to PostgreSQL then calls `KafkaTemplate.send()` as two independent operations (flagged as an explicit, deliberate gap in ADR 0012, not an oversight). A Kafka publish failure after a successful database commit leaves a `work_items` row that `workers` never sees; a broker hiccup, not a code bug, is enough to trigger it.
- Acceptance Criteria: A design decision (ADR) between at least an outbox-table-plus-relay approach and an idempotent-consumer-plus-retry approach, with the rejected alternative recorded; a reproducible failure test that forces a publish failure after a committed save and proves no work item is silently lost; the fix documented in ADR 0012's consequences once landed.
- Dependencies: #14.
- Priority: P2. Labels: `backend`.

---

## M3 Observability

Starts once its own items' dependencies clear, not once M2 is fully
closed — see `docs/roadmap/milestones.md`. #17 only depends on Kafka
(#13, done), so it can run in parallel with #15/#16.

### Epic: Telemetry

**17. Instrument services with OpenTelemetry**
- Purpose: Every service emits traces, metrics, and logs in a consistent format.
- Acceptance Criteria: Gateway, API, workers all export OTel data; a single trace can be followed across all three.
- Dependencies: #13.
- Priority: P0. Labels: `observability`.

**18. Deploy Prometheus and Grafana**
- Purpose: Metrics are collected and visualisable, without long-term/multi-tenant storage this single-node cluster doesn't need yet.
- Acceptance Criteria: Metrics from #17 queryable in Grafana via Prometheus; retention policy documented.
- Dependencies: #17, #6.
- Priority: P0. Labels: `observability`.

**18a. Mimir — treat as a separate experiment, not a dependency of #18**
- Purpose: Long-term/multi-tenant metrics storage is a real capability worth learning, but nothing here needs it yet — one node, one tenant, no retention requirement beyond "recent." Bundling it into #18 would gate basic dashboards on infrastructure the AC doesn't actually call for.
- Acceptance Criteria: A standalone write-up/PoC evaluating Mimir specifically (what it adds over Prometheus's own storage at this scale, what it costs to run), done whenever there's an actual question it answers — not scheduled as a prerequisite for #18/#19.
- Dependencies: #18.
- Priority: P2. Labels: `observability`.

**19. Deploy Loki and Tempo for logs and traces**
- Purpose: Logs and traces are centrally queryable and correlated with metrics.
- Acceptance Criteria: Logs from all services in Loki; traces from #17 in Tempo; Grafana can pivot from a trace to a log line and back.
- Dependencies: #18.
- Priority: P1. Labels: `observability`.

**19a. Prometheus exemplars — metric-to-trace pivot, treat as a separate follow-up to #19**
- Purpose: #19's original "metric to trace" pivot needs exemplars — a Prometheus sample carrying the trace ID active when it was recorded — which needs native histograms/OpenMetrics scraping and a Micrometer exemplar bridge on all three services, none of which exists yet. Deploying Loki/Tempo and wiring the trace↔log pivot (#19) doesn't need this; bundling it in would gate a working two-way pivot on a separately-scoped app-level change.
- Acceptance Criteria: A Prometheus panel showing request latency has an exemplar linking a sample to its Tempo trace, verified for at least one service.
- Dependencies: #19.
- Priority: P2. Labels: `observability`.

**20. Build baseline Grafana dashboards for golden signals**
- Purpose: Latency, traffic, errors, saturation are visible at a glance for every service.
- Acceptance Criteria: One dashboard per service covering the four golden signals; dashboards are code (provisioned, not click-built).
- Dependencies: #19.
- Priority: P1. Labels: `observability`.

---

## M4 Reliability

### Epic: SRE Practices

**21a. Real histogram/lag/clinvar metrics — prerequisite for #21, not a repeat of ADR 0017's deferred gap**
- Purpose: ADR 0017 shipped golden-signal dashboards with two named, deliberately-deferred gaps (no true latency percentiles — average/max only, no `_bucket` series; `workers`' saturation panel uses thread-pool usage as a stated proxy, no real Kafka consumer-lag metric) and `clinvar-service` (ADR 0019) has zero Prometheus metrics at all. Writing SLOs (#21) against a stand-in instead of the real signal would pick thresholds against the wrong number. ADR 0020 makes this the deferred follow-up, due now.
- Acceptance Criteria: `management.metrics.distribution.percentiles-histogram.http.server.requests` (and the `spring.kafka.listener` timer equivalent) enabled on `gateway`/`api`/`workers`, giving a real `histogram_quantile(0.95, ...)`. `workers` gets a real consumer-lag metric via explicit `KafkaClientMetrics(consumer).bindTo(meterRegistry)` registered against its hand-built `ConsumerFactory` (Boot's auto-configured Kafka metrics binder doesn't apply here, same reason `spring.kafka.listener.observation-enabled` was already a no-op, ADR 0011). `clinvar-service` gets a `/metrics` endpoint (`prometheus_client`) exposing an ingestion-duration histogram, an `in_progress` gauge, a counter on the 409 concurrent-rejection path (services#36), and a lookup-latency/count histogram. ADR 0017's three dashboards updated in the same wave to plot the real values instead of the stated average/max/thread-pool stand-ins.
- Dependencies: #20.
- Priority: P0. Labels: `backend`, `observability`.

**21. Define SLOs and alerting rules**
- Purpose: "Healthy" is defined numerically, and alerts fire on the definition, not on vibes.
- Acceptance Criteria: One SLO per service (ADR 0020's table): `gateway`/`api` non-5xx rate + p95 latency (`api` additionally on `GET /variants/lookup` specifically, its own external-dependency failure mode); `workers` listener-error rate + consumer-lag threshold (not latency — a queue consumer's saturation signal is backlog depth); `clinvar-service` lookup non-5xx rate + p95, plus an ingestion-freshness SLO (time since last successful ingestion exceeding the scheduled cadence) and an ingestion-duration-anomaly alert (a run taking several multiples of the ~90s real-data baseline — the exact signal that would have made the double-ingestion incident visible as a metric instead of a `kubectl logs --previous` read after the fact). Alertmanager enabled (`argocd/apps/prometheus.yaml`), alert rules via Prometheus's own `serverFiles.alerting_rules.yml` (no Operator/CRD, ADR 0014's precedent). No external notification channel (Slack/email/PagerDuty) wired up yet — stated openly as deferred, not silently incomplete; alerts visible in Alertmanager's/Grafana's own alerting views for now.
- Dependencies: #21a.
- Priority: P0. Labels: `observability`.

**21b. ~~Error-budget policy and multi-window burn-rate alerts~~ — CLOSED, simplification (ADR 0021)**
- Multi-window burn-rate alerting is an enterprise/multi-team ritual for detecting a slow-burning error budget across shared, externally-generated traffic. On a single-operator project whose traffic is self-generated (manual/test requests, not real users), there is no budget to unknowingly burn — #21's per-SLO threshold alerts are already the right altitude for this project's actual scale. Closed rather than built as unearned complexity.

**21c. Wire Alertmanager to a real notification channel with severity routing**
- Purpose: ADR 0020 enabled Alertmanager but shipped it with no external receiver, stated openly as deferred rather than assumed away — an alert today is only visible to someone already looking at Alertmanager's or Grafana's own UI, which defeats the point of alerting for a project with no one watching a dashboard continuously. ADR 0020 names a real destination as the only thing blocking this, not a design question.
- Acceptance Criteria: Alertmanager's config gets one real receiver — a free destination (ntfy topic, Discord webhook, or Slack incoming webhook) reachable from the cluster — plus a severity-based routing tree (e.g. a `page`-equivalent severity routes to the real destination immediately, a `warning` severity batches/dedups) so noise doesn't drown a real page. At least one alert from #21's table is verified firing end-to-end into the chosen destination live, not just config-reviewed.
- Dependencies: #21.
- Priority: P1. Labels: `observability`.

**21d. Node-disk / PVC-growth capacity alert**
- Purpose: every PVC on this cluster (both Postgres instances, Loki, Tempo, `clinvar-service`'s refdata) uses the `local-path` StorageClass, confirmed to enforce no storage quota — a PVC's `resources.requests.storage` is advisory only, not an enforced ceiling, so unbounded growth on any one of them silently eats the single node's real disk with no warning. Nothing in #21's per-service SLO table watches this, since it's a node-level signal, not a per-service one.
- Acceptance Criteria: a node/PVC disk-usage alert (whichever metric is already scraped — node filesystem or PVC-level) fires with real lead time before the node's disk actually fills, added to #21's `alerting_rules.yml`; routed through #21c's destination once that lands, but not blocked on it — visible in Alertmanager/Grafana meanwhile. Runbook per #22's convention.
- Dependencies: #21.
- Priority: P1. Labels: `observability`, `platform`.

**21e. Status-labeled request/success counters for clinvar-service's lookup and ingestion paths**
- Purpose: #21 implements ADR 0020's SLO table against clinvar-service's real metrics (#21a) everywhere those metrics actually support it — but two of that table's rows turned out to need a metric dimension #21a didn't add, found while writing #21's alert rules against a live Prometheus, not assumed from the ADR text. `GET /internal/clinvar/lookup`'s non-5xx rate SLI needs a status/outcome label on a request counter; the shipped `clinvar_lookup_duration_seconds` histogram (`app/metrics.py`) records latency only, with no status split, so there is no real signal to alert a non-5xx rate against yet — #21 ships without that specific alert rather than faking one against data that doesn't exist. Separately, the ingestion-freshness SLI's "time since last *successful* ingestion" (ADR 0020's own wording) needs a success-labeled counter distinct from `clinvar_ingestion_duration_seconds_count`, since that histogram's `.time()` wrapper (`app/ingestion.py`) increments on both the success and failure paths alike — #21's `ClinVarIngestionFreshnessBreach` alert ships anyway, with this exact limitation stated in its own rule comment: it can only detect "no ingestion attempt at all in 8 days", not "attempts happened but every one failed".
- Acceptance Criteria: `clinvar-service` gets a status-labeled lookup-outcome counter (e.g. `clinvar_lookup_requests_total{status=...}`) and a success-only ingestion signal (a counter or a last-success-timestamp gauge, not reusing the duration histogram for this). Both confirmed as real series on a live `/metrics` scrape before `#21`'s deferred `ClinVarLookupHighErrorRate` alert is written and before `ClinVarIngestionFreshnessBreach`'s expression is corrected to key off successful runs specifically.
- Dependencies: none — can start independently of #21b/#21c/#21d.
- Priority: P1. Labels: `backend`, `observability`.

**22. Write incident response runbooks**
- Purpose: Whoever's on call for an alert has a documented first response, not a blank page.
- Acceptance Criteria: One runbook per alert defined in #21, living in `observability/runbooks/`, each covering what fired/what it means/first response/how to confirm resolution.
- Dependencies: #21.
- Priority: P0. Labels: `documentation`, `observability`.

**23. Chaos / failure-injection test plan — Done (3/3)**
- Purpose: Confidence that the alerts and runbooks actually work, proven before a real incident does it for us — and a source of real evidence (logs, metrics, screenshots) for writeups, not a narrative constructed after the fact.
- Acceptance Criteria (trimmed to three scenarios, ADR 0021/S6 — the original seven's scenarios 4-7 re-exercised the same "does an alert fire and route correctly" muscle without a genuinely new SRE signal): each of the three below produces a signal, a dashboard, an alert, a runbook, proof of the fault injection, proof of recovery, and a fact pack (commands run, timestamps, screenshots) usable for an article:
  1. **Kafka broker unavailable (produce/consume path) — DONE, live, `observability/chaos/01-kafka-broker-unavailable.md`.** Ran real, unscripted: ArgoCD's selfHeal auto-reverted the fault in ~2 minutes (unprompted), which meant no existing alert actually fired (none are tuned for a brief outage under this project's low manual-test traffic) — a real, honestly-reported gap, not papered over, tracked as new #42. Also found `WorkItemProducer`'s Kafka publish isn't actually non-blocking under a metadata-unavailable topic (a real ~60s synchronous block, not the silently-swallowed failure previously assumed) — tracked as new #43. Recovery proven: topics recreated, a real produce→consume cycle completed in 1s.
  2. **PostgreSQL unavailable — DONE, live, `observability/chaos/02-postgresql-unavailable.md`.** Took two attempts: the first self-healed in 16s before it could be observed, revealing that `root`'s own selfHeal reverts a live-patched child Application's sync policy just as fast as it reverts workload drift — no live pause is possible on this nested app-of-apps setup, only a real git-committed one (a second, real PR to remove `postgresql`'s `automated` block, tested, then reverted by a follow-up PR). With a genuine outage window: a real ~30s HikariCP-timeout hang before 500 (mirroring Kafka's blocking pattern from scenario 1), a confirmed readiness-probe blind spot (Boot's readiness group excludes the DataSource indicator by design, so Kubernetes never stopped routing traffic to the degraded pod), and — with ~6 minutes of real sustained failing traffic generated — `ApiHighErrorRate` fired for the first time ever on this cluster, with a real notification confirmed delivered to the live `ntfy.sh` topic. **"PVC full" dropped from this scenario, found untestable**: `local-path`'s "2Gi" PVC request is unenforced, the real underlying mount is the node's shared 173GB-free disk, and deliberately filling that risks the whole node, not just Postgres — an unacceptable blast radius, reported as a finding rather than attempted.
  3. **Consumer group lag (workers falling behind `work-items`) — DONE, live, `observability/chaos/03-consumer-lag.md`.** Took two attempts like scenario 2 (naive scale self-healed instantly; a real sync-pause was needed). The scenario's own planned question turned into the smaller finding: `WorkersConsumerLagHigh` never fired — not a rule bug, but a real structural gap (tracked as new #76) — its lag metric is self-reported by the consumer's own JVM, so it goes completely dark (no Prometheus target at all) exactly when the consumer is fully stopped, the one case its own alert description already tells a human to check by hand. The bigger, unplanned finding: Kafka itself OOMKilled during the outage window (real, timestamp-aligned evidence — restart count 47→48, `OOMKilled`, crash window entirely inside the fault window), a real broker instability under an accumulating, unconsumed backlog that this project had never encountered — not cleanly isolated from a temporarily-elevated traffic rate used to make the test tractable, so tracked as new #75 for a clean re-run rather than overclaimed here. `workers` restored early (7m01s into the outage) once this was noticed, prioritizing cluster stability over completing the originally-planned 10-minute sustained-lag window; real backlog drain observed (a genuine catch-up burst in `workers`' own logs), no data loss (Kafka's own offset-commit model gives at-least-once delivery across the restart for free), Kafka topics survived (container-level OOM-restart, not a Pod reschedule, so `emptyDir` was never torn down).
- Dependencies: #22.
- Priority: P1. Labels: `observability`, `platform`.

**44. Add readiness-probe design decision note: Boot excludes downstream dependencies by default**
- Purpose: chaos scenario 2 confirmed live that `api`'s readiness probe (`/actuator/health/readiness`) never reflected a real, sustained PostgreSQL outage — the full `/actuator/health` endpoint (which does include the DataSource indicator) correctly hung/failed, but the readiness *group* specifically excludes it. This is very likely Spring Boot's own intentional design (so one DB blip doesn't pull every replica out of rotation simultaneously) rather than a bug, but the project has never stated this as a deliberate decision — it currently reads as an unexamined default.
- Acceptance Criteria: a short, explicit decision note (ADR addendum or backlog note) stating whether this default is accepted as-is for this project's scale (single replica, so "avoid pulling every replica out of rotation" doesn't even apply here the way it would in a multi-replica fleet) or whether the DataSource indicator should be added to the readiness group given that tradeoff doesn't hold with one replica. Either answer is fine — the point is stating it, not leaving the real, measured ~30s-hang-with-no-probe-signal behavior undocumented.
- Dependencies: none.
- Priority: P2. Labels: `backend`, `observability`.

**23a. Backup and restore procedure for stateful data**
- Purpose: No stateful component has a documented or automated backup/restore path — `api`'s PostgreSQL (`work_items`), `clinvar-service`'s dedicated PostgreSQL (`clinvar_release`/`clinvar_variant_index`), Loki, and Tempo are all a single node-pinned `local-path` PVC each on the one k3s node, with no `pg_dump`, snapshot, or off-node copy anywhere. A disk failure or an accidental `kubectl delete pvc`/`helm uninstall` currently means silent, total, unrecoverable data loss with no runbook to even attempt recovery — a gap that fell through the cracks because it's nobody's specific milestone item (M2 built the databases, M4's other items are scoped to alerting/chaos, not backup) and no single persona's remit names it explicitly.
- Acceptance Criteria: A documented decision (ADR or runbook) on backup approach for at minimum the two PostgreSQL instances — a `pg_dump` CronJob writing to a second local PVC is sufficient for this project's actual stakes; explicitly stating Loki/Tempo telemetry data is *not* backed up (acceptable, since it's regenerable observability data, not source-of-truth state) is a valid answer too, as long as it's a stated decision and not a silent gap. A restore is proven at least once — into a fresh PVC/instance, with row counts verified to match, and the elapsed time for that restore recorded as a real, measured RTO (not estimated) — the node-pinned PVC's known consequence (a real game-day rehearsal of losing the whole k3s node is ceremony on a single-node laptop cluster, per ADR 0021/S7: the same "single node/disk loss is unrecoverable on-node" acceptance and the same restore-timing ask covers it without a separate exercise) is stated explicitly as an accepted risk for a personal single-node project, not an implicit, undiscussed assumption.
- Dependencies: none — can start independently of #21a/#21/#22/#23.
- Priority: P1. Labels: `platform`, `documentation`.

**23b. ~~Node-loss/DR game-day, proven restore, and an explicit accepted-risk statement~~ — MERGED into #23a (ADR 0021/S7)**
- A dedicated "kill the node" game-day is ceremony on a single-node laptop cluster where #23a already documents node-loss as an accepted risk and proves a restore. Its one genuinely distinct ask — recording a real, measured restore time rather than an estimate — is folded into #23a's own acceptance criteria above. No separate exercise needed.

**33. ~~Blameless postmortems for the three real incidents already lived~~ — CLOSED, simplification (ADR 0021)**
- Duplicates content already living in ADRs 0018/0019 and `docs/SESSION_STATE.md`. A "blameless" postmortem process exists to remove blame friction across a team; for a solo project that friction doesn't exist, so a dedicated postmortem doc is a second writeup of the same incident, not new information. The narrative value this was chasing is `#31`'s job (the top-level "what this project demonstrates" doc), not a `/postmortems` directory.

**34. ~~Capacity baseline: real load test establishing measured p95 and ingestion-duration distribution~~ — CLOSED, simplification (ADR 0021)**
- Load-testing self-generated synthetic traffic on a single laptop node measures the laptop's own ceiling, not a real capacity baseline against real user demand — there is no real demand signal here to baseline against. The ~90s ClinVar ingestion figure already cited in ADR 0020/`SESSION_STATE.md` is a real measured number from an actual production-data ingestion run, sufficient for the anomaly alert it backs; a dedicated k6/vegeta exercise adds ceremony without a new number worth having.

**35. Namespace resource governance: `LimitRange` + `ResourceQuota` + a CI check**
- Purpose: `api`/`workers` have memory limits set but no CPU limits anywhere in their manifests today, except `clinvar-service` (`platform/kubernetes/clinvar-service/deployment.yaml`, which sets both) — a runaway CPU-bound process in `api`/`workers`/`gateway` has no ceiling, and no namespace has a `ResourceQuota` capping total consumption either, on a single-node cluster where one namespace's runaway pod affects every other namespace's remaining capacity.
- Acceptance Criteria: a `LimitRange` per namespace defaulting a CPU limit for any container that doesn't set one explicitly; a `ResourceQuota` per namespace bounding total CPU/memory request+limit; a CI check (`platform` repo) that fails a PR introducing a container manifest with no CPU/memory limit, rather than relying on manual review — the gap this item exists to close was only found by an external review, not caught earlier.
- Dependencies: none.
- Priority: P1. Labels: `platform`.

**36. Remove Secret non-idempotency at the root: `existingSecret` migration**
- Purpose: platform#34 (Postgres Secret regeneration, confirmed recurring twice — see `docs/SESSION_STATE.md`) was patched with `spec.ignoreDifferences` (platform#40) on each affected Bitnami chart's generated Secret (`postgresql`, `redis`, `clinvar-postgresql`, `kafka`) — a workaround that stops ArgoCD from fighting the drift in its diff view, not a fix for the drift's actual cause (`common.secrets.passwords.manage`'s reuse-idempotency depends on a live-cluster Helm `lookup()` that ArgoCD's `helm template` rendering never performs, per `SESSION_STATE.md`'s "suspected but unconfirmed cause"). The root cause is still live; only its visibility to ArgoCD was suppressed.
- Acceptance Criteria: all four charts migrated from chart-generated passwords to a pre-created Kubernetes Secret referenced via each chart's `auth.existingSecret` (or equivalent) value, removing the chart's ability to generate or regenerate a password at all. Once migrated, the `ignoreDifferences` blocks platform#40 added are removed as no longer needed, not left in place redundantly. If this changes how Secrets are provisioned/rotated meaningfully, a small ADR recording the decision may be warranted — noted here for whoever picks this up, not written as part of this item.
- Dependencies: none.
- Priority: P1. Labels: `platform`, `security`.

**37. Rollback runbook: prove a one-command deploy rollback**
- Purpose: every deploy path (an image-tag bump merged, ArgoCD syncing it) is documented and exercised constantly; the reverse — rolling a bad deploy back — has never been proven end to end, and is exactly the action needed under real incident pressure, not the moment to be discovering the steps for the first time.
- Acceptance Criteria: a runbook (`observability/runbooks/` or the `platform` repo) documenting the actual one-command rollback path (reverting the image-tag-bump commit and letting ArgoCD sync, or `argocd app rollback`) for at least one service; timed once for real against the live cluster, with the elapsed time recorded in the runbook as a real reference point, not an estimate.
- Dependencies: none.
- Priority: P1. Labels: `platform`, `documentation`.

---

## M5 Clinical Variant Annotation

**24. Add clinical variant annotation lookup endpoint — DONE, gnomAD dropped (ADR 0021/S3)**
- Purpose: Expose the M5 variant annotation capability from ADR 0018 — query by chrom/pos/ref/alt or rsID and get back ClinVar clinical significance. ClinVar is the sole annotation source (gnomAD enrichment dropped, ADR 0021/S3 — never built, ~7.7GB real footprint doesn't fit this single-node cluster, and it added a second data source with no new SRE/platform signal). Added alongside the existing synthetic work-item domain, not replacing it.
- Acceptance Criteria: Endpoint in `api` accepts chrom/pos/ref/alt OR rsID (mutually exclusive, not both). Response includes clinical significance and the ClinVar release identifier behind the answer. Integration test covers both lookup key styles and a not-found case, against a known variant (e.g. rs80357906, BRCA1) with an asserted expected classification. Done and verified live.
- Dependencies: #25, #26, #28.
- Priority: P0. Labels: `backend`.

**24a. ~~Rescope gnomAD enrichment to remote tabix range queries, not a full download~~ — CLOSED (ADR 0021/S3)**
- This item's own "deprioritising gnomAD entirely is an equally valid outcome" clause is now the actual decision: no gnomAD, sole ClinVar source (#24). Nothing left to rescope.

**25. ClinVar GRCh38 ingestion pipeline with release tracking**
- Purpose: Close the project's previously-flagged provenance gap — ingest ClinVar's GRCh38 VCF on a recurring schedule and persist which release (version/date, parsed from the VCF's own header, not file mtime) backs each stored record.
- Acceptance Criteria: Ingestion runs inside the existing `workers` shape (no Kubernetes Job) via an in-process scheduled trigger, downloads and tabix-indexes the VCF, records a `clinvar_release` row with header-derived `published_date` and a variant count matching the source file. A manual admin-triggered re-ingestion path exists for dev/CI. Re-ingesting a new release does not destroy provenance of previously served/cached answers. Ingestion failures are observable, not silent.
- Dependencies: #27.
- Priority: P0. Labels: `backend`.

**26. Release-aware cache invalidation for variant lookups**
- Purpose: Introduce the project's first real invalidation-on-write cache behavior. Existing caching (#15, Redis, ADR 0016) is TTL-only; variant lookups must actively invalidate when a new ClinVar release changes a cached variant's classification, not merely expire.
- Acceptance Criteria: On a completed ingestion (#25), only cache entries actually present in Redis are diffed against the new release (not a full-dataset diff) and evicted where classification changed. Invalidation-triggered eviction is a distinct, independently observable Micrometer counter from TTL expiry. Test proves a seeded stale entry is evicted immediately following a new-release ingest, verified via the counter and a live Redis check, not mocked.
- Dependencies: #25, #15.
- Priority: P0. Labels: `backend`.

**27. ~~ClinVar/gnomAD storage footprint and refresh scheduling~~ — CLOSED, superseded by ADR 0019**
- Written against ADR 0018's original design (shared RWX PVC across `api`/`workers`). ADR 0019 replaced this after two real cross-namespace bugs (a PVC, then a Postgres Secret, neither shareable across the `api`/`workers` boundary): `clinvar-service` got its own dedicated namespace, PVC, and Postgres instead of a shared one, and `workers` was reverted to stateless. The actual provisioning this item wanted already shipped, in a different shape, via platform#36/#38. Closed as superseded (ADR 0020); no replacement item needed.

**28. Release-ID propagation through OTel trace correlation**
- Purpose: Extend the existing trace-correlation path (ADR 0013/0015) so the ClinVar release behind any given answer is visible end-to-end, not just stored at the data layer.
- Acceptance Criteria (rescoped for ADR 0019, ADR 0020): the release ID now crosses a live HTTP boundary into `clinvar-service`, a separate Python/FastAPI process with its own OTel SDK — this project's first Java↔Python trace stitch. Verify live, not assumed, that FastAPI's OTel instrumentation actually propagates the inbound W3C `traceparent` end to end. Release ID surfaced as a `clinvar.release_id` span attribute (confirmed search-enabled in Tempo) and a bounded-cardinality metric tag derived from the same field, carried in the HTTP response body from `clinvar-service` rather than read from a local DB by `api`. Visible in Loki as structured metadata, same pattern as `trace_id`/`span_id`. Verified live: a real request's trace ID shows the release attribute in Tempo, pivots to the matching Loki log line, and the Prometheus counter carries the same value.
- Dependencies: #24, #25.
- Priority: P1. Labels: `backend`, `observability`.

**29. Grafana dashboard + alert: variant-lookup access pattern and invalidation correctness**
- Purpose: Give visibility into the project's first genuinely skewed cache access pattern and its invalidation-on-write behavior (#26), neither of which the existing golden-signal/TTL-only dashboards capture — and alert on the one failure mode here that's a correctness issue, not just a performance one.
- Acceptance Criteria (rescoped for ADR 0019, ADR 0020): dashboard now needs two separate signal sources, not one — `clinvar-service`'s own golden signals (#21a's new metrics: lookup latency/count, ingestion duration/freshness) alongside `api`'s existing `workItemCache`/`variantAnnotationCache` Redis hit/miss/error view. A bounded top-N-hot-keys-vs-long-tail panel (not a raw per-variant label), invalidation-event rate by reason, and cache-entry-age distribution. `ClinVarInvalidationLag` alert's failure surface is now "did `clinvar-service`'s Kafka publish happen, did `api`'s consumer drain it" — `clinvar-service` owns the diff/publish step end-to-end (ADR 0019), `api` no longer recomputes anything. Every other new panel stays explicitly labeled in-panel as a stepping-stone toward #21, matching the precedent #20 already set. Verified with real synthetic traffic shaped like each domain, and a staged invalidation failure confirmed to fire the alert inside the window.
- Dependencies: #26, #21a.
- Priority: P1. Labels: `observability`.

**38. Fix `find_coordinates_by_rsid`: `LIMIT 1` silently drops alternate matches (real bug, not an enhancement)**
- Purpose: a real correctness bug found by review, not a feature request — flagged and prioritized accordingly, distinct from the enhancement items around it. `services/clinvar-service/app/repository.py`'s `find_coordinates_by_rsid` queries `clinvar_variant_index WHERE rsid = %s LIMIT 1`; an rsID that maps to more than one allele or position (a real, non-edge-case occurrence in ClinVar's data) returns one arbitrary row instead of all matches, silently discarding the rest with no error, warning, or log line — a caller has no way to know a match was dropped.
- Acceptance Criteria: `find_coordinates_by_rsid` (and its caller on the lookup path) returns every matching coordinate row for a given rsID, not just one; the API-facing response shape handles the multi-match case explicitly (e.g. a list, or a documented disambiguation rule) rather than picking silently. A regression test seeds a multi-mapped rsID and asserts every match is returned.
- Dependencies: none.
- Priority: P1. Labels: `bug`, `backend`.

**39. Query-side variant normalization (left-align/trim indels)**
- Purpose: flagged as the single highest-signal, cheap fix available in this domain — without normalization, a clinically-equivalent but differently-represented indel query (unaligned/untrimmed against ClinVar's own internally-normalized representation) produces a false-negative 404 rather than the correct match, a real correctness gap disguised as a missing-data result.
- Acceptance Criteria: incoming `(chrom, pos, ref, alt)` queries are left-aligned and trimmed against the reference before being matched against the tabix/index lookup, so a differently-represented but equivalent indel resolves to the same record ClinVar itself normalized to. A test proves a deliberately unnormalized query for a known indel variant returns the same result as its normalized form.
- Dependencies: none.
- Priority: P1. Labels: `backend`, `enhancement`.

**40. ~~HGVS notation support for variant lookup~~ — CLOSED, simplification (ADR 0021/S5)**
- Clinical-genomics-depth surface aimed at a clinical/bioinformatics audience, not a new SRE/platform signal. `#38` (the real rsID bug) and `#39` (indel normalization) are kept as genuine correctness work; HGVS is depth-for-depth's-sake beyond that.

**41. ~~GRCh37→GRCh38 liftover support~~ — CLOSED, simplification (ADR 0021/S5)**
- Same reasoning as `#40`: bioinformatics depth for a bio audience, no new SRE/platform signal for this portfolio's stated goal.

**30. ~~Reserve M6 — real batch/alignment pipeline (placeholder, tracking only)~~ — CLOSED, simplification (ADR 0021/S4)**
- Object-storage + batch-Job + real-alignment-pipeline depth is bioinformatics depth for a bio audience, not SRE/platform depth — extending toward it is the exact "bio coat of paint" failure mode this placeholder was originally raised to guard against. The project's distinctive polyglot/data-provenance story is already delivered by `clinvar-service` (M5); M6 would be adding domain breadth, not SRE/platform depth. Not reserved. If a real batch/object-storage need ever surfaces from an SRE angle (not a bio one), it earns a fresh ADR then, not a resurrection of this one.

---

## M6 Real Demand and Progressive Delivery

The expansion phase (ADR 0022) starts here. Every prior milestone was
built and verified against an **idle** cluster — the single most
consequential unstated assumption in the project. Both live chaos
scenarios recorded the same finding in writing: no alert fired on the
first attempt, because every rule needs a sustained window of real,
non-zero traffic this project's manual/test requests never produce
(`docs/SESSION_STATE.md`). M6 removes that assumption and then uses it:
once demand is continuous, a deploy can be *gated* on it.

Note the boundary against ADR 0021: this is not a resurrection of #34
(capacity baseline), which was correctly cut and stays cut — see #45.

**45. Continuous shaped workload generator (permanent demand, not a load test)**
- Purpose: every SLO (#21), alert rule, dashboard (#20/#29), and chaos fact pack in this project was produced against a cluster that is idle except when someone types a `curl`. Chaos scenarios 1 and 2 both recorded the consequence live: `ApiHighErrorRate` needs ~5 minutes of sustained non-zero traffic and did not fire until ~6 minutes of failing traffic was generated *by hand* on purpose. Consumer-lag (chaos scenario 3, still open) is not even meaningfully testable without a sustained produce rate. This is explicitly **not** backlog #34, closed by ADR 0021/S7 — #34 wanted a one-off k6/vegeta run to derive a "capacity baseline", which on a single laptop node measures the laptop. This item derives no number and claims no baseline; it is a permanently-running workload so that every other signal in the system has something real to measure. Stated openly: traffic you author yourself is still not user demand, which is why #21b (burn-rate policy) stays closed (ADR 0022).
- Acceptance Criteria: a small generator component (own namespace, own ArgoCD Application, deliberately the simplest thing that works — a container running a script is a valid answer; it does not need to be a Spring Boot service) drives all three real paths continuously: `POST`/`GET /work-items` (producing genuine Kafka throughput and cache hit/miss ratios), `GET /variants/lookup` against a *skewed* key distribution (a hot set of a few rsIDs plus a long tail, so #29's hot-key panel plots something real), and a configurable non-zero error/404 fraction. Request rate follows a shaped, non-flat pattern over the day (a diurnal curve or a step schedule) so dashboards show variance rather than a flat line — a flat rate teaches nothing about saturation. Rate is a single configurable value that can be turned down to near-zero without a redeploy. Generated traffic is distinguishable from real manual traffic at query time (a dedicated user-agent or header surfaced as a metric label/log field), so no dashboard or fact pack ever silently attributes synthetic load to a real request. Its own resource limits are set with the #35 cold-start lesson applied. Confirmed live: 24 hours of continuous operation with the existing golden-signal dashboards showing real, varying series, and node CPU/memory headroom recorded before and after.
- Dependencies: #21a (real histogram/lag metrics, done).
- Priority: P0. Labels: `observability`, `platform`.

**46. Progressive delivery: Argo Rollouts with an automated SLO analysis gate**
- Purpose: the project has a proven *forward* deploy path (image-tag bump → ArgoCD sync) and a proven manual rollback (#37), but no automated safety between them — and it has already been bitten by exactly what that gap allows. During the #35 resource-governance work a routine rollout sat in `CrashLoopBackOff` for **95 minutes** while the old pod kept serving traffic, because a Kubernetes rolling update's default behaviour is to leave the old ReplicaSet up: the deploy was completely stuck and nothing was visibly "down", so nothing alerted and nobody noticed until someone looked. A canary with an automated analysis step turns that silent 95-minute stall into an automatic abort with a reason attached. This composes with what already exists rather than adding a parallel stack: the analysis queries the *same* Prometheus and the *same* SLO expressions #21 already wrote, against the real traffic #45 now guarantees.
- Acceptance Criteria: Argo Rollouts installed as an ArgoCD Helm Application (`argocd/apps/argo-rollouts.yaml`, same pattern as every other platform component, ADR 0003). At least `api` migrated from `Deployment` to `Rollout` with a canary strategy; `clinvar-service` optionally follows. An `AnalysisTemplate` queries the live Prometheus for the service's own SLIs (non-5xx rate and p95 latency — the exact expressions from #21's `alerting_rules.yml`, not new ones invented for this) and fails the canary on breach. Interaction with ArgoCD's `selfHeal` is resolved explicitly and documented — a Rollout mid-canary is drift by ArgoCD's definition, and the nested app-of-apps selfHeal behaviour recorded in `docs/SESSION_STATE.md` is known to fight live changes; whatever the answer is (`ignoreDifferences`, sync options, or accepting the interaction), it is stated, not discovered later. **Proven live in both directions**: a deliberately-broken image (e.g. one that fails readiness, reproducing the #35 CrashLoopBackOff shape) is confirmed to abort the canary automatically and leave the previous version serving, with the abort reason and elapsed time recorded; a good image is confirmed to promote cleanly. A runbook covers the manual promote/abort commands, and #37's rollback runbook is updated to say which path now applies.
- Dependencies: #45 (analysis against an idle cluster proves nothing), #21.
- Priority: P1. Labels: `platform`, `observability`. **Done** (platform#65) — `api` is a `Rollout`, both directions proven live (clean promotion in 2m56s; automatic abort reproducing the exact #35 shape in 3m01s, previous pod undisturbed), selfHeal non-interaction confirmed by ArgoCD's own compiled-in `Rollout`/`ReplicaSet` defaults, `docs/runbooks/canary.md` written.

**47. Re-validate the existing alert rules under real sustained traffic**
- Purpose: chaos scenarios 1 and 2 both ended with the same honestly-reported gap — the alerts did not fire, and the stated cause was traffic volume, not the rules. That explanation was reasoned, not proven; nothing has since re-run those scenarios under conditions where the explanation would be falsifiable. Once #45 makes sustained traffic permanent, the same faults become a cheap, direct experiment: if the rules are right, they now fire unaided, and the two fact packs get a real "confirmed under load" postscript instead of an open question. If any of them still does not fire, that is a genuine rule bug that was previously hidden behind the traffic excuse.
- Acceptance Criteria: chaos scenarios 1 (Kafka broker unavailable) and 2 (PostgreSQL unavailable) re-run against the live cluster with #45's workload running, using the same fault-injection method the original fact packs document. For each: whether each alert fired, how long it took, and whether the ntfy notification arrived, appended to the existing `observability/chaos/01-*.md` / `02-*.md` files as a dated postscript rather than a new document. Any rule that still fails to fire is either fixed or has its limitation written into its own rule comment (the precedent `ClinVarIngestionFreshnessBreach` already set). #42 (Kafka availability alert) is reassessed in light of the result — it may be exactly right, or it may be unnecessary once traffic is real; either answer is recorded.
- Dependencies: #45, #42.
- Priority: P1. Labels: `observability`. **Done** (`observability/chaos/01-*.md`/`02-*.md` postscripts, 2026-07-31) — both rules fired unaided under real #45 traffic (~8m44s Kafka, ~8m13s Postgres), real ntfy notifications confirmed both times, falsifying the original "traffic volume, not the rules" hypothesis in the direction it predicted. #42 reassessed, not closed — downgraded P1→P2 below.

---

## M7 Multi-Node Substrate

The move to a dedicated desktop host is the enabling change for this
milestone — not because "more RAM is nice" but because several genuinely
distinct classes of problem are *unreachable* on one node and become
routine on three: pod scheduling and eviction, node drain and rolling
node upgrades, PodDisruptionBudgets, a CNI that is not flannel, and
replicated storage. ADR 0021/S7 called a node-loss game day "ceremony
**on a single-node laptop cluster**"; that reasoning is unchanged and
the substrate is what moves (ADR 0022).

Sequencing warning: **#23a (backup/restore) is a hard prerequisite for
this entire milestone**, not a nice-to-have alongside it. Migrating
hosts with no proven restore path is how a single-node project loses
everything it has ingested.

**48. Multi-node k3s on the dedicated host, provisioned from the existing Terraform**
- Purpose: `platform/terraform/` already provisions k3s via SSH remote-exec and its destroy/recreate cycle is proven (#5), but it has only ever produced one server node on the owner's laptop — every scheduling decision this cluster has ever made was trivially "the only node." Moving to the dedicated desktop is the natural moment to make it a real multi-node cluster (one server plus two or more agents, whether separate physical hosts, local VMs, or a mix) and to prove the reproducibility claim under conditions where it actually matters. Everything else in M7 depends on there being more than one node.
- Acceptance Criteria: Terraform variables and remote-exec extended to provision one server plus N agents, with the join token handled as a real secret rather than a hardcoded value; a `terraform apply` from scratch produces a healthy multi-node cluster with all nodes `Ready`. The full platform (ArgoCD root app-of-apps → every child Application) reconciles onto the new cluster from Git with no manual `kubectl apply` beyond the documented bootstrap step — the strongest available test of whether the GitOps claim in ADR 0003 is real. Node roles/labels documented. Cutover procedure documented in a runbook, including the restore step from #23a and how long the whole migration actually took, measured. The old single-node path stays supported (a variable, not a fork) so the laptop remains a valid target.
- Dependencies: #23a (backup/restore proven first — non-negotiable).
- Priority: P0. Labels: `platform`.

**49. Replace flannel with Cilium; enable Hubble flow observability (ADR 0023)**
- Purpose: this project has metrics, logs, traces, and (with #57) profiles, and **zero** visibility into what actually talks to what on the network. Several past incidents were exactly the shape a flow map answers immediately — the OTel collector port that was open in-process but had no Service routing to it, the doubled `/v1/traces` path 404, `clinvar-service`'s unrestricted NCBI egress. k3s's default flannel offers neither flow visibility nor a policy model worth building on, so getting either means replacing the CNI, which means a cluster rebuild — which #48 is doing anyway. ADR 0023 records the decision and, equally importantly, why the *other four* excluded tools (service mesh, Vault, Crossplane, Backstage) stay excluded.
- Acceptance Criteria: k3s installed with `--flannel-backend=none --disable-network-policy --disable-kube-proxy` via #48's Terraform; Cilium deployed as an ArgoCD Helm Application (`argocd/apps/cilium.yaml`) with Hubble and Hubble UI enabled; all existing workloads confirmed healthy afterward, including the cross-namespace paths that matter (`api`→`clinvar-service` HTTP, everything→Kafka, Alloy→Loki, Prometheus scrapes). Hubble metrics scraped into the existing Prometheus via `extraScrapeConfigs` (ADR 0014's no-Operator pattern) and Hubble UI exposed on the standard `*.local.adamastorx.test` + `adamastorx-ca` Ingress pattern. **A tested flannel-restore runbook is written and rehearsed before this is attempted, not after** — a broken CNI is the one failure here that ArgoCD cannot recover from, since nothing can reach the API server. The kernel version the eBPF dataplane requires is recorded as a real Terraform-level constraint. `docs/architecture/overview.md` gains a network-dataplane section.
- Dependencies: #48. ADR 0023.
- Priority: P1. Labels: `platform`, `observability`, `security`.

**50. First NetworkPolicies: default-deny per namespace, explicit allows**
- Purpose: ADR 0019's own correction states it plainly — no NetworkPolicy exists anywhere in `platform/kubernetes/` or `argocd/apps/`, and none was planned. Every pod can reach every other pod and the public internet, including `clinvar-service`'s unrestricted egress to NCBI. This is the largest remaining unaddressed gap in the platform, and it was left open partly because on flannel it would have been unenforced and invisible. With #49 it is both enforced and observable, which is what makes it worth doing now rather than a checkbox.
- Acceptance Criteria: default-deny ingress and egress per namespace, with explicit allows derived from **observed** Hubble flows rather than guessed from the architecture doc — the gap between the two is itself the interesting finding and is recorded. At minimum: `api`→`clinvar-service`, `api`/`workers`→Kafka, `api`→its Postgres/Redis, `clinvar-service`→its own Postgres, everything→OTel Collector, Prometheus→every scrape target, Alloy→Loki, and `clinvar-service`→NCBI (the only permitted public egress in the cluster). DNS explicitly allowed everywhere (the classic default-deny footgun — record it, since hitting it is the useful part). Each policy verified by a real denied-flow observation in Hubble, not by assuming the manifest works. A runbook entry covers "a service broke and I think it's a NetworkPolicy" using Hubble's drop reasons.
- Dependencies: #49.
- Priority: P1. Labels: `security`, `platform`.

**51. Replicated/RWX storage, and an honest re-test of ADR 0019's founding constraint**
- Purpose: every PVC here is k3s `local-path` — node-pinned, unenforced-quota (confirmed live, which is what made "PVC full" untestable as a chaos scenario), and unreplicated. On one node that was merely accepted risk; on a multi-node cluster it becomes an active scheduling constraint, because a node-pinned volume pins its pod too. Separately and more interestingly: ADR 0019 exists because a PVC could not be shared across the `api`/`workers` namespace boundary, "without real network-attached storage (NFS or equivalent), which this project doesn't run." Once this project *does* run it, that premise is testable rather than assumed — and the genuinely valuable outcome may well be confirming ADR 0019's decision was still right for reasons beyond storage (single ownership, blast radius), which is a better answer than quietly discovering it was avoidable.
- Acceptance Criteria: a replicated storage layer (Longhorn, or an NFS-backed StorageClass — whichever is chosen, with the rejected option and why recorded) deployed as an ArgoCD Application, offering both RWO with replication and a working RWX mode. At least one existing stateful component (a Postgres instance, or Loki/Tempo) migrated onto it, with its data proven intact via #23a's restore-verification method. A real capability test: a pod using a replicated volume is rescheduled to a different node and still sees its data. A short written re-assessment of ADR 0019's shared-PVC constraint — either an ADR addendum or a note in this item's closing comment — stating explicitly whether the ADR 0019 split would still be made today, and why. Backup (#23a) is re-pointed at replicated storage or explicitly stated as still-local, not left ambiguous.
- Dependencies: #48, #23a.
- Priority: P1. Labels: `platform`.

**52. Node-loss, drain, and rolling node upgrade — reopened from #23b because the substrate changed**
- Purpose: #23b was closed by ADR 0021/S7 as "ceremony on a single-node laptop cluster", and that was correct: on one node, killing the node is just killing everything, and the useful part (a measured restore time) folded into #23a. On a multi-node cluster the same exercise is the entire reason for the substrate — eviction, rescheduling, PodDisruptionBudgets, node cordon/drain, and a rolling k3s version upgrade are all real operations with real failure modes that a single node cannot produce. The reasoning of S7 is upheld, not overturned; its stated precondition no longer holds (ADR 0022).
- Acceptance Criteria: PodDisruptionBudgets defined for the components where they mean something (and explicitly *not* defined, with a stated reason, for single-replica components where a PDB would just block drains forever — that distinction is the actual lesson). A real `kubectl drain` of a worker node executed live: what got evicted, what refused to move and why (node-pinned `local-path` volumes are the expected culprit — see #51), how long the cluster took to settle, and whether any alert fired, all recorded as a fact pack in `observability/chaos/` following the existing convention. A rolling k3s minor-version upgrade across the nodes, done node by node with the cluster staying available throughout. An ungraceful node loss (hard power-off of an agent) with the recovery timeline measured — this is the one #23a's `pg_dump` restore genuinely cannot stand in for.
- Dependencies: #48, #51, #23a.
- Priority: P1. Labels: `platform`, `observability`.

**59. Istio ambient mesh, sprint 1: mTLS + ingress/egress gateway (ADR 0024)**
- Purpose: ADR 0010 states plainly "no auth between in-cluster services" as a deliberate M1 simplification, and nothing has revisited it since — every in-cluster call (`api`→`clinvar-service`, everything→Kafka/Postgres) is unauthenticated plaintext. ADR 0024 overturns ADR 0023's mesh exclusion to close that gap and to give the project a traffic-control layer (#60) it does not have. This sprint is the mesh's foundation only: ambient mode specifically (no per-pod sidecar — a per-node ztunnel plus waypoints where L7 is actually needed), chosen as the lighter and more novel-to-write-about model. Layered on **after** Cilium (#49) is proven, as its own change, so a dataplane failure is attributable to one layer, not two at once.
- Acceptance Criteria: ambient Istio installed on the Cilium cluster as an ArgoCD Helm Application (`argocd/apps/istio.yaml`, ADR 0003 pattern); existing workloads brought into the mesh with all cross-namespace paths confirmed healthy (`api`→`clinvar-service`, everything→Kafka, Prometheus scrapes, Alloy→Loki); STRICT `PeerAuthentication` enforcing mTLS mesh-wide, verified by a denied plaintext connection observed live, not assumed; an Istio ingress/egress gateway stood up. The Cilium↔Istio integration edges are worked and written down, not glossed — kube-proxy replacement stays Cilium's (ambient does not reintroduce it), and how ambient's ztunnel/waypoint dataplane sits on Cilium's eBPF datapath is documented in `docs/architecture/overview.md`'s network-dataplane section, including any real friction hit. Istio does **not** take over L7 network policy — that stays Cilium's (#50); the boundary is stated so neither is bought twice.
- Dependencies: #49 (Cilium proven first — non-negotiable, for failure attribution). ADR 0024.
- Priority: P1. Labels: `platform`, `security`, `observability`.

**60. Istio ambient mesh, sprint 2: retries, timeouts, circuit breaking, outlier detection (ADR 0024)**
- Purpose: the direct fix for the exact failure both live chaos scenarios recorded — a downstream outage does not fail fast, it hangs the calling HTTP thread for tens of seconds before erroring (~60s Kafka `max.block.ms`, `observability/chaos/01-*.md` and #43; ~30s HikariCP acquisition, `observability/chaos/02-*.md`). This is traffic *control*, not the traffic *visibility* OTel/Prometheus already provide, and it is the same problem in two languages (Java `api`, Python `clinvar-service`) — which is why a mesh solving it once at the dataplane beats a per-client, per-language fix, the argument ADR 0024 makes against ADR 0023's "handful of lines in two clients."
- Acceptance Criteria: per-route timeout, retry, circuit-breaking, and outlier-detection policy applied via Istio to at least the `api`→`clinvar-service` and the application→Kafka/Postgres paths, with an explicit timeout budget shorter than the ~30–60s hangs above. Proven live by re-running chaos scenarios 01 and 02 with the mesh in place: the caller now fails fast with a clear error instead of hanging, with before/after latency recorded as a dated postscript in the existing fact packs. Outlier detection confirmed ejecting an unhealthy endpoint under a partial-failure injection. Mesh telemetry (Istio's own metrics) scraped into the existing Prometheus, not a parallel stack.
- Dependencies: #59.
- Priority: P1. Labels: `platform`, `observability`.

**61. Istio ambient mesh, sprint 3: fault injection as a deliberate chaos exercise (ADR 0024)**
- Purpose: Istio delay/abort fault injection is a genuinely new fault-injection tool for this project — application-layer, targeted per-route, and injectable without touching the app or killing infrastructure (unlike the broker/DB kills of scenarios 01/02). ADR 0022's content goal values this kind of deliberate, controlled experiment; done as its own sprint rather than folded into #60 so the resilience policy (#60) is proven *by* the fault injection here, closing the loop.
- Acceptance Criteria: an Istio `VirtualService` fault (HTTP delay and abort) injected on a real path, with the resulting behaviour — whether #60's timeouts/retries/circuit-breaking absorb it, whether any SLO alert fires, blast radius, recovery — recorded as a fact pack in `observability/chaos/` following the existing convention. At least one injection tuned to confirm #60's circuit breaker opens as designed. Fault removed and steady state confirmed restored.
- Dependencies: #60.
- Priority: P2. Labels: `observability`, `platform`.

**62. Resolve the Argo Rollouts / Istio traffic-splitting overlap (ADR 0024)**
- Purpose: #46 installs Argo Rollouts as the progressive-delivery controller with an SLO-analysis gate; once Istio (#59) is present, both tools can independently split traffic, which is a real overlap ADR 0024 requires resolving as a stated decision rather than leaving two mechanisms fighting over the same weights. Argo Rollouts and Istio have a real, supported integration where Rollouts drives Istio `VirtualService` subset weights — Rollouts stays the *controller*, Istio becomes the traffic-management *provider*.
- Acceptance Criteria: `api`'s `Rollout` (from #46) reconfigured to use Istio as its `trafficRouting` provider (driving `VirtualService`/`DestinationRule` subset weights) instead of Rollouts' own splitting; a canary proven live to shift weight through Istio while the #46 `AnalysisTemplate` still gates on the same Prometheus SLIs. The decision recorded in #46's runbook and referenced from ADR 0024, so the trail from "two tools split traffic" to "one controls, one provides" is explicit. Interaction with ArgoCD `selfHeal` re-checked (a mid-canary `VirtualService` is drift by ArgoCD's definition), reusing #46's resolution.
- Dependencies: #46, #59.
- Priority: P2. Labels: `platform`, `observability`.

---

## M8 Application Logic: Delivery Semantics and Stream State

The owner's ask is more services and more application logic. The
constraint from ADR 0022 is that a new service must produce an
operational shape this project does not already have. Today there are
three: synchronous CRUD (`work-items`), cache-aside with
invalidation-on-write (`/variants/lookup`), and a scheduled batch
ingest. The shapes below are chosen for what is missing — guaranteed
fan-out delivery, long-running async work with an observable state
machine, and stateful stream processing with recoverable local state —
and each composes with something that already exists rather than
standing alone.

**53. `watchlist-service`: subscriptions and guaranteed fan-out on a ClinVar release change** — Done (services#45, platform#68, ADR 0026). Subscription CRUD, a second independent Kafka consumer group on `clinvar.ingestion.completed`, outbox-table-plus-relay delivery (`deliveries` table + `NotificationRelay`), per-subscriber dead-lettering, `watchlist_fanout_latency_seconds`/`watchlist_delivery_latency_seconds`/`watchlist_delivery_attempts_total`/`watchlist_delivery_dlq_depth` metrics with a Grafana dashboard, `WatchlistDlqDepthHigh` alert, ADR 0020 SLO table row, own namespace/Postgres/ArgoCD Applications. **The crash-mid-delivery AC — the acceptance criterion this item exists for — was proven live against the real cluster, not simulated**: a real image built via an in-cluster Kaniko build (no local Docker this session) and pushed to `ghcr.io/adamastorx/watchlist-service` (confirmed via the GitHub Packages API); a real subscription created; a real `clinvar.ingestion.completed` event produced on the real Kafka broker; the pod force-killed between the delivery row being durably persisted and the relay's next tick; the row confirmed to survive in Postgres, still `PENDING`. Two real bugs (both a Spring AOP self-invocation defeating `@Transactional`) were found and fixed live in the process — the second only because the first "fix" was itself re-tested live rather than trusted because it compiled — see ADR 0026's addendum. After the fix, the surviving row was delivered on restart, confirmed both in the pod's own logs and independently via the real `ntfy.sh` topic's message history (timestamp matching the delivery row's `updated_at` to the second). Idempotent redelivery was proven both live (redelivering the identical Kafka message against the real broker a second time: zero new rows, zero duplicate notifications) and by a real automated integration test (`DeliveryIdempotencyIntegrationTest`, real embedded Kafka, real fake-ntfy HTTP server). **What still needs a human check post-merge**: the live rehearsal used a hand-applied, pre-merge deployment (a `postgres:16-alpine` stand-in, not the real Bitnami chart — `helm` wasn't available locally; a manually `kubectl set image`'d Deployment, not the real ArgoCD-managed one) — see the services/platform PR descriptions for the full split of what's proven versus what a human should re-confirm once both PRs merge and ArgoCD syncs the real Applications. Gene-based subscriptions are schema-ready but not resolved against real events — no component in this project extracts a gene symbol from ClinVar's data today (see `watchlist-service/README.md`), stated as a real gap, not silently dropped.

**Post-merge finding (2026-08-01)**: the real `build-publish.yml` publish failed the first time with a 403 — the GHCR package the agent's pre-merge Kaniko rehearsal had created was never linked to the `services` repository, so the repo's own `GITHUB_TOKEN` had no write access to it. Fixed by granting the `services` repo Actions access to the package (org Packages → package settings → Manage Actions access), then re-running the publish job. Separately and more seriously: the same rehearsal briefly made the package **public**, unprompted and unauthorized, to work around an `ImagePullBackOff` — caught and reverted before merge; the correct fix (an `imagePullSecret`, since this is the project's first-ever private image) was never actually applied to the committed manifests. Deployed today with the package private and no pull secret, so `watchlist-service`'s pod is currently `ImagePullBackOff` on the real cluster — accepted, low-impact (isolated to its own namespace, `watchlist-postgresql` is up and healthy) pending a deliberate decision on the correct fix (see #74).
- Purpose: `clinvar-service` already computes, on every ingestion, the exact set of variants whose classification changed between releases (ADR 0019) and publishes them on `clinvar.ingestion.completed` — today that event has exactly one consumer, which deletes some Redis keys. That is a real, valuable event stream being used for cache hygiene and nothing else. A watchlist turns it into a delivery problem: a subscriber registers interest in a set of variants or a gene, and when a new release changes one of them, they must be notified **exactly once, eventually, even across restarts**. That is a genuinely new failure class here — fan-out on write, per-subscriber delivery state, idempotency across redeliveries, and dead-lettering a subscriber that permanently fails — none of which `work-items`' fire-and-forget or the cache's best-effort invalidation exercise. It also finally makes **#16 (transactional outbox / idempotent consumer)** matter for real: `work-items` could tolerate a lost publish because nothing downstream depended on it; a missed notification is a silently wrong answer to a user, which is exactly the pressure that makes the outbox worth its complexity instead of an academic exercise. Notification delivery reuses the ntfy channel #21c already proved works.
- Acceptance Criteria: a new service (language chosen on ADR 0019's rule — Java if it is generic request/messaging work, which it likely is, *not* Python by default) owning subscription CRUD and per-subscriber delivery state in its own namespace-local Postgres. Consumes the existing `clinvar.ingestion.completed` event; for each changed variant, resolves matching subscriptions and delivers. Delivery is idempotent and proven so by a test that redelivers the same event and asserts exactly one notification. A permanently-failing subscriber is dead-lettered rather than blocking the fan-out, with a metric and an alert. A deliberately-induced crash between "event consumed" and "notification sent" is proven not to lose the notification — this is the acceptance criterion the whole item exists for, and #16's outbox decision is made here if it has not been made already. Fan-out latency, delivery attempts, and DLQ depth are Prometheus metrics with a dashboard; a subscriber-facing SLO is added to ADR 0020's table. Traces span `clinvar-service`→Kafka→`watchlist-service`→delivery, extending the existing correlation story to a third hop.
- Dependencies: #16 (transactional outbox — this is the item that gives it a real reason), #26.
- Priority: P1. Labels: `backend`, `architecture`.

**54. Async job control plane: turn ClinVar ingestion into fire-and-poll**
- Purpose: `docs/SESSION_STATE.md` names this directly as an open fragile shape — `POST /internal/clinvar/ingest` blocks the HTTP request for the *entire* multi-minute ingestion. services#36 stopped two overlapping calls from running concurrently (409) after they took the pod down, but the underlying shape is unchanged: a long-running operation behind a synchronous request, at the mercy of every client, proxy, and Ingress timeout between the caller and the process. Making it a real job — `202 Accepted` plus a job id, an observable state machine (`queued`/`running`/`succeeded`/`failed`/`cancelled`), progress, and a poll or stream endpoint — is a new operational shape for this project: jobs orphaned by a pod restart mid-run, at-least-once execution versus at-most-once, cancellation of work already in flight, and reconciling job state with reality after a crash. **This is explicitly not a resurrection of the closed M6/#30** (ADR 0022): no object store, no alignment pipeline, no new data domain, no new bioinformatics tooling — the same ingestion that already runs, given a request shape that does not fall over.
- Acceptance Criteria: ingestion trigger returns `202` with a job id immediately; job state persisted in `clinvar-service`'s own Postgres, not in memory (in-memory state is precisely what a pod restart destroys). `GET` job-status endpoint reports state plus real progress, reusing the per-250k-record progress logging already added. A job interrupted by a pod kill is, on restart, either resumed or explicitly marked failed with a reason — never left `running` forever; a test kills the pod mid-ingest and asserts the terminal state. Cancellation supported and proven to actually stop the work, not just relabel it. The `threading.Lock` concurrency guard is either retired in favour of job-level state or explicitly retained with a reason. Job counts by terminal state exposed as metrics, and the `ClinVarIngestionFreshnessBreach` alert (and #21e's success-signal gap) re-pointed at real job outcomes — which is a strictly better signal than the duration-histogram proxy it currently uses.
- Dependencies: #21e. (The specific gap #21e names for the ingestion path — a success-only signal distinct from the duration histogram — is closed by this item's own `clinvar_ingestion_jobs_total{status="succeeded"}` metric; #21e's other half, a status-labeled lookup-outcome counter for `ClinVarLookupHighErrorRate`, is unrelated to this item and stays open.)
- Priority: P1. Labels: `backend`, `observability`. **Done** (services#46, platform#69, platform#70) — trigger returns `202` in 51ms (measured); a real ingestion against real NCBI data was force-killed mid-`running` (`kubectl delete pod --grace-period=0 --force`, caught at 4,458,175 records scanned) and confirmed reconciled to `failed` with an explicit reason on the replacement pod's startup, no abandoned release ever went active (confirmed via `GET /variants/lookup` 404 and a direct `psql` check); a second real ingestion was cancelled mid-scan (at 750,000 of ~4.46M records) and confirmed to actually stop — `recordsScanned` stayed frozen for 20+ seconds of polling after cancellation, not just a relabelled row. `threading.Lock` (services#36) retired, not kept: `clinvar_ingestion_job`'s own partial unique index is the concurrency guard now, since it — unlike the Lock — survives a pod restart. 54 tests pass (46 pre-existing + 8 new) against a real Postgres. Real image (`948ee83...`) built, deployed to the production `clinvar` namespace, and confirmed `Synced`/`Healthy` with a live `/healthz` check post-merge, closing the one gap the PR left for human follow-up.

**55. Stateful stream processing over the existing topics**
- Purpose: `workers` consumes `work-items` and logs it — after M2 that consumer has never been given a real job, and stateless consumption is a shape the project has already fully explored. Windowed, stateful stream processing is a genuinely different scaling and failure shape: local state stores, changelog topics, state restoration time after a rebalance, and the fact that a consumer's *recovery* cost is now proportional to its state rather than constant. It is also on a collision course with something this project has already documented and would have to confront honestly: ADR 0011 deliberately gave Kafka **ephemeral storage**, and `docs/SESSION_STATE.md` records all three topics silently vanishing on a broker restart. A stream processor whose durability model is "the changelog topic in Kafka" on a broker whose topics do not survive a restart is a real, concrete, non-obvious architectural conflict — and resolving it (persist Kafka, accept rebuildable state, or bound the window) is worth more than the aggregation itself.
- Acceptance Criteria: a stream processing component (Kafka Streams is the obvious fit given the existing Spring/Kafka stack; Flink is a defensible alternative if the additional operational cost is stated and accepted) computing real windowed aggregates over `work-items` and the lookup event stream — e.g. per-window request rates, hot-variant counts feeding #29's top-N panel with real data instead of a synthetic approximation — written to a queryable store or a compacted output topic. State store recovery measured for real: kill the pod, measure how long restoration takes, and record how that scales with window size. The ADR 0011 ephemeral-Kafka conflict resolved explicitly in an ADR (whichever way it goes), not discovered during an incident. Consumer lag and state-restoration duration are metrics; the existing lag alert threshold is re-evaluated now that a lagging consumer might be restoring state rather than falling behind — telling those two apart is a real on-call problem worth documenting.
- Dependencies: #45 (a stream processor over near-zero traffic aggregates nothing), #23 (done — scenario 3 also surfaced a real reason to be cautious here: Kafka is already memory-tight on this node under an accumulating backlog, see new #75; a stateful stream processor's own state stores/changelog topics add real further memory pressure on the same broker, worth weighing before starting this).
- Priority: P2. Labels: `backend`, `observability`, `architecture`.

**56. Per-tenant API keys and rate limiting at the edge (Traefik middleware, not a new service)** — Done (platform#71, services#47, ADR 0027).
Traefik middleware chain (`api-cors` → `api-key-auth` → `api-key-ratelimit`, `kubernetes/api/middlewares.yaml`) on api's real Ingress: HTTP Basic auth as the API-key mechanism (one tenant:apr1-hash line per caller in the `api-tenant-keys` htpasswd Secret), 5 req/s average / burst 10 per-key rate limiting (`sourceCriterion` on the `Authorization` header). Keys provisioned via `bootstrap/create-stateful-secrets.sh` (platform#36's existing out-of-band-Secret pattern, extended rather than a second mechanism), never committed to git. `clinvar-viewer` sends its key via a deploy-time-mounted `config.js` (stated plainly as not a confidentiality boundary — a static page has no backend to keep it out of the browser); `workload-generator` moved from in-cluster Service DNS to api's public Ingress hostname specifically so its synthetic traffic is subject to the same edge enforcement, carrying its own key via `secretKeyRef`. Traefik's Prometheus metrics (`traefik_entrypoint_requests_total`) back a new `ApiRateLimitRejectionsHigh` alert and a new `edge-auth-rate-limiting` Grafana dashboard; per-key request-rate visibility uses Loki access logs (`ClientUsername` field) instead of a Prometheus label, a deliberate cardinality-avoidance call, not an oversight. ADR 0027 (adamastorx repo) records the decision against ADR 0021's own offered path.

**Proven live against the real cluster, both directions, repeatedly (see platform PR for the full record)**: an unauthenticated request against the real Ingress got a real `401`; a request with any of the three real tenant keys (generated by the actual committed bootstrap script, not placeholders) got a real `200`/`202`; a real 20-30 request burst against one key produced a real mix of `200`/`429` (with `Retry-After`/`X-Retry-In` headers) while the mechanism was live, confirmed via `traefik_entrypoint_requests_total{code="429"}` on the real running Prometheus-compatible metrics endpoint; a browser-shaped CORS preflight (OPTIONS, `Access-Control-Request-Headers: authorization`, no credentials) got a real `200` with the right `access-control-*` headers, answered by the `api-cors` middleware before ever reaching auth — the exact failure this item's own design note flags as the gotcha that would otherwise have broken `clinvar-viewer`. `workload-generator`'s actual updated `generator/client.py` (not a mock) was run directly against the real protected Ingress from outside a container — 401 with no key, 200/202 with its real key — and the identical hostAliases + CA-ConfigMap-mount approach committed to its Deployment manifest was independently re-proven from inside a real ephemeral pod in its own namespace. Between every one of these live tests the Ingress's middleware annotation was reverted, confirmed back to unauthenticated `200`, before moving on — `api` was never left mid-test or broken at the end of the session; `workload-generator`'s continuously-running real pod was confirmed unaffected throughout (it talks to api's in-cluster Service directly today, unaffected either way, precisely the gap this item's platform PR closes).

**What still needs a human check post-merge** (both services PRs must merge and publish new images, and `platform`'s Deployment manifests bumped to those SHAs, *before* the `api` Ingress's middleware annotation actually lands and gets enforced by ArgoCD's `selfHeal` — see the exact merge-order note in the platform PR description): the real `clinvar-viewer`/`workload-generator` **container images** carrying this item's code changes were not independently built and deployed live this session (would need a real CI publish or an in-cluster pre-merge image build, out of this session's budget) — the code paths themselves were proven live outside a container (above), and unit tests (`test_client.py`'s new `Authorization`-header assertions) are added for CI to hold the guarantee under regression, but the actual `clinvar-viewer` browser flow end-to-end and the actual redeployed `workload-generator` pod's first real authenticated request are not yet confirmed against the real cluster. Traefik's `accessLog.enabled`/`addRoutersLabels` values change (per-key Loki visibility, router-level metric granularity) is schema-verified against the real chart's `values.yaml` but was deliberately not applied live this session (would trigger a second cluster-wide Traefik restart on top of the ones already exercised) — a human should confirm post-merge that `ClientUsername` actually appears in Loki and the new dashboard panel renders real data.

**Post-merge human check, done (2026-08-01)**: merged in the exact order the platform PR required (`services#47` first, real images published, both Deployment SHAs bumped, then `platform#71`). One real gap found and fixed along the way, not a new one this item introduced: `clinvar-viewer`'s Application was left `Synced` against a stale revision after `root`'s refresh (the same known nested-app-of-apps lag this project has hit before) and had to be refreshed directly before it picked up the new image — without that, its real browser traffic would have kept sending zero `Authorization` header against an already-enforcing Ingress. After that fix, confirmed live: unauthenticated request → real `401`; a real tenant key read directly from the live `workload-generator-api-key` Secret → real `200`; `clinvar-viewer`'s real, deployed `config.js` → real key present; a full simulated browser call (preflight `OPTIONS` → `200`, then the authenticated cross-origin `GET` with that exact key) → real `200` with real `/variants/lookup` data. `workload-generator`'s continuously-running pod confirmed on the new image, sending real authenticated traffic against the public Ingress with zero interruption throughout the whole merge. Traefik's `accessLog`/`addRoutersLabels` still not independently re-verified against live Loki data — left open, low-priority, not blocking.
- Dependencies: #45, #53.
- Priority: P2. Labels: `security`, `platform`, `backend`.

---

## M9 New Signal Classes

Two additions that each introduce a category of signal or control the
project has never had, both grounded in a specific incident that already
happened rather than in a tool list. Can run in parallel with M8.

**57. Continuous profiling — the pillar this stack does not have**
- Purpose: the project has metrics, logs, and traces, and one of its most instructive incidents was invisible to all three. After #35 added a 500m CPU limit to `api`, a rollout sat in `CrashLoopBackOff` for 95 minutes: `kubectl top` showed the pod pegged at 498m/500m during JVM cold start (Hibernate/Flyway/Kafka bootstrapping) while steady-state usage was ~30m. The lesson recorded in `docs/SESSION_STATE.md` — "a CPU limit sized from steady-state usage alone can starve a JVM's cold start" — was reached by inference from a single aggregate number. A continuous profiler answers *which code* burned that CPU, which is the difference between a plausible story and a demonstrated one. The same blind spot applies to `clinvar-service`'s pure-Python VCF scan (the step that took the pod down under contention, with no OOM evidence anywhere) — a CPU/memory profile of that loop is exactly the missing evidence from that incident.
- Acceptance Criteria: a continuous profiler (Pyroscope is the natural fit — it is a Grafana-stack component, so it lands as a datasource in the Grafana that already exists rather than as a separate UI) deployed as an ArgoCD Application, receiving profiles from at least one JVM service and `clinvar-service`. A real, captured flame graph of `api`'s cold start under a constrained CPU limit — the #35 incident reproduced deliberately and profiled, turning an inference into evidence. A profile of `clinvar-service`'s ingestion scan, with whatever it shows recorded honestly (including "nothing surprising"). Profile-to-trace correlation wired up if the versions in play support it; if not, stated as a gap rather than assumed. Retention and storage cost measured against the node's real disk, given `local-path`'s unenforced quota (#21d).
- Dependencies: #45 (profiles of an idle process are not interesting).
- Priority: P2. Labels: `observability`. **Done (platform#82/#83, ADR 0028)** — Pyroscope 2.2.0 (own namespace, Grafana >=12.3.0's bundled datasource, confirmed against this cluster's 12.8.0), `api`/`clinvar-service` instrumented via an unprivileged init-container agent-injection pattern (real published Java/Python SDKs fetched into a shared `emptyDir`, no rebuilt image, no privileged cluster-wide profiler — see ADR 0028 for the two rejected alternatives). Real bug found and fixed live post-merge: both init containers initially shipped with no `resources` block, which api's/clinvar-service's namespace memory `ResourceQuota`s reject outright — blocked `api`'s entire Rollout with a real `failed quota` `FailedCreate` until platform#83's fix. Once fixed, verified live: both services confirmed pushing real, continuous profiles (`pyroscope-0`'s own logs, `"profile accepted"` for `api`/java and `clinvar-service`/python every ~10s). **The #35 incident reproduced live and profiled for real**: `api`'s Rollout CPU limit temporarily set to `500m`, confirmed pegged via `kubectl top pod` (`498m/500m`, the exact original incident numbers), Argo Rollouts' `progressDeadlineAbort` (#46) caught it automatically in ~3 minutes, previous good pod never stopped serving. **The real flame graph (queried from Pyroscope's own render API for that exact crash window) does not confirm the original hypothesis** — recorded honestly: self-time is dominated by the JVM's own C2 JIT compiler internals (`PhaseChaitin::elide_copy`, `PhaseIdealLoop::build_loop_early/late`, `PhaseLive::compute`) and class-loading overhead (`SymbolTable::do_lookup`, `libzip.so.inflate_fast`), not application-level Hibernate/Flyway/Kafka bootstrap code as originally assumed — a real, demonstrated lesson that the JIT compiler's own background work competes with application startup for the same constrained CPU budget. Profile-to-trace span correlation stated as a real, unshipped gap (needs a language-specific OTel bridge package in each service's own code, out of this item's scope). Cluster confirmed left clean afterward (`api` CPU limit back to `1`, `Healthy`). Real retention/PVC-growth numbers not yet measured (needs a few real days of traffic) — left open, low-priority, not blocking.

**58. Admission-time policy enforcement, and the failure mode it introduces**
- Purpose: #35 wanted a CI check that fails a PR introducing a container with no CPU/memory limit; ADR 0021/S7 downgraded that to optional, correctly, on the grounds that a lint gate is gold-plating for a solo repo where review already catches it. An admission controller is a different proposition and worth distinguishing from that: it enforces at the cluster boundary rather than the PR boundary, so it catches things CI structurally cannot — a Helm chart's rendered output, an ArgoCD-synced upstream manifest, anything applied by hand during an incident. It also introduces a genuinely new and instructive failure mode this cluster has never had: **a validating webhook is a single point of failure in front of every write to the API server.** If the policy engine is down and `failurePolicy: Fail`, nothing deploys — including the fix. That trade-off, exercised deliberately, is the reason to do this.
- Acceptance Criteria: a policy engine (Kyverno is the lighter fit for this scale; Gatekeeper/OPA is defensible if the choice is argued) deployed as an ArgoCD Application, with a small set of policies that reflect this project's own actual lessons rather than a generic starter pack — require CPU/memory requests and limits (#35), require probes to be `httpGet` rather than `tcpSocket` where the app exposes HTTP (the ADR 0019 rollout lesson), disallow `:latest` image tags (ADR 0008's SHA-tag policy, currently convention only). Policies run in audit mode first with the existing violations reported, then enforced. **The webhook-down failure mode is deliberately exercised and documented**: scale the policy engine to zero and attempt a deploy, with the resulting behaviour, blast radius, and recovery recorded as a fact pack in `observability/chaos/`, and the `failurePolicy` choice (`Fail` vs `Ignore`) made as a stated decision with its reasoning. An alert fires if the policy engine is unavailable.
- Dependencies: #35.
- Priority: P2. Labels: `platform`, `security`.

---

## M10 Platform Automation: Elastic Scaling, Chaos, and Cost

Three platform capabilities that each gain their value once the cluster
carries real, continuous, and diverse load (#45, M12) rather than a single
idle workload — event-driven autoscaling, chaos automation, and cost
visibility. None is on the excluded-tools list; each earns its place by a
gap already recorded, per ADR 0022's rule. Can run in parallel with M8/M9.

**63. KEDA: event-driven autoscaling on Kafka consumer lag**
- Purpose: every scaling decision this project can currently make is CPU/memory-based (HPA-shaped), and `workers` — a Kafka consumer — is exactly the workload that metric fits worst: its real pressure signal is consumer-group lag (#21a added the metric), not CPU. Chaos scenario 3 (consumer-group lag, done) and #45's sustained produce rate make lag a real, varying signal for the first time. KEDA scaling `workers` on lag teaches a genuinely new Kubernetes pattern (a `ScaledObject` driving replica count from an external event source, including scale-to-zero) that HPA cannot express — and it does it against a real signal, not a synthetic one. Scenario 3's own findings are directly relevant here, not just background: a `ScaledObject` reacting to lag needs the lag metric to actually be visible at the moment it matters, and #76 found it goes dark exactly when the consumer is fully stopped (scale-to-zero territory) — KEDA's own external-metrics polling path should be checked against that same blind spot before relying on it to scale back up from zero.
- Acceptance Criteria: KEDA deployed as an ArgoCD Helm Application (`argocd/apps/keda.yaml`, ADR 0003 pattern); a `ScaledObject` scales `workers` on real Kafka consumer-group lag, proven live by driving lag up with #45's generator and observing scale-out, then scale-in as the backlog drains. Interaction with the existing lag *alert* (#21) is stated: an autoscaler reacting to lag and an alert firing on lag must not fight or double-count — the thresholds are reconciled explicitly. Scale-to-zero behaviour (and its cold-start cost, applying the #35/#57 JVM cold-start lesson) is either used with a stated reason or explicitly disabled with one — if used, explicitly re-check #76's finding (KEDA typically queries Kafka's own consumer-group offsets directly for scale-from-zero decisions, not the Prometheus metric that goes dark, but this should be confirmed against the real chart/config rather than assumed). Scaling events visible in Prometheus/Grafana.
- Dependencies: #45, #23 (done).
- Priority: P2. Labels: `platform`, `observability`. **Done (platform#80)** — KEDA 2.20.2, native `kafka` scaler (queries the broker's own committed offsets directly, confirmed to sidestep #76's dark-metric gap structurally rather than inherit it, unlike a Prometheus-backed trigger). `WorkersConsumerLagHigh`/`WorkersConsumerMissing` reconciled explicitly: KEDA reacts first at `lagThreshold: 50` (an order of magnitude below the alert's `500`/`10m`), the alert is the backstop for when KEDA's own response can't fix it. Scale-to-zero evaluated and explicitly not used (`minReplicaCount: 1`) — no kube-state-metrics on this cluster to distinguish "KEDA intentionally scaled to zero" from "a real stuck consumer" for `WorkersConsumerMissing`, stated as a real follow-up rather than shipped broken. A real, separate GitOps/HPA conflict was found and fixed along the way: `workers`' Deployment had `replicas: 1` git-tracked, which ArgoCD's `selfHeal` would have fought against every KEDA scale event — the field is now deliberately absent, ArgoCD's own documented pattern for externally-controlled replica counts. Proven live (2026-08-01): a real ~2,600-request burst (fired directly at `api`'s in-cluster Service, bypassing #56's edge rate limit deliberately for this test) drove real lag to `150` — `keda-hpa-workers` correctly computed `ceil(150/50)=3` desired replicas and requested all 3. **Real, honest finding**: only 1 of 3 actually reached `Running` — the other 2 sat `Pending` on `Insufficient cpu`, confirming the real node-capacity risk this item's own design comments flagged in advance, not discovered as a surprise. The 1 running replica alone drained the entire real backlog to `0` lag across all 3 partitions within ~90s (workers' handler is trivial — log-only), and after Kubernetes' own HPA scale-down stabilization window (~5m, not just KEDA's shorter `cooldownPeriod: 120s` — a real, worth-noting distinction from what the manifest's own comment implied), replica count correctly returned to `1`, pending pods cleanly removed. Kafka (backlog #75's new 1536Mi limit) had zero restarts throughout — a real, larger-volume validation than the original chaos scenario, though still not a clean isolated proof of #75's own root-cause question.

**64. Chaos Mesh: formalize the manual chaos exercises**
- Purpose: this project already does real chaos engineering — three live scenarios with fault packs (`observability/chaos/`), run by hand (scaling a broker/DB down, git-committing a sync-policy change). Chaos Mesh formalizes that existing practice as declarative, repeatable experiments (pod-kill, network delay/partition/loss, IO fault, time skew) rather than manual, one-off steps. This is an upgrade to territory the project already occupies, not new territory — low risk, real value: the same scenarios become re-runnable on demand (which #47 wants anyway) and gain fault types the manual method could not safely reach (a real network partition between two namespaces, distinct from Istio's app-layer fault injection #61).
- Acceptance Criteria: Chaos Mesh deployed as an ArgoCD Application; at least one existing manual scenario (01 Kafka or 02 Postgres) re-expressed as a declarative Chaos Mesh experiment and confirmed to reproduce the original finding; at least one genuinely new fault the manual method could not do safely (e.g. a `NetworkChaos` partition or delay between `api` and `clinvar-service`) run and recorded as a fact pack. The relationship to Istio fault injection (#61, app-layer) vs Chaos Mesh (infra/network-layer) stated so the two tools' scopes don't blur. Experiments are version-controlled, not click-built.
- Dependencies: #45.
- Priority: P2. Labels: `observability`, `platform`.

**65. Kubecost: cost-per-namespace / per-workload visibility, priced against real owned hardware**
- Purpose: the project has no view of what any workload actually *costs* to run — CPU/memory/storage allocated vs. used, per namespace and per workload. **Real risk stated up front, not glossed**: Kubecost's actual value normally comes from reconciling usage against a real cloud invoice; on owned hardware with no cloud bill behind it, its default posture is an *assumed* retail pricing sheet the operator makes up — synthetic numbers, which breaks this project's own real-data discipline (the same standard ClinVar's real ingestion and the chaos fact packs already hold themselves to). The fix that keeps this real: price the cluster against **actual owned-hardware TCO** — the desktop PC's purchase price amortized over its expected service life, plus real measured or spec-derived power draw, plus the operator's real electricity tariff — not Kubecost's default cloud-shaped price sheet. That reframing is also a rarer, more differentiated angle than typical cloud-FinOps content: "what does my own homelab actually cost me in real money" is a real number almost nobody publishes, versus generic cloud cost-allocation writeups. Becomes genuinely useful once there is real workload diversity (M12's bio pipelines, MinIO object storage, Nextflow Jobs) competing for the same finite host, where "which namespace is eating the node, and what does that namespace actually cost" is a real question. Standalone value even before that: it turns the #35 resource-governance work (requests/limits) from a guess into a measured allocation-vs-usage efficiency number.
- Acceptance Criteria: Kubecost (or OpenCost, if the lighter option is argued and chosen — rejected alternative recorded) deployed as an ArgoCD Application, exposed on the standard `*.local.adamastorx.test` + `adamastorx-ca` Ingress pattern, **with its pricing model explicitly overridden to real owned-hardware costs** — the desktop's amortized purchase price, a real (measured, e.g. via a plug power meter, or honestly spec-derived if not) power-draw figure, and the operator's actual electricity price per kWh — documented as real inputs, not Kubecost's default assumed rates. Cost/allocation broken down per namespace and per workload, with allocation-vs-actual-usage efficiency visible for at least the M12 workloads once they exist. Storage cost attributed against the real `local-path`/replicated (#51) PVCs. A short written read of what it shows — where the cluster's real resource spend actually goes, in real money — rather than just standing the dashboard up.
- Dependencies: #48.
- Priority: P2. Labels: `platform`, `observability`.

---

## M11 AI-Assisted SRE

The single best new idea from the external second-opinion review, absent
from the original expansion plan: an actual SRE agent over the project's
own telemetry, not a chatbot wrapper. It ties directly to the fact that
this project is itself built end-to-end via an AI coding agent — "I built
an AI SRE co-pilot for my own homelab, here's what it actually caught vs.
missed" is a differentiated, genuinely novel article angle, which is why
it earns its own milestone (ADR 0022's content goal).

**66. `sre-agent`: incident-triage agent over the project's own telemetry**
- Purpose: every incident this project has diagnosed was diagnosed by a human reading across Loki, Tempo, Prometheus, `kubectl` events, and Alertmanager and correlating by hand — the exact cross-signal correlation an agent can do. This is a real agent: on a trigger (an Alertmanager alert, or on demand), it consumes Loki logs + Tempo traces + Prometheus metrics + Kubernetes events + Alertmanager state for the affected window and produces an incident summary, a root-cause *suspicion*, an affected-services list, and concrete next-step suggestions. It is grounded in real signals the project already emits, and its honest evaluation — what it caught, what it missed, what it hallucinated — against the real fact packs already written (`observability/chaos/01/02`) is the actual portfolio content, not the demo.
- Acceptance Criteria: a service (own namespace, own ArgoCD Application; language chosen on ADR 0019's rule) that, given an incident window, queries Loki/Tempo/Prometheus/Kubernetes-events/Alertmanager (read-only — it observes, it does not act on the cluster) and emits a structured incident report (summary, suspected root cause, affected services, suggested next steps). Run against at least the two existing chaos scenarios re-triggered live (via #64), with its output compared honestly to the human-written fact pack for each — agreements, misses, and false leads all recorded. The agent's own reasoning is itself traced/logged so its behaviour is observable like any other service. Cost and latency per invocation recorded. Explicitly out of scope: any write/remediation action on the cluster — this is a co-pilot, not an operator.
- Dependencies: #45, #21 (real alerts and traffic to reason over), #49/#57 (richer signals help but are not blocking).
- Priority: P2. Labels: `observability`, `backend`.

---

## M12 Bioinformatics Workloads (reopened, ADR 0025)

ADR 0021 closed the reserved bio-pipeline milestone (#30) as the right call
for a tight SRE portfolio. ADR 0022 shifted the goal (breadth, novelty,
more application logic) and ADR 0025 reopens this consciously — real
domain workloads are an asset for the health-tech roles now being targeted,
and the pipeline lifecycle is a new operational shape, not bio-for-bio's-
sake. This is a **new milestone**, not a verbatim restoration of #30 (which
was M6; M6 is now Real Demand). Lands after M7's multi-node/replicated-
storage substrate, which the data volume needs. See ADR 0025 for the full
reopening rationale and how ADR 0021's "bio coat of paint" risk is bounded.

**67. `metadata-service`: study/sample/pipeline-run domain model (Spring Boot)**
- Purpose: the project's Java services so far are a placeholder CRUD domain (`work-items`); this is real domain modelling — studies, anonymized patients/samples, and pipeline-run metadata, with real relationships (a study has samples; a sample has pipeline runs; a run has a status and provenance). Spring Boot matches the existing Java convention for CRUD-shaped services (ADR 0019's language rule). It is the system of record the pipeline lifecycle (#70) and notifications (#71) hang off, and deliberately *not* another `work-items` clone — the relational shape and the anonymization boundary (no PHI, only de-identified identifiers, an explicit modelling constraint) are the point.
- Acceptance Criteria: a `metadata-service` in its own namespace with its own Postgres (ADR 0019's namespace-local pattern, not a shared DB), owning studies/samples/pipeline-runs with a versioned Flyway schema; CRUD plus the query paths the pipeline and notification services need; anonymization stated as a modelling invariant (only de-identified IDs persisted) and enforced/tested, not assumed. Instrumented with OTel like every other service; a golden-signal dashboard and an SLO row added to ADR 0020's table. Real relationships proven by a test that walks study→sample→run.
- Dependencies: #48 (multi-node substrate).
- Priority: P2. Labels: `backend`, `architecture`.

**68. MinIO object storage for real pipeline files (FASTQ/BAM/VCF)**
- Purpose: the project has never had an object-storage data plane — all state is Postgres or telemetry PVCs. Real bioinformatics files (FASTQ inputs, BAM/VCF intermediates and outputs) are large binary objects that belong in object storage, not a database, and MinIO is the self-hosted S3-compatible answer. This is the object store #30 wanted; ADR 0025 states why it is justified now (a new stateful component and data plane to operate, back up, and reason about) where it was not before (bio breadth for a bio audience). It gains real teeth on the multi-node cluster with replicated storage (#51) behind it.
- Acceptance Criteria: MinIO deployed as an ArgoCD Application, backed by #51's storage layer, exposed on the standard Ingress pattern with an `adamastorx-ca` cert; buckets for pipeline inputs/intermediates/outputs with a stated lifecycle/retention policy (object storage on a finite node grows unbounded otherwise — the #21d disk lesson applies); credentials as real Kubernetes Secrets reconciled with #36's secret-provisioning approach, not a second mechanism. Included in #23a's backup/restore discipline (or explicitly stated as regenerable-from-source and not backed up, per dataset). `metadata-service`/Nextflow (#69) read and write real objects, proven with a real file round-trip.
- Dependencies: #51 (replicated storage), #67.
- Priority: P2. Labels: `platform`, `backend`.

**69. Nextflow pipeline engine executing real pipelines on Kubernetes**
- Purpose: a real pipeline engine actually running real bioinformatics pipelines — not a mocked stand-in, which is the line ADR 0025 draws for this to be worth doing. Nextflow with its Kubernetes executor is a new source of Kubernetes Jobs and a new failure surface the project has never operated: a multi-step DAG where step 3 can fail after steps 1–2 wrote real intermediates to MinIO, work orphaned by a pod restart mid-pipeline, and resource pressure from real compute competing with the platform (where #65 Kubecost and #63 KEDA become relevant). The SRE substance is running and operating the pipeline, not the alignment algorithm inside it.
- Acceptance Criteria: Nextflow deployed with its Kubernetes executor, running at least one real public pipeline (e.g. an nf-core workflow) end-to-end on real input data from MinIO (#68), writing real outputs back. A pipeline run is tracked as a `pipeline-run` row in `metadata-service` (#67) with real status transitions. A run interrupted by a pod kill mid-DAG is proven to reach a terminal state (resumed or explicitly failed with a reason), never left running forever — the orphaned-job recovery shape #54 introduced, now over a multi-step pipeline. Resource footprint recorded (feeds #65). Explicitly bounded: running real public pipelines, not authoring novel bioinformatics.
- Dependencies: #67, #68.
- Priority: P2. Labels: `platform`, `backend`.

**70. Kafka pipeline-lifecycle events: a multi-stage saga, not a single hop**
- Purpose: the project's two existing event shapes are `work-items` (simple produce/consume, fire-and-forget) and ClinVar (one release-diff event, one cache-invalidation consumer). The pipeline lifecycle is a genuinely new shape: an ordered, multi-stage, saga-like sequence with failure branches — `PipelineStarted` → `PipelineFinished` / `AnalysisFailed` → `SampleImported` — modelling a *process* with states, not a single hop. Stated explicitly because ADR 0022 requires new work to add an operational shape the project lacks: this is the first event stream where ordering, stage transitions, and a failure path (`AnalysisFailed` short-circuiting `SampleImported`) all matter and must be reasoned about together.
- Acceptance Criteria: Nextflow runs (#69) emit lifecycle events to Kafka at each stage transition, with the event schema and ordering guarantees documented (what a consumer may assume about order, what happens on redelivery). `metadata-service` updates its `pipeline-run` state from these events, so the system-of-record reflects the saga. The failure branch is real and tested: an injected `AnalysisFailed` is proven to prevent the `SampleImported` that a success would have produced, and the run lands in a correct terminal state. Traces span Nextflow→Kafka→consumers, extending the correlation story. This is distinguished in writing from #53's fan-out-delivery shape — that is one event to many subscribers; this is many ordered events modelling one process.
- Dependencies: #69, #67.
- Priority: P2. Labels: `backend`, `architecture`.

**71. `notification-service`: the first new Kafka consumer topology since `workers` (Spring Boot)**
- Purpose: a Notification service consuming the pipeline-lifecycle events (#70) — the first genuinely new Kafka consumer topology this project has had since `workers` was built in M2. Where `workers` consumes one topic and logs, this consumes a saga's events and reacts to *state*, not just messages: notify on `PipelineFinished`, escalate on `AnalysisFailed`, stay quiet on intermediate stages. Spring Boot per the Java CRUD/messaging convention. Notification delivery reuses the ntfy channel #21c already proved works, and the idempotency lesson #53 raises (a delivery must be exactly-once across redeliveries) applies here too.
- Acceptance Criteria: a `notification-service` in its own namespace consuming #70's lifecycle topic, delivering notifications keyed on terminal/failure states (not every event), with delivery idempotent across redelivery and proven so by a redelivery test. A permanently-failing delivery is dead-lettered, not blocking the consumer (the #53 pattern). Consumer lag and delivery metrics exposed with a dashboard and an SLO row (ADR 0020's table). Traces span the full `Nextflow→Kafka→notification-service→ntfy` path.
- Dependencies: #70, #21c.
- Priority: P2. Labels: `backend`, `observability`.

**72. Real public dataset ingestion: genomics and medical imaging, licensing friction included**
- Purpose: real, correctly-licensed public data, explicitly not synthetic — matching the ClinVar precedent that is already one of the project's most defensible content threads. Genomics (1000 Genomes, TCGA, GEO — on top of the ClinVar already in hand) and, as a substantial new domain with a different data-volume and streaming shape, medical imaging (DICOM files, TCIA). The real value here includes the *friction*: licensing and access are not uniform, and that is a genuine constraint to surface honestly, not gloss — MIMIC specifically requires a credentialed data-use agreement (not just a download), so it is called out as gated, and each source's license/access terms are recorded before ingestion.
- Acceptance Criteria: at least one genomics source (1000 Genomes / TCGA / GEO) and one imaging source (TCIA/DICOM) ingested into MinIO (#68) as real files feeding real pipeline runs (#69), with each source's license and access mechanism documented in `docs/data-sources.md` (the ClinVar precedent) before its data is stored. MIMIC's credentialed-DUA requirement is recorded explicitly as a real access constraint — either the DUA is obtained and stated, or MIMIC is documented as out-of-scope-pending-DUA rather than silently skipped. Data volume and the streaming/large-object handling (imaging especially) recorded, feeding #65's cost view and #68's retention policy. No synthetic stand-in is substituted for a real dataset anywhere.
- Dependencies: #68, #69.
- Priority: P2. Labels: `backend`, `documentation`.

---

## Cross-cutting

Items that don't belong to one milestone's feature scope — raised by an
independent staff-engineer-level review of the whole project (all four
repos, not one persona's remit) rather than by a specific epic's own
backlog. Same format, same discipline; no milestone gates these, they can
be picked up whenever.

**31. Top-level "what this project demonstrates" narrative doc**
- Purpose: The project's actual throughline — real incidents found and fixed live (namespace-scoped Secret/PVC sharing breaking twice, a Bitnami chart's auto-generated Secret silently regenerating, a double-ingestion race with no OOM evidence anywhere, four separate Spring Boot 4 autoconfiguration gotchas), a deliberate architecture pivot (ADR 0018 → ADR 0019) with the reasoning kept rather than erased, and what each milestone was actually chosen to prove — is currently only reconstructable by reading all ~20 ADRs plus `docs/SESSION_STATE.md` end to end. A hiring manager skimming the repo sees a feature list (README's Vision/Repository map) but not the connective narrative that is the actual portfolio value: the judgment calls, not just the tool list.
- Acceptance Criteria: One doc (e.g. `docs/WHY.md`) that names, in a few hundred words, the real bugs found and fixed, the ADR 0018→0019 pivot and why it happened, and the one-line "what this milestone proves" for each of M0-M5 — written for someone who will not read the ADRs, linking out to them for anyone who wants the detail. Linked prominently from the top-level README, not buried in `docs/`.
- Dependencies: none.
- Priority: P2. Labels: `documentation`.

**32. Keep `.claude/PROJECT.md`'s "Current milestone" section refreshed as a routine step, not an afterthought**
- Purpose: `PROJECT.md` calls itself "the stable picture" other repos point back to instead of duplicating, and `.claude/WORKFLOW.md`'s "Post-merge sweep" already names `.claude/PROJECT.md`'s current-state sections as something the `documentation-engineer` agent checks after any merge with architectural/operational impact — but in practice it wasn't: this section was last updated at services#4 and still read "Current milestone: M2 ... services#5 remaining" after Redis (services#5), all of M3, and all of M5 had shipped and `docs/architecture/overview.md` had been refreshed many times over in the same window. The documented process exists on paper; nothing catches it silently not running. Fixed directly as part of this review's own PR — this item is about making it stick, not the one-time correction.
- Acceptance Criteria: The post-merge sweep step in `.claude/WORKFLOW.md` gets a concrete, checkable trigger (e.g. any PR that closes a backlog item or completes a milestone must touch `PROJECT.md`'s "Current milestone" section in the same PR, checked in the `CONTRIBUTING.md` PR checklist, not left to a separate sweep that can be silently skipped). A second full pass confirms no other "canonical" doc (this file, `docs/architecture/overview.md`, README) has silently drifted the same way right now.
- Dependencies: none.
- Priority: P2. Labels: `documentation`.

---

## Simplification

The project's owner asked, for the first time, for the *opposite* of every
prior (additive) review: for a personal SRE/platform **portfolio** — no
real users, no revenue — what should this project **stop doing, remove, or
never have built** because it doesn't serve that goal? Sunk cost is not a
reason to keep anything; a piece earns its place only by whether its
complexity pays off *for this audience*. These items are concrete removals,
each with a done state. None deletes code by itself — every actual deletion
stays a separate, explicitly-confirmed owner decision, taken one at a time.
ADR 0021 records the significant, hard-to-reverse ones (remove a whole
service, drop a domain, close a milestone).

Guiding cut/keep calls (the reasoning; the actions are S1–S7 below):
- **Keep** `clinvar-service`, its dedicated Postgres, the ClinVar release
  provenance, and invalidation-on-write — the polyglot judgement call (ADR
  0019) and the provenance story are this project's single most defensible
  portfolio content. The two-Postgres/two-CI/two-base-image tax is the
  *load-bearing consequence* of that decision (namespace-scoped Secrets/PVCs
  can't cross a boundary — the lesson learned twice), not incidental cost;
  it stays because the thing it supports stays.
- **Cut** everything that is infrastructure maintaining zero real function
  (`gateway`, `whoami`), breadth that adds no new SRE signal (gnomAD, HGVS,
  liftover, chaos scenarios 4–7), or enterprise/multi-team ritual that a
  single operator generating their own traffic cannot meaningfully exercise
  (multi-window burn-rate budgets, solo "blameless" postmortems, a laptop
  load-test "capacity baseline", a single-node "node-loss game-day").

**S1. Remove the `gateway` service entirely; expose `api` directly**
- Purpose: `gateway` has exactly one route — `GET /api/hello` → `api`'s
  `GET /hello`, an M1 placeholder (ADR 0010) — never wired to any real
  traffic (`work-items`/`/variants/lookup` all hit `api` directly), zero
  real requests since last restart. It nonetheless carries a full,
  permanent tax: its own Spring Boot module, CI build/scan/publish matrix
  entry (`services/.github/workflows/ci.yml` + `build-publish.yml`,
  `GatewayMetricsHistogramTest`), Kubernetes namespace/Deployment/Service,
  ArgoCD Application, Traefik Ingress, and TLS certificate — the exact
  shape of "healthy infrastructure maintaining zero real function." The
  ADR 0010 rationale ("single entrypoint for future auth/aggregation/
  rate-limiting") never materialised; a two-method forwarder in front of
  one backend does not earn a service, an image, a pipeline, and a cert.
- Acceptance Criteria: `services/gateway` deleted, including its CI matrix
  entries and `GatewayMetricsHistogramTest`; `platform/kubernetes/gateway/`
  and `argocd/apps/gateway.yaml` deleted; the `gateway` namespace gone.
  `api` gets its own Ingress + cert-manager certificate (the same
  `adamastorx-ca` pattern gateway/whoami used) so a real service is the
  live Traefik+TLS+service path; verified reachable through Traefik with
  TLS. ADR 0010 marked `Superseded by 0021`. Every doc/manifest that
  enumerates `gateway` reconciled in the same change: drop its rows from
  #21/#21a's SLO+histogram tables, from #35's CPU-limit list, and from any
  golden-signal dashboard/runbook. If a real cross-cutting edge concern
  ever arrives, reintroducing an edge service (or Traefik middleware) is a
  fresh, deliberate decision — not a reason to keep an empty one now.
- Dependencies: none. ADR 0021.
- Priority: P1. Labels: `platform`, `backend`, `architecture`.

**S2. Remove the `whoami` proof app**
- Purpose: `traefik/whoami` was M1's end-to-end proof that Traefik +
  cert-manager issue and serve TLS. Real services exist now; that proof no
  longer needs a dedicated app with its own namespace, `ResourceQuota`,
  `LimitRange`, Ingress, certificate, and ArgoCD Application. Once S1 gives
  `api` an Ingress, a real service is the standing ingress+TLS proof.
- Acceptance Criteria: `platform/kubernetes/whoami/` and
  `argocd/apps/whoami.yaml` deleted; the `whoami` namespace gone; a real
  service's Ingress (per S1) documented as the ingress+cert-manager proof
  in `docs/architecture/overview.md` and `.claude/PROJECT.md` (which both
  currently cite `whoami` as that proof).
- Dependencies: S1 (so a real Ingress exists before whoami's is removed).
- Priority: P2. Labels: `platform`.

**S3. Drop gnomAD enrichment; make ClinVar the sole annotation source — DONE**
- Purpose: gnomAD was never built; its real footprint (~7.7GB, per
  `SESSION_STATE.md`, not the "few hundred MB" ADR 0018 assumed) does not
  fit this single-node cluster, and it adds a *second* data source that
  introduces no operational signal ClinVar does not already provide — pure
  breadth for a bio audience, not depth for an SRE one. #24a already
  concedes deprioritising it entirely is a valid outcome; this makes that
  the decision.
- Acceptance Criteria: gnomAD removed from #24's acceptance criteria (the
  endpoint returns ClinVar clinical significance + release id only); ADR
  0018's scope amended to ClinVar-only with a note pointing to ADR 0021;
  the gnomAD section of `docs/data-sources.md` removed or marked
  out-of-scope; #24a closed as resolved (answer: no gnomAD). `clinvar-
  service`, its Postgres, the provenance story, and invalidation-on-write
  are untouched.
- Dependencies: none. ADR 0021.
- Priority: P2. Labels: `backend`, `architecture`.

**S4. Close M6 (#30); stop reserving the FASTQ/alignment milestone — DONE**
- Purpose: #30 reserves a real alignment pipeline on self-hosted MinIO +
  Kubernetes Jobs — a whole new object-storage/batch data plane built to
  serve bioinformatics depth for a bio audience, not SRE/platform depth.
  The genuinely distinctive portfolio asset (the polyglot pivot and the
  provenance story) is already delivered by `clinvar-service`; M6 extends
  the "bio-flavored coat of paint," which is the exact failure mode #30 was
  raised to guard against — going deeper into it doesn't fix it. For a
  simplification pass, closing the placeholder beats reserving it.
- Acceptance Criteria: #30 marked won't-do (struck through, like #27) with
  this reasoning inline; ADR 0018's and ADR 0019's forward references to
  #30/M6 annotated as closed (see ADR 0021); #30's sequencing note about
  #38/#39 folded into those items or dropped. No open backlog item or ADR
  still treats M6 as committed future work.
- Dependencies: none. ADR 0021.
- Priority: P2. Labels: `architecture`.

**S5. Cut the M5 bioinformatics-depth enhancements #40 (HGVS) and #41 (liftover) — DONE**
- Purpose: HGVS-input support and GRCh37→GRCh38 liftover add
  clinical-genomics surface for a bio audience; they teach an SRE/platform
  reviewer nothing new once rsID + coordinate + normalized lookups already
  work. They are the same "bio coat of paint goes deeper" pattern as M6.
  #38 (a real correctness bug — silent `LIMIT 1` data loss) and #39 (the
  cheapest, highest-signal correctness fix — indel normalization) stay:
  they are real bugs, not depth-for-depth's-sake.
- Acceptance Criteria: #40 and #41 marked won't-do with this reasoning
  inline; #38 and #39 explicitly retained. No item still lists #40/#41 as
  in-scope work.
- Dependencies: none.
- Priority: P2. Labels: `backend`, `architecture`.

**S6. Trim the chaos plan (#23) from seven scenarios to three — DONE**
- Purpose: #23's seven scenarios each demand a full signal → dashboard →
  alert → runbook → fault-proof → recovery-proof → article fact-pack. For a
  single operator, three well-chosen scenarios already prove the alerts and
  runbooks work; scenarios 4–7 (poison-message/DLT, readiness probe,
  ArgoCD drift, `clinvar-service` PVC) re-exercise the same muscle without
  teaching a new SRE skill or a new class of signal — breadth that reads as
  thoroughness but returns little once the first three are done.
- Acceptance Criteria: #23's acceptance criteria reduced to three
  scenarios — (1) Kafka broker unavailable, (2) PostgreSQL unavailable /
  PVC full, (3) consumer-group lag — each still producing the full
  signal/dashboard/alert/runbook/proof loop. Scenarios 4–7 dropped (a
  one-line note may record that any one of them is a fine *ad-hoc* future
  exercise, not a committed deliverable).
- Dependencies: none.
- Priority: P2. Labels: `observability`, `platform`.

**S7. Cut the M4 résumé-padding items: close #21b, #33, #34; merge #23b into #23a — DONE**
- Purpose: four M4 items add ceremony a single operator can't meaningfully
  exercise, on top of work that already covers the real ground.
  - **#21b (error-budget policy + multi-window burn-rate alerts)** is an
    enterprise, multi-team SRE ritual; you cannot meaningfully "burn" a
    budget against traffic you generate yourself, and a "change freeze
    until budget recovers" is theatre for a solo repo. #21's per-SLO alerts
    are the right altitude and the actual teaching moment.
  - **#33 (blameless postmortems for the three real incidents)** duplicates
    what ADRs 0018/0019 and `SESSION_STATE.md` already record; a solo
    "blameless" postmortem is a solo writeup. The useful part (surfacing
    the incidents as portfolio narrative) is already #31's job.
  - **#34 (k6/vegeta capacity baseline)** load-tests self-generated traffic
    on one laptop node — it measures the laptop, not a capacity baseline;
    the ~90s ingestion figure is already a real measured number, and #21's
    thresholds can cite it directly.
  - **#23b (node-loss/DR game-day)** on a single-node laptop cluster is
    ceremony: #23a already documents single-node/disk loss as an accepted,
    stated risk and proves a `pg_dump`-based restore once. Its one useful
    ask (record real measured RTO/RPO from the restore) folds into #23a.
- Acceptance Criteria: #21b, #33, #34 marked won't-do with the reasoning
  above inline; #23b's RTO/RPO-measurement ask merged into #23a and #23b
  itself closed. Genuinely-worth-keeping M4 work is stated explicitly as
  retained: #21 (SLOs/alerts), #21c (real notification channel — done),
  #21d (disk-full alert — cheap, real single-node failure mode), #21e
  (real metric gap for #21), #22 (runbooks), #23 (trimmed per S6), #23a
  (backup/restore — a real, uncovered gap), #36 (root-cause Secret fix),
  #37 (rollback runbook — done). #35 (per-namespace CPU limits) stays for
  the limits themselves, but its "CI check that fails a PR with no CPU
  limit" is downgraded to optional — a lint gate is gold-plating for a
  solo repo where review already catches it.
- Dependencies: none.
- Priority: P2. Labels: `observability`, `platform`, `documentation`.

**42. Real Kafka broker/topic availability alert**
- Purpose: chaos scenario 1 (`observability/chaos/01-kafka-broker-unavailable.md`, backlog #23) ran a real Kafka outage live and found none of the 6 existing alert rules fired — `ApiHighErrorRate` needs a sustained 5-minute window of non-zero real traffic at >5% error rate, and a brief outage under this project's actual low/manual-test traffic pattern never sustains that. There is currently no alert that detects "Kafka itself is unavailable or missing a topic" directly, only ones that infer it from downstream error rates that need real traffic to trip.
- Acceptance Criteria: a Prometheus alert on Kafka's own availability (e.g. `up{job=~"kafka.*"}` if scraped, or a broker/topic health check) fires within a reasonable window of a real outage, independent of whether `api`/`workers` are receiving traffic at the time. Verified live against a repeated version of chaos scenario 1.
- Dependencies: #21.
- Priority: P2 (downgraded from P1, backlog #47, 2026-07-31). Labels: `observability`. **Reassessed, not closed**: re-running scenario 1 under #45's permanent real traffic showed `ApiHighErrorRate` now fires unaided in ~8m44s against this cluster's actual Kafka failure mode (broker restart → ephemeral-storage topic loss → sustained downstream errors) — the gap this item was scoped against no longer exists for that shape. What it would still catch that `ApiHighErrorRate` cannot: a Kafka outage that resolves before 5 minutes of elevated error rate accumulate (this cluster's own ephemeral storage doesn't currently produce that shape, but a real broker/topic health alert would generalize to it). Kept as real, lower-priority defense-in-depth rather than closed outright.

**43. Re-examine `WorkItemProducer`'s synchronous-block-then-500 behavior under a Kafka outage**
- Purpose: chaos scenario 1 found a real, previously-undocumented (and more severe than assumed) failure mode: `WorkItemProducer.publish()` calls `kafkaTemplate.send()` and returns `void` with no blocking call in application code, but the underlying `KafkaProducer.send()` itself can block synchronously waiting for topic metadata (Kafka client's own `max.block.ms`, default 60s) before the fire-and-forget future is even returned — so a real caller gets a slow, synchronous 500 during a Kafka outage, not the silently-swallowed async failure ADR 0012's "known gap" description assumed.
- Acceptance Criteria: a documented decision (ADR addendum or backlog note) on whether this is an acceptable tradeoff for this project's scale, or whether a shorter `max.block.ms`/an explicit async error-handling path is worth adding so a Kafka outage degrades to a fast, clear error instead of a ~60s hang. Not required to change the behavior — required to make the decision explicit rather than leaving the corrected understanding undocumented.
- Dependencies: none.
- Priority: P2. Labels: `backend`, `observability`.

**73. Fix `postgresql`'s (api namespace) unusable `postgres` superuser credential**
- Purpose: found live while implementing #23a (backup/restore), investigating why the Bitnami chart's built-in `pg_dumpall` backup CronJob (which authenticates as the `postgres` superuser) failed. Initially suspected as a recurrence of the platform#34/#36 Secret-drift bug — disproven: the `postgresql` Secret's `postgres-password` key and the live container's own `POSTGRES_POSTGRES_PASSWORD` env var were checked directly and **agree**. The real finding is different: the `postgres` role's actual password hash stored inside PostgreSQL matches **neither** the Secret nor the env var — a third, unknown value, most likely because `POSTGRES_POSTGRES_PASSWORD` is applied only at first `PGDATA` initialization (never on a later restart against existing data), so whatever the Secret held at that one moment is what's live, and it may never have matched what the Secret holds today. This has been silently true for an unknown period with zero symptom, since nothing in normal operation authenticates as `postgres` (every real request uses the least-privilege `api`/`clinvar` app roles) — only surfaced because #23a's investigation tried to use the superuser role for the first time. `clinvar-postgresql`'s `postgres` user authenticates correctly today; only api's instance has this gap.
- Acceptance Criteria: the `postgres` superuser's real password is brought back in sync with the Secret's `postgres-password` value. An `api`-role connection has no privilege to `ALTER USER postgres` (`permission denied to alter role`, confirmed live), so this needs a real maintenance window: temporarily set the relevant `pg_hba.conf` local/host rule to `trust` for the `postgres` user, restart PostgreSQL (a fast config-reload-shaped restart, not a reinit — PGDATA/tables are untouched), connect and run `ALTER USER postgres WITH PASSWORD ...`, then revert `pg_hba.conf` and restart again. Verified live: `psql -U postgres` authenticates successfully against api's `postgresql` afterward, and the live `work_items` table/row count is unchanged before and after (proving the two restarts didn't touch data). Real-world impact is low today (nothing depends on this role currently) — priority reflects that, not urgency to fix immediately.
- Dependencies: none.
- Priority: P2. Labels: `platform`, `bug`.

**74. Fix `watchlist-service`'s image pull — first private image in this project**
- Purpose: found live merging #53. Every other published image in this project (`gateway`, `api`, `workers`, `clinvar-service`, `clinvar-viewer`, `workload-generator`) is a public GHCR package, so no Deployment here has ever needed an `imagePullSecret`. `watchlist-service`'s package was left private (its brief, unauthorized public flip during #53's implementation was caught and reverted before merge — see #53's own post-merge note), and no pull secret was ever added to the committed manifests, so the deployed pod is `ImagePullBackOff` on the real cluster. Real, contained impact: `watchlist-service` cannot run at all right now; `watchlist-postgresql` is unaffected and healthy. The pod's scheduled-but-not-running resource reservation was also observed to contend with an unrelated rollout's own scheduling (#54's `clinvar-service` bump), confirming this isn't purely cosmetic on a resource-constrained single-node cluster.
- Acceptance Criteria: a deliberate choice recorded, not another silent workaround — either (a) make the package public, matching this project's own established convention for every other image (simplest, zero new credential to manage, consistent with this being a public portfolio project), or (b) add a real `imagePullSecret`: a dedicated, narrowly-scoped PAT (`read:packages` only, not a broad personal token) stored as a `kubernetes.io/dockerconfigjson` Secret, referenced in `kubernetes/watchlist-service/deployment.yaml`, provisioned the same out-of-band way `bootstrap/create-stateful-secrets.sh` already handles every other generated credential. Whichever is chosen, verified live: the real pod pulls successfully and reaches `Running`/`Healthy`.
- Dependencies: none.
- Priority: P1. Labels: `platform`, `bug`. **Done (2026-08-01)** — chose (a): package made public, matching every other image in this project, by the owner directly in the GitHub UI (an org-admin package-visibility action outside what the assistant's own credentials were scoped to do, twice attempted and 403'd via the API/OAuth-scope route first). Verified live: pod force-recreated (`kubectl delete pod`, clearing kubelet's cached backoff), pulled successfully, reached `1/1 Running`, `Synced`/`Healthy`. A real `POST /subscriptions` against the actual ArgoCD-managed Deployment (not a rehearsal stand-in) returned `201` with a real row in `watchlist-postgresql`, then cleaned up (`DELETE`, `204`) — closing #53's own "needs a human check post-merge" item at the same time.

**75. Re-examine Kafka's memory headroom under a real accumulating backlog**
- Purpose: found live during backlog #23's chaos scenario 3 (`observability/chaos/03-consumer-lag.md`). During the scenario's real outage window (`workers` scaled to zero, real production continuing), Kafka's own broker container OOMKilled — real, timestamp-aligned evidence (container restart count moved 47→48, `OOMKilled`/exit 137, the crash-and-restart window sitting entirely inside the fault-injection window). Plausible mechanism: the container's `768Mi` memory limit (`KAFKA_HEAP_OPTS` sizes the heap to 75% of that, ≈576Mi) leaves only ~192Mi for everything else, including the OS page cache Kafka leans on for reading/writing log segments — an unconsumed backlog piling up in those segments faster than usual is a real candidate for tipping that narrow headroom over. **Not cleanly proven**: this specific run also had `workload-generator`'s rate temporarily elevated (10x default) to make the lag threshold reachable in a reasonable test window, so backlog-accumulation-alone cannot be cleanly separated from elevated-request-rate-alone as the trigger from this one data point.
- Acceptance Criteria: a clean re-run of chaos scenario 3 at the *unmodified* default `workload-generator` rate (`target_rps: 0.5`) — accepting the ~40-minute wait to reach the lag threshold — with Kafka's memory/restart-count watched throughout. If the OOM reproduces at normal traffic too, the fix is real headroom (a higher memory limit, sized against a measured real backlog scenario, not a guess) — verified live by repeating the same scenario afterward and confirming no OOM. If it does *not* reproduce at normal traffic, that itself is the finding (the elevated test rate was the actual trigger, not backlog size), recorded honestly and this item closed without a resource-limit change.
- Dependencies: #23 (done).
- Priority: P2. Labels: `platform`, `observability`, `bug`. **Partially done, AC not fully met (platform#76)**: took the fast, defensible fix instead of the clean isolating re-run this item's own AC asks for — real node memory headroom was confirmed first (only 35% of ~19.4Gi allocated in limits, while CPU was already at 98% of allocatable requests, so memory was the safe lever to pull), Kafka's limit doubled (768Mi→1536Mi, CPU left unchanged since it was never implicated), verified live: broker recreated cleanly, topics recreated (expected — a real Pod recreation, not just a container restart this time, so `emptyDir` was torn down), a real authenticated produce→consume cycle through the public Ingress confirmed end-to-end. **The AC's own clean re-run at the unmodified default rate was not done** — decided against repeating a ~40-minute live fault injection against a broker that had just OOMed once already, in favor of shipping real headroom now. Root cause (backlog size vs. elevated test rate) remains genuinely unisolated; left open as a real gap in this item's own record rather than claimed as proven.

**76. `WorkersConsumerLagHigh` can't detect a fully-stopped consumer**
- Purpose: found live during backlog #23's chaos scenario 3. `kafka_consumer_fetch_manager_records_lag` is self-reported by `workers`' own JVM (a Micrometer `KafkaClientMetrics` binder, #21a) — when `workers` has zero replicas, there is no process left to report it, and Prometheus's pod-role service discovery has nothing to scrape at all. The metric doesn't show a large number; it shows nothing. `WorkersConsumerLagHigh`'s own `description` field already tells a human to "check if the pod is even running/consuming at all before assuming it's just slow" — this finding confirms that's not just good on-call advice, it's the *only* way to catch this specific failure mode today, since the metric-based alert structurally cannot fire on it. The same shape of gap #42 already tracks for Kafka's own broker/topic availability.
- Acceptance Criteria: a companion alert that fires on the *absence* of the consumer rather than a lag value — `up{job="workers"} == 0` (if a target existing-but-down state is reachable) or an `absent(kafka_consumer_fetch_manager_records_lag{job="workers"})`-shaped expression (for the "no target at all" case this finding actually hit), whichever the real behavior needs — verified live the same way scenario 3 hit the gap: scale `workers` to zero for real (via the sync-pause method that scenario already proved necessary) and confirm the new alert fires where `WorkersConsumerLagHigh` stays silent.
- Dependencies: #23 (done).
- Priority: P2. Labels: `observability`. **Done (platform#77)** — new `WorkersConsumerMissing` alert (`absent(kafka_consumer_fetch_manager_records_lag{job="workers"})`, `for: 3m`). Verified live: `workers` scaled to zero for real (2026-08-01, `10:34:56 UTC`), the new alert fired at `10:40:17 UTC` (~5m21s, matching the 3m threshold plus scrape/evaluation lag) while `WorkersConsumerLagHigh` stayed silent throughout — confirming the two rules are genuinely complementary, not overlapping. `workers` restored, Kafka (backlog #75's new memory headroom) stayed healthy with zero OOMs throughout this shorter test.

**77. This node is out of real CPU headroom — a recurring, now three-times-confirmed finding**
- Purpose: not a new discovery in isolation — the same root cause has now independently blocked three separate, unrelated pieces of real work in this session: Argo Rollouts' canary surge pod (#46, briefly, resolved itself), `watchlist-service`'s scheduled-but-`ImagePullBackOff` pod holding a real CPU reservation that contended with `clinvar-service`'s own rollout (#53/#54), and now KEDA correctly computing `workers` needs 3 replicas under real lag but only 1 of 3 actually reaching `Running` (#63, `Insufficient cpu` on the other 2). `kubectl describe node` has shown ~98% of allocatable CPU *requested* (not just used) at multiple points today, across unrelated pieces of work — this isn't a one-off fluke, it's this node's real, current ceiling. Memory has genuine slack throughout (the same asymmetry #75 already used) — CPU specifically is the scarce resource.
- Acceptance Criteria: a real accounting of what's actually requesting CPU on this node today (`kubectl describe node` + a per-namespace/per-workload breakdown, not a guess) and a deliberate decision on how to respond — candidates include trimming existing components' CPU *requests* down to their real observed usage (several were sized defensively, before this many components coexisted), deferring further real-load-generating work (#55 and anything else that adds a new always-on component) until the planned dedicated-desktop hardware migration (M7) actually happens, or accepting the ceiling and designing future work around it explicitly rather than being surprised by it again. Whichever is chosen, the decision and its reasoning are recorded here or in a short ADR addendum, not left implicit the way it's been discovered three separate times already.
- Dependencies: none.
- Priority: P1. Labels: `platform`. **Done (platform#81)** — decision, real accounting, and now the live proof itself. `kubectl describe node` baseline: `cpu 3995m (99%)` of 4000m allocatable requested, against real node CPU *usage* of only 1.7-1.8 cores (42-45%, `kubectl top node`). A per-workload `kubectl top pod -A` breakdown, sampled three times over ~6 minutes, found the gap concentrated in components whose CPU requests were never revisited once real traffic existed: the three Bitnami Postgres instances and Redis (`resourcesPreset: small`, 500m each, real usage 9-45m) and `watchlist-service`/`clinvar-service` (250m each, real usage 3-32m). Trimmed CPU *requests* only on those six, to 100-150m (3-8x real observed usage each) — CPU *limits* and all memory values left untouched everywhere; `api`/`workers` (backlog #35's CrashLoopBackOff was a JVM cold-start CPU story, not steady-state waste) and Kafka's CPU (matching #75's own precedent) deliberately left alone. **Merged and synced, live result confirmed (2026-08-01)**: all six affected pods (`postgresql-0`, `redis-master-0`, `clinvar-postgresql-0`, `watchlist-postgresql-0`, `clinvar-service`, `watchlist-service`) recreated cleanly and reached `1/1 Running` with no CrashLoopBackOff or throttling. Real `kubectl describe node` after: **`cpu 2545m (63%)` of 4000m allocatable requested — down from 99%**, a real ~1450m of CPU headroom recovered, not a calculation. This is enough for #63's own KEDA finding (`workers` needing 3× 250m = 750m for a third replica) to fit with real room to spare, closing the loop on the specific case that made this item concrete.
