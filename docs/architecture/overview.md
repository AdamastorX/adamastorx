# Architecture overview

Status: M0-M5 complete/verified live. The expansion phase (ADR 0022)
followed, and its work has landed unevenly across milestones rather than
one at a time — M6's progressive delivery and M8's guaranteed-fan-out/
async-job-control-plane items are done and live, M9's continuous profiling
is done and live, M10's autoscaling is done and live, and **M13's
market-sentiment pipeline (ADR 0029) is done and live since 2026-08-04**
(all five services, built under an explicit owner override of the M7
gate — see backlog's M13 section). Still **not yet built**: M7's
multi-node/Cilium/Istio substrate, M11's SRE agent, and M12's reopened
bioinformatics milestone — real, ADR-recorded decisions (0023-0028)
gated on a hardware move this project hasn't made. M14/M15 (ADR 0031,
post-expansion consolidation: reach/packaging, then observability
completeness) are underway, not unstarted: M14's #31 has been Done since
2026-08-06 (`WHY.md`, PR #89) and #89 is partially done (retroactive
asset capture for existing fact packs is a stated, open gap); M15 is
closed on the large majority of its items (`docs/roadmap/backlog.md`,
§M15) — #94 (retention/SLO report, blocked on a declined PVC resize)
and #101 (VPA, deliberately sequenced last) remain open by explicit
choice, not oversight. The diagram below shows the current shape, with a
note underneath marking what exists today; it is the map, not the
territory.

## Shape of the system

