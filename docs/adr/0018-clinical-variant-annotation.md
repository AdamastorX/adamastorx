# 0018. Real clinical variant annotation lookup: added alongside the work-item domain, not replacing it

Status: Accepted

## Context

M2/M3 built and proved a full distributed-systems stack against one
domain: synthetic "work item" CRUD through `gateway`→`api`→Kafka→`workers`,
cache-aside on Redis, persisted to Postgres. That domain did real work —
the Kafka trace-correlation path is a proven, tested demonstration and is
the subject of ADR 0011/0012/0016 and the existing Grafana dashboards —
but it has a structural limitation the project's own review process
surfaced: work items are immutable once created, so every cache story
this project has ever demonstrated is TTL-based expiry against data that
never changes underneath the cache. There is no invalidation-on-write
story and no genuinely skewed access pattern, because nothing in the
domain has ever forced one. A separate, earlier cross-domain review also
flagged that the project has no reproducibility/provenance story —
nothing tracks *which version of the truth* produced a given answer —
latent until now only because the synthetic domain has no versioned
truth to lose track of.

Several real-data domains were evaluated (weather/air-quality APIs, the
USGS earthquake feed, Wikipedia's EventStreams SSE firehose, a
self-referential CVE/NVD feed, a GEO gene-expression matrix, a full
alignment pipeline on real FASTQ data via Kubernetes Jobs and
self-hosted MinIO) against three criteria: near-drop-in cost against the
*existing* `gateway`/`api`/`workers`/Kafka/Postgres/Redis shape (no new
infrastructure pattern this milestone), introduces a genuinely new
signal the system hasn't exercised, and has enough real-world weight to
be worth building. All were rejected for this milestone specifically
(wrong access-pattern shape, requires a new streaming-consumer pattern,
requires batch-Job/object-storage infrastructure this milestone
deliberately excludes, or simply produces no new signal) — full
reasoning for each in the project's cross-domain review notes, not
repeated here.

Real clinical variant annotation — looking up a genomic variant against
ClinVar for clinical significance, optionally cross-referenced against a
gnomAD slice for population allele frequency — was independently
converged on by two separate expert reviews run without shared context
(a Staff SRE review and a Staff Bioinformatician review). It satisfies
all three criteria: it fits the existing request/response shape, it
produces a real, heavily skewed access pattern (a small number of
well-known pathogenic variants looked up constantly, a long tail almost
never), and the data itself is real and non-trivial (ClinVar's GRCh38
VCF, ~250MB compressed, updated weekly, tabix-indexable).

The Staff Bioinformatician flagged one requirement as easy to miss and
expensive to retrofit: ClinVar *reclassifies* variants over time — a
Variant of Uncertain Significance today can be reclassified Pathogenic
on the identical coordinates months later as the evidence base grows.
This is the project's provenance gap surfacing concretely for the first
time, not a staleness detail — a correctness requirement. Whatever gets
built must record which specific ClinVar release produced any given
answer, from day one.

## Decision

**Add a variant-annotation domain alongside the existing work-item
domain. Do not replace it.** The work-item domain represents real,
already-tested infrastructure investment (the Kafka trace-correlation
path is referenced by three existing ADRs and the current dashboards);
replacing it would be an expensive rewrite for uncertain benefit, and
the two domains are not actually redundant — work-item CRUD demonstrates
a write-heavy, event-sourced, TTL-only cache story, variant lookup
demonstrates a read-heavy, skewed-hot-key, invalidation-on-write cache
story. Different SRE properties, not two toy versions of the same thing.
If the work-item domain is ever judged genuinely redundant, that's a
future ADR's call to make deliberately, not a side effect of this one.

Concretely, this milestone (**M5 — Clinical Variant Annotation**) adds:

- **A lookup endpoint in `api`**, accepting `(chrom, pos, ref, alt)` or an
  rsID, returning clinical significance from ClinVar and, optionally,
  population allele frequency from a gnomAD chr21/chr22 slice (a
  deliberately bounded subset, not the full genome — keeps M5's storage
  and ingestion footprint small; broader chromosome coverage is a future
  call, not part of this one). rsID lookups resolve through a small
  Postgres index table (`clinvar_variant_index`) populated during
  ingestion, since tabix indexes are position-based — scanning 250MB per
  rsID lookup is a non-starter.
