# 0025. Reopen the bioinformatics-workloads milestone that ADR 0021 closed

Status: Proposed

## Context

ADR 0021 closed the reserved M6 (backlog #30) — a real batch/alignment
pipeline on self-hosted MinIO plus Kubernetes Jobs, working on real FASTQ
data — and it was right to, *for the goal it was written under*. A staff
bioinformatician review had warned that such a milestone would demonstrate
"bioinformatics depth for a bio audience, not SRE/platform depth," and that
the whole project risked reading as *a bioinformatics side-project with a
k8s coat of paint* rather than an SRE portfolio. ADR 0021's judgement — for
a tight, defensible SRE portfolio aimed at a hiring manager skimming a
repo — was that the distinctive asset (`clinvar-service`'s polyglot pivot
and data-provenance story) was already delivered, and that going deeper
into the bio domain added breadth without a new operational signal. That
reasoning is not being called wrong here, and it is not being strawmanned:
it was correct for its stated goal.

The goal has since changed, and that change is already on record. **ADR
0022** documents the shift from "a tight portfolio a hiring manager skims"
to "a genuinely interesting home lab to publish about, expanding services
and application logic, where a component earns its place by producing a new
*class* of operational problem." Two things follow that ADR 0021 could not
have weighed:

1. Under the changed goal, a real domain workload is no longer "breadth for
   a bio audience with no new signal." A multi-stage pipeline over real
   files on object storage is a new operational *shape* this project does
   not have — which is precisely ADR 0022's own bar for reopening
   something.
2. The owner is specifically targeting **health-tech industry roles**,
   where a real, domain-relevant, correctly-licensed data workload is a
   genuine asset rather than noise. ADR 0021 weighed the bio domain as a
   liability against a generalist SRE audience; against this audience the
   sign flips.

This is the natural, explicit consequence of ADR 0022's goal shift reaching
the one thing ADR 0021 closed — the same pattern ADR 0022 already applied
to #34→#45 and #23b→#52: *reopened in changed form because the premise
changed, not because the original reasoning was wrong.* This ADR states it
plainly rather than letting a future reader think ADR 0021 was quietly
reversed.

## Decision

**Reopen the bioinformatics-workloads work as a new milestone (M12, backlog
#67–#72), not as a verbatim restoration of the closed #30.** The scope is
chosen so the SRE/platform learning is the point and the bio domain is the
substrate that makes it real:

- **Metadata API (`metadata-service`, Spring Boot)** — owns studies,
  anonymized patients/samples, and pipeline-run metadata. Real domain
  modelling with real relationships, not another `work-items` clone.
- **Object storage (MinIO)** for real files — FASTQ, BAM, VCF. This is the
  object-storage data plane #30 wanted; the difference from #30 is *why* —
  see below.
- **A real pipeline engine (Nextflow)** actually executing real
  bioinformatics pipelines on Kubernetes, not a mocked stand-in.
- **Kafka events modelling the pipeline lifecycle** — `PipelineStarted` →
  `PipelineFinished` / `AnalysisFailed` → `SampleImported`. What is
  genuinely new here, stated explicitly: a **multi-stage, saga-like
  lifecycle**, not a single hop. It is distinct from both existing event
  shapes — `work-items` (simple produce/consume) and ClinVar
  (release-diff / cache-invalidation, one event with one consumer). This is
  the project's first event stream that models a *process* with ordered
  states and failure branches.
- **A Notification service (`notification-service`, Spring Boot)** consuming
  that lifecycle — the first genuinely new Kafka consumer topology this
  project has had since `workers`.
- **Real public datasets, explicitly not synthetic**, matching the ClinVar
  precedent of real, correctly-licensed public data: genomics (1000
  Genomes, TCGA, GEO — ClinVar already in hand) and, as a substantial new
  domain with a different data-volume/streaming shape, **medical imaging
  (DICOM, TCIA)**. The real licensing/access friction is flagged per
  dataset honestly, not glossed — **MIMIC specifically requires a
  credentialed data-use agreement, not just a download**, and that is a
  real constraint on what can be ingested, not a footnote.

The SRE/platform substance — the reason this clears ADR 0022's bar rather
than being bio-for-bio's-sake — is the lifecycle and the data plane: jobs
orphaned by a pod restart mid-pipeline, a saga's failure branch,
object-storage as a new stateful component to back up and reason about,
and a real large-file / streaming ingestion volume the project has never
carried. The alignment algorithms themselves are not the deliverable; the
platform behaviour around running them is.

## Consequences

- ADR 0021's closure of #30 (and Simplification #S4) is **narrowed to the
  goal it was written under**, exactly as ADR 0022 narrowed the rest of
  ADR 0021 — it is not superseded, and its reasoning stays the correct
  record of why this was right to close for a tight SRE portfolio.
- The "bio coat of paint" risk ADR 0021 named is **real and consciously
  accepted**, not dismissed: the mitigation is that the milestone's
  acceptance criteria are written around operational shapes (saga lifecycle,
  orphaned-job recovery, object-store data plane), and the bio depth is
  bounded to running real public pipelines on real licensed data, not
  building novel bioinformatics.
- Operational surface grows materially: MinIO is a new stateful component
  that #23a's backup/restore discipline must cover; Nextflow's Kubernetes
  executor is a new source of Jobs and a new failure surface; the imaging
  datasets bring a data volume the single-node history never had, which is
  itself a reason this lands after the M7 multi-node/replicated-storage
  substrate, not before it.
- This is a **new milestone number**, not a resurrected M6 — M6 is now
  "Real Demand and Progressive Delivery" (ADR 0022). Reusing the number
  would falsely imply the old scope; the changed goal gets a fresh slot.
</content>
