# 0039. `sre-agent` v1 scope: an offline diagnosis harness graded against the real Mimir incident series, not a live-triggered triage service

Status: Accepted

## Context

Backlog #66 (M11) has sat as a one-line Purpose/AC since it was first
scoped — its own Purpose already frames the ambition correctly ("a real
agent... not a chatbot wrapper"), but names no concrete first step. The
2026-08-09 staff-engineer review (§6 D5, §8 step 7) argues the case for
building it next has gotten stronger, specifically because the real,
human-graded incident inventory it would be evaluated against has grown:
three independent Mimir bugs found live in sequence (ADR 0038, backlog
#108), a real Beyla OOM diagnosed through a selfHeal false start and a
red-herring detour (ADR 0036, backlog #102), and a reverted-and-corrected
architecture decision on Faro (ADR 0037, backlog #103).

#66's existing Acceptance Criteria is the full end state: a standing
service (own namespace, own ArgoCD Application) that, on a live trigger,
queries Loki/Tempo/Prometheus/Kubernetes events/Alertmanager for an
incident window and is run against the two existing chaos scenarios
re-triggered live. That end state is real and unchanged by this ADR —
but it is not a legitimate *first* slice under this project's own
"smallest real version first" discipline (`docs/WHY.md`; ADR
0011/0014/0032/0038 all reject standing up disproportionate machinery
before a real question demands it). This ADR scopes what actually gets
built first, and against which real incident.

## Decision

**v1 is an offline, on-demand diagnosis harness — a script, not a
standing service.** No own namespace, no own ArgoCD Application, no
Alertmanager trigger, no live Loki/Tempo/Prometheus/Kubernetes-events
query integration. Concretely, v1:

1. Takes a fixed, hand-assembled **incident bundle** as input, one per
   real Mimir bug, built from artifacts this project already has —
   ADR 0038's own account, the real error message, the real relevant log
   lines, the real metric value at the time (e.g.
   `prometheus_tsdb_head_series` ≈186,604 against the 150,000 cap) — not
   a live query against the cluster.
2. Sends that bundle to an LLM via the Anthropic Claude API (Messages
   API), with a system prompt establishing the SRE-incident-triage role.
   The natural, no-new-vendor-relationship choice: this project is
   itself built end-to-end via Claude Code (#66's own Purpose states
   this directly), so the owner already has the account this needs,
   unlike Faro's real external-account blocker (ADR 0037) or the
   off-node-backup deferral (#99).
3. Produces one structured output per bundle: `summary`,
   `suspected_root_cause`, `affected_components`,
   `suggested_next_steps`, and a self-reported `confidence` (0-1) — the
   same output shape #66's own AC already specifies, just produced from
   a static bundle instead of a live query. No write/remediation action
   of any kind: the same "co-pilot, not an operator" boundary #66
   already states, carried forward unchanged.
4. Is graded by a human against each bug's own real, already-written
   answer (ADR 0038's account of the actual root cause and actual fix),
   recorded as agreement / partial match / miss / hallucinated false
   lead per bug — the same honest "what it caught vs missed" bar #66's
   Purpose sets, and the same self-grading discipline #102 and #108
   already applied to themselves.

### Why the Mimir series, not Beyla, Faro, or a chaos scenario, for v1

- **Mimir has three independent, cleanly-bounded incidents in one
  series**, each with an unambiguous before-state (a specific
  misconfiguration), an unambiguous symptom (a specific error message or
  metric value), and an unambiguous after-state (the exact fix, on
  record in ADR 0038) — the cleanest symptom-to-diagnosis shape of the
  three, and the freshest.
- **Beyla's incident is real but messier for a first grading pass**: the
  human diagnosis itself chased a red herring (the AppArmor
  ptrace-DENIED detour) before the real fix, and a live `selfHeal`
  revert happened mid-diagnosis (ADR 0036/#102) — genuinely interesting
  future grading material (does the agent also chase the red herring?
  does it know about selfHeal reverting live patches?), but a harder
  first case, not a simpler one.
- **Faro's episode is an architecture-decision reversal, not an incident
  with a symptom to diagnose** — grading "did it re-derive that a
  reasonable-sounding first analysis was wrong" is a different, harder
  evaluation problem than triaging a fault, better suited to a later
  version once the harness itself is proven.
- **The two existing chaos scenarios (01/02) are exactly the full #66
  AC's own intended next step, not this ADR's**: they're live
  re-triggerable, which is real value v1 deliberately defers rather than
  needing on day one.

### Why static input, not live signal queries, for v1

All three Mimir bugs are already fixed on the real cluster — there is no
live symptom to query today short of deliberately re-breaking a real,
currently-working component (reverting `ingester.ring.replication_factor`
to 3, or the series cap to 150,000) purely to feed the agent, a real
live-cluster risk this ADR does not authorize. Static bundles let the
harness itself — prompt design, output structure, grading method — get
proven first, exactly the sequencing #66's own Dependencies line already
states ("#49/#57 richer signals help but are not blocking").

## Consequences

- **#66's full AC is sequenced, not replaced.** The live-triggered,
  own-namespace, own-ArgoCD-Application, both-chaos-scenarios version
  stays the real backlog #66 end state; this ADR's v1 is the first slice
  toward it, not a redefinition downward.
- **A real, stated evaluation gap**: v1's "fact pack" for Mimir is ADR
  0038 plus backlog #108's own closing note, not a file under
  `observability/chaos/` — Mimir has no chaos/ fact pack of its own
  (only scenarios 01-03 do, per `observability/chaos/README.md`). This
  is the same gap #89 (article-asset habit) already names as real and
  open; this ADR doesn't silently treat it as closed.
- **Confidence scores are explicitly uncalibrated in v1** — a
  self-reported number with no ground-truth validation against a corpus
  large enough to calibrate against (three incidents isn't one), stated
  honestly rather than presented as a real reliability metric.
- **A new external-credential-shaped dependency, but a low one**: an
  Anthropic API key, documented the same not-generated-by-this-agent way
  `finnhub-api-key`/`blackbox-api-key` already are in
  `bootstrap/create-stateful-secrets.sh` — except v1 isn't a
  cluster-deployed service, so it needs no Kubernetes Secret yet; a
  local environment variable is enough until v1 graduates into the real
  #66 service.
- Rollback, if v1's grading comes back weak (a legitimate outcome, same
  as Mimir's own "not yet worth it" conclusion, ADR 0038): the harness
  is a script with no cluster footprint to unwind — delete it, keep the
  write-up as the honest record of what was tried.
