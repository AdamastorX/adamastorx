# Four joints nobody owns, a mesh that got more expensive, and the GitOps question answered the other way — 2026-10-18

Ninth in the review series (`2026-08-06-staff-engineer-review.md`,
`2026-08-09-staff-engineer-review.md`,
`2026-08-09-hardware-constrained-strategy.md`,
`2026-08-11-staff-review-differentiation-and-article-strategy.md`,
`2026-08-15-operate-followthrough-and-m12-reality.md`,
`2026-08-21-staff-engineer-full-audit.md`,
`2026-10-01-agentic-working-model-assessment.md`,
`2026-10-09-project-review-opus.md`). It starts from one fixed input,
same as the eighth review: **Mimir stays** (#135) — this review records
the decision's own record-consistency gap where it surfaced, and does
not re-litigate the decision itself.

**Method, stated plainly because it differs from most of this series.**
Produced by a multi-agent workflow — five parallel investigation agents
(haiku/sonnet) reading the real `services`, `platform`, `observability`
and `adamastorx` repos plus the relevant ADRs and backlog history, feeding
one high-effort opus synthesis pass, with a final haiku pass formatting
the resulting backlog items — orchestrated by a Claude Code session with
**no live `kubectl`/cluster access** (the node is reachable only via
Tailscale/SSH from the owner's own machine, confirmed unreachable from
this session). Every claim below about *current code, ADRs, and
committed records* is grounded in an actual file read by an investigation
agent. Claims about *live cluster state* (the `api` Rollout's real
status, real alert-firing history, real measured link quality) are
sourced from this project's own existing committed records — principally
`docs/SESSION_STATE.md` and the eighth review — not from a fresh live
query this session could not make. Where the source is a record rather
than a fresh live check, that is the honest limit of this pass, not a
claim to the contrary.

**Immediate action taken, not just reported:** this pass found the
reviewed `api`-deployability defect (§1.1 below) was real, current, and
mechanically fixable without live cluster access — the image tag was
simply stale. Fixed directly (platform#246, backlog #163 AC1) rather
than only written up. The remaining acceptance criteria on #163 (the
canary actually going `Healthy`, confirmed live) still need a session
with cluster access.

---

<!-- BEGIN: opus synthesis -->

## Staff review: AdamastorX, 2026-10-18

Read against the four investigation passes and the primary records (ADRs
0003/0009/0024/0040/0047, SESSION_STATE.md, the 2026-10-09 opus review,
backlog.md). Mimir's retention is out of scope per standing owner
decision #135; it appears only as a record-consistency note.

Short version: components are real and the engineering inside each
change is good. What is unhealthy is everything that exists only
*between* components — the cross-repo deploy seam, the dependency
pipeline, the self-monitoring loop, the written record. Three are live
defects, not risks. The second node is the right next chapter and M19
already carries most of it. Istio is still the wrong purchase and a
second node makes it worse, not better. On the headline ask — GitOps in
every repo with code — I think the premise is wrong and the pain behind
it is real.

### 1. Functional end to end?

Component-wise yes, with real data: 2,895,522 rows in
`clinvar_variant_index`; the 2026-10-07 ingestion ran 1m52s and published
40,063 changed keys as 3 events that `api` evicted exactly; a live
Finnhub websocket; real RSS polling; 108,581 `work_items` rows; backups
green three nights to 2026-10-09. Four seams are broken or unproven.

**1.1 The flagship service cannot be deployed, and a second trap is
armed.** `api`'s Rollout is Degraded/RolloutAborted at revision 4 since
2026-10-09T03:02:35Z: platform#238 merged 60s after services#96, pointed
`JAVA_TOOL_OPTIONS` at `/app/pyroscope-agent.jar`, and left the image at
`api:e26a01e` (2026-08-15, no baked jar). Production serves from stable
rev 3. Worse, `api-network-policies` is manual-sync and OutOfSync because
#238 deleted `api-pyroscope-agent-egress.yaml` — syncing it to clear the
only firing alert removes the GitHub egress the *stable* pod's init
container needs, so the next restart of the only serving pod sticks at
Init. #163 covers the instance; the mechanism is untracked.
*Update, same day: fixed directly, platform#246 — see the note above.*

**1.2 The oldest data path may be dead and nothing would say so.**
`workload-generator` POSTs `/work-items` continuously; `api` persists and
relays via `OutboxRelay.send`; `workers` sets `setObservationEnabled(true)`
explicitly (`WorkItemConsumerConfig:148`). Yet
`spring_kafka_listener_seconds_count` exists only for `api` and
`watchlist-service` (#185). #185 frames this as a dead alert; the more
interesting hypothesis is a dead *path* — either `workers` consumes
nothing, or it is unscraped, or the relay is not publishing. Nobody has
root-caused it, and there is no end-to-end assertion anywhere of the form
"a message produced by api was consumed by workers in the last 5m".
Resolve that before deleting the alert.

**1.3 The supply chain is deadlocked.** 10 open Renovate PRs in platform
with 0 status checks (cause: `renovate.yml` runs with
`secrets.GITHUB_TOKEN`, whose events do not trigger workflows); in
services, 5 of 10 show 0 checks. Meanwhile services CI blocks every PR on
real HIGH/CRITICAL CVEs — `aggregator`'s app.jar (13, 3 critical) and
alpine libcrypto3/libssl3/pcre2 in the nginx frontends. The PRs that would
fix the CVEs are the PRs that never get a check. #164 describes half of
this; the deadlock framing is recorded nowhere else.

**1.4 Self-monitoring is self-referential.** 25 alerts, all to one ntfy
webhook over the node's own Wi-Fi uplink; `ALERTS{alertname="Watchdog"}`
is empty. 34 lifetime carrier changes, 11 in 7 days, with `argo-rollouts`
and `keda-operator` each restarting 11 times on lease loss.
`prometheus_tsdb_lowest_timestamp_seconds` is 2026-10-03T16:09Z, so #94's
report cannot be written before ~2026-11-02. NetworkPolicies exist in 8
of 29 namespaces with pods while PROJECT.md:114 claims enforcement
"across every real namespace". `beyla`'s target is down with 29
restarts, so #145's comparison dashboard has nothing to compare.

Verdict: application layer real and healthy; delivery and
self-monitoring carry three live defects, each at a joint nobody owns.

### 2. The `api` name and the `workers` question

**api** owns four things: `HelloController`, work-item CRUD (Postgres +
Redis cache-aside + outbox/relay to Kafka), the ClinVar variant-lookup
read path (HTTP client, Redis annotation cache, and a Kafka consumer of
`clinvar.ingestion.completed` for invalidation), and the relay itself. It
is also the only service with an Ingress, TLS cert, per-tenant API keys
(#56) and a canary with an SLO gate.

Recommendation: **do not rename; do split, and split exactly one
thing** — extract the variant-lookup read path into its own service,
taking the `clinvar` package with it, so `api` stops consuming
`clinvar.ingestion.completed` entirely.

Why not rename first: the cost is concrete and currently unaffordable. A
`job`-label change rewrites every `job="api"` series — #177's `slo:*`
recording rules, #178's SLO table (now the Grafana home), the canary
`AnalysisTemplate` threshold, 25 alert expressions, the dashboards — and
it resets the only continuous time series you have, three weeks after
losing 33 days. Pay a rename only as a side effect of a split, or not at
all.

Why split: the name is a symptom, the coupling is the defect. One canary
gates three unrelated change classes, so a caching change on the variant
path can abort a rollout that was really about work-items; and the SLO
mixes two traffic populations with different shapes (continuous
synthetic work-item traffic versus a lookup path with zero real requests
in six days, which is why #183 exists). `VariantLookupController`'s own
comment — "only this controller stays same-origin-only by default" — is
the code admitting the boundary is wrong. The split also finishes ADR
0019 honestly: `clinvar-service` was extracted to Python after a real
cross-namespace bug, but its consumer-facing half stayed in Java inside
`api`.

The one thing that would make me wrong: ADR 0021 removed `gateway` for
being an empty hop, and a thin variant-gateway would recreate it. State
the distinguishing test up front — the extracted service must own the
Redis annotation cache and the Kafka invalidation consumer. No state and
no consumer, no split.

**workers.** The framing "generic, underused, give it a purpose or
retire it" was already asked and answered as #106, closed Done
2026-08-08 via the honest-restatement path. That was defensible. What has
changed is not genericness but that the justification decayed:
`WorkersListenerErrorRate` can never fire (#185); scale-to-zero was
explicitly rejected (`minReplicaCount: 1`); and the only proven scale-out
(2026-08-01) put 2 of 3 replicas Pending on insufficient CPU while one
replica drained 150 lag in ~90s, because `LoggingWorkItemHandler` is one
log line. Lag on a log statement is not a pressure signal.

Recommendation: **keep workers, move its two jobs to where they mean
something, and give it the one job it is uniquely good at.** Move KEDA's
ScaledObject and the lag alerting to `sentiment-analyzer` — real
per-message CPU cost in VADER scoring, real burstiness tied to news
arrival, and a stated v1 idempotency gap
(`sentiment-analyzer/README.md:120`) that a rebalance under scale-out
would expose for real. That is the operational lesson `workers` was
built to simulate and structurally cannot produce. Then restate
`workers`' purpose as the second node's scheduling and drain canary: it
is the best candidate for #172's stateless allowlist (no PVC, no
Service, no Ingress, trivial memory, KEDA-driven replica count), making
cross-node scheduling and #52's drain behaviour visible with zero data at
risk.

I considered outright retirement on ADR 0021's precedent (gateway and
whoami both carried real infrastructure while doing no real work, which
describes `workers` almost word for word). The T460s allowlist role tips
it: deleting `workers` now means inventing a disposable stateless
workload for #52 later.

### 3. Technical debt, prioritized

P0

1. **The cross-repo image/manifest seam.** #163 fixes the instance and
   its AC5 adds a *written rule*. There is no *check*. A platform CI gate
   that fails when a manifest references an image that does not exist in
   GHCR, or whose env/args name a path the image does not contain, fails
   #238 on the spot. Rules do not survive 03:00 merges; checks do.
2. **Renovate 0-checks plus the CVE merge deadlock** (#164 covers the
   credential half only).
3. **No dead-man's switch** (#165): the pager rides the monitored link.

P1

4. **The work-items path is unverified end to end** (§1.2). Root-cause it
   before #185 removes the only alert pointing at it.
5. **NetworkPolicy coverage 8/29 versus a doc claiming full coverage**
   (#168 policies, #167 record).
6. **One disk, one node, no off-node copy.** All 14 PVCs `local-path`
   with unenforced quota, Terraform state only on the operator machine,
   and backup CronJobs that failed for days with no pod ever created and
   a root cause never confirmed (#157). #176 is the highest-value item in
   M19.
7. **13 of 47 Applications are manual-sync.** The chicken-and-egg
   justification is real for `cilium` only; the M13 services' "staged
   rollout" reason has outlived its staging, and `cilium` itself has been
   OutOfSync and undiffed since 2026-10-04. Manual-sync is the de facto
   GitOps opt-out and it is now a third of the cluster.
8. **Two canonical records contradict each other on #135's trigger** —
   the 2026-10-09 review records it Done with a 2026-12-01 dated review;
   SESSION_STATE.md's 2026-10-06 entry still says the trigger is unset.
   Not re-litigating Mimir: the debt is that both files are canonical and
   disagree.

P2

9. **Prose debt as an operating cost.** backlog.md is 1,696 lines; single
   items pass 1,500 words; SESSION_STATE.md is 488 lines against its own
   current-state-only rule with 5 of 6 "still open" entries already
   resolved. Every agent session pays this on read, and it is
   demonstrably where stale claims survive.
10. **Dashboard source duplication.** `observability/grafana/dashboards/`
    holds only a README spec; the live JSON is generated into
    `platform/argocd/apps/grafana.yaml` by a hand-run
    `gen-slo-dashboards.py` — precisely the "second place with no source
    of truth" ADR 0003 exists to prevent.
11. `HelloController` still ships in `api`.

### 4. New services and flows worth building

Gate note: ADR 0031's "no new application services until #90–#97 close"
is still open, because #94 cannot close before ~2026-11-02 after the
history reset. M13 overrode this gate once by explicit owner decision;
overriding it twice makes it decorative. Queue these behind #94 rather
than through it.

**(a) alert-ledger.** Alertmanager's deliveries hit ntfy and vanish; the
project has no durable record of its own operational history, which is
exactly what the retention loss demonstrated. A small service consuming
the webhook, persisting every firing/resolution keyed on
`fingerprint`+`startsAt`, exposing a timeline API. New shapes: idempotent
ingest against a mechanism that *guarantees* duplicates (Alertmanager
resends on `repeat_interval`), and incident history independent of metric
retention. It also grows #128's grading corpus automatically instead of
by hand.

**(b) market-replay.** Reads an archived window of `stock.price.tick` and
`news.sentiment.scored` and republishes into shadow topics so
`aggregator` can be re-run against a known window. New shapes:
replay-vs-live determinism, Kafka Streams state rebuild from a chosen
offset (its `StateRestoreMetrics` exist and #90 plotted them, but
restoration has never been deliberately exercised), and the first
*oracle* the aggregates have had — today nothing can answer "was that
15-minute average right?". It also removes the market-hours dependency
from every M13 verification, and gives MinIO (#68) a non-bio
justification.

**(c) signal-service.** Consumes `aggregator`'s per-ticker aggregates,
evaluates user-defined rules (sentiment < −0.5 and price move > 2% in
15m), delivers through `watchlist-service`'s existing outbox/ntfy path.
New shapes: a rules read-path over a stream, exactly-once delivery across
restart with a real dedup store (fixing `sentiment-analyzer`'s stated gap
properly, once), and the project's first DLQ with redrive. Structurally
it joins the two disjoint halves of the system — the clinvar/watchlist
domain and the market pipeline are currently unconnected graphs.

Each is one stateless service, no new infrastructure, and each adds an
operational shape ADR 0022's rule requires.

### 5. The T460s as a real second node

M19 (#171–#176) plus ADR 0047 is a good plan; I would not rewrite it.
Five refinements and one correction.

**Sequencing.** Phase 0, before anything: #163 (so `api` is deployable),
#165 (dead-man's switch), and **#162 (stable addressing)** — M19's gate
names only the first two, but #173's AC (`k8sServiceHost` on an address
both nodes reach) and ADR 0047 decision 2 are unsatisfiable while the
server's address is a DHCP lease that has already changed once under a
running cluster.

Phase 1: #171 — clean slate, measurements, power policy, ADR 0047
Proposed → Accepted. Add a link measurement: the overlay will be VXLAN
inside WireGuard over Wi-Fi, and 11 carrier changes in 7 days means
cross-node traffic will partition routinely. Put the T460s on Ethernet
even if the NucBox cannot be.

Phase 2: #172 and #173 **before the node exists.** This is the
de-risking insight worth stating: affinity pins and taints are satisfied
trivially on a one-node cluster, so merge, selfHeal and verify them while
there is still only one node to break. Do not merge them in the same
window as the join.

Phase 3: #174, running its AC4 removal rehearsal *immediately* after the
first successful join, while nothing is scheduled on the agent.

Phase 4: #176 off-node backups — highest real value in the milestone,
and it should land before the drills, not after. Phase 5: #175 requests,
then #51 (rescoped) and #52.

**Real risks.** The `cilium` `k8sServiceHost` change needs a sync of a
manual-sync Application whose *full* sync rotates the Hubble mTLS certs —
scope it to the DaemonSet and operator per the SESSION_STATE gremlin. The
T460s's old `local-path` directories hold copies of old Postgres data,
so #171 AC2's deletion is irreversible and rightly owner-gated. A drain
of the NucBox will block on the `kafka-broker` PDB (0 disruptions) — a
#52 finding to record, not a bug to pre-fix. And two nodes double the
surface that can go dark, which is why #165 gates rather than follows.

**What it unblocks:** #52 in full (eviction, PDBs, cordon/drain, rolling
k3s upgrade) — the real prize; #51's *capability* test; #176; and
scheduling as a subject at all. On M12: #69 stays blocked — a compute
problem, and a 2-core laptop adds roughly nothing. But **#67
(metadata-service) is the one M12 item the second node genuinely
moves** — it was reassessed as capacity-blocked, not node-blocked, and
~19.5GB on an allowlisted node is real headroom for a JVM CRUD service
with its Postgres pinned to the NucBox — at which point cross-node JDBC
over Wi-Fi becomes the experiment, which is the interesting part.

**Correction to carry forward:** this is one server and one tainted
agent, not a multi-node substrate. #52's ungraceful-node-loss drill can
only target the agent; losing the NucBox is still losing the control
plane and all 14 PVCs at once. ADR 0045's "genuine multi-node substrate"
language must not survive into M19's write-up (#167 is the right item).

### 6. Istio

**No.** Still not worth it, and the second node makes the case worse.
The cost is per node: ztunnel at 200m/512Mi *per node* plus istiod at
500m/2048Mi. Adding a 2-core/4-thread machine adds another ztunnel bill
to a host where the DaemonSet tax already runs ~220m/578Mi requests and
~3.2Gi limits. ADR 0040's math was never about node count, and ADR 0047
decision 4 already restated that Istio stays superseded — which is the
honest answer to the question as asked.

Both problems ADR 0024 was bought for have shipped answers: #43 (a
stated `max.block.ms` budget) and #105 (tuned HikariCP `connectionTimeout`
plus a Resilience4j breaker), un-deferred by ADR 0040. ADR 0024's
strongest argument — the same hang in two languages — was explicitly
parked until a Python-side hang is documented, and none has been since.

The remaining honest want is mTLS, and the second node does change
something real: cross-node pod traffic now rides the overlay. But if you
join over Tailscale, WireGuard already encrypts the wire, so a mesh buys
nothing there. The actual residual gap is *workload identity*, and the
cheapest route to that lesson is SPIFFE/SPIRE scoped to Kafka client
auth, or Cilium's own transparent encryption plus the L3/L4 identity it
already has. Not a mesh.

If you want a mesh for content reasons rather than need, the defensible
version is not Istio: it is **Linkerd**, piloted on exactly two
namespaces (`api` ↔ `clinvar-service`, the one path with a documented
hang history and a real cross-language boundary). A Rust micro-proxy at
tens of MB per pod is a different price class from istiod plus ztunnel.
No backlog item proposed for it below — it should not start before #163,
#165 and M19 — but that is the shape to accept if the answer has to be
yes.

### 7. GitOps in every repo with code

Disagree with the premise, agree with the pain. What's actually wanted,
most likely: *merge in any repo has a reviewed, automatic, ordered path
to the cluster, and no step depends on anyone remembering.* That does not
require ArgoCD to read four repos, and the four-repo version actively
costs something CLAUDE.md itself names.

*Option A: ArgoCD watches `services/` and `observability/` directly
(multi-source or per-repo Applications).* Manifest ownership splits:
`platform/kubernetes/api/rollout.yaml` today carries resources, probes,
securityContext, env, and soon #172's node affinity, gated by platform
CI's kubeconform run, `render-helm-charts.sh`, and #172's render-time
check. Move it into `services/` and those gates are duplicated or lost.
Blast radius: CLAUDE.md's stated principle is that the repo boundary
doubles as the blast-radius boundary, and PROJECT.md already applies it
asymmetrically on purpose — Claude Code plugins are enabled in
`adamastorx` and `services` and explicitly *not* in `platform`/
`observability`, because "blast radius differs, and symmetry is not a
reason." Option A hands cluster-mutating authority to the one repo where
an agent loop is sanctioned to run — that is the project's own rule
inverted. PR ergonomics cut both ways: co-locating code and manifest
fixes the #163 class, but a cross-cutting change to resources/probes/OTel
env across eleven services is one PR today and N PRs after — and ADR
0009's "raw manifests, no shared chart" decision only stays cheap because
they are co-located. And it does not fix #163 unless *all* eleven
services move, which is the full inversion of ADR 0009, not an extension.

*Option B: platform stays sole entrypoint; automate both seams.*
`services` CI, on merge, opens (never merges) a bump PR in `platform`
with the digest it just pushed; `observability` CI runs
`gen-slo-dashboards.py` and opens a PR instead of depending on memory.
ADR 0009 already named this as the thing to do first — "automate the PR
*creation* first — still human-merged — before ever considering Image
Updater" — and pre-rejected it on cross-repo-token and ownership grounds,
so one clause needs an ADR to overturn. The revisit trigger has fired,
but through a different signal than ADR 0009 anticipated: not toil
volume — a *correctness* failure (#163) and a silent-drift failure (the
dashboards). That is a stronger trigger than toil, and the ADR should say
so rather than pretend the bump PRs got numerous.

*Option C: a root Application per repo.* More GitOps per repo,
multiplies reconciliation points, no documented pain asks for it. Reject.

**Recommendation: Option B, plus one thing neither option names.**
Automating PR creation removes the forgetting failure but not the
ordering failure. The mechanical fix for #163 is a platform CI check that
fails when a manifest references an image that does not exist in GHCR,
or whose env/args name a path the referenced image does not contain. That
check fails #238 on the spot, lives in the repo that owns the manifest,
and is verifiable against a known-bad commit — a strictly better
guarantee than #163 AC5's written rule.

**Where the instinct is straightforwardly right: `observability`.** It
is the weakest repo by every measure — no required status check on
`main` at all, no `renovate.json` (both in #164 AC5), and a "source of
truth" that is a prose spec while the deployed JSON is generated into
platform by a hand-run script whose own comment admits the deployed truth
lives elsewhere. That is the second-place-with-no-truth ADR 0003 exists
to prevent, except across repos. Fix that one properly — generator-of-
record in `observability`, automatic PR into `platform`, and a platform
CI check that fails if the committed JSON differs from what the
generator produces — and it delivers the whole value reached for, in the
one place it is actually missing.

**The defensible pattern, plainly:** platform centrally owns all
deployment manifests and is the only GitOps source; services and
observability own code, contracts and CI. Keep it, then close the two
seams mechanically so "one repo tells the cluster what runs" stops
costing a remembered step.

### 8. Other technologies worth a pilot

**Kyverno/Gatekeeper — yes, and it is already #58.** Fits: enforces
lessons learned the hard way at a boundary CI structurally cannot reach
(a Helm chart's rendered output, an ArgoCD-synced upstream manifest, a
hand-applied incident fix) — requests/limits (#35), `httpGet` over
`tcpSocket` probes (the ADR 0019 lesson), no `:latest`. Cost/risk: a
validating webhook is a single point of failure in front of every API
write; with `failurePolicy: Fail` on an OOM-prone node, nothing deploys
including the fix — which #58's own AC already requires exercising.
Highest-value item on this list, needs no new decision, sitting at P2.

**Argo Events + Argo Workflows — yes, pilot.** Fits unusually well:
already runs ArgoCD and Argo Rollouts, already has Kafka, and has already
hand-rolled two batch control planes (`clinvar-service`'s internal weekly
scheduler, three `pg_dump` CronJobs). Events triggering a Workflow from a
Kafka event gives the ordered multi-stage DAG with failure branches that
#70 reserved and #69 blocked on compute — the saga shape without the
bioinformatics compute bill. Cost/risk: another controller, and Argo
Events' default EventBus is NATS, which would make a *third* messaging
system next to Kafka and Redis unless the Kafka EventBus is chosen
deliberately.

**vCluster — yes, small pilot on the T460s.** Fits: the riskiest changes
are cluster-wide and currently rehearsed by performing them in
production — #49's own closing note records the `terraform
destroy`/`apply` rehearsal was skipped and the real rebuild went first. A
vCluster gives a disposable real API server for the API-level half of
that class, starting with #58's webhook-down exercise. Cost/risk, stated
up front: it shares the host kernel and CNI, so it does *not* rehearse
CNI swaps or node-level changes — the class #49 most wanted — and it is
another always-on control plane on the weaker machine.

**SPIFFE/SPIRE — interesting, not yet.** Fits: closes ADR 0012's
"PLAINTEXT, no auth" for Kafka with real workload identity and no
dataplane, which is the actual residual gap once the mesh is off the
table. Cost/risk: a new stateful component and a new CA on a node that
already OOM-kills things, and nothing consumes SVIDs today, so v1 issues
identities nobody checks unless scoped to exactly one path.

**Explicit no's, so they are not left ambient.** *Temporal/Dapr*:
Temporal's durable-execution model is the right shape for long-running
workflows, but its server needs its own datastore plus four services, and
adopting it would make the outbox+relay (ADR 0026, #53) redundant — a
content loss, not just a resource cost. *Knative*: KEDA already covers
event-driven scaling, scale-to-zero was deliberately rejected in #63, and
its networking layer would fight Traefik and Cilium. *Thanos/
VictoriaMetrics*: would re-litigate a settled stack choice and re-cut a
retention story three weeks after the window reset.

**Crossplane — the tension, flagged rather than ignored.** It is on
PROJECT.md's explicit exclusion list and would need an ADR. The exclusion
should *stay*, for a reason unrelated to the original argument: there is
no cloud account for it to reconcile, so today it would manage nothing.
But the honest tension is that this list is not load-bearing policy — it
has been overturned twice (ADR 0023 for Cilium, ADR 0024 for the mesh),
so it functions as a default, not a prohibition. The trigger worth
recording now: ADR 0040 decision point 6 already contemplates a future
cloud annex. If that lands, Crossplane becomes its natural second ADR,
and the exclusion should be re-examined then rather than defended on
inertia.

### 9. Where this review disagrees with the owner's framing

1. **"GitOps in every repo with code."** Disagree with the shape, agree
   with the pain. The four-repo version costs the blast-radius boundary
   CLAUDE.md states and inverts PROJECT.md's deliberate asymmetry about
   where agent loops may run. The property actually wanted is an
   automatic *ordered* path, which Option B plus a mechanical image/
   manifest check delivers inside the existing boundary. Partial
   concession: for `observability` specifically the instinct is simply
   correct.
2. **"Is Istio feasible now that there are two nodes?"** Disagree with
   the premise. The blocker was never node count — ADR 0040's math is
   per node and ADR 0047 decision 4 already said Istio stays superseded.
   Asking again risks the exact re-litigation pattern #135 was criticized
   for. A weaker second node adds a ztunnel bill, not headroom.
3. **"The project has two real machines."** It will have one server and
   one tainted agent — asymmetric capacity, not a multi-node substrate.
   #52's node-loss drill can only target the agent; losing the NucBox is
   still losing the control plane and all 14 PVCs. Do not let ADR 0045's
   phrasing survive into M19's write-up.
4. **The `workers` question** was already asked and answered as #106
   (Done, honest-restatement path). The new fact justifying a reopen is
   #185's dead alert and the decayed KEDA story, not genericness —
   reopening it on the original grounds would be re-deciding a settled
   question.
5. **Renaming `api`.** Disagree with rename-first: the label cost is
   concrete (#177's recording rules, #178's table, the AnalysisTemplate
   threshold, 25 alerts) and a `job`-label change resets the only
   continuous series available, three weeks after losing 33 days. Split
   first; rename as a side effect or not at all.
6. **New services now.** The ADR 0031 gate is still open because #94
   cannot close before ~2026-11-02. M13 overrode it once by explicit
   owner decision; a second override makes the gate decorative.
7. **Record consistency, not Mimir.** The 2026-10-09 review records
   #135 Done with a 2026-12-01 dated decommission review; SESSION_STATE.md's
   2026-10-06 entry still says the trigger is unset. The decision to keep
   Mimir is settled — but two canonical files disagreeing about whether a
   trigger exists is the same defect class as PROJECT.md calling a
   six-week-old migration an open decision.
8. **About this review's own suggestions.** Two of the four technologies
   in §8 are new tools on a capacity-bound node, against this project's
   stated ethos of boring tools for real problems. If only one starts,
   start #58 — already in the backlog, and the only one that mechanically
   enforces lessons already paid for.

<!-- END: opus synthesis -->
