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
   SLO is missing its headline signal. **The cause is a template gap,
   not an execution gap**, and the distinction matters for the fix:
   #78–#82's own ACs asked for real *metrics*, and real metrics were
   delivered — nothing shipped in violation of its own AC. What no AC
   asked for was the dashboard, SLO row, alert, and runbook that ADR
   0017/0020 set as the standing bar. #90 closes the instance; the AC
   template is what has to change so the next milestone doesn't repeat
   it.
3. **ADR 0011's ephemeral-Kafka premise no longer matches the system.**
   The decision was written for 3 topics and a log-only consumer; the
   system now has 6+ application topics, Streams changelog topics, and a
   provisioning Job whose non-re-run caused two M13 bring-up incidents
   (#79/#80, gremlin in #84). Its cost is now paid weekly.
4. **Doc drift is systemic, and process has failed twice.** #32's
   checklist fix did not prevent #83; #83's fix regressed on the same
   file within 48 hours of M13 closing (overview.md again claimed M13's
   services "do not exist yet"). That file, twice, is the process
   argument. **Two further backlog.md defects found in the same review
   have a different cause and are recorded as such rather than folded
   into the drift narrative** — item #87 appears twice verbatim (a bad
   `Edit` anchor in the #86(a) commit re-emitted the neighbouring block,
   a mechanical editing failure) and item #79's heading was destroyed
   entirely, swallowed into the tail of #78's `Priority:` line. They are
   not evidence that a *checklist* failed; they are evidence that no
   structural validation of this file exists at all, which is why #97's
   scope covers both classes and not just the roster.

## Decision

**1. Two new milestones, executed ahead of M7/M11/M12** (which are
unchanged in scope; their gates stand):

- **M14 Reach and Packaging** (backlog #31, #88, #89): the narrative
  doc, public read-only access to the live system (Cloudflare Tunnel →
  read-only Grafana + `visualizer`, sidestepping ADR 0004's no-public-DNS
  constraint), and an article-asset habit. Days, not weeks; no new
  runtime components. #31 is reprioritized P2→P0 and is M14's first item.
- **M15 Consolidation: Operate What You Built** (backlog #90–#103,
  #107–#109): M13's observability surface (dashboards, consumer-lag
  alerts, SLO rows), an AC template fix so the next new service doesn't
  repeat the gap (#109), the pipeline freshness SLO with the REST-poll
  fallback correctly excluded from it (#91), kube-state-metrics/
  node-exporter (unblocking #21d and #63's scale-to-zero question),
  blackbox synthetic monitoring, raised Prometheus retention plus a
  first SLO-over-time report (#94, split from the deferred #18a Mimir
  experiment, which moved to #108 once #94's own real numbers showed
  retention length was the actual blocker), the Kafka durability re-decision,
  event contracts across the Java↔Python boundary, doc-drift *automation*
  (#97, replacing the failed checklist approach), and hygiene:
  Renovate, off-node backup copies, a secrets-management decision, VPA,
  Beyla, Faro.

**2. Gate: no new application services until backlog #90–#97 close** —
the standard-of-care subset of M15, not the whole milestone. ADR 0022's
"new operational shape" test currently fails for every candidate — the
marginal shape per new service has dropped below the doc/CI/alert tax,
which is ADR 0022's own gate applied to the current state.

The gate stops at #97 deliberately. #98–#103 (Renovate, off-node
backups, a secrets decision, VPA, Beyla, Faro) are worth doing and are
sequenced here, but they are *new* surface rather than debt the
expansion phase left behind — gating all future application work behind
building Beyla and Faro would contradict this gate's own rationale.
Among the infra components: **the retention/SLO-report work (#94) and
the blackbox exporter (#93) are inside the gated set** because they
close real gaps (a report ADR 0020's table can't produce yet;
verification that is currently a one-time human `curl`). **Mimir itself
(#108, split from #94) sits outside the gate alongside Beyla (#102) and
Faro (#103)**, and is labelled honestly as a lab experiment rather than
carried in
on a gap-closing justification they don't meet.

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

**6. Backlog #107 (the ntfy topic) lands before #88** — added while
reviewing this ADR, not by the review it records. Alertmanager's ntfy
receiver states its own threat model correctly ("the only protection is
not being guessable") and then commits the topic name in the same file,
in a public repository, defeating it entirely. It is not a leaked
credential — ntfy topics hold no secret — which is precisely why secret
scanning and a careful human read of that same file both passed over it:
the defect is a design whose stated assumption the repo invalidates.
Since #88 deliberately widens what is publicly reachable, this class is
decided first, and #88's own AC must pin down (verified live, not
assumed from a documented default) whether an anonymous Grafana Viewer
can reach Explore — arbitrary PromQL would expose #56's per-tenant
API-key labels and internal hostnames.

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
