# 0048. `recruiter-pipeline` as a new AdamastorX flow, isolated, and a JEV pilot

Status: Proposed

## Context

The owner runs a separate personal project, `recruiter-pipeline`
(https://github.com/lmpeixoto/recruiter-pipeline): Gmail LinkedIn
notifications → LLM classification → LLM structured extraction → web
enrichment → LLM fit assessment → Notion board. Today it runs manually,
locally, against the owner's own Gmail/Notion accounts via OpenRouter.

Three real, separable wants drove this decision, discussed together
because the first two only make sense inside AdamastorX and the third
gates whether they should be:

1. **Automatic polling.** The owner wants it running on a schedule, not
   triggered by hand — the exact shape `clinvar-service`'s weekly
   ingestion and `news-ingestor`'s RSS polling already have.
2. **A real-traffic pilot of TypeSafe AI's Jev**, a "System One" model
   (typed, calibrated, sub-second structured decisions, not generated
   text) for exactly the steps that are already typed decisions in this
   pipeline: `Classification` (bool + confidence) and most of
   `OpportunityAssessment` (0-100 scores + a closed-set
   `recommended_action`). `ProposalExtraction`'s free-text fields
   (names, titles, salary, summary) stay on the existing OpenRouter LLM
   path — Jev's guarantee (output drawn from a predefined set) does not
   fit open-vocabulary extraction. Jev is early-access/waitlisted
   (`console.typesafe.ai`); this ADR does not depend on access being
   granted, only on the decision to pilot it once it is.
3. **A genuinely new operational shape for AdamastorX**: no existing
   flow here polls an external mailbox, and none has an LLM (or a
   typed-decision model) sitting as a routing/filtering node inside a
   Kafka pipeline rather than a side-call. That is real, new content for
   this project's own stated goal (ADR 0022: a new service earns its
   place by adding a shape, not a buzzword) — matching the
   `news-ingestor → sentiment-analyzer → aggregator` idiom already
   proven for M13.

The real tension, named plainly rather than smoothed over: every
existing AdamastorX flow processes public data (ClinVar, market prices,
financial news). This one processes the owner's own personal
correspondence and writes to the owner's own Notion workspace. The
project's own stated direction includes eventually exposing some Grafana
dashboards publicly (backlog #88 — currently Descoped, no public
exposure exists today) and publishing articles with real operational
evidence (backlog #129). A new namespace's dashboards being swept into
that by default, or a published article illustrating the JEV pilot with
real company names or compensation figures, would leak personal data
through a surface built for a different purpose.

Resolved, owner-confirmed: Grafana carries no public exposure today
(#88 Phase 2 stays Descoped) — Notion's own privacy is unaffected by
where the pipeline runs, since only the owner's Notion auth ever reads
it. What actually needs a standing rule is this namespace's own
observability surface, independent of whatever #88 eventually decides
for the rest of the cluster, and the discipline a future article has to
follow.

**Alternatives considered.** Running `recruiter-pipeline` unchanged on a
personal scheduler elsewhere (a home cron, a scheduled GitHub Action,
Fly.io) would satisfy want 1 alone, at the cost of forgoing wants 2 and
3 — a separate, idle piece of infra instead of reusing what the owner
already operates and wants to keep exercising. Rejected: the owner
explicitly wants this inside AdamastorX for the distributed-systems
value, not despite it.

## Decision

1. **Go.** `recruiter-pipeline` becomes a new AdamastorX flow: a
   scheduled Gmail-poll producer, Kafka topics for
   ingested/classified-opportunity/extracted/assessed stages, a
   Notion-sink consumer, its own namespace (`recruiter` — exact service
   boundaries decided at implementation time, not fixed here), its own
   Postgres (same namespace-local pattern as `api`/`clinvar-service`/
   `watchlist-service`, replacing the local SQLite file).
2. **Jev is piloted on the `Classification` and `OpportunityAssessment`
   steps only.** `ProposalExtraction`'s free-text fields keep the
   existing OpenRouter LLM path, run in parallel where the two can
   overlap. **Sequencing: Jev is validated standalone inside the
   existing `recruiter-pipeline` repo first** — a `JevClassifier`
   dropped in next to today's `Classifier`, compared against real
   historical state before any cluster work starts, decoupling "does
   Jev work for this data" from "should this live in AdamastorX."
3. **Standing exclusion, independent of #88's own outcome:** the
   `recruiter` namespace's dashboards, alerts, and any aggregate metrics
   are permanently excluded from any future public Grafana exposure,
   recorded here so it is never a default inclusion anyone has to
   remember to carve out later.
4. **Publishing guardrail:** an article about the Jev pilot may cite
   this project's real architecture and the real pipeline shape, but
   may not include real company names, recruiter identities, or
   compensation figures — synthetic or redacted examples only. This is
   the opposite data-sensitivity case from ClinVar (real but public
   data), stated so the two are never conflated.
5. **Credentials** (Gmail OAuth, Notion token, OpenRouter key, the Jev
   key once granted) follow the existing out-of-band Secret pattern
   (`bootstrap/create-stateful-secrets.sh`), never committed. The Gmail
   OAuth scope is narrowed as far as the Gmail API actually allows
   (ideally restricted to the LinkedIn-notifications label, not the
   whole mailbox) — verified at implementation time, not assumed
   available.
6. **Standard-of-care applies unchanged:** dashboard, SLO row, alert,
   and runbook per #109's AC template; a CiliumNetworkPolicy batch for
   the namespace per #50/#168's pattern; the same branch→PR→human-review
   discipline as every other service.

## Consequences

- First AdamastorX flow carrying personal, non-public data — a higher
  trust tier than ClinVar/market data, which never needed one. The
  exclusion in Decision 3 and the credential scoping in Decision 5 are
  the concrete bar that tier has to clear; a future reviewer should
  check both are still true, not assume they are.
- First real-traffic (not synthetic-benchmark) test of a "System One"
  typed-decision model in this project — genuine new content, in the
  same tradition as #28's Pyroscope flame-graph finding (measure, don't
  assume the model's own claims).
- Named plainly: this flow does not teach AdamastorX a distributed-
  systems lesson the project was missing the way ClinVar (bioinformatics
  data shape) or M13 (real-time multi-source correlation) did — it
  exists because the owner wants it running here. That is an accepted
  reason, stated rather than dressed up as something else.
- Implementation lands as normal: service(s) in `services`, manifests
  and NetworkPolicy in `platform`, dashboard/alert/runbook in
  `observability`, backlog items filed against this ADR rather than
  re-arguing it.
