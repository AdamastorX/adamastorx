# 0041. This node's memory is as tight as its CPU already was — measured, not assumed

Status: Accepted

## Context

ADR 0040 measured this laptop's real CPU ceiling (91-93% of allocatable
already requested) and made a deliberate, recorded decision about what
fits on it. It did not do the same for memory — memory requests sat at a
comfortable-looking 46% of allocatable, so nothing prompted the same
scrutiny at the time.

Backlog #131 found the gap live, closing out #122: a real, triggered
ClinVar ingestion (a single bursty workload) SIGKILLed its own pod twice
in a row. The first kill was a genuine per-container sizing gap (768Mi
limit, real usage climbed to 767MiB — fixed, `platform`#170, doubled to
1536Mi). The **second** kill, on the resized pod, peaked at only
765.4MiB — under half the new 1536Mi limit — which rules out the
container's own cgroup ceiling as the cause. A **third** attempt,
retried after this ADR's own §Decision #3 was written (a real,
human-checked `free -h`/`kubectl top node` beforehand showed the same
chronic tightness this ADR describes, not a worse-than-usual moment —
tried anyway, since waiting for a categorically better moment turned
out not to be realistic on this machine), was killed a third time,
peaking at 905.6MiB — still 59% of the 1536Mi limit, not near it. Three
consecutive real attempts, three different peak values (767, 765, 906
MiB), all killed well under an unchanged 1536Mi ceiling, is no longer
explainable as a one-off timing coincidence. Independently, `mimir`
(kept deployed by ADR 0040 §5's own explicit, standing owner override)
has been chronically OOM-cycling the entire time this project has been
watching it: 11-12 restarts when the 2026-08-11 staff review first
flagged it, 24 and still climbing as of this ADR, roughly one restart
every 4 hours. Checked directly rather than assumed: its own memory
trace peaks at 703MiB against a 768Mi limit right before each kill —
also well under its own ceiling.

Two independent, unrelated workloads, both killed with real headroom
left in their own declared limits, is the signature of real node-wide
memory pressure, not two separate per-container misconfigurations.
Measured directly rather than inferred:

- `kubectl describe node`: memory **requests** 46% of allocatable
  (9242Mi/20331756Ki) but memory **limits** already **114%**
  overcommitted (22690Mi) — the gap between "requested" and "what's
  actually declared as a ceiling" is wide, exactly the shape that lets
  real usage exceed real capacity without any single request-based
  scheduling decision looking wrong.
- The host's own `free -h`/`swapon --show` (this is a single physical
  laptop, not a VM — the node *is* the host): 11-13Gi of 19Gi RAM
  genuinely in use, with **4.4-5Gi of the 8Gi swap partition resident
  at rest**, not just transiently touched during a spike.
- `kubectl top node`: CPU still sits at 51-62%/2000-2500m against a
  4000m allocatable in routine operation — consistent with ADR 0040's
  own ~91-93% figure once real workload traffic (not idle) is running.
- **Not a leak**: a 4-day Prometheus trend of
  `sum(container_memory_working_set_bytes)` across every real container
  in the cluster oscillates between 6.8-8.3GiB with no directional
  trend — noisy, but flat. Total real demand isn't growing; it's
  chronically sitting close enough to the real ceiling that ordinary
  variance (a bursty ingestion job, Mimir's own compaction cycle, a
  scrape spike) is enough to tip the kernel's OOM killer into acting,
  and it doesn't always pick the workload that's "responsible" — it
  picks whichever process looks worst by its own scoring at that
  instant.

## Decision

**1. This machine's real memory ceiling is accepted as a known,
measured operating constraint — the same way ADR 0040 accepted the CPU
one — not treated as a bug to chase down.** The 4-day flat trend rules
out a leak; the two independent OOM victims rule out isolated
misconfiguration. What's left is real, honest scarcity: this project
runs ~30 real workloads (business services, the full observability
stack including Mimir/Beyla by ADR 0040 §5's own explicit override, a
CI-adjacent workload generator) on one 19GB laptop, and that combination
is genuinely tight. Living with real, bounded swap use (roughly 4-5Gi
resident, not growing) is this project's actual, current tradeoff for
staying on owned hardware per ADR 0035's story — recorded here rather
than silently tolerated.

**2. Mimir's chronic OOM-restart pattern is not independently
actioned.** Bumping its own container memory limit would not fix
it — it dies with real headroom left in the 768Mi it already has,
exactly like clinvar-service's second kill. It is a symptom of #1, not
a separate defect, and ADR 0040 §5 already settled whether Mimir stays
deployed (yes, by explicit owner decision, despite its cost) — this ADR
does not revisit that.

**3. Bursty, memory-heavy operations (ClinVar's weekly ingestion is the
concrete example; any future similar batch job inherits this) are
treated as capacity-aware, not fire-and-forget** — a real, human-in-the-
loop check of `free -h`/`kubectl top node` before manually triggering
one outside its normal schedule, not a new automated gate (this machine
has no scheduler sophisticated enough to make that worth building).
**Tested, and found insufficient on its own**: a third real attempt,
made after this exact check and finding nothing worse than the
project's own chronic normal, still failed (§Context). The tight state
this ADR describes isn't an occasional dip to wait out — it's close
enough to the steady state that "wait for headroom" doesn't reliably
have anywhere better to arrive at on this machine. The check stays
useful (it would have caught a genuinely-worse moment), but it is not,
on its own, a fix for this specific workload. New backlog **#132**
tracks the real remaining lever: making the ingestion's own peak memory
smaller (the real candidate is streaming the VCF parse/index build
instead of buffering it, not attempted here — that's real engineering
scope, not an incident-pressure patch) rather than continuing to retry
the same shape of request against an unchanged ceiling.

**4. No new memory-hungry component gets added without either an
equivalent real trim elsewhere or an explicit, stated acceptance of
further swap growth** — the same discipline ADR 0040 §5 already applies
to CPU (backlog #120's re-trim lever), extended to memory. This doesn't
retroactively touch anything already running.

**5. Re-measure before trusting these numbers, same caveat ADR 0040
gave its own figures.** This ADR's numbers are a snapshot, not a
standing budget with headroom tracked elsewhere — anyone about to add
real load (a new service, a bigger batch job, a heavier profiling
sample rate) should re-run the checks in §Context first rather than
assume this ADR's percentages are still current.

## Consequences

- Backlog #131's measurement/decision half of its own AC is satisfied by
  this ADR — the real baseline is measured, the leak question is
  answered (no), and the scheduling-awareness question is answered (a
  real, human-checked practice, tested, and found necessary-but-not-
  sufficient on its own for this specific workload). #131's other half
  — a real, triggered ingestion actually succeeding — remains
  **unmet after three consecutive real attempts**, so #131 stays open
  rather than marked Done, with its remaining scope carried to the new
  #132.
- `clinvar-service`'s freshness alert (backlog #122) is **not** closed
  by this ADR. Simply retrying is not, by itself, expected to work
  reliably given three consecutive real failures — #132's real
  memory-efficiency work is the credible next step, not another retry
  of the same request.
- Nothing here revisits ADR 0040 §5's Mimir/Beyla decision, decommissions
  anything, or adds new infrastructure. The only lever pulled is
  awareness and a stated, honest constraint — matching ADR 0040's own
  "measure, then decide, then say so" shape for the other half of this
  same machine's real ceiling.