- **htsjdk (`com.github.samtools:htsjdk`), in-process, not a
  `bcftools`/`tabix` subprocess**, for querying the tabix-indexed VCF.
  This is a request-path lookup; per-request fork/exec latency and
  stdout-parsing fragility are worse than one extra JVM dependency.
  Reserve subprocess-shelling for nothing in this milestone.
- **An ingestion path inside the existing `workers` shape** — explicitly
  not a new job system, no Kubernetes Jobs — that downloads and
  tabix-indexes the ClinVar VCF (validating NCBI's published `.tbi`
  against a checksum, rebuilding only if validation fails) and records
  each release's version/date (parsed from the VCF's own `##fileDate`
  header, not file mtime) as first-class, queryable Postgres metadata
  (`clinvar_release` table).
- **Weekly refresh via an in-process scheduled trigger** (`@Scheduled`)
  inside `workers`, not a Kubernetes `CronJob`. A `CronJob` spawns a
  `Job` under the hood — on a literal reading it would violate this same
  ADR's "no Kubernetes Jobs" boundary, and it's a K8s primitive this
  project has never used (missed-schedule handling, concurrency policy,
  job-history GC, RBAC for job creation — new failure surface for no
  benefit here). In-process scheduling avoids the ambiguity outright
  rather than requiring a judgment call every time someone reads this
  ADR. A manual admin-triggered re-ingestion endpoint exists alongside it
  for dev/CI use.
- **A shared RWX PVC** (`/data/refdata`, ~2Gi, sized from measured
  artifact size with headroom for a double-buffered download-then-swap
  so a partially-written release is never served) mounted on both `api`
  and `workers` — not self-hosted MinIO, not object storage; this
  milestone stays inside the existing volume model (`local-path`
  StorageClass, same pattern as Postgres/Prometheus/Loki/Tempo's
  continuity-valued PVCs). `workers` writes a new release into its own
  versioned subdirectory and only flips a `current` pointer after the
  Postgres row commits, so readers never see a half-written release.
  **This is `workers`' first PVC — a real precedent shift from stateless
  to stateful**, and `local-path` PVCs are node-pinned in k3s, which
  means `workers` must stay at `replicas: 1` (or gain node affinity) for
  as long as this PVC exists. Stated explicitly rather than left
  implicit: if `workers` ever needs to scale out for the work-item
  domain, this is why it can't without a StatefulSet-style rework.
  Acceptable now — a node loss degrades to "re-download on next start,"
  not data loss of anything irreplaceable, since this is a cache of
  public reference data.
- **Release-aware cache invalidation, not TTL-only, for variant-lookup
  cache keys.** On a completed ingestion, the previous and new tabix
  files are diffed *only* for keys actually present in Redis (`SCAN` the
  `variantAnnotation:*` keyspace, point-query just those coordinates
  against both releases) — not a full ~2M-record diff every week. Only
  entries whose classification actually changed get evicted. This is the
  specific new cache behavior this milestone exists to produce; a new
  `cache.invalidations{cache="variant-annotation",reason="release-changed"}`
  Micrometer counter makes it independently visible on
  `/actuator/prometheus`, distinct from the existing `cache.gets` hit/miss/error
  counters (ADR 0016).
- **Provenance propagation**: every annotation response and its Redis
  cache entry carries the ClinVar release identifier that produced it.
  Stamped once, at response-assembly time, into a single shared field
  (`VariantAnnotation.clinvarReleaseId`) — not computed independently as
  a span attribute and a metric tag, which would let the two silently
  drift. From that one field: a `clinvar.release_id` span attribute on
  the variant-annotation-resolution child span (propagated through the
  existing Kafka-header trace-context mechanism, ADR 0013), a
  `clinvar_release` tag on the lookup counter (bounded cardinality —
  releases are infrequent), and structured metadata (not an indexed
  label) in Loki, matching how `trace_id`/`span_id` are already handled
  under ADR 0015. Tempo's custom-attribute search-enablement needs
  explicit confirmation (not assumed working just because `trace_id`
  works) before this is called done.
