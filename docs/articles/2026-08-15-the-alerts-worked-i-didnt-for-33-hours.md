# The alerts worked. I didn't — for 33 hours.

*A real incident log from a solo homelab SRE platform: four alerts, 189
delivered notifications, zero acknowledgments, and the three unrelated
root causes hiding behind them once I finally looked.*

## Why this exists

My last post here described AdamastorX's core constraint: AI writes most
of the code, I stay responsible for everything else — the architecture,
the review process, and what happens when it breaks. This post is the
sharpest test that framing has had yet, and it's the uncomfortable half:
the code wasn't the problem this time. The alerting wasn't the problem
either. I was.

## What was actually happening while nobody looked

Five days earlier I'd rebuilt the cluster's CNI from scratch — a
deliberate, rehearsed, from-Git rebuild to swap flannel for Cilium and get
real network policy enforcement. Every check I ran afterward passed: 35 of
35 Prometheus scrape targets up, `cilium status: OK`, Kafka consumer
groups rejoined, three Postgres instances restored with matching row
counts. I called it done and moved on to other work.

Four days later, an independent review of the cluster (a habit I've built
into this project on purpose — I don't just trust my own "looks fine")
found four alerts actively firing:

- `BlackboxProbeFailing` — 6 targets, ~33 hours
- `ApiVariantsLookupHighErrorRate` — ~21 hours
- `ApiHighErrorRate` — ~20 hours
- `MarketDataStaleFeed` — 5 tickers, ~6 hours

Alertmanager's own log showed 189 notifications successfully delivered
across that window. Zero failures on the delivery side. A runbook already
existed for every single one of them. The detection layer did exactly its
job, continuously, for over a day. Nothing on the response side happened
at all, because nothing was watching.

That gap — not a bug, not a bad AI-generated commit, just a human who
declared victory and stopped looking — is the actual subject of this
post. The three root causes behind it are the concrete, technical part;
the 33 hours of silence in front of them is the part that actually
mattered.

## Root cause 1: the topic that was never in Git

`api` and `watchlist-service` had been logging
`UNKNOWN_TOPIC_OR_PARTITION` for `clinvar.ingestion.completed` roughly
once a second, for 34 hours straight — over 148,000 and 168,000 log lines
respectively by the time anyone looked. The topic simply didn't exist on
the rebuilt broker.

Root cause, once I actually went looking: it had never been declared in
the Kafka provisioning manifest, in any commit, ever. It existed on the
old broker only because someone (me, weeks earlier) had created it
manually at some point and it had just... persisted, silently
undocumented, until a real rebuild wiped it along with everything else
that wasn't in Git. This project's entire premise is that cluster state
lives in Git — this was the gap in that premise, found the expensive way.

Fixed by adding it declaratively where it always should have lived. The
sync itself didn't retrigger the provisioning job automatically (already
`Synced`, no diff to act on), so I fell back to the documented manual
path: `kafka-topics.sh --create --if-not-exists`, live, against the real
broker. Confirmed within seconds: both services stopped logging the
error, and `watchlist-service` showed a real partition assignment.

## Root cause 2: a Healthy pod giving 502s to everyone

`clinvar-service`'s `/variants/lookup` endpoint was returning 502 for
every real request. The Postgres index behind it was fully intact — 2.9
million rows, untouched by the rebuild. The pod was `Running`, `Ready`,
passing every probe. And it was 502ing on every single lookup, because
the reference VCF file the service reads from disk — `/data/clinvar/`,
a 4.0K directory with nothing in it — had been wiped by the rebuild and
never regenerated.

This is the same "Healthy pod, broken business logic" shape this project
has now hit three separate times (a RocksDB crash masked behind a green
liveness probe, a poisoned Kafka producer that hid for two days, and now
this). Each time the fix has been a bespoke, per-service liveness
indicator, which is correct for that one service and covers nothing else.
That pattern — and the backlog item it's now produced, generalizing a
per-service fix into an actual post-rebuild business-path checklist — is
the most useful thing to come out of this incident, and it's still open.

Fixed here by triggering a real ingestion (`POST
/internal/clinvar/ingest`), watched to completion: ~7 minutes, 4.46
million records scanned, 2.9 million index rows rebuilt, real files back
on disk. `GET /variants/lookup?rsid=rs80357906` — the same test variant
this project has used since its very first correctness check — came back
`200`, real classification, `Pathogenic`.

## Root cause 3: the comment that predicted its own failure

`blackbox-exporter`'s `hostAliases` pinned Traefik's ClusterIP by hand —
a value that changes on every cluster rebuild, since ClusterIPs aren't
stable across a full re-provision. The file's own comment, written when
that value was first hardcoded, said as much: this will need updating
after a rebuild. It was still wrong when the rebuild actually happened,
because a comment is a note to a human, not a mechanism, and I hadn't
read it in months.

Fixed for now (corrected the IP, `BlackboxProbeFailing` dropped from 6
firing targets to 1), with the real fix — something that can't drift the
way a hand-typed IP can — recorded as future work rather than pretended
away.

## Fixing it surfaced two more real bugs

Neither of these was part of the original four alerts. Both were found
by actually working the incident instead of stopping at the first green
checkmark.

