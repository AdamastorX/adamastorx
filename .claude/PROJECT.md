# AdamastorX — Project Context

Canonical source. Other repos (`platform`, `services`, `observability`)
carry a short pointer back here instead of a copy — one file to keep
current beats four copies drifting apart.

Before starting work, also check `docs/SESSION_STATE.md` — in-flight
work, open PRs, known gremlins, and anything the last session left
unfinished. This file (`PROJECT.md`) is the stable picture; that one is
the scratch log of *right now*.

## Mission

Operate a small, realistic distributed system — cluster, GitOps delivery,
application, observability stack — using boring, well-understood tools, to
generate genuine platform/SRE/DevOps problems worth solving.

## Goals

- A cluster and delivery pipeline that could plausibly run in a small
  real-world platform team.
- An application (API/workers/`clinvar-service`) that's just complex
  enough to need Kafka, PostgreSQL, and Redis for real reasons, not for
  show — and no more surface than that. A simplification pass (ADR
  0021) removed `gateway` and `whoami` entirely once both were found
  carrying real infrastructure while doing no real work.
- Observability and reliability practice that's actually exercised (alerts
  fire, runbooks get used, SLOs get burned), not decorative.

## Current architecture

A single-node k3s v1.36.2 cluster (the owner's local machine, provisioned via
Terraform SSH remote-exec from `platform/terraform/`; moving to a dedicated
host is a planned variable change) runs ArgoCD v3.4.5 as the GitOps
entrypoint — an app-of-apps root Application watches the `platform` repo's
`argocd/apps/` on `main` with prune + selfHeal, so all cluster changes flow
through Git. Traefik 41.0.2 (hostPort 80/443) and cert-manager v1.21.0 are
deployed as ArgoCD Helm Applications, with a local CA chain (`selfsigned` →
`adamastorx-ca` ClusterIssuer); Let's Encrypt is deliberately deferred until
a host with public DNS. `api` has its own Ingress and TLS certificate
(ADR 0021) — the live Traefik+TLS+service path, after `gateway` (one
placeholder route, no real function) and `whoami` (the original
one-time Traefik+TLS proof, superseded) were both removed. See
`docs/architecture/overview.md` for what's live vs. the target shape.

## Technology decisions

Approved: Kubernetes (k3s), Terraform, Helm, ArgoCD, GitHub Actions, Kafka
(KRaft), PostgreSQL, Redis, OpenTelemetry, Prometheus, Grafana, Loki, Tempo,
Mimir, Traefik, cert-manager, Trivy, Spring Boot.

Explicitly excluded — do not introduce without an ADR overturning this:
Vault, Crossplane, Backstage. The platform stays intentionally small.
Cilium and service mesh were both on this list originally; both were
overturned (ADR 0023, ADR 0024 respectively) and removed from it — neither
is deployed yet (both are M7, not yet built, see "Current milestone"
above), but the exclusion itself no longer applies to either.

## Current milestone

M0-M5 are complete/verified live. **M4 Reliability** itself is not fully
closed — runbooks (#22) are partial and backup/restore (#23a) is still
open — but per `docs/roadmap/milestones.md`'s own rule (an item starts
when its own dependencies clear, not when the whole previous milestone
closes), real work from the expansion phase that followed (ADR 0022) has
already landed in parallel and is live today: **M6** progressive delivery
(`api` is an Argo Rollouts canary with an automated SLO-analysis gate,
backlog #46) and the continuous workload generator (#45); **M8**
`watchlist-service`'s guaranteed outbox-plus-relay fan-out (#53, ADR 0026)
and `clinvar-service`'s async ClinVar-ingestion job control plane (#54);
**M9** continuous profiling via Pyroscope (#57, ADR 0028); and **M10**
KEDA autoscaling `workers` on real Kafka consumer lag (#63). Per-tenant
API keys and rate limiting at the edge (#56, ADR 0027) also shipped,
satisfying the reintroduction condition ADR 0021 left open when `gateway`
was removed.

**Not yet built**: M7's multi-node substrate — Cilium (ADR 0023) and an
Istio ambient mesh (ADR 0024) are approved decisions, not running
components — still gates M11 (`sre-agent`) and the reopened M12
bioinformatics milestone (ADR 0025), neither of which has started.

**M13's real-time market-sentiment pipeline (ADR 0029) is complete and
live** — originally gated on M7 for CPU-headroom reasons (#77), the owner
explicitly overrode that gate 2026-08-02 to build and deploy
incrementally on the current single-node laptop instead (a real headroom
check before each service's own sync, `docs/roadmap/backlog.md`'s M13
intro has the full tradeoff). All five services are built, merged, and
running on the real cluster: `news-ingestor` (#79, real WSJ/MarketWatch
articles → `news.article.published`), `market-data-ingestor` (#78, real
Finnhub websocket → `stock.price.tick`), `sentiment-analyzer` (#80, real
VADER scores → `news.sentiment.scored`), `aggregator` (#81, this
project's first Kafka Streams app, windows both topics into per-ticker
price/sentiment aggregates, serves `GET /aggregates`), and `visualizer`
(#82, a static Chart.js page — same no-backend shape as `clinvar-viewer`
— polling `aggregator` live). Two real, live-only bug classes were found
and fixed along the way, not just in code review: #84 (Kafka CLI/
ArgoCD-sync fragility) and #85 (`aggregator`'s two RocksDB incidents, a
`libstdc++`/Alpine gap and a metrics-wiring bug, both silently masked by
a Healthy-reporting pod — #85's own liveness-probe hardening follow-up
remains open, tracked not glossed). Real trade/news traffic wasn't
flowing at final verification time (outside real US market hours), so
end-to-end proof used a mix of organic data (news) and directly-injected
real messages/requests (ticks, aggregates) — stated honestly per
service, not glossed as fully organic. **Simplification pass (ADR 0021)**: `gateway` and
`whoami` were removed entirely; gnomAD, HGVS/liftover (#40/#41), and
several over-scoped M4 items were cut — upheld by ADR 0022, except that
M6 (the closed batch/bioinformatics reservation, backlog #30) was
deliberately reopened under a new milestone number, M12, once the
project's own stated goal changed (ADR 0022/0025) — not silently
reversed.

See `docs/architecture/overview.md` for the detailed real/live-vs-not-yet
breakdown, `docs/roadmap/milestones.md` and `docs/SESSION_STATE.md` for
exactly what's in flight right now — this section is a point-in-time
summary, those files are the current source of truth.

## Repository map

| Repo | Owns |
|---|---|
| `adamastorx` | Docs, roadmap, backlog, Claude context — this repo |
| `platform` | Terraform, Helm, ArgoCD, Kubernetes manifests, bootstrap |
| `services` | Gateway, API, workers, shared libraries |
| `observability` | Grafana, dashboards, alerts, runbooks, OTel config |

## Coding principles

- Small PRs, incremental delivery.
- Simple over clever; boring over novel.
- No gold plating, no premature optimisation, no framework for a problem you
  don't have yet.
- Three similar lines beat a premature abstraction.

## Definition of Ready

- Purpose and acceptance criteria are written.
- Dependencies are identified and either resolved or explicitly `blocked`.
- Fits in one epic, ideally one repo.

## Definition of Done

- Acceptance criteria met.
- Tests pass (where the change has runtime behaviour to test).
- Docs updated — architecture, ADR, or runbook, whichever applies.
- Opened as a PR (never committed straight to `main`) and merged only after
  the human owner reviews and approves it — see `.claude/WORKFLOW.md`.
