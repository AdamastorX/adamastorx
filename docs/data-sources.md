# Data sources

Status: ClinVar ingestion is live (M5, ADR 0018/0019), verified end to
end against the real cluster. gnomAD enrichment was planned alongside
ClinVar but was never built and is now explicitly cut (ADR 0021,
simplification pass, backlog #24/#24a) — ClinVar is the sole annotation
source.

## ClinVar

- Publisher: NCBI (National Center for Biotechnology Information).
- License: public domain (US federal government work).
- Format/build: VCF, GRCh38.
- Update cadence: weekly.
- Source: <https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/>
- Use: primary and sole source for clinical significance lookups by
  chrom/pos/ref/alt or rsID (backlog #24). Each ingested record is tagged
  with the specific ClinVar release it came from (backlog #25), so every
  served answer is traceable to a release. No modification of the
  underlying data beyond ingestion/indexing.
