# 0032. Persistent Kafka broker storage, superseding ADR 0011's ephemeral-storage decision

Status: Accepted

## Context

ADR 0011 accepted `emptyDir` (no PVC) for the single Kafka broker as "a
current constraint to revisit," not a permanent design choice, for a
system with **one topic (`work-items`, 3 partitions) and one log-only
consumer (`workers`) with no persistent state of its own**. The
premise that decision was written against no longer exists. This
cluster now runs **6 real application topics**
(`work-items`, `stock.price.tick`, `news.article.published`,
`news.sentiment.scored`, plus two more implied by `aggregator`'s own
inputs) **plus Kafka Streams' own internal changelog and restore
topics** (`aggregator-price-window-store-changelog`,
`aggregator-sentiment-window-store-changelog`,
`aggregator-latest-price-store-changelog`,
`aggregator-latest-sentiment-store-changelog`) — a stateful stream
processor whose entire correctness model depends on those changelog
topics actually existing.

**The cost is real and already paid, repeatedly, not hypothetical.**
Every broker restart on `emptyDir` wipes every topic. The
topic-provisioning Job (`argocd/apps/kafka.yaml`'s own
`provisioning.topics`) only runs when ArgoCD actually syncs the `kafka`
Application — a broker pod restart alone (node pressure, an OOM per
backlog #75's own real incident, a routine `kubectl delete pod`) does
**not** re-trigger it. This directly caused or complicated four
separate real incidents this project's own records name: #79 and #80's
M13 bring-up (`news.article.published`/`news.sentiment.scored` didn't
exist yet after their first real sync, because the provisioning Job's
own prior run had been silently invalidated by an intervening broker
restart), and the general fragility backlog #84 recorded (`docs/SESSION_STATE.md`'s
own "ArgoCD stuck-operation gremlin" section, hit while trying to
resync `kafka` for exactly this reason). Backlog #90's own real
finding this week reinforces the same shape from the consumer side:
`aggregator`'s state-restore duration is a real, measured, non-zero
cost (`aggregator_state_restore_duration_seconds`) paid on *every*
restart specifically because there is nothing to restore from short of
a full changelog replay — persistence would make most restarts cheap
(resume from local RocksDB state) instead of paying that cost every
time.

Real, current headroom, checked live before deciding (`kubectl ...
stats/summary`), not assumed: **176GB free disk** on this single node
(250GB capacity), against topic volumes this project's own session
records have repeatedly measured as tiny (a handful to a few dozen
ticks/scores per ticker per 15-minute window, backlog #87). Disk is
not, and was never, the constrained resource here — CPU is (83%
requested, backlog #77's real accounting). Whatever ADR 0011's
original hesitation about persistence was weighing, it was never a
real disk-capacity concern on this hardware.

## Decision

**(a) Enable real PVC-backed persistence for the Kafka broker**
(`controller.persistence.enabled: true`, chart's own default `8Gi`,
default StorageClass — `local-path`, same as every other stateful
component on this cluster: Postgres, Prometheus, Loki, Tempo). This is
the smallest possible change that kills the entire incident class at
its actual root: once topic data survives a broker restart, the
provisioning Job's own re-run trigger stops mattering for routine
restarts (it still runs, harmlessly and idempotently, on every real
`kafka` Application sync — `--if-not-exists` — it just no longer needs
to for data to survive). RF stays 1 (single broker, unchanged;
persistence protects against *restart* data loss, not *broker* loss —
that remains a real, single point of failure, unchanged from ADR 0011
and not what this ADR is deciding).

**Rejected: Strimzi (declarative `KafkaTopic` CRs).** ADR 0011 already
rejected this once for a smaller system ("disproportionate... for one
topic"); re-examined here on its own merits for the current, larger
topic surface, not dismissed by inertia — and rejected again, for a
reason specific to what this project's topics actually are now, not
just "still too small." **The comparison the gate discussion asked
for, stated explicitly**: ADR 0014 rejected the Prometheus Operator
because Prometheus's own config is genuinely static — a human-edited
file, applied wholesale, with no runtime process inside the cluster
that creates new scrape targets or alert rules on its own. Kafka's
topic surface in *this* system is not static in the same way, even
today: `aggregator` (Kafka Streams) creates and manages its own four
internal changelog topics via its own embedded `AdminClient` calls at
startup, entirely outside any declarative topic list — confirmed
against `AggregatorTopology`'s own real behavior, not assumed. A
Strimzi `KafkaTopic` CR model would cover the 6 explicitly-declared
application topics perfectly, but would have **nothing to say** about
the four Kafka-Streams-owned changelog topics, which would keep
existing exactly as they do today, self-managed by the client
application. Adopting Strimzi would not replace the current
provisioning Job with one clean declarative mechanism — it would add a
second, partial one running alongside the first, for less coverage
than persistence alone already achieves. That is the disproportionate
outcome, not merely "an operator for one broker."

**Rejected: status-quo storage plus a fixed provisioning-trigger
mechanism (e.g., an ArgoCD sync hook re-running the Job on a schedule,
or a Kafka broker postStart hook).** This treats the symptom, not
the cause. The provisioning Job re-running reliably would still mean
every real restart — a routine pod eviction, a node drain once M7
lands, a chart version bump — genuinely deletes and then recreates
every topic from empty, discarding whatever real data existed a moment
before. That is real, silent data loss on an ordinary operational
event, not just an inconvenience the Job's own re-run timing happens
to paper over. Fixing persistence fixes this for every trigger at
once, including ones a provisioning-trigger fix wouldn't anticipate;
fixing only the trigger leaves the actual loss window open.

## Consequences

- **The dominant class of M13 bring-up incidents (#79, #80, #84) cannot
  recur in this shape.** A broker restart no longer requires a human to
  notice missing topics and manually re-sync `kafka` — verified live
  by an actual `kubectl delete pod` against the real running broker
  (see backlog #95's own closing record for the real before/after).
- **`aggregator`'s state-restore cost drops for the common case.**
  Most restarts now resume from real local RocksDB state plus a
  present, unwiped changelog, rather than paying a full changelog
  replay every time — `aggregator_state_restore_duration_seconds`
  (backlog #90's own new dashboard panel) is the metric to watch for
  this improvement going forward, not re-measured as a fixed number
  in this ADR.
- **RF=1 remains a real single point of failure**, unchanged: this ADR
  protects against *restart* data loss (the actual, repeatedly-hit
  incident class), not *broker* loss, which still means real data loss
  if the sole broker's disk fails. That is the same real, accepted
  trade ADR 0030 already states for Postgres on this single-node
  cluster — not a new gap this ADR introduces, and not silently
  extended to imply broker loss is now covered when it isn't.
- **Kafka's own PVC is not currently covered by backlog #99's off-node
  backup work** (which scopes `pg_dump` PVCs and Terraform state, not
  Kafka) — stated here as a real, known gap for whoever picks up #99
  next, not assumed already covered.
- ADR 0011 is corrected, not silently reversed — its own text is left
  intact with a note pointing here, per this project's own convention
  for reversed decisions (ADR 0018 → ADR 0019 is the precedent this
  follows).
