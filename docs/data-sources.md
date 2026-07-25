# Data sources

Status: reference note added ahead of implementation, alongside ADR 0018
(M5). The ingestion/usage described below is planned, not yet built — see
`docs/roadmap/backlog.md` items #24-#30 for current status.

## ClinVar

- Publisher: NCBI (National Center for Biotechnology Information).
- License: public domain (US federal government work).
- Format/build: VCF, GRCh38.
- Update cadence: weekly.
- Source: <https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/>
- Planned use: primary source for clinical significance lookups by
  chrom/pos/ref/alt or rsID (backlog #24). Each ingested record is tagged
  with the specific ClinVar release it came from (backlog #25), so every
  served answer is traceable to a release. No modification of the
  underlying data beyond ingestion/indexing.

## gnomAD

- Publisher: Broad Institute (Genome Aggregation Database).
- License: open/public access; citation expected per Broad's terms of
  use — confirm current wording at
  <https://gnomad.broadinstitute.org> before publishing citation text in
  a user-facing surface, terms may change independent of this note.
- Slice used: chr21 and chr22 only, deliberately bounded — not the full
  genome — to keep M5's storage and ingestion footprint small (ADR 0018).
  Broader chromosome coverage is a future call, not part of M5.
- Update cadence: infrequent relative to ClinVar (versioned releases, not
  weekly); refresh handled separately from ClinVar's weekly cycle
  (backlog #27).
- Source: <https://gnomad.broadinstitute.org/downloads>
- Planned use: optional enrichment on the variant lookup endpoint — when
  a queried variant falls within the ingested chr21/chr22 slice, its
  gnomAD allele frequency is returned alongside ClinVar clinical
  significance (backlog #24).
