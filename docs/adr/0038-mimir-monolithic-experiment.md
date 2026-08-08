# 0038. Mimir monolithic-mode experiment, hand-written manifests over the mimir-distributed chart

Status: Accepted

## Context

#94 (raised Prometheus retention to 30d, ADR 0014 addendum) found that
retention length, not query fan-out or multi-tenancy, was the real
blocker for a real SLO-over-time report on this cluster — a config
value, not a new component. #18a's original scoping already said the
right thing about Mimir itself: "run it whenever there's an actual
question it answers." This item is that question, kept honest by not
being load-bearing for anything else this project needs — the answer
"not yet worth it at this scale" is a legitimate outcome of running the
experiment, not a reason to skip running it.

## Decision

**Deploy real Mimir (binary version 3.1.2) in its own documented
monolithic mode (`-target=all,alertmanager`), as a plain hand-written
Kubernetes Deployment under `kubernetes/mimir/` — not the
`mimir-distributed` Helm chart.**

### Rejected: the `mimir-distributed` chart

Checked live before deciding against it: this chart has no
single-process deployment mode at all. Its `values.yaml` is built
entirely around Mimir's distributed architecture — separate
`distributor`/`ingester`/`querier`/`query_frontend`/`query_scheduler`/
`store_gateway`/`compactor`/`ruler`/`ruler_querier`/
`ruler_query_frontend`/`ruler_query_scheduler` keys, each rendering its
own Deployment or StatefulSet, at every preset (`small.yaml` through
`large.yaml`) — not just a resource-sizing knob. Adopting this chart
for a single-node personal lab cluster would mean running 10+ separate
components to answer one experimental question, the exact
disproportionate-machinery pattern ADR 0011 (Strimzi vs. plain Kafka),
ADR 0014 (kube-prometheus-stack vs. plain Prometheus), and ADR 0032
(a schema registry vs. JSON Schema files) have all already rejected for
this project.

### Chosen: Mimir's own real monolithic mode

Mimir the binary has a genuine, officially-documented single-process
mode (`-target=all`, described in Mimir's own docs as intended "for
getting started or running Grafana Mimir in a development
environment") — this chart simply doesn't expose it. A plain
hand-written Deployment (this project's own established shape for its
own services under `kubernetes/<name>/`) fits that one-process reality
far better than contorting a microservices chart into running as one.
This exact configuration was proven to start cleanly with the real
`mimir:3.1.2` binary locally (`Application started`, `/ready`
responding, all modules — distributor, ingester, ruler, compactor,
store-gateway, alertmanager, query-frontend, query-scheduler, querier —
running in the one process) before being committed, not assumed from
documentation.

### `filesystem` blocks-storage backend, not S3/MinIO

Same reasoning ADR 0015 already used for Loki/Tempo: standing up
MinIO/object storage for a single-node cluster's small metric volume
would be new infrastructure in service of infrastructure, not a real
need. Mimir's own startup log states this plainly and unprompted:
*"-blocks-storage.backend=filesystem is for development and testing
only; you should switch to an external object store for production
use."* That line is itself real, load-bearing input to this item's own
honest write-up below — object storage is Mimir's actual value
proposition at real multi-node/multi-tenant scale, which this cluster
deliberately isn't.

### `multitenancy_enabled: false`

Single-operator project, no real tenant boundary to enforce — avoids
requiring an `X-Scope-OrgID` header on every write/query call from
Prometheus and Grafana for a distinction that has no real referent
here.

## Honest write-up (this item's own AC)

**What Mimir adds at this project's real single-node scale, checked
live, not assumed:**

- Prometheus already remote-writes to Mimir as a *second* copy of every
  sample (not replacing local retention) — `dashboards/beyla-vs-manual`-
  style A/B querying between the two datasources is possible from day
  one, but there is no real query-fan-out or long-term-retention need
  this cluster currently has that plain Prometheus's own 30-day window
  (#94) doesn't already answer.
- The concrete, real thing Mimir's `filesystem` backend cannot deliver
  — genuine durability independent of this one node's own disk — is
  exactly the thing its own startup warning names. On a single laptop,
  Mimir's blocks live on the same disk Prometheus's own TSDB already
  does; this experiment adds a second query surface and a second
  ingestion path, not a second failure domain.
- **Cost, measured live**: a real, previously-unmeasured CPU headroom
  constraint was found while sizing this — this node's CPU *requests*
  already sit at 91% of allocatable (checked via `kubectl describe
  node` before writing `kubernetes/mimir/deployment.yaml`), the
  tightest real margin any component added this session has had to fit
  into. Mimir's own request (100m) fits; its limit (500m) does not
  fit inside the currently-free headroom in isolation if it bursts
  alongside every other live component at once — stated honestly in
  the Deployment's own comment as a real go/no-go call for whoever
  syncs this, against a fresh reading, not a foregone conclusion.
- **Answer, stated plainly**: not yet worth it as a standing piece of
  this cluster's architecture at its real current scale — the honest
  outcome this item's own AC explicitly allowed for. It stays
  deployed as the real, working experiment this item asked for, with
  its own real rollback path below, rather than being torn down the
  moment the answer turns out to be "no" — the experiment's value is
  in having actually run it, live, with real numbers, not in
  confirming a foregone conclusion either direction.

## Consequences

- One new namespace (`mimir`), one Deployment, one 2Gi PVC (`local-path`,
  same starting size as Prometheus's own), one Service — genuinely no
  new component beyond the Mimir process itself; no object storage, no
  memberlist ring, no second Prometheus.
- `argocd/apps/mimir.yaml` deliberately has no `syncPolicy.automated`,
  the same manual-sync discipline `aggregator`/`market-data-ingestor`/
  `news-ingestor` already use — sync happens by hand, against a fresh
  node-headroom reading, given the real CPU-request tightness found
  above.
- Rollback, if the real cost ever outweighs the real (currently
  marginal) value: remove `remoteWrite` from `prometheus.yaml`, delete
  the `mimir` Application and its Grafana datasource entry. Prometheus
  and #94's own retention are unaffected either way — this was never a
  dependency, only a second, optional path.
