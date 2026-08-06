# 0031. Post-expansion consolidation: reach and packaging (M14), then consolidation (M15), before any new services

Status: Accepted

## Context

The expansion phase ADR 0022 opened is delivered: M6–M13 shipped
progressive delivery, a permanent workload, guaranteed fan-out, an async
job control plane, continuous profiling, KEDA autoscaling, and a
five-service real-time market pipeline on genuinely external data. The
owner's stated goals are now: an observability pipeline fed with real
data, distributed-systems depth, a lab for new and established
technology, and **published articles that grow an SRE reputation**.

An independent staff-engineer review of all four repos
(`docs/reviews/2026-08-06-staff-engineer-review.md`, 2026-08-06) found
the project's binding constraints are no longer technical depth:

1. **The reputation-critical work keeps losing to feature work.** #31
   (the narrative doc) has survived three milestones unbuilt; nothing is
   publicly reachable, so no article can link a live artifact; SLOs exist
   but are never reported on over time (3-day Prometheus retention caps
   any reliability trend); the most novel unbuilt item (M11's
   `sre-agent`) is untouched.
2. **M13 shipped below the project's own observability standard.** Five
   services with scrape configs and one alert, but no dashboards and no
   ADR 0020 SLO-table rows — the bar ADR 0017/0020 enforced on every
   prior service. A streaming pipeline without an end-to-end freshness
   SLO is missing its headline signal.
3. **ADR 0011's ephemeral-Kafka premise no longer matches the system.**
   The decision was written for 3 topics and a log-only consumer; the
   system now has 6+ application topics, Streams changelog topics, and a
   provisioning Job whose non-re-run caused two M13 bring-up incidents
   (#79/#80, gremlin in #84). Its cost is now paid weekly.
4. **Doc drift is systemic, and process has failed twice.** #32's
   checklist fix did not prevent #83; #83's fix regressed on the same
   file within 48 hours of M13 closing (overview.md again claimed M13's
   services "do not exist yet"). backlog.md also carries item #87 twice,
   verbatim.

## Decision

**1. Two new milestones, executed ahead of M7/M11/M12** (which are
unchanged in scope; their gates stand):

- **M14 Reach and Packaging** (backlog #31, #88, #89): the narrative
  doc, public read-only access to the live system (Cloudflare Tunnel →
  read-only Grafana + `visualizer`, sidestepping ADR 0004's no-public-DNS
  constraint), and an article-asset habit. Days, not weeks; no new
  runtime components. #31 is reprioritized P2→P0 and is M14's first item.
- **M15 Consolidation: Operate What You Built** (backlog #90–#103):
  M13's observability surface (dashboards, consumer-lag alerts, SLO
  rows), the pipeline freshness SLO, kube-state-metrics/node-exporter
  (unblocking #21d and #63's scale-to-zero question), blackbox synthetic
  monitoring, long-term metrics via the deferred #18a Mimir experiment
  plus a first SLO-over-time report, the Kafka durability re-decision,
  event contracts across the Java↔Python boundary, doc-drift *automation*
  (#97, replacing the failed checklist approach), and hygiene:
  Renovate, off-node backup copies, a secrets-management decision, VPA,
  Beyla, Faro.

**2. Gate: no new application services until M15 closes.** ADR 0022's
"new operational shape" test currently fails for every candidate — the
marginal shape per new service has dropped below the doc/CI/alert tax,
which is ADR 0022's own gate applied to the current state. Infra
components M15 itself adds (Mimir, blackbox exporter, Beyla) are
explicitly not gated; they close observability gaps rather than open new
application surface.

**3. M11 (`sre-agent`) is sequenced after M15, deliberately** — its
honest evaluation needs the retention window and richer signals M15
delivers (the fact packs alone are the graded dataset; the retention
makes the agent's inputs complete). It is not cancelled.

**4. ADR 0011 must be re-litigated in a new ADR (#95) before M7** — the
system it was written for no longer exists. Persistent broker storage,
Strimzi (evaluated honestly against ADR 0014's anti-Operator precedent,
including why Kafka's topic management differs), or a genuinely
declarative provisioning mechanism are the options; quiet continuation
is not.

**5. What does not change:** ADR 0022 §2's upheld cuts stay closed
(#21b burn-rate policy included — M15's retention enables honest SLO
*reporting*, the valuable 20% of that idea, without the theatre). M12
stays gated on M7. The exclusion list's remaining entries stay excluded.

## Consequences

- Milestone numbering grows to M14/M15; the GitHub milestone list (stale
  since M4) is synced to match, and new backlog items are mirrored as
  GitHub issues so the org project board reflects the plan — backlog.md
  remains the canonical tracker.
- `docs/architecture/overview.md` is corrected for the third M13-related
  drift in the same PR as this ADR; #97 exists because correction without
  automation has now failed twice.
- The review doc pattern (`docs/reviews/`) becomes the standing input
  format for external/part-time review — a named artifact the next
  review can diff against.
- The article pipeline this ADR exists to serve has its first six topics
  pre-evidenced in-repo (review §D6); M14/M15 each add their own fact
  packs on top.
