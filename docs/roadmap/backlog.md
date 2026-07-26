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

**16. Transactional outbox / idempotent consumer for `work-items`**
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

**21b. Error-budget policy and multi-window burn-rate alerts**
> Simplification proposed (S7, ADR 0021): CUT — enterprise/multi-team ritual; you can't meaningfully burn a budget against traffic you generate yourself. #21's per-SLO alerts are the right altitude.
- Purpose: #21 defines each SLO's target; nothing yet defines what happens once the budget is spent, or fires an alert fast enough to matter before it's gone. A single instantaneous-rate-exceeds-threshold alert (the naive shape #21 stops short of) either fires too late (a slow multi-week burn never crosses a moment-in-time threshold) or too often (a short self-resolving spike trips it needlessly) — the exact failure mode the SRE workbook's multi-window burn-rate method exists to replace.
- Acceptance Criteria: for each SLO in ADR 0020's table (`gateway`/`api`/`workers`/`clinvar-service`), a fast-burn (short window, high burn-rate multiple) and slow-burn (long window, lower multiple) alert pair, added to the same `serverFiles.alerting_rules.yml` ADR 0020 already established — no new alerting mechanism. A written error-budget policy (`observability/runbooks/` or `docs/`) states what "budget exhausted" means operationally for a single-operator project (a stated change freeze on the affected service until budget recovers, not aspirational), who lifts it, and where remaining budget is checked (a Grafana panel, not a mental estimate).
- Dependencies: #21.
- Priority: P1. Labels: `observability`.

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

