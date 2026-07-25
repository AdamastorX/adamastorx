# Backlog

23 issues, grouped by epic within each milestone. No implementation detail —
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

**21. Define SLOs and alerting rules**
- Purpose: "Healthy" is defined numerically, and alerts fire on the definition, not on vibes.
- Acceptance Criteria: At least one SLO per service with an error budget; alert rules wired to the SLO, no dashboard-only "alerts".
- Dependencies: #20.
- Priority: P0. Labels: `observability`.

**22. Write incident response runbooks**
- Purpose: Whoever's on call for an alert has a documented first response, not a blank page.
- Acceptance Criteria: One runbook per alert defined in #21, living in `observability/runbooks/`.
- Dependencies: #21.
- Priority: P0. Labels: `documentation`, `observability`.

**23. Chaos / failure-injection test plan**
- Purpose: Confidence that the alerts and runbooks actually work, proven before a real incident does it for us — and a source of real evidence (logs, metrics, screenshots) for writeups, not a narrative constructed after the fact.
- Acceptance Criteria: Six concrete scenarios, each producing: a signal, a dashboard, an alert, a runbook, proof of the fault injection, proof of recovery, and a fact pack (commands run, timestamps, screenshots) usable for an article:
  1. Kafka broker unavailable (produce/consume path).
  2. PostgreSQL unavailable, and separately, PVC full.
  3. Consumer group lag (workers falling behind `work-items`).
  4. Poison message / dead-letter topic triggered.
  5. Readiness probe failing (traffic correctly stops routing).
  6. ArgoCD drift (manual cluster change reverted by selfHeal, or blocked/flagged if prune is off).
- Dependencies: #22.
- Priority: P1. Labels: `observability`, `platform`.

---

## M5 Clinical Variant Annotation

**24. Add clinical variant annotation lookup endpoint**
- Purpose: Expose the M5 variant annotation capability from ADR 0018 — query by chrom/pos/ref/alt or rsID and get back ClinVar clinical significance, optionally enriched with gnomAD chr21/chr22 allele frequency. Added alongside the existing synthetic work-item domain, not replacing it.
- Acceptance Criteria: Endpoint in `api` accepts chrom/pos/ref/alt OR rsID (mutually exclusive, not both). Response includes clinical significance and, when available, gnomAD allele frequency, plus the ClinVar release identifier behind the answer. Integration test covers both lookup key styles and a not-found case, against a known variant (e.g. rs80357906, BRCA1) with an asserted expected classification.
- Dependencies: #25, #26, #28.
- Priority: P0. Labels: `backend`.

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

**27. ClinVar/gnomAD storage footprint and refresh scheduling**
- Purpose: Provision where the ingested ClinVar (weekly) and gnomAD chr21/chr22 slice (infrequent) data lives, sized and scheduled — the first non-trivial-volume dataset and the first time `workers` becomes stateful.
- Acceptance Criteria: Shared RWX PVC mounted on both `api` and `workers`, sized from measured artifact size with headroom for a download-then-swap so a partially-written release is never served; `workers` pinned to a single replica (documented consequence of a node-pinned `local-path` PVC). Data survives a pod restart with no re-download (verified via checksum/mtime before and after `kubectl delete pod`). A `dev` values overlay points ingestion at a small CI fixture instead of NCBI for scratch-cluster bring-up.
- Dependencies: none.
- Priority: P0. Labels: `platform`.

**28. Release-ID propagation through OTel trace correlation**
- Purpose: Extend the existing trace-correlation path (ADR 0013/0015) so the ClinVar release behind any given answer is visible end-to-end, not just stored at the data layer.
- Acceptance Criteria: Release ID stamped once into a single shared field at response-assembly time, surfaced as a `clinvar.release_id` span attribute (confirmed search-enabled in Tempo, not assumed) and a bounded-cardinality metric tag derived from the same field — not computed independently in two places. Visible in Loki as structured metadata, same pattern as `trace_id`/`span_id`. Verified live: a real request's trace ID shows the release attribute in Tempo, pivots to the matching Loki log line, and the Prometheus counter carries the same value.
- Dependencies: #24, #25.
- Priority: P1. Labels: `backend`, `observability`.

**29. Grafana dashboard + alert: variant-lookup access pattern and invalidation correctness**
- Purpose: Give visibility into the project's first genuinely skewed cache access pattern and its invalidation-on-write behavior (#26), neither of which the existing golden-signal/TTL-only dashboards capture — and alert on the one failure mode here that's a correctness issue, not just a performance one.
- Acceptance Criteria: Dashboard contrasts `workItemCache` vs `variantAnnotationCache` hit/miss/error rate, a bounded top-N-hot-keys-vs-long-tail panel (not a raw per-variant label), invalidation-event rate by reason, and cache-entry-age distribution. One alert ships with this item, not deferred to #21: `ClinVarInvalidationLag`, firing on invalidation-job failure or a served entry older than the latest completed release by more than a 15-minute sweep window, with a linked runbook. Every other new panel stays explicitly labeled in-panel as a stepping-stone toward #21, matching the precedent #20 already set. Verified with real synthetic traffic shaped like each domain, and a staged invalidation failure confirmed to fire the alert inside the window.
- Dependencies: #26, #27.
- Priority: P1. Labels: `observability`.

**30. Reserve M6 — real batch/alignment pipeline (placeholder, tracking only)**
- Purpose: Explicitly reserve the milestone that actually closes the project's remaining architectural gap (no object-storage/batch-Job data plane) — a real alignment pipeline on real FASTQ data, self-hosted MinIO, Kubernetes Jobs or a workflow engine — so it isn't left as vague "eventual" work. Raised directly by the Staff Bioinformatician's review of ADR 0018, against the specific failure mode of stopping at "portfolio project with a bio-flavored coat of paint."
- Acceptance Criteria: Stays open and unscheduled until a dedicated future ADR defines its concrete scope; must not be closed as part of M5 work. Cross-referenced from ADR 0018 as the commitment mechanism for the reserved milestone.
- Dependencies: none — intentionally unscoped placeholder.
- Priority: P2. Labels: `architecture`.