**A slow-burning OOM crash loop in `api`, unrelated to the rebuild.**
70-plus restarts, real `OutOfMemoryError: Java heap space`. Root cause:
no explicit JVM heap sizing, so `MaxRAMPercentage` defaulted to roughly
25% of the container's memory limit — about 128MiB of real heap for a
Spring Boot app running Kafka clients, a connection pool, Tomcat, and
continuous profiling all at once. This had nothing to do with the
rebuild; it had just never been noticed. Fixed with explicit heap sizing
and a real memory bump.

**The fix for that bug then broke its own canary rollout, three times.**
First two aborts: a Prometheus query timeout during the automated
SLO-analysis gate. Root cause: `argo-rollouts`' own controller had never
been added to Prometheus's NetworkPolicy ingress allow-list when that
policy was first written — a periodic, triggered flow, not the kind of
constant traffic a live capture window happens to catch, so nobody had
noticed the gap until this exact rollout needed it. Third abort, after
that was fixed: a real metric failure, because the still-crashing *old*
pod's own bad requests were polluting the shared latency aggregate the
analysis was reading from. Once both were understood, I promoted the
rollout directly rather than let it keep retrying against a metric the
outgoing pod would keep contaminating for as long as it existed — a
judgment call, made and recorded, not silently taken.

## The alert that wouldn't clear

Three of the four alerts cleared within the first day of actually working
this. The fourth — ClinVar ingestion freshness — stayed red for three
more days, and chasing it down is the part of this incident I learned the
most from.

First puzzle: why hadn't it self-cleared once the underlying fix landed?
Because of a genuinely subtle metrics bug — the client library only
creates a labeled counter's time series the first time that label
combination is actually incremented. A service that has *never* had a
prior success gets that series born already at `1`, with no earlier `0`
sample for a rate-of-change alert to compare against. The alert had been
firing continuously for 22 hours, not intermittently — fixed by
explicit-zero-initializing every real status value at startup, verified
both ways: the regression test fails with the fix reverted, passes with
it applied.

Second puzzle, once the metric itself was honest: getting one real
ingestion to actually finish. The first live attempt was SIGKILLed
partway through, right at the container's old 768MiB limit — a real,
legitimate sizing gap, fixed by doubling it. The *second* attempt, on the
resized pod, was also SIGKILLed — peaking at only 765MiB, nowhere near
the new ceiling. That ruled out the container's own limit as the cause.
The real host was sitting at 12 of 19GiB used, with 5GiB already resident
in swap — this is a single laptop running roughly thirty real workloads
at once, and node-wide memory pressure, not any one container's declared
budget, was picking off the fastest-growing process in the moment. A
third attempt, made specifically to test whether a quieter moment would
help, failed too — three consecutive failures with three different peak
values is not bad luck anymore.

That got written down honestly as an accepted, chronic constraint of this
hardware rather than a bug to keep chasing — the same treatment I'd
already given the CPU side of this node in an earlier ADR. But "the node
is tight" turned out not to be the whole story. Two real, separate
memory bugs were still hiding in the ingestion code itself, found by
actually measuring where each attempt's memory trace peaked instead of
guessing: one function was building the entire ~2.9 million-row index in
memory before a single database write; another was holding two full
4.4-million-entry dictionaries in memory at once to compute a diff that a
single streaming pass could do just as correctly — verified with a
20,000-trial fuzz test that the streaming rewrite preserves the exact
comparison semantics of the version it replaced, edge cases included. The
fifth real attempt, after both fixes, succeeded end to end.

## Healthy is not the same as working

Here's the finding underneath all three root causes: every single check I
ran right after the rebuild was a *component*-liveness check, and every
one of them passed. Not one was a *business*-path check. A pod can be
`Running`, `Ready`, scraped, and reporting `Synced` in ArgoCD while the
actual thing it exists to do quietly doesn't work at all — three separate
times, in the same 20-minute post-rebuild window, and my own checklist
had no way to see any of them.

That's the part no amount of AI code review would have caught, because
it isn't a code problem. The commits were fine. The infrastructure
definitions were fine. The gap was entirely in what I, the human in this
loop, chose to verify — and then in the four days after that where I
verified nothing at all, because I'd already decided the story was over.
An AI wrote clean Kubernetes manifests and clean Java. It did not, and
structurally cannot, notice that nobody read the pager for four days.
That part is still, entirely, mine.

## So — was it worth it?

The direct cost of this incident was real and not small: most of a
working session spent chasing three unrelated root causes, then two more
that came out of fixing them, then three more days on a single alert that
refused to clear for reasons that turned out to be a metrics-library
quirk, then a chronic hardware constraint, then two genuine application
bugs underneath that. None of it was glamorous.

But it's also the most complete, most honest incident this project has
produced — real timestamps, real error strings, real wrong turns left in
rather than edited out, and it's already doing real work downstream: it's
the first entry in a standing operations log I'm now building specifically
so a four-alert, 33-hour silence doesn't happen unnoticed again, and it's
the strongest single case in the training corpus for an AI on-call agent
I'm building separately, precisely because it's messy and multi-cause
instead of one clean root cause with a clean fix.

The uncomfortable honest answer to "was it worth it": the system told me
the truth for 33 hours before I listened. Building the thing that catches
that gap — not another dashboard, a habit — is worth more to this project
right now than anything I could add to the stack this week.

---

*Real evidence, for anyone who wants to check any of this rather than
take my word for it: the full incident, including every root cause, every
follow-on bug, and the five real ingestion attempts, is recorded in
backlog item #122; the node-wide memory finding is ADR 0041; the fixes
landed across a dozen-plus real pull requests against this cluster's
GitOps and application repos, each reviewed before merge.*