**23. Chaos / failure-injection test plan**
> Simplification proposed (S6, ADR 0021): TRIM from seven scenarios to three (Kafka down, Postgres/PVC full, consumer-lag). Scenarios 4–7 re-exercise the same muscle without a new SRE signal.
- Purpose: Confidence that the alerts and runbooks actually work, proven before a real incident does it for us — and a source of real evidence (logs, metrics, screenshots) for writeups, not a narrative constructed after the fact.
- Acceptance Criteria: Seven concrete scenarios, each producing: a signal, a dashboard, an alert, a runbook, proof of the fault injection, proof of recovery, and a fact pack (commands run, timestamps, screenshots) usable for an article:
  1. Kafka broker unavailable (produce/consume path).
  2. PostgreSQL unavailable, and separately, PVC full.
  3. Consumer group lag (workers falling behind `work-items`).
  4. Poison message / dead-letter topic triggered.
  5. Readiness probe failing (traffic correctly stops routing).
  6. ArgoCD drift (manual cluster change reverted by selfHeal, or blocked/flagged if prune is off).
  7. `clinvar-service`'s dedicated Postgres/PVC unavailable during a live `/variants/lookup` call (ADR 0020) — proves the failure degrades that path only (`work-items` unaffected) and that the node-pinned `local-path` PVC's known consequence (can't reschedule onto another node) is observed directly, not assumed.
- Dependencies: #22.
- Priority: P1. Labels: `observability`, `platform`.

**23a. Backup and restore procedure for stateful data**
- Purpose: No stateful component has a documented or automated backup/restore path — `api`'s PostgreSQL (`work_items`), `clinvar-service`'s dedicated PostgreSQL (`clinvar_release`/`clinvar_variant_index`), Loki, and Tempo are all a single node-pinned `local-path` PVC each on the one k3s node, with no `pg_dump`, snapshot, or off-node copy anywhere. A disk failure or an accidental `kubectl delete pvc`/`helm uninstall` currently means silent, total, unrecoverable data loss with no runbook to even attempt recovery — a gap that fell through the cracks because it's nobody's specific milestone item (M2 built the databases, M4's other items are scoped to alerting/chaos, not backup) and no single persona's remit names it explicitly.
- Acceptance Criteria: A documented decision (ADR or runbook) on backup approach for at minimum the two PostgreSQL instances — a `pg_dump` CronJob writing to a second local PVC is sufficient for this project's actual stakes; explicitly stating Loki/Tempo telemetry data is *not* backed up (acceptable, since it's regenerable observability data, not source-of-truth state) is a valid answer too, as long as it's a stated decision and not a silent gap. A restore is proven at least once — into a fresh PVC/instance, with row counts verified to match. The blast radius this doesn't protect against (loss of the single node/disk itself, which no on-node backup survives) is stated explicitly as an accepted risk for a personal single-node project, not an implicit, undiscussed assumption.
- Dependencies: none — can start independently of #21a/#21/#22/#23.
- Priority: P1. Labels: `platform`, `documentation`.

**23b. Node-loss/DR game-day, proven restore, and an explicit accepted-risk statement**
> Simplification proposed (S7, ADR 0021): MERGE into #23a — a "kill the one node" game-day on a single-node laptop is ceremony; #23a already documents node-loss as accepted risk and proves a restore. Keep only its RTO/RPO-measurement ask, folded into #23a.
- Purpose: consolidates two independently-reached recommendations (a Staff SRE review and a Staff Platform Engineer review, run separately, converging on the same gap). #23a documents a backup approach and proves a restore once into a fresh instance, but doesn't yet rehearse the actual disaster it exists for: the loss of the one k3s node itself, since every PVC here (`local-path`) is node-pinned with no cross-node replication. Both reviews independently flagged that "single node/disk loss is unrecoverable on-node" needs to be a stated, accepted decision, not an implicit assumption nobody has actually rehearsed end to end.
- Acceptance Criteria: a documented decision (an ADR, or an addition to #23a's runbook) stating explicitly that single node/disk loss is unrecoverable on-node, accepted as a reasonable risk for a personal single-node project, paired with #23a's proven `pg_dump`-based restore as the actual mitigation. A real game-day exercise: kill the node (or its PVC, whichever is safely simulable on this cluster) and rehearse restoring from #23a's backup into a fresh PVC/node, with real, measured RTO and RPO recorded from the exercise itself, not estimated in the abstract.
- Dependencies: #23a.
- Priority: P1. Labels: `platform`, `documentation`.

**33. Blameless postmortems for the three real incidents already lived**
> Simplification proposed (S7, ADR 0021): CUT — duplicates ADRs 0018/0019 + `SESSION_STATE.md`; a solo "blameless" postmortem is a solo writeup. The narrative value is already #31's job.
- Purpose: three real production incidents have already happened and been fixed live — the SIGKILL-with-no-OOM-evidence double-ingestion incident (services#36, `dmesg`/`journalctl` all checked clean, see `docs/SESSION_STATE.md`), the Postgres Secret drift (platform#34), which recurred a second time immediately after platform#40's `ignoreDifferences` fix landed, and the ADR 0018→0019 namespace-bug architecture pivot (a PVC, then a Secret, neither shareable cross-namespace) — but none has a dedicated postmortem; each is only reconstructable today by reading ADRs and `SESSION_STATE.md`'s scattered notes end to end.
- Acceptance Criteria: a new `/postmortems` directory (repo root or `docs/postmortems/`), one Markdown doc per incident covering timeline, impact, root cause, and action items already taken — cross-referencing services#36, platform#34/#40, and ADR 0018/0019 respectively rather than duplicating their content. Blameless in the literal sense: framed around process/signal gaps (no metric existed, a workaround masked a root cause), not individual fault.
- Dependencies: none.
- Priority: P2. Labels: `documentation`, `observability`.

**34. Capacity baseline: real load test establishing measured p95 and ingestion-duration distribution**
> Simplification proposed (S7, ADR 0021): CUT — load-testing self-generated traffic on one laptop node measures the laptop, not a capacity baseline. The ~90s ingestion figure is already a real measured number #21 can cite.
- Purpose: #21's latency SLOs and ADR 0020's ingestion-duration-anomaly alert both need a real number to compare against; today the only reference point is the informal "~90s baseline" in ADR 0020/`SESSION_STATE.md`'s incident notes and code comments — a single anecdotal observation, not a measured distribution. Setting a p95 threshold or an anomaly multiplier against that risks the exact mistake ADR 0020 already named: picking a threshold against the wrong number.
- Acceptance Criteria: a repeatable load test (k6 or vegeta) against `gateway`/`api`/`workers` under representative traffic, plus repeated real ClinVar ingestion runs (or a controlled subset) capturing the actual ingestion-duration distribution. Results recorded in a doc or committed artifact and cross-referenced from #21/ADR 0020 as the source the thresholds actually trace back to, replacing "~90s" with a real measured number.
- Dependencies: #21a.
- Priority: P2. Labels: `observability`.

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

**24. Add clinical variant annotation lookup endpoint**
> Simplification proposed (S3, ADR 0021): drop gnomAD enrichment — the endpoint returns ClinVar significance + release id only. If S3 is accepted, this item's gnomAD clauses fall away; the ClinVar lookup itself stays.
- Purpose: Expose the M5 variant annotation capability from ADR 0018 — query by chrom/pos/ref/alt or rsID and get back ClinVar clinical significance, optionally enriched with gnomAD chr21/chr22 allele frequency. Added alongside the existing synthetic work-item domain, not replacing it.
- Acceptance Criteria: Endpoint in `api` accepts chrom/pos/ref/alt OR rsID (mutually exclusive, not both). Response includes clinical significance and, when available, gnomAD allele frequency, plus the ClinVar release identifier behind the answer. Integration test covers both lookup key styles and a not-found case, against a known variant (e.g. rs80357906, BRCA1) with an asserted expected classification.
- Dependencies: #25, #26, #28.
- Priority: P0. Labels: `backend`.

**24a. Rescope gnomAD enrichment to remote tabix range queries, not a full download**
> Simplification proposed (S3, ADR 0021): close this — its own "deprioritise gnomAD entirely is an equally valid outcome" clause is now the decision. No gnomAD, so nothing to rescope.
- Purpose: #24's AC already scopes gnomAD enrichment as optional and ADR 0018 already bounded it to a chr21/chr22 slice, but `docs/SESSION_STATE.md` flags a real, unresolved gap underneath that: gnomAD's real footprint is ~7.7GB, not the "few hundred MB" ADR 0018 originally assumed, on a single-node laptop cluster with no headroom for that — noted there as "flagged during M5 planning, not yet tracked in a dedicated issue." A full download of even just the chr21/chr22 slice at that size is the wrong shape for this cluster regardless of whether gnomAD enrichment gets built at all.
- Acceptance Criteria: if/when gnomAD enrichment (#24) is implemented, it queries gnomAD's own public HTTP-hosted, tabix-indexed VCFs directly via remote range requests scoped to exactly the chr21/chr22 coordinates a given lookup needs — never a full or partial local download. If a live remote dependency on the request path is judged not worth the added latency/reliability surface, deprioritizing gnomAD entirely is an equally valid outcome — record the decision either way rather than leaving it silently deferred.
- Dependencies: #24.
- Priority: P2. Labels: `backend`.

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

**40. HGVS notation support for variant lookup**
> Simplification proposed (S5, ADR 0021): CUT — clinical-genomics surface for a bio audience, no new SRE signal. Keep #38/#39 (real correctness), cut #40/#41 (depth-for-depth).
- Purpose: ClinVar's own VCF already carries HGVS notation in the `CLNHGVS` INFO field, unused today; accepting `c.`/`g.` HGVS strings as a query input format (the notation clinicians and clinical data actually use, not just chrom/pos/ref/alt) closes a real usability gap between what the source data already contains and what the lookup endpoint accepts.
- Acceptance Criteria: `CLNHGVS` parsed during ingestion (#25) and stored queryably; the lookup endpoint (#24) accepts an HGVS string (`c.` or `g.` form) as a fourth query key style alongside chrom/pos/ref/alt and rsID, using a maintained library (e.g. `biocommons/hgvs`) rather than hand-rolled parsing. Integration test covers an HGVS-form query against a known variant.
- Dependencies: #24, #25.
- Priority: P2. Labels: `backend`, `enhancement`.

**41. GRCh37→GRCh38 liftover support**
> Simplification proposed (S5, ADR 0021): CUT — same reasoning as #40 (bio depth, no new SRE signal).
- Purpose: the service is GRCh38-only today with no build-awareness signal at all — a caller submitting GRCh37/hg19 coordinates (still common in clinical and legacy data) gets a silently wrong or not-found answer, not a clear rejection or an automatic correction, since nothing distinguishes the two builds at the API boundary.
- Acceptance Criteria: incoming coordinate-form queries can be tagged (or auto-detected where feasible) as GRCh37 and lifted over to GRCh38 (e.g. `pyliftover` or CrossMap plus the standard NCBI/UCSC chain file) before matching against the GRCh38-indexed data; a query with no build tag keeps today's GRCh38-assumed behavior unchanged, so this is additive, not breaking. Test covers a known GRCh37-coordinate variant resolving correctly after liftover.
- Dependencies: #24.
- Priority: P2. Labels: `backend`, `enhancement`.

**30. Reserve M6 — real batch/alignment pipeline (placeholder, tracking only)**
> Simplification proposed (S4, ADR 0021): CLOSE this — stop reserving M6. Object-storage + batch-Job + alignment is bioinformatics depth for a bio audience, not SRE/platform depth; the distinctive polyglot/provenance story is already delivered by `clinvar-service`, and extending the "bio coat of paint" is the exact failure mode #30 was meant to guard against. If accepted, this becomes struck-through like #27.
- Purpose: Explicitly reserve the milestone that actually closes the project's remaining architectural gap (no object-storage/batch-Job data plane) — a real alignment pipeline on real FASTQ data, self-hosted MinIO, Kubernetes Jobs or a workflow engine — so it isn't left as vague "eventual" work. Raised directly by the Staff Bioinformatician's review of ADR 0018, against the specific failure mode of stopping at "portfolio project with a bio-flavored coat of paint."
- Acceptance Criteria: Stays open and unscheduled until a dedicated future ADR defines its concrete scope; must not be closed as part of M5 work. Cross-referenced from ADR 0018 as the commitment mechanism for the reserved milestone.
- Dependencies: none — intentionally unscoped placeholder.
- Priority: P2. Labels: `architecture`.
- Sequencing note (Staff Bioinformatician review): #38 (the rsID bug) and #39 (variant normalization) carry more bioinformatics novelty than this reserved milestone and are cheap relative to it — landing them before M6 begins is what makes M5 genuinely defensible as real domain work, not just "shipped and done."

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

**S3. Drop gnomAD enrichment; make ClinVar the sole annotation source**
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

**S4. Close M6 (#30); stop reserving the FASTQ/alignment milestone**
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

**S5. Cut the M5 bioinformatics-depth enhancements #40 (HGVS) and #41 (liftover)**
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

**S6. Trim the chaos plan (#23) from seven scenarios to three**
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

**S7. Cut the M4 résumé-padding items: close #21b, #33, #34; merge #23b into #23a**
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