- **A dashboard contrasting the new pattern against the existing one**:
  hit/miss/error rate split by cache (`workItemCache` vs
  `variantAnnotationCache`), a bounded top-N-hot-keys-vs-long-tail view
  (an allow-listed set of ~20 known high-traffic variants plus an
  `other` bucket — *not* a raw per-variant-ID label, which would be
  unbounded cardinality against ~3M ClinVar records), invalidation-event
  rate split by reason (`release-changed` vs the work-item domain's
  `ttl-expiry`), and cache-entry-age distribution (sawtooth for
  work-item, right-skewed for variant lookups). ClinVar release
  surfaces both as a bounded Prometheus label (cache population by
  release) and as a Loki drill-down (which specific variants were
  invalidated for a given release — inherently per-key detail that
  belongs in logs, not metrics).
- **One narrow, deliberate exception to "ship the dashboard first, defer
  alerting to M4"** (the precedent ADR 0017 already set for the
  golden-signal dashboards): cache-invalidation correctness here isn't
  a performance nicety like p99 latency — a stale-served answer after a
  classification changed is a correctness bug with a clinical-safety
  framing, a different risk class than "dashboard exists before the SLO
  framework does." One alert ships now: `ClinVarInvalidationLag`, firing
  on an explicit invalidation-job-failure counter, or on a served cache
  hit whose release is older than the latest completed ingestion by more
  than a 15-minute sweep window. It ships with a runbook (manual targeted
  invalidation sweep, verification via a `variantAnnotation:*` key scan
  cross-checked against the endpoint, trace lookup for the failed sweep).
  Every other new panel (hit/miss ratio, skew, entry-age) stays
  unalerted, explicitly labeled in-panel as a stepping-stone toward M4,
  exactly as ADR 0017 already established the pattern for.
- **No new ArgoCD Application, namespace, or Secret.** This is a
  `valuesObject` diff on the existing `workers` Application (a
  persistence block plus resource limits sized from a measured
  refresh-burst profile). `workers` keeps its current namespace — unlike
  Postgres/Redis (ADR 0012/0016), there's no single-consumer-credential
  concern to isolate, since ClinVar and gnomAD are public, unauthenticated
  downloads. No Secret object to reason about at all, a genuine
  simplification worth stating rather than leaving implicit.
- **Hard scope boundary, restated**: no Kubernetes Jobs, no object
  storage, no workflow engine (Nextflow/Snakemake) anywhere in M5. Those
  are reserved for a separately sequenced future milestone.

## Consequences

- The system gains a real, heavily skewed cache access pattern and a
  real invalidation-on-write behavior it has never had, alongside the
  existing TTL-only pattern — a genuine before/after story for the
  Grafana dashboards, not a relabeled version of the same shape.
- The provenance/reproducibility gap, previously only flagged as a
  weakness, closes for this domain from the first release, not
  retrofitted after the fact.
- Marginal infrastructure cost stays low: no new deployment pattern, no
  new data-plane concept, reuses Postgres/Redis/Kafka/observability as
  deployed today. The one real precedent shift is `workers` becoming
  stateful for the first time (a PVC, node-pinned, `replicas: 1`) —
  accepted, documented, not silently absorbed.
- Two domains now coexist in the codebase for demonstration purposes
  rather than product necessity. Intentional, per the Decision above —
  not accidental scope creep.
- The ~250MB, weekly-updated ClinVar file needs a small fixture slice
  for fast CI runs (`services` repo concern) and a `dev` values overlay
  pointing at that fixture instead of NCBI for scratch-cluster bring-up
  (`platform` repo concern) — tracked as backlog items, not solved by
  this ADR itself.
- Data licensing/attribution (ClinVar: NCBI, public domain; gnomAD:
  Broad Institute, open access with citation expectations — confirm
  exact current wording before publishing citation text) is documented
  in a data-sources note, not assumed.
- **Sequencing commitment, not left vague**: this ADR explicitly reserves
  — and does not attempt to pull forward — a second, larger milestone
  (tentatively **M6**): a real batch/Job-based alignment pipeline on real
  FASTQ data, landing results in self-hosted MinIO via Kubernetes Jobs.
  That milestone is what actually closes the project's remaining
  architectural gap (no object-storage/batch-Job data plane) and is the
  correct home for the Nextflow/Snakemake-style orchestration questions
  this ADR explicitly excludes here. Tracked as a placeholder backlog
  item so it cannot silently disappear. Letting it float indefinitely as
  aspirational is the specific failure mode the Staff Bioinformatician
  warned against: the project stopping at "portfolio project with a
  bio-flavored coat of paint" instead of demonstrating the harder
  batch/object-storage story it's actually capable of.