```
                      ┌──────────────────────────┐
                      │        GitHub            │
                      │  (source of truth, all   │
                      │   repos, Actions CI)      │
                      └────────────┬─────────────┘
                                   │ push
                                   ▼
                      ┌──────────────────────────┐
                      │         ArgoCD           │
                      │   (GitOps entrypoint,    │
                      │    watches `platform`)   │
                      └────────────┬─────────────┘
                                   ▼
┌───────────────────────────── k3s cluster ──────────────────────────────┐
│                                                                          │
│  Traefik (ingress) ── CORS → API-key auth → rate limit ──▶ API Rollout  │
│  cert-manager (TLS)   (middleware chain, ADR 0027)          (canary,    │
│                                                               ADR/#46)  │
│                                        ├─▶ PostgreSQL (+ outbox table)  │
│                                        ├─▶ Redis                       │
│                                        ├─▶ Kafka (KRaft) ─▶ Workers    │
│                                        │      (KEDA-scaled on lag,     │
│                                        │       native kafka scaler)    │
│                                        └─▶ clinvar-service (Python)    │
│                                             ├─▶ its own PostgreSQL     │
│                                             │   (async ingestion job   │
│                                             │    state, #54)           │
│                                             └─▶ ClinVar VCF (PVC)      │
│                                                    │                    │
│                              clinvar.ingestion.completed                │
│                                                    ▼                    │
│                                        watchlist-service               │
│                                        (own namespace/Postgres,        │
│                                         outbox-table-plus-relay,       │
│                                         ADR 0026) ─▶ ntfy.sh            │
│                                                                          │
 │  Finnhub wss ─▶ market-data-ingestor ─▶ stock.price.tick ──┐          │
 │  WSJ/MarketWatch RSS ─▶ news-ingestor ─▶ news.article.     │          │
 │    published ─▶ sentiment-analyzer ─▶ news.sentiment.scored ┤          │
 │                                                             ▼          │
 │                                              aggregator (Kafka Streams,│
 │                                               windowed + latest-known, │
 │                                               GET /aggregates)         │
 │                                                             │          │
 │  clinvar-viewer (static IGV.js widget) ─┐                   │          │
 │  visualizer (static Chart.js) ──────────┤─▶ public Ingress  │          │
 │  workload-generator (shaped synthetic   ┤  (keyed for api;  │          │
 │    demand, permanent) ──────────────────┘  CORS for visualizer)        │
│                                                                          │
│  OTel Collector, Prometheus + Alertmanager, Loki, Tempo, Beyla (eBPF), │
│  mimir (remote-write, monolithic), Pyroscope (profiling) ─▶ Grafana    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Live today:** GitHub as source of truth; a single-node k3s v1.36.2 cluster
(provisioned via Terraform from `platform/terraform/`); ArgoCD v3.4.5
(app-of-apps over the `platform` repo's `argocd/apps/`, prune + selfHeal);
Traefik 41.0.2 on hostPort 80/443; and cert-manager v1.21.0 with a local CA
chain (`selfsigned` → `adamastorx-ca` ClusterIssuer — Let's Encrypt deferred
until a host with public DNS, ADR 0004). Local hostnames are all
`*.local.adamastorx.test` (switched from `.dev`, which turned out to be an
HSTS-preloaded TLD with no manual override for an untrusted cert — a real
incident found live, recorded in `docs/SESSION_STATE.md`). The `services`
repo's CI builds and Trivy-scans every PR image as a required merge gate.

**`api`** (Maven module in `services`, Spring Boot/webmvc/actuator) is no
longer a plain Kubernetes `Deployment`: it is an Argo Rollouts **`Rollout`**
with a canary strategy, gated by an `AnalysisTemplate` that queries the
live Prometheus for the service's own SLIs (non-5xx rate, p95 latency —
the same expressions `alerting_rules.yml` already defines, backlog #46,
Done) and aborts automatically on breach. This closes a real incident: a
routine rollout once sat in `CrashLoopBackOff` for 95 minutes while the old
pod kept serving traffic, because a plain `Deployment`'s rolling update
leaves the old ReplicaSet up with nothing visibly "down" to alert on. Both
directions are proven live against the real cluster — clean promotion in
under 3 minutes, and automatic abort reproducing that exact 95-minute
CrashLoopBackOff shape in ~3 minutes with the previous pod undisturbed.
`api` still has its own public Ingress and TLS certificate
(`api.local.adamastorx.test`, ADR 0021) — the earlier `gateway`/`whoami`
services this replaced are gone entirely, not paused.

**`api`'s public Ingress now sits behind a real Traefik middleware
chain** (ADR 0027, backlog #56, Done): `api-cors` → `api-key-auth` →
`api-key-ratelimit` (`kubernetes/api/middlewares.yaml`). HTTP Basic auth
is the API-key mechanism — one `tenant:apr1-hash` htpasswd line per
caller, tenant name as username, key as password — backed by a real
Kubernetes Secret provisioned out-of-band by
`bootstrap/create-stateful-secrets.sh`, never committed to git. Per-key
rate limiting is Traefik's native `rateLimit` middleware keyed on the
`Authorization` header (5 req/s average, burst 10). A `headers`
middleware answers a browser's CORS `OPTIONS` preflight before auth ever
runs — the real gotcha a naive ordering would have broken `clinvar-viewer`
on. Proven live in both directions repeatedly: unauthenticated → `401`;
a real tenant key → `200`/`202`; a real request burst → a real mix of
`200`/`429`. This satisfies the reintroduction condition ADR 0021 itself
left open when `gateway` was removed ("reintroducing an edge service — or
using Traefik middleware, is a deliberate future decision") — no new
service was added.

`api` also persists to PostgreSQL (ADR 0012) — but **the original dual-write
gap is closed**: `POST /work-items` no longer calls `KafkaTemplate.send()`
directly. `WorkItemOutboxService` persists the `work_items` row and an
`outbox_events` row in one transaction; an independent `OutboxRelay`
poll loop publishes to Kafka and marks the row published (outbox-table-
plus-relay, ADR 0026, closing backlog #16). `GET /work-items` still reads
the row back; Postgres runs as a single-instance Bitnami chart in `api`'s
own namespace with a real PVC (2Gi, `local-path`). `api` also fronts
`GET /work-items/{id}` with the existing Redis cache-aside layer (ADR
0016), fail-open to PostgreSQL on a Redis outage.

**`workers`** (services#3) still has no Service (no business HTTP API,
ADR 0011) and consumes `work-items` from the single-broker Kafka (KRaft,
combined mode, `kafka` namespace) — but it is no longer a fixed-replica
`Deployment`. **KEDA (2.20.2) scales `workers` on real Kafka consumer-group
lag** via its native `kafka` scaler (backlog #63, Done) — querying the
broker's own committed offsets directly, not a Prometheus-backed trigger,
which structurally sidesteps a real gap found live (backlog #76: the lag
metric is self-reported by the consumer's own JVM and goes dark exactly
when the consumer is fully stopped). KEDA reacts at `lagThreshold: 50`,
an order of magnitude below the `WorkersConsumerLagHigh` alert's `500`/
`10m`, which stays as the backstop for when autoscaling alone can't fix
it. Scale-to-zero is now adopted (`minReplicaCount: 0`, backlog #113,
2026-08-09) — kube-state-metrics (enabled cluster-wide since backlog
#92) supplies `kube_deployment_status_replicas{deployment="workers"} >
0`, gating `WorkersConsumerMissing` alongside its existing `absent(...)`
clause so a real KEDA scale-to-zero can't be mistaken for a stuck
consumer, closing the exact follow-up backlog #76 originally deferred.
Proven live: a real ~2,600-request burst drove lag to 150, KEDA correctly
computed and requested 3 replicas (only 1 actually scheduled — see the
CPU-headroom note below), and the running replica alone drained the
backlog to zero lag within ~90s.

**Known gap:** Kafka's own memory limit was raised 768Mi→1536Mi
(backlog #75) after a real, timestamp-aligned OOMKill during a consumer-
lag chaos scenario, but the root cause (accumulating unconsumed backlog
vs. a temporarily-elevated test traffic rate) was not cleanly isolated —
recorded honestly as a real, still-open question rather than a closed
one. This node's CPU, not memory, was separately found to be the scarce
resource: `kubectl describe node` showed CPU requested at 99% of
allocatable at multiple points blocking real, unrelated work three
separate times (backlog #77, Done) — CPU *requests* on the over-
provisioned Postgres/Redis instances were trimmed to real observed usage,
recovering the node to 63% requested (2545m/4000m, ~1.4 free cores). This
headroom is real but finite — it was the stated reason M13 was originally
gated on the M7 hardware move, until the owner explicitly overrode that
gate (2026-08-02) and M13 was built here anyway, incrementally, with a
fresh headroom check before each service's sync (83% requested after the
full M13 deploy, per backlog #87's own last check).

**Observability (four pillars):** `api`/`workers` export traces via
Micrometer Tracing + OTLP to an OpenTelemetry Collector (ADR 0013) into
Tempo (72h retention, 2Gi PVC). Metrics flow via Boot actuator/
`prometheus_client` into a plain Prometheus chart (30-day retention since
backlog #94; PVC is 16Gi in git but still 2Gi live — `local-path` needs a
delete+recreate to actually grow, and the owner has so far declined it,
leaving the `prometheus` Application persistently `OutOfSync`, backlog
#118), scraped from `api`/`clinvar-service` (static targets) and `workers`
(pod-role service discovery). Logs are shipped by Alloy into Loki
(72h retention, 2Gi PVC). Grafana has Prometheus/Loki/Tempo pre-wired
with the trace/log pivot, golden-signal dashboards per service, and real
latency percentiles plus a real Kafka consumer-lag metric (backlog
#21a). Prometheus also remote-writes to mimir (own monolithic-mode
Deployment, hand-written manifests, ADR 0038) as a second, opt-in
Grafana datasource — a real, completed experiment (backlog #108), not
a dependency of anything else. Beyla runs as an eBPF auto-
instrumentation DaemonSet (ADR 0036), plotted alongside `api`/
`aggregator`/`workers`' own manual instrumentation on its own
dashboard, not replacing it. Alertmanager is live with an `ntfy.sh` notification channel and
SLO-backed alert rules — re-validated for real under sustained traffic
(backlog #47, Done): the same two rules that didn't fire in the original
chaos scenarios both fired unaided once #45's continuous traffic existed,
falsifying the "traffic volume, not the rules" hypothesis in the
direction it predicted.

**Pyroscope is now this stack's fourth observability pillar — continuous
profiling** (backlog #57, ADR 0028, Done). `api` (Java) and
`clinvar-service` (Python) are both instrumented via an unprivileged
**init-container agent-injection pattern**: an ordinary, non-root init
container fetches the real published Pyroscope SDK into a shared
`emptyDir`, and the main container picks it up with no image rebuild
(`JAVA_TOOL_OPTIONS=-javaagent:...` for `api`; a `command` override
wrapping `uvicorn` for `clinvar-service`) — deliberately not the
alternative of a privileged, cluster-wide Alloy DaemonSet running as
root in the host PID namespace, which ADR 0028 declined to adopt
unilaterally inside one item's scope. Both services confirmed pushing
real, continuous profiles against the live cluster. The #35
CrashLoopBackOff incident was deliberately reproduced and profiled for
real, and the real flame graph **did not confirm the original
hypothesis**: self-time was dominated by the JVM's own C2 JIT compiler
internals and class-loading overhead, not application-level Hibernate/
Flyway/Kafka bootstrap code as originally assumed — recorded honestly.
Profile-to-trace span correlation is a stated, unshipped gap: it needs a
language-specific OTel bridge package wired into each service's own code,
not something an init-container can retrofit.

**M5 Clinical Variant Annotation:** `clinvar-service` (own `clinvar`
namespace, ADR 0019) is this project's first non-JVM component — FastAPI
+ `pysam` + `psycopg` + `confluent-kafka` (since joined by
`sentiment-analyzer` and `workload-generator`, also Python). It owns
ClinVar end to
end: weekly download from NCBI, a pysam tabix rebuild, a dedicated
Postgres instance, and a `clinvar_variant_index` table for rsID lookups.
`api` calls it over HTTP (`ClinVarServiceClient`) and fronts the result
with Redis cache-aside, invalidated on write via `clinvar.ingestion.
completed`. **The ingestion trigger is no longer synchronous-blocking**:
`POST /internal/clinvar/ingest` returns `202` with a job id in ~51ms
(measured); job state — `queued`/`running`/`succeeded`/`failed`/
`cancelled` — is persisted in `clinvar-service`'s own Postgres, not in
memory, so it survives a pod restart (backlog #54, Done). Proven live: a
real ingestion force-killed mid-run reconciled to `failed` with an
explicit reason on the replacement pod's startup, with no abandoned
release ever going active; a second real ingestion was cancelled
mid-scan and confirmed to actually stop, not just relabel. The old
`threading.Lock` concurrency guard (services#36) was retired in favor of
a Postgres partial unique index, which — unlike the Lock — survives a
restart. `GET /variants/lookup?rsid=rs80357906` still returns BRCA1's
real ClinVar classification, `"Pathogenic"`, proven against a real
ingestion of 4,453,798 VCF records.

**`watchlist-service`** (backlog #53, ADR 0026, Done) is a new component:
its own namespace, its own Postgres, its own ArgoCD Applications. It owns
subscription CRUD and **guaranteed, idempotent, exactly-once-eventually
fan-out delivery** on `clinvar.ingestion.completed` — a second,
independent Kafka consumer group from `api`'s cache-invalidation listener
on the same topic. The delivery mechanism is outbox-table-plus-relay: a
`ClinVarIngestionListener` resolves matching subscriptions and inserts
`PENDING` rows into a `deliveries` table in the same transaction as the
Kafka offset acknowledgment; a fully independent `NotificationRelay` poll
loop actually calls `ntfy.sh` and marks rows `SENT`, with a `UNIQUE`
constraint plus `ON CONFLICT DO NOTHING` making redelivery idempotent,
and per-subscriber dead-lettering so one permanently-broken subscriber
never blocks another's fan-out. The crash-mid-delivery acceptance
criterion — the reason this pattern was chosen over an inline idempotent-
consumer-plus-retry design — was proven live against the real cluster: a
pod force-killed between a delivery row being persisted and the relay's
next tick left the row durably `PENDING`, and it was delivered on restart,
confirmed independently via the real ntfy.sh message history. **Known,
stated gap**: a crash between a row being claimed and the notification
call completing leaves that one row stuck in a `SENDING` state with
nothing to reclaim it — a real, valuable follow-on (a stuck-`SENDING`
reaper), not built here. Gene-based subscriptions are schema-ready but
unresolved: no component in this project extracts a gene symbol from
ClinVar's data today.

**`clinvar-viewer`** (an IGV.js genome-browser widget) and
**`workload-generator`** (a permanent, shaped synthetic-traffic generator,
backlog #45, Done) are both real, live components, not test fixtures.
`clinvar-viewer` is a static page with no backend of its own — a
deploy-time-mounted `config.js` carries its API key, stated plainly in
three places as *not* a confidentiality boundary, since a static page
can't keep anything out of view-source. `workload-generator` drives all
three real request paths (`work-items`, `/variants/lookup` against a
skewed key distribution, a configurable error fraction) continuously on
a shaped, non-flat rate, and reaches `api` via the public Ingress
hostname specifically so its own traffic is subject to the same edge
auth/rate-limit enforcement as everything else. Both carry their own
per-tenant API key via the same out-of-band Secret mechanism.

**Not yet:** the expansion phase's remaining milestones are real,
ADR-recorded decisions that have **not been built**, not silent gaps —
each is gated on a dedicated-desktop hardware move (M7) this project
hasn't made yet.

*Correction record:* M13 was listed below as unbuilt until 2026-08-06,
two days after it went live — the third recurrence of drift on this
file, and the reason backlog #97 replaces process with a CI check. It is
not in the list any more because it is done, not because the claim was
softened; the live description is at the top of this document.

- **M7 Multi-Node Substrate**: a multi-node k3s rebuild, **Cilium**
  replacing flannel with Hubble flow observability (ADR 0023) and the
  project's first NetworkPolicies, an **Istio ambient mesh** layered on
  afterward for mTLS and traffic-control/circuit-breaking (ADR 0024),
  replicated storage, and node-drain/rolling-upgrade exercises. Backlog
  #23a (backup/restore) is a hard prerequisite and is **Done** as of
  2026-08-04 (platform#62, ADR 0030) — a real restore drill with a
  measured RTO, on-node only, with single-disk loss accepted explicitly
  (backlog #99 converts that acceptance into a real off-site copy).
  **Neither Cilium nor Istio is deployed anywhere in this cluster today**
  — both remain on `.claude/PROJECT.md`'s approved list only via their
  respective ADRs, not as running components.
- **M11 AI-Assisted SRE** — an `sre-agent` over the project's own
  telemetry; not started.
- **M12 Bioinformatics Workloads (reopened, ADR 0025)** — `metadata-
  service`, MinIO, a real Nextflow pipeline engine, a saga-shaped Kafka
  lifecycle, `notification-service`, real licensed public datasets
  (1000 Genomes/TCGA/GEO/TCIA); gated on M7's storage substrate. None of
  its services (#67-#72) exist yet.
- Admission-time policy enforcement (Kyverno/Gatekeeper, backlog #58),
  Chaos Mesh formalizing the existing manual chaos exercises (#64), and
  Kubecost cost visibility priced against real owned-hardware TCO (#65)
  are also not yet built.
- Incident-response runbooks (#22) are partial — `docs/runbooks/` has
  the canary promote/abort runbook (#46) and the cross-repo rollout
  runbook, not yet one per alert rule as #22's own AC asks.

## Boundaries

- **platform** owns everything below the application: cluster, ingress, TLS,
  GitOps delivery, CI pipeline definitions.
- **services** owns the application: API, workers, `clinvar-service`,
  `watchlist-service`, the M13 market pipeline (`market-data-ingestor`,
  `news-ingestor`, `sentiment-analyzer`, `aggregator`, `visualizer`),
  `clinvar-viewer`, `workload-generator`, shared libraries.
- **observability** owns what you look at when something breaks: dashboards,
  alerts, runbooks, OTel config. Kept separate from `platform` deliberately —
  different change cadence and different owners in a real org (SRE vs.
  platform team), and it keeps blast radius of a dashboard edit away from
  cluster-changing Terraform/Helm.

## Why this split and not fewer repos

Four repos, not one monorepo, because the repo boundary doubles as the
ownership/blast-radius boundary — a Terraform change in `platform` should
never be gated on an unrelated Spring Boot PR in `services`. This is a
deliberate real-world constraint, not an accident of scale.

Decisions that deviate from the approved stack, or that are non-obvious and
worth defending later, go in `docs/adr/` — this file only describes the
current shape, not the reasoning.
