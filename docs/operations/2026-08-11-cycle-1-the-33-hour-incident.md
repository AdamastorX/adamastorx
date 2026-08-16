# Operations review — cycle 1 (2026-08-11 → 2026-08-12)

First cycle of backlog #124's standing operations review. Per #124's own
AC, cycle 1's content is retroactive: the 2026-08-11 four-alert incident
(backlog #122) already generated exactly the record this review exists
to produce, it just never got formatted as one. Where a field genuinely
can't be reconstructed after the fact (a live node-headroom snapshot
*at incident time*, specifically), that's stated honestly below rather
than backfilled with today's number wearing an old date.

## Alerts that fired, real duration, real time-to-acknowledge

Found firing by an independent review on 2026-08-11, all four traced to
backlog #49's 2026-08-10 cluster rebuild:

| Alert | Real firing duration | Runbook existed? |
|---|---|---|
| `BlackboxProbeFailing` (6 targets) | ~33h | Yes |
| `ApiVariantsLookupHighErrorRate` | ~21h | Yes |
| `ApiHighErrorRate` | ~20h | Yes |
| `MarketDataStaleFeed` (5 tickers) | ~6h | Yes |

Alertmanager delivered **189 notifications, zero failures**, across all
four. Time-to-acknowledge: **up to 33 hours** — the detection layer
worked exactly as designed; nobody answered. This gap, not a signal
gap, is #124's entire reason for existing.

## What was actually done

Three distinct root causes, all downstream of the same rebuild, fixed
and verified live (not assumed) on 2026-08-12:

1. **`clinvar-service` refdata PVC empty** — a stale pre-rebuild
   `clinvar_release` row pointed at a VCF that no longer existed. Fixed
   by triggering a real ingestion (~7 min, 4,461,717 records) and
   confirming `GET /variants/lookup?rsid=rs80357906` returns a real
   `200`/`Pathogenic`, not a 502.
2. **`clinvar.ingestion.completed` topic missing on the rebuilt
   broker** — never declared in git; created live via
   `kafka-topics.sh --create --if-not-exists` (the sanctioned fallback
   `docs/SESSION_STATE.md` already documents for a stuck ArgoCD
   provisioning Job), then formalized in `kafka.yaml`. `api` and
   `watchlist-service` both stopped logging `UNKNOWN_TOPIC_OR_PARTITION`
   within seconds.
3. **`blackbox-exporter`'s `hostAliases` pinned a pre-rebuild Traefik
   ClusterIP** — corrected to the real live IP; `BlackboxProbeFailing`
   dropped from 6 firing targets to 1 (a separate, real finding, below).

`MarketDataStaleFeed` cleared on its own before the response began —
confirmed, not investigated further, since the #87 fallback was
serving real data throughout.

**Three further real, separate findings surfaced investigating the
above, none of them rebuild casualties**:

- `api` OOM crash loop (70+ restarts, no explicit JVM heap sizing) —
  fixed live, canary-deployed.
- `argo-rollouts` missing from `prometheus-server`'s own Cilium
  NetworkPolicy egress list — the same "periodic, not constant traffic"
  class of gap #50's original batch already had two other instances of.
  Fixed live.
- `GET /work-items` unbounded (`repository.findAll()`, ~14MB/108,000+
  rows) — the one `BlackboxProbeFailing` target that didn't clear with
  the other five. Confirmed a genuine risk the hard way: measuring its
  real latency OOM'd the just-fixed `api` pod a second time. Not
  hot-fixed under incident pressure — tracked separately as #130,
  closed later with real pagination and tests.

A fourth, slower-burning thread (`ClinVarIngestionFreshnessBreach`) ran
alongside this incident but didn't fully close until 2026-08-14, after
three further real attempts and two application-level memory fixes —
see #122's own backlog entry for the full multi-day account; not
duplicated here since this cycle's scope is the four-alert window
above.

## What's still open, and why

- **#122's own remaining AC is still open, not closed by this
  document.** #122 explicitly asks for a fact pack in
  `observability/chaos/`, following that directory's existing
  chaos-scenario convention — a different repo and a different format
  than this cycle-1 review. This document satisfies #124's own "first
  cycle is the #122 incident" requirement and covers the same real
  events, but is a complementary artifact, not a substitute for #122's
  own stated deliverable. The lag between "root causes fixed
  (2026-08-12)" and "either write-up done" (this one, 2026-08-16; the
  `observability/chaos/` one, still pending) is itself the kind of
  thing this review exists to make visible.
- #130 (work-items pagination) — tracked and closed separately, not
  part of this incident's own scope.
- The deeper `ClinVarIngestionFreshnessBreach` saga (three ingestion
  attempts, two memory fixes, a duration-baseline recalibration) is
  real, closed, and documented in backlog #122 itself — referenced,
  not reproduced here.

## Node headroom at incident time

**Not captured live during the incident** — no one thought to run
`kubectl describe node` and record it while responding, and it can't
be reconstructed honestly after the fact. This is itself a real gap
this review's own future cycles are meant to close: cycle 2 (below)
is the first cycle with a real, live headroom snapshot attached.

## Restart counts at incident time

Partially reconstructable from what #122 itself recorded: `api` had
**70+ restarts** (the OOM finding above) at the point it was
discovered. No other service's restart count from this specific window
was recorded at the time — another gap this review format exists to
close going forward (cycle 2 has a real, live count for every
namespace).

## Anything that changed without a PR

Two real, deliberate exceptions during incident response, both
already-sanctioned fallbacks rather than undocumented drift:

- `kafka-topics.sh --create --if-not-exists`, run directly against the
  live broker to unblock two services immediately, then formalized in
  git the same session (`kafka.yaml`).
- A live `kubectl apply` of the missing `argo-rollouts` NetworkPolicy
  rule, formalized in git the same session.

Both match `docs/SESSION_STATE.md`'s own documented pattern for this
class of live-unblock-then-formalize action — not silent standing
edits.
