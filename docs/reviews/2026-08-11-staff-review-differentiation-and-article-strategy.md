# Differentiation, the article strategy, and the operations gap — 2026-08-11

Third in the review series (`2026-08-06-staff-engineer-review.md`,
`2026-08-09-staff-engineer-review.md`,
`2026-08-09-hardware-constrained-strategy.md`). The first two audited what
was built and what drifted; the third decided where the project goes under
a real hardware ceiling. This one answers the question the owner asked
directly: **reassess where the project stands, propose backlog items that
make it better and more article-worthy, and decide which direction gives
the greatest differentiation** — explicitly leaving the choice between
"go deeper on what exists" and "add a small new domain" to this review
rather than pre-committing to either.

The rubric is unchanged — the owner's four standing objectives:

1. An observability pipeline fed with real data
2. Microservices / distributed systems depth
3. A lab/playground for state-of-the-art and established technologies
4. Articles (blog/Medium) to grow a public SRE reputation

Scope of evidence: all 40 ADRs, the full 1,220-line backlog, both prior
staff reviews and the hardware-constrained strategy review,
`docs/WHY.md`, `docs/architecture/overview.md`, `docs/roadmap/milestones.md`,
`.claude/PROJECT.md`, the drafted-but-unpublished article
(`docs/articles/2026-08-09-mimir-three-bugs-and-a-fourth.md`), the three
chaos fact packs, the `observability/sre-agent/` harness, the 19 runbooks,
`platform/argocd/apps/*.yaml` (47 live Applications) — and, because every
load-bearing claim in §1 is a live claim, a **read-only inspection of the
running cluster** performed during this review: `kubectl describe node`,
`kubectl top`, the live Prometheus `/api/v1/rules` and `/api/v1/alerts`,
Alertmanager's own `/api/v2/alerts` and notification counters, real pod
logs, the real Kafka topic list, and the real contents of
`clinvar-service`'s refdata volume. Nothing was mutated: no `apply`,
`patch`, `delete`, `scale`, or sync.

---

## 1. The finding: this cluster is alerting correctly, and nobody is answering

Everything below was read off the live system during this review, not
inferred from the repos.

**Four alert rules are firing right now. Three have been firing for
between 6 and 33 hours. Alertmanager has successfully delivered 189
notifications with zero failures.**

| Alert | Firing since (UTC) | Elapsed at check | Severity |
|---|---|---|---|
| `BlackboxProbeFailing` ×6 targets | 2026-08-10 10:33 | **~33h** | critical |
| `ApiVariantsLookupHighErrorRate` | 2026-08-10 22:17 | **~21h** | critical |
| `ApiHighErrorRate` | 2026-08-10 23:24 | **~20h** | critical |
| `MarketDataStaleFeed` ×5 tickers | 2026-08-11 13:31 | **~6h** | warning |

`alertmanager_notifications_total{integration="webhook"}` reads **189**;
`alertmanager_notifications_failed_total{...}` reads **0** across every
reason. The ntfy path (#21c, rotated under #107) works. Every one of these
four alerts has a runbook in `observability/runbooks/` — coverage is
genuinely 19 of 19, verified. **The detection layer is not the gap. The
response layer is.**

What the alerts are correctly telling you:

**1a. The ClinVar lookup path — M5's flagship feature — has been returning
502 for ~21 hours, because the cluster rebuild wiped the reference data and
nothing put it back.** `clinvar-service`'s logs show, on every lookup:

```
File "/app/app/vcf_query.py", line 70, in query
  with pysam.VariantFile(str(vcf_path)) as vf:
FileNotFoundError: [Errno 2] Could not open variant file:
  No such file or directory: '/data/clinvar/current/clinvar.vcf.gz'
```

Checked directly rather than inferred: `/data/clinvar/` on the live
`clinvar-service-refdata` PVC is **completely empty** — `du -sh` returns
`4.0K`, directory mtime `Aug 10 08:59`, i.e. recreated bare by #49's
`terraform destroy`/`apply`. `clinvar_ingestion_duration_seconds_count` is
`0` on this pod: no ingestion has ever run since the rebuild.

This is the most instructive shape in the whole finding. #49's own backlog
entry records the restore as verified, and it *was* — `clinvar_variant_index`
came back with 2,895,522 rows, counted and matched. But the index is only
half of this service's state: the row tells you which coordinates to look
at, and the **VCF file the row points into** is the other half. Backup
scope (#23a, extended by #121) covers the three Postgres instances and
explicitly, correctly states Loki/Tempo are regenerable-and-not-backed-up.
`clinvar-service-refdata` fell into neither bucket — it is regenerable (a
re-download from NCBI), but nothing triggers the regeneration, and no
restore step names it. **A row-count-based restore verification structurally
cannot see this class of gap**, which is precisely why it passed.

Note also which SLI actually caught it. `ClinVarIngestionFreshnessBreach`
exists exactly for "the data is stale" — and it is `inactive`, because its
window is 8 days and the rebuild was 1.4 days ago; it would have fired
around 2026-08-18. The downstream consumer's error-rate SLI
(`ApiVariantsLookupHighErrorRate`, the row ADR 0020 added specifically
because `api`'s dependency on `clinvar-service` is a distinct failure
mode) beat it by **six and a half days**. That is a genuinely publishable
observation about SLI design, and it came free.

**1b. `clinvar.ingestion.completed` does not exist on the broker, and two
services have been hot-looping on it for ~34 hours.** The real topic list
(`kafka-topics.sh --list`, exit 0) is:

```
__consumer_offsets, aggregator-{latest-price,latest-sentiment,
price-window,sentiment-window}-store-changelog,
news.article.published, news.sentiment.scored, stock.price.tick, work-items
```

`clinvar.ingestion.completed` is absent. `api` and `watchlist-service` each
log `UNKNOWN_TOPIC_OR_PARTITION` roughly once per second — correlation ids
at check time were **148,296** and **168,618** respectively. Consequences,
in order of seriousness: `watchlist-service`'s guaranteed outbox-plus-relay
fan-out (#53, ADR 0026) — the capability both prior reviews single out as
"the single best engineering story in the project" — is **structurally dead
right now**: no topic, no events, no deliveries, and `WatchlistDlqDepthHigh`
cannot fire because nothing flows. `#26`'s release-aware cache invalidation
is equally inert. And two JVMs are burning CPU and Loki volume on a metadata
retry loop on a node at 84% CPU requests.

ADR 0032 (#95) made broker storage persistent so topics survive a *restart*
— and it does. It does not survive a PVC wipe, and the topic-provisioning
Job re-created only the topics in its own list. This is the same incident
class as #79/#80/#84, in the one shape ADR 0032's verification (a plain
`kubectl delete pod`) could not reach.

**1c. All six blackbox probes have been failing since the rebuild, and the
cause is a hard-coded IP whose own code comment predicted this exact
failure.** `probe_success` is `0` for all six targets — `api` (auth),
`api` (401-expected), `aggregator`, `grafana`, `visualizer`,
`clinvar-viewer`. Cause, confirmed by direct comparison:

- `argocd/apps/blackbox-exporter.yaml` pins `hostAliases: - ip: 10.43.225.45`
- Traefik's real ClusterIP today is **`10.43.205.209`**

The same file's comment, written when #93 shipped, reads: *"confirmed live
via `kubectl get svc -n traefik traefik`, not assumed stable across a chart
upgrade — **revisit if Traefik's own Service is ever recreated with a
different ClusterIP**."* The rebuild recreated it. Nobody revisited. The
project's entire continuous-verification capability — the thing #93 exists
to provide, "converts point-in-time verification into continuous
verification" — has been dark since the moment the biggest change in the
project's history landed, and it said so, critically, 189 times.

**1d. `MarketDataStaleFeed` is correct and the fallback is working.**
`market_data_stale_feed` is `1` for all five tickers during real US market
hours; `market_data_websocket_reconnects_total` is `3`; ticks published
total `1093`. Meanwhile `GET /aggregates` returns real data with
`priceAsOf: 2026-08-11T18:57Z` — the 30-minute REST-poll fallback (#87)
doing precisely its job while the websocket is down. That is a design
working as intended and worth saying out loud among the bad news.

**1e. Restarts nobody is watching.** `mimir` has restarted **11 times**,
most recently 5h55m before this check, exit code `137` against a `768Mi`
limit with real usage at `693Mi` (90% of limit) and **no liveness probe
configured at all** — so this is memory pressure, not probe flapping.
`watchlist-service`: 7 restarts. `clinvar-service`: 4. `keda-operator`,
`market-data-ingestor`, `argocd-dex-server`: 1–3 each. There is **no alert
anywhere on container restarts or OOMKills**, despite `kube-state-metrics`
being live since #92 and `kube_pod_container_status_restarts_total` being
right there. The project has already learned this lesson twice by hand
(#85's silent-but-Healthy RocksDB crash, #86's poisoned Kafka producer that
hid for two days) and both times fixed it *per service* with a bespoke
liveness indicator, which is the right fix for those two and no fix at all
for the general case.

**1f. The capacity picture, re-measured.** `kubectl describe node`:
**3395m/4000m CPU requested (84%)**, memory requests 8858Mi (44%), memory
*limits* 20898Mi (**105% — overcommitted**). `kubectl top node`: 2070m
(51%) / 12403Mi (62%). Host `free -h`: 19Gi total, 6.9Gi available, **4.4Gi
of 8Gi swap in use**; `nproc` 4 on 2 physical cores; load average 3.83.
ADR 0040's conclusion is unchanged and re-confirmed: **CPU is the binding
resource, memory has real slack in requests but not in reality.**

---

## 2. Verdict

The 2026-08-06 review found the binding constraint was packaging and drift.
The 2026-08-09 strategy review found the binding constraint was a hardware
ceiling. Both were right at the time. The binding constraint now is
something neither anticipated, and it is not technical:

> **The project's build rate has outrun its operate rate.** In 24 days
> (first commit 2026-07-18) it has produced 380 merged PRs, 40 ADRs, 47
> ArgoCD Applications, 19 alerts, 19 runbooks and 12 dashboards — and as of
> this review it is 33 hours into a four-alert incident that its own
> monitoring caught immediately, notified 189 times, and wrote a runbook
> for in advance. Nothing was building the operational track record; the
> project was building more things to operate.

That reframes the differentiation question, and it answers it. This is
also, uncomfortably, the honest answer to "are we following our own good
practices": the practices are *written* and *automated* to an unusually
high standard, and the last 34 hours are the first real test of whether
they are *lived*. They weren't.

**The recommendation, in one line:**

> **Stop adding components entirely for this stretch. Convert the project
> from a build log into an operations log: close the live incident and
> fact-pack it, make post-rebuild verification a real acceptance gate,
> stand up a dated operations review as a recurring first-class artifact,
> and publish. This is "go deeper on what exists" — but deeper in
> operational tenure and incident narrative, not deeper in technology,
> which is the axis where this project is already saturated and the axis
> where it is genuinely rare.**

Every item this implies costs **zero additional CPU**. Several return CPU.

---

## 3. Differentiation: weighing both directions with evidence

The bar the owner set is the right one and worth restating: *what can this
project say that almost nobody else's blog can?* Not "what is technically
impressive." Measured against that bar, here is the honest scoring.

### 3a. What is genuinely rare here

- **A single-node cluster that was deliberately destroyed and rebuilt from
  Git plus backups, with the honest list of what did not come back.** This
  is the rarest asset the project owns and it is **perishable** — the
  evidence is live right now (§1a/1b/1c) and decays the moment someone
  fixes it without writing it down. Almost nobody `terraform destroy`s
  their only cluster on purpose. Of those who do, essentially nobody
  publishes the *incomplete* half of the restore. "I rebuilt my whole
  cluster from Git. Here are the four things GitOps didn't bring back" is,
  by a distance, the best unwritten article in this repo.
- **A real, measured hardware ceiling that killed a planned milestone.**
  ADR 0040 and backlog #48's closure-as-superseded are unusual: most
  homelab writing describes what fits, not what was measured and found not
  to. "My multi-node plan didn't survive contact with `lscpu`" is relatable
  in a way that a working Istio install is not.
- **A recorded decision-reversal habit at unusual density.** 18 of 40 ADRs
  contain supersession/overturning/correction language. ADR 0018→0019,
  0021→0022, 0023→0024→0040, 0035 falsified by its own follow-up
  measurement, ADR 0037's decision made wrong then corrected in the record
  rather than silently. This is the thing the 2026-08-06 review called "the
  engineering culture is the product," and it remains true.
- **An AI-built system observed by an AI agent, graded against human-written
  fact packs it did not help write.** Still unbuilt (`sre-agent` v1 has
  never been run against the real API), still the single most novel item in
  the backlog, and the incident corpus available to grade it against has
  roughly doubled since ADR 0039 was written.
- **Alert-response behaviour of a solo operator, measured honestly.** Nobody
  publishes their homelab's real time-to-acknowledge. This review just
  measured it accidentally: 33 hours, 21 hours, 20 hours, 6 hours. That is
  not a flattering number and it is exactly why it is interesting.

### 3b. What is not rare, and where the last week went

Blunt, because the prior reviews earned the right to be: **the most recent
week is the least differentiated week in the project's history**, measured
by "could someone else have written this."

Between 2026-08-07 and 2026-08-11 the cluster gained `kube-state-metrics`,
`node-exporter`, `blackbox-exporter`, `mimir`, `beyla`, `cilium`+`hubble`
(relay, UI), and a `vpa` recommender with 50 VPA objects — plus Faro
(which correctly reused Alloy and added no component). Several are
genuinely justified: ksm/node-exporter unblocked three items, Cilium is the
most modern thing this machine can run and ADR 0040 sequenced it correctly,
blackbox closed a real verification gap. But the *aggregate* shape is
component collection, and the evidence that it has become the project's
default mode is right there in the ledger:

- Mimir (100m/256Mi requested, **693Mi real, OOM-restarting 11 times
  unnoticed**) and Beyla (100m/256Mi requested, **772Mi real**) are both
  concluded experiments whose own ADRs say so — ADR 0038's verdict is
  literally "not yet worth it as a standing piece of this cluster's real
  architecture." They stay deployed by explicit owner decision (#120 records
  it verbatim, and this review respects it without relitigating). But their
  *combined real memory* is ~1.5Gi on a host running 4.4Gi into swap, and
  Mimir is failing continuously with nothing watching.
- VPA landed 2026-08-11 with its own entry honestly stating the report and
  the adjustment cycle both still need the data to mature — i.e. it is a
  deployed component that has not yet produced its own AC's output.
- Meanwhile **#29 — `clinvar-service`'s golden-signal dashboard, a P1 from
  M5 — is still open.** Confirmed live: `grafana.yaml` carries 12
  dashboards and not one of them is `clinvar-service`. It is the only
  backend service in the cluster with an ADR 0020 SLO row and no dashboard,
  and it is the service the project's own Simplification section calls
  "this project's single most defensible portfolio content." An
  installation of Beyla is worth less than the dashboard for the service
  the project says it is proudest of.

"I installed Cilium / Mimir / Beyla / VPA on my homelab" is a commodity
genre with thousands of entries. Ten more components does not move
objective 4 at all, and it actively costs objective 4 by consuming the
weeks in which nothing gets published.

### 3c. Weighing "add a small new domain"

Taken seriously, not dismissed. The candidates are M12's bio pipeline
(#67–#72) and any new application service.

Against it, in descending order of decisiveness:

1. **The project's own gate still stands and is still not cleared.** ADR
   0031's "no new application services until #90–#97 close" — #91's positive
   case needs real market hours (and the websocket is currently down, §1d),
   and #94's report needs ~26 more days. This review is restating the
   project's rule, not inventing one.
2. **It doesn't fit.** 84% CPU requested; the two most recent M13 services
   already burst *above* their requests (#120 measured `aggregator` at 501m
   real peak against a 250m request). A new always-on Spring Boot service is
   ~250m, i.e. roughly 40% of remaining headroom, before its Postgres.
3. **It fails ADR 0022's own test.** The test is "a new operational shape
   this project does not already have." The project now has synchronous
   CRUD, cache-aside with invalidation-on-write, scheduled batch ingest,
   guaranteed fan-out with outbox+relay+DLQ, async job control plane,
   windowed stateful stream processing, edge auth/rate-limiting, event-driven
   autoscaling, and canary-with-SLO-gate. There is no cheap unclaimed shape
   left. M12's genuinely new shape (a multi-step DAG with orphaned-work
   recovery) needs MinIO plus Nextflow plus replicated storage (#51,
   blocked-on-hardware) — it does not fit and its own dependencies say so.
4. **The doc/alert/runbook tax is already unpaid.** #29 open since M5, 21 of
   26 namespaces with no NetworkPolicy (§4c), no restart alerting. Adding
   surface to a system whose existing surface is 33 hours into an unattended
   outage is the wrong purchase at any price.

**Verdict: no new domain, no new application service, no new always-on
component this stretch.** Not "later" — not this stretch, as a stated
stop, so it does not erode into a default.

### 3d. Weighing "go deeper on what exists"

"Deeper" has two very different readings and only one of them is right.

- **Deeper technically** — exemplars (#19a), profile↔trace correlation,
  Chaos Mesh (#64), Kyverno (#58), Kubecost (#65). Each is defensible in
  isolation; each adds a component or a component's worth of maintenance;
  none of them is something another blogger cannot do in an afternoon.
  Chaos Mesh in particular is a controller + daemonset + dashboard on a node
  at 84% — and this project already does chaos engineering *better than
  Chaos Mesh users do*, by hand, with three fact packs that read like
  incident reports rather than tool demos. Formalizing that in a tool trades
  the differentiated asset (the narrative) for an undifferentiated one (the
  tool).
- **Deeper operationally** — tenure, incidents, response, and the record of
  both over time. This is where the project is uniquely positioned and
  currently at zero. It is also the only reading that costs no CPU.

**The call: deeper operationally.** Concretely, the project's next
differentiating asset is not a component; it is a **dated series of real
operational events with real response times and honest outcomes**, of which
it has just accidentally generated the best one it will ever get.

---

## 4. Are the project's own good practices actually being followed?

Checked against the project's own written standards, live, not recited.

### 4a. Where the standard genuinely holds (say this in articles)

- **Runbook coverage is 19/19.** Every live alert has a runbook, verified
  file-by-file against `/api/v1/rules`. #111 found this gap once and
  #117's CI check now enforces it. This is better than many production
  teams.
- **`#114`'s resources rule holds for everything the project controls.**
  Only five containers cluster-wide have no `resources` block, and four are
  ArgoCD's own vendored `install.yaml` components, which #114 explicitly
  scoped out with a stated reason.
- **Doc-drift automation (#97) works.** `overview.md` mentions Cilium (20×),
  Hubble (15×), VPA, Mimir, Beyla — the roster check is doing its job on the
  class it was built for.
- **Alert delivery works end to end**, proven by 189 real notifications with
  zero failures.
- **`#87`'s fallback design works**, proven by real data being served while
  the primary feed is down.
- **Prometheus history survived a full cluster destroy.** Queried live: real
  `up` series at 1/2/3/4/5/6/7-day offsets, zero at 10 days. #94's 30-day
  clock (started 2026-08-07) is intact and the SLO-over-time report is
  ~26 days out. This is a genuinely impressive outcome of #49's PVC-copy
  discipline and should be said in the rebuild article.

### 4b. Where it does not hold — specifically

1. **"Never ship a service without its observability" (#109/ADR 0017/0020)
   — violated for `clinvar-service`, still, since M5.** SLO row: yes.
   Alerts: yes. Runbooks: yes. Dashboard: **no**. #29 is the open item and
   it has outlived three milestones. #109's grace-period check does not
   catch it because the check requires the component to be *mentioned* in
   `grafana.yaml`, and `clinvar-service` is mentioned there in comments —
   a real, narrow false-negative in a check that otherwise works.
2. **"Never ship a component without its alert" — violated for the whole
   restart/OOMKill class.** §1e. The signal exists (ksm, #92) and nothing
   consumes it. Mimir has been OOM-looping for at least 33 hours in silence.
3. **The rebuild had no whole-system acceptance criteria.**
   `flannel-restore.md` covers backup, PVC inventory and restore, and #49's
   entry lists an impressive per-item verification — 35/35 scrape targets
   up, `cilium status OK`, real HTTP `api`→`clinvar-service`, Kafka consumer
   groups rejoined. Every one of those checks passed *and* the system was
   broken in three places, because the checks were component-liveness
   checks, not **business-path** checks. Nothing verified "a real variant
   lookup returns a real answer," "the `clinvar.ingestion.completed` topic
   exists," or "the blackbox probes still pass." The project already knows
   this lesson under a different name — #85/#86's "silent-but-Healthy" —
   and has not yet generalized it from pods to the cluster.
4. **`#50` is marked Done and the cluster has the project's own policies in
   5 namespaces out of 28.** This is not a misrepresentation — #50's AC named a minimum flow
   list and every flow in it is genuinely live and verified, which is a real
   achievement including the `toCIDR` workaround for the upstream Cilium
   DNS-proxy bug. But the item's *title* is "default-deny per namespace," and
   live `kubectl get cnp -A` shows policies in `api`, `clinvar`, `workers`,
   `alloy`, `prometheus` only. Unenforced: `aggregator`,
   `market-data-ingestor`, `news-ingestor`, `sentiment-analyzer`,
   `watchlist`, `kafka`, `grafana`, `loki`, `tempo`, `otel`, `pyroscope`,
   `visualizer`, `clinvar-viewer`, `beyla`, `mimir`, `vpa`, `keda`,
   `blackbox-exporter`, `traefik`, `argo-rollouts`, `cert-manager`.
   **`kafka` is the one that matters**: ADR 0012 records it as `PLAINTEXT,
   no auth`, it holds every event in the system, and any pod in the cluster
   can reach it. The egress side is constrained for `api`/`workers`; the
   ingress side is not constrained at all.
5. **ADR 0020's SLO table still carries a `gateway` row.** `gateway` was
   deleted by ADR 0021/S1. The table is the live registry #109's check reads
   against; a removed service in it is small but real drift in exactly the
   file the project treats as authoritative.
6. **Memory limits are 105% overcommitted** on a host already 4.4Gi into
   swap. Each individual limit is defensible (#114 sized them from real
   measurements); the aggregate has never been checked as an aggregate, and
   Mimir's repeated 137s are what that looks like from the inside.

### 4c. Security posture

No leaked-credential class found; #107's cross-repo sweep held up. The real
gaps are the two above (#4b.4's unrestricted Kafka ingress, and the
unenforced namespaces generally). `#112`'s `Prune=false` annotations are
live. `#88` remains descoped, so there is no public attack surface at all —
which is a real, if accidental, mitigation.

---

## 5. Proposed backlog items

**These are proposals, not added items.** `docs/roadmap/backlog.md` is
deliberately untouched by this PR — the owner asked for the document only.
Each item below is written in the backlog's own four-line format
(Purpose / Acceptance Criteria / Dependencies / Priority + Labels) and
numbered contiguously from the current maximum (#121) so they satisfy
#97's structural check if pasted in as a block.

---

**122. Close the four live alerts, and fact-pack the response as this project's first unattended-incident record**
- Purpose: on 2026-08-11 an independent review found four alert rules firing — `BlackboxProbeFailing` (6 targets, ~33h), `ApiVariantsLookupHighErrorRate` (~21h), `ApiHighErrorRate` (~20h), `MarketDataStaleFeed` (5 tickers, ~6h) — with Alertmanager reporting 189 successfully delivered notifications and zero failures, and a runbook already written for every one of them. The detection layer worked perfectly; nobody answered. Three real, distinct root causes sit behind them, all traceable to #49's cluster rebuild: `clinvar-service`'s refdata PVC is empty (`/data/clinvar/`, 4.0K, no VCF) so every variant lookup 502s while its Postgres index is intact — the exact failure a row-count restore verification cannot see; `clinvar.ingestion.completed` does not exist on the rebuilt broker, so `api` and `watchlist-service` have logged `UNKNOWN_TOPIC_OR_PARTITION` roughly once a second for 34 hours (correlation ids 148,296 and 168,618) and #53's entire guaranteed fan-out capability is inert; and `blackbox-exporter`'s `hostAliases` still pins Traefik's pre-rebuild ClusterIP (`10.43.225.45` vs the real `10.43.205.209`), which the file's own comment predicted in writing. The response — not just the fixes — is the artifact: this is the project's first chance to record its own real time-to-acknowledge honestly.
- Acceptance Criteria: each of the three root causes fixed and verified live, not assumed — a real `GET /variants/lookup` against a known variant (`rs80357906`, the same one #24's own AC uses) returns a real classification, not a 502; `clinvar.ingestion.completed` exists and both `api` and `watchlist-service` stop logging metadata warnings, with a real fan-out proven end to end per #53's own method rather than assumed from topic existence; all six `probe_success` series return `1`, and the `hostAliases` value is either corrected *and* given a stated re-check trigger, or replaced with a mechanism that cannot drift (a CoreDNS rewrite or Traefik Service DNS name — decision recorded either way, since #93's own comment shows a comment is not a mechanism). A fact pack in `observability/chaos/` following the existing convention, covering: what fired, when, how long each ran unanswered, what the notification path actually did, which runbook was opened first and whether it helped, and the real elapsed time from starting work to green. `MarketDataStaleFeed` is triaged and either resolved or explicitly accepted with a reason (the #87 fallback is serving real data throughout, confirmed live). #89's asset-capture step applied — the firing-alert screenshots for this incident exist only while it is firing.
- Dependencies: none.
- Priority: P0. Labels: `observability`, `platform`, `bug`, `documentation`.

---

**123. Post-rebuild acceptance verification: the business-path checks #49's component-liveness checks structurally could not fail**
- Purpose: #49's rebuild verification was thorough and every check passed — 35/35 scrape targets up, `cilium status OK`, consumer groups rejoined, three Postgres instances restored with matching row counts, Prometheus's real multi-day history intact. The system was nevertheless broken in three places (#122), because every check was a *component-liveness* check and none was a *business-path* check. This is the project's own already-learned "silent-but-Healthy" lesson (#85, #86) generalized from a pod to a cluster: a component can be Running, Ready, scraped, and Synced while the thing it exists to do does not work. `flannel-restore.md` is the natural home — it already covers backup, PVC inventory, and restore, and is the document a future rebuild will actually be executed from.
- Acceptance Criteria: `platform/docs/runbooks/flannel-restore.md` gains a mandatory post-restore acceptance section that is a real, runnable checklist, not prose — at minimum, one end-to-end assertion per real user-visible path: a real variant lookup returning a real classification; a real `POST /work-items` observed consumed by `workers`; the full expected Kafka topic list compared against a committed expected set (not eyeballed); every `probe_success` series equal to 1; `GET /aggregates` returning non-empty data with a fresh `priceAsOf`; a real `clinvar.ingestion.completed` fan-out reaching a real delivery row. Separately and explicitly: an inventory of **non-Postgres state** each PVC holds and how it is restored or regenerated — `clinvar-service-refdata` is the instance that was missed, and the general rule ("a PVC whose contents are regenerable still needs a stated, triggered regeneration step, not just the word 'regenerable'") is written down rather than left to the next rebuild to rediscover. #23a's and #121's backup scope statements updated to name the refdata volume's disposition explicitly. Proven by walking the checklist against the current, post-#122 cluster and recording the real result of each line.
- Dependencies: #122.
- Priority: P0. Labels: `platform`, `documentation`, `observability`.

---

**124. A standing operations review: a dated, published operational log**
- Purpose: this project has an exceptional *build* record (380 merged PRs, 40 ADRs, every closure carrying real evidence) and no *operations* record at all. The 2026-08-11 review's central finding is that the two have diverged: the cluster alerted correctly and delivered 189 notifications about a four-alert incident that ran for up to 33 hours unanswered. The fix is not more signal — coverage is 19/19 alerts with 19/19 runbooks — it is a recurring, dated activity that produces an artifact. This is also the missing input to three things the project already wants: #94's SLO-over-time report needs something to narrate alongside the numbers, #66's `sre-agent` needs a growing graded incident corpus (it currently has three Mimir bundles), and objective 4 needs a publishable series rather than one-off write-ups. Writing costs zero CPU, which under ADR 0040's ceiling is the whole point.
- Acceptance Criteria: a dated document per review cycle in a new `docs/operations/` directory (cadence chosen and stated — weekly is the suggestion, but a stated cadence that is actually kept beats an ambitious one that isn't), each covering: every alert that fired in the window with its real firing duration and real time-to-acknowledge; what was actually done; what is still open and why; a live re-read of `kubectl describe node` headroom; the current restart counts of every workload; and anything that changed without a PR. At least two consecutive cycles completed before this is considered proven — a process that runs once is a document, not a habit. Explicitly cheap by design: this is a read-only sweep plus a page of writing, not an engineering task, and if a cycle finds nothing that is a valid and worth-recording outcome. The first cycle's report is the #122 incident.
- Dependencies: #122.
- Priority: P1. Labels: `documentation`, `observability`.

---

**125. Alert on container restarts and OOMKills — the signal class this cluster already scrapes and never uses**
- Purpose: found live 2026-08-11. `mimir` has restarted **11 times** (most recent 5h55m before the check, exit `137`, real memory 693Mi against a 768Mi limit, and no liveness probe configured — so this is memory pressure, not probe flapping); `watchlist-service` 7 times; `clinvar-service` 4; `keda-operator`, `market-data-ingestor`, `argocd-dex-server` 1–3 each. Nothing alerts on any of it, and nothing has for the ~33 hours Mimir has been looping. `kube-state-metrics` has been live since #92 and exports `kube_pod_container_status_restarts_total`, `kube_pod_container_status_last_terminated_reason`, and `kube_pod_container_status_waiting_reason` — the signal is already scraped and simply unused. This project has learned the underlying lesson twice already (#85's RocksDB crash behind a Healthy pod, #86's poisoned Kafka producer that hid for two days) and both times fixed it with a bespoke per-service liveness indicator, which is correct for those two services and no coverage at all for the other 25 workloads. It also covers the #35 shape directly: a rollout stuck in `CrashLoopBackOff` for 95 minutes while the old pod kept serving.
- Acceptance Criteria: two alert rules in `argocd/apps/prometheus.yaml`'s `alerting_rules.yml` — a restart-rate alert (a workload restarting more than N times in a stated window) and a `CrashLoopBackOff`/`OOMKilled` alert keyed off `kube_pod_container_status_waiting_reason` / `last_terminated_reason` — with thresholds picked against this cluster's real observed restart history rather than a round number, and an explicit decision on whether Jobs/CronJob pods are excluded. Each with a runbook per the #22 rule and #117's CI check. Verified live the way this project verifies alerts: the expression queried against the real running Prometheus and confirmed to actually return `mimir`'s real restart series today, not just reasoned about from the metric name. Mimir's own repeated OOM is then triaged as this alert's first real subject — either its 768Mi limit is raised against a real measurement (the #84 method) or the restarts are accepted with a stated reason; not left unexplained now that something is watching.
- Dependencies: #92 (done).
- Priority: P1. Labels: `observability`, `platform`.

---

**126. Extend NetworkPolicies past #50's minimum list, starting with Kafka's unrestricted ingress**
- Purpose: #50 is Done and correctly so — every flow in its own stated minimum list is live, verified, and survived a genuinely hard upstream Cilium DNS-proxy bug that forced a `toFQDNs`→`toCIDR` rewrite. But the item's own title is "default-deny per namespace," and a live `kubectl get cnp -A` on 2026-08-11 shows the project's own `CiliumNetworkPolicy` objects in five namespaces (`api`, `clinvar`, `workers`, `alloy`, `prometheus`) out of 28 non-system ones — `argocd` is separately covered by seven core `NetworkPolicy` objects shipped by its own upstream install manifests, not authored here. Unenforced today: `aggregator`, `market-data-ingestor`, `news-ingestor`, `sentiment-analyzer`, `watchlist`, `kafka`, `grafana`, `loki`, `tempo`, `otel`, `pyroscope`, `visualizer`, `clinvar-viewer`, `beyla`, `mimir`, `vpa`, `keda`, `blackbox-exporter`, `traefik`, `argo-rollouts`, `cert-manager`. **`kafka` is the one that matters and should go first**: ADR 0012 records the broker as `PLAINTEXT, no auth`, it carries every event in the system, and while `api`/`workers` egress *to* it is constrained, its own ingress is not constrained at all — any pod in the cluster can read or write any topic. This costs no CPU (Cilium policies are eBPF datapath rules, not workloads) and the method is fully proven by #50's five batches, including the hard-won operational lessons (verify against a fresh disposable endpoint, `cilium-dbg endpoint list` to confirm `policy-enabled: both`, container ports not Service ports).
- Acceptance Criteria: `kafka` gets an ingress policy allowing exactly the real, observed client set (`api`, `workers`, `watchlist-service`, `aggregator`, `sentiment-analyzer`, `market-data-ingestor`, `news-ingestor`, plus the chart's own provisioning Job and the controller's internal listeners) derived from a live `hubble observe --namespace kafka` capture cross-checked against each service's real config, per #50's own established method — not guessed from the architecture doc. Then the four M13 application namespaces and `watchlist`, in batches, same method. Each batch verified with a real drop-monitor and real TCP connects at real Service ports, zero restarts, and `policy-enabled: both` confirmed via `cilium-dbg` (the #50/platform#161 lesson). Infrastructure namespaces (`grafana`, `loki`, `tempo`, `otel`, `pyroscope`, `traefik`, `cert-manager`, `argo-rollouts`, `keda`, `vpa`, `beyla`, `mimir`, `blackbox-exporter`) may be explicitly deferred with a stated reason rather than done in this item — but the deferral is written down, so "Done" never again means a fifth of the cluster. #50's own entry updated to say plainly how much of the namespace surface it actually covered.
- Dependencies: #49, #50 (both done).
- Priority: P1. Labels: `security`, `platform`.

---

**127. A component budget, and a decommission rule for concluded experiments**
- Purpose: between 2026-08-07 and 2026-08-11 this cluster gained `kube-state-metrics`, `node-exporter`, `blackbox-exporter`, `mimir`, `beyla`, `cilium`+`hubble` (relay, UI) and a `vpa` recommender — seven new always-on workloads in five days, on a node whose CPU requests sit at 84% and whose host runs 4.4Gi into swap. Several were individually justified; the aggregate is component collection, which is the exact pattern ADR 0021 and 0022 exist to catch and which PROJECT.md's own principles forbid ("no framework for a problem you don't have yet"). The evidence that it has become the default mode: Mimir and Beyla are concluded experiments whose own ADRs say they are not worth standing (`ADR 0038`: "not yet worth it as a standing piece of this cluster's real architecture"), together consuming ~1.5Gi of *real* memory, with Mimir OOM-restarting unwatched; VPA shipped before it could produce its own AC's output; and meanwhile #29 — `clinvar-service`'s golden-signal dashboard, a P1 from M5 — is still open, making it the only backend service with an SLO row and no dashboard. **This item does not propose removing Mimir or Beyla**: #120 records the owner's explicit, verbatim decision to keep both, and that decision stands untouched here. It proposes the *rule* that should have governed the additions after them.
- Acceptance Criteria: a short ADR (or an addendum to ADR 0022) stating a component budget in real terms — a stated ceiling on always-on workloads and/or on total CPU requests, checked against a live `kubectl describe node` before any new Application is merged, the same pre-flight discipline M13's own intro already applies per-service but applied to the decision to add at all. Plus a **standing decommission rule**: any component deployed as an experiment states its own conclusion criteria and its removal trigger *in its ADR at deploy time*, so "kept deployed as the completed experiment" is a decision with a date attached rather than a default. Existing experiment components (Mimir, Beyla, VPA, Pyroscope) get their conclusion criteria written retroactively — including the honest answer "keep indefinitely, owner decision" where that is the real answer. Checked by an addition to `CONTRIBUTING.md`'s PR checklist, matching #109's precedent.
- Dependencies: none.
- Priority: P1. Labels: `platform`, `architecture`, `documentation`.

---

**128. `sre-agent` v1 real run, plus the rebuild-aftermath bundles the corpus just gained**
- Purpose: `observability/sre-agent/` is real, CI-tested, and has **never been run against the real API** — the single most novel item in this backlog, blocked only on an owner-supplied key (ADR 0039, #66, same owner-only class as #99). The 2026-08-09 strategy review already argued the case had strengthened; it has strengthened again, and materially. When ADR 0039 scoped v1, the graded corpus was three Mimir bundles. Since then the project has produced: the Cilium transparent-DNS-proxy incident (two live rollbacks, one theoretically-sound fix that was re-tested and found still broken, a third false alarm caused by dialing a container port instead of a Service port — a genuinely hard diagnosis with a documented wrong turn), the `alloy`/`alertmanager` `policy-enabled: egress` finding (a policy that looked correct and wasn't enforced at all), #86's `LinkageError` class-poisoning root cause, and now the #122 rebuild aftermath — three simultaneous, differently-shaped failures behind four alerts, with the ground truth freshly written. That last one is the best evaluation case this project will ever build, because it is multi-cause and the human diagnosis is documented.
- Acceptance Criteria: the owner runs `harness.py` against the three existing bundles with a real key, and the output is graded by a human against each bundle's `reference_answer` — agreements, misses, and hallucinations all recorded verbatim, including any case where the agent was right for the wrong reason. Then at least three new bundles built from the incidents above (Cilium DNS proxy, the #122 rebuild aftermath, one of #85/#86's silent-but-Healthy crashes), each with a real `reference_answer` derived from the existing fact pack or backlog entry rather than written fresh. The write-up is the deliverable and is explicitly an article draft, not an internal note: "what my AI SRE caught, missed, and hallucinated about my own real incidents." v2 (live queries, standing service, #66's full AC) stays out of scope — it adds a workload to a node at 84%, and v1's grading is where the content is.
- Dependencies: #66/ADR 0039 (v1 built), #122 (supplies the best new bundle). Owner action required for the API key.
- Priority: P1. Labels: `observability`, `backend`, `documentation`.

---

**129. An article publishing cadence, with the next three targets named**
- Purpose: #119 made "publish article #1" a first-class item and it worked as far as producing a complete, publication-ready 2,000-word draft (`docs/articles/2026-08-09-mimir-three-bugs-and-a-fourth.md`) — and then stopped, because the item's own scope ends at one article and the last step is an owner action nobody scheduled. Objective 4 remains at zero published words after 24 days and three staff reviews all naming it as the binding gap. One article is not a reputation; a cadence is. The material for the next several is already written or is being generated faster than it is being published: the rebuild aftermath (#122/#123), the hardware-ceiling story (ADR 0040), the Cilium DNS-proxy incident (#50), the sre-agent grading (#128), and the SLO-over-time report (#94, due ~2026-09-06).
- Acceptance Criteria: #119's Mimir draft actually published, on a named platform, with the URL recorded in this backlog — that step alone, not blocked on anything else. Then a stated cadence (one article per N weeks, N chosen honestly against real available time) and the next **three** targets named in order with their evidence already in-repo, so no article ever starts from a blank page: the suggestion is (1) "I rebuilt my cluster from Git — here's what didn't come back" (#122/#123), (2) "My multi-node plan didn't survive `lscpu`" (ADR 0040, #48's superseded closure), (3) the sre-agent grading (#128). Each article links checkable in-repo evidence — the ADR, the backlog entry, the fact pack — rather than restating claims, matching #119's own bar. If #88 Phase 1's go/no-go ever lands go, articles gain live links; nothing waits on it.
- Dependencies: #119 (draft complete).
- Priority: P1. Labels: `documentation`.

---

## 6. Existing items to re-prioritize rather than duplicate

Three gaps this review found are already in the backlog and should be
re-prioritized with the new evidence attached, not re-filed under new
numbers:

1. **#42 (Kafka broker/topic availability alert): P2 → P1.** It was
   downgraded on 2026-07-31 as "defense in depth" against a shape this
   cluster's ephemeral storage didn't produce. §1b is that shape, in
   production, for 34 hours: a topic that does not exist, two consumers
   spinning on it, and no alert. #42's own AC ("fires within a reasonable
   window of a real outage, independent of whether `api`/`workers` are
   receiving traffic") is exactly the missing rule. The AC should now
   explicitly include *topic existence*, not just broker liveness.
2. **#29 (`clinvar-service` dashboard + invalidation alert): still P1, and
   now the oldest open standard-of-care violation in the project.** Live:
   12 dashboards in `grafana.yaml`, none for `clinvar-service`. It is the
   only backend service with an ADR 0020 SLO row and no dashboard, for the
   service the project itself calls its most defensible content. Worth
   noting for #109's checker: `clinvar-service` *is* mentioned in
   `grafana.yaml` (in comments), so the grace-period check passes on a
   false negative — a real, narrow bug in an otherwise working check.
3. **ADR 0020's SLO table still carries a `gateway` row** for a service
   deleted by ADR 0021/S1. Small, but it is the file #109's check treats as
   the live SLO registry. Fix in whatever PR next touches the table.

Also worth an explicit note, not an item: **#91's positive case is now
doubly blocked** — it needs a real `source="WEBSOCKET"` tick during US
market hours, and the websocket has been stale for the whole trading day
(§1d). #122's resolution of `MarketDataStaleFeed` is its unblocker.

---

## 7. Ranked sequence, with real costs

Ordered by differentiation-per-CPU, dependencies respected. CPU figures are
*additional steady-state requests on the node*, which is the only number
that matters at 84%.

| # | Work | CPU | Effort | Article it unlocks |
|---|---|---|---|---|
| 1 | **#122** close the live incident + fact pack | **0m** (one ~90s ingestion burst) | half a day | "I rebuilt my cluster from Git — here's what didn't come back" |
| 2 | **#123** post-rebuild acceptance checks | **0m** | half a day | same article's second half — the fix |
| 3 | **#129** publish the Mimir draft, name the next three | **0m** | ~2 hours | article #1, already written |
| 4 | **#125** restart/OOMKill alerting | **0m** (rules only) | half a day | "the alert I didn't have for the failure I couldn't see" |
| 5 | **#124** standing operations log, cycle 1 | **0m** | ~1h/cycle | the series' spine; feeds #94 and #128 |
| 6 | **#128** sre-agent v1 run + new bundles | **0m** (runs off-cluster) | a day + owner key | "what my AI SRE caught, missed, and hallucinated" |
| 7 | **#127** component budget + decommission rule | **negative** | half a day | the ADR itself is content |
| 8 | **#42** (reprioritized) Kafka topic-existence alert | **0m** | half a day | folds into #122's article |
| 9 | **#29** `clinvar-service` dashboard | **0m** | half a day | closes the oldest standard-of-care gap |
| 10 | **#126** NetworkPolicy coverage, `kafka` first | **0m** (eBPF, no workload) | 1–2 days | "default-deny, one namespace at a time — and the upstream bug that nearly stopped it" |
| 11 | **#94** SLO-over-time report (~2026-09-06) | **0m** | a writing day | still the most differentiated single article available |

Total added CPU across the entire recommended stretch: **zero**. That is
not a rhetorical flourish — it is the direct consequence of choosing
operational depth over technological depth under ADR 0040's ceiling, and it
is why this direction is available at all.

## 8. What not to do, and what I would cut

- **Do not add any always-on component this stretch.** Not Chaos Mesh
  (#64), not Kyverno (#58), not Kubecost (#65), not a Faro/exemplar
  extension that needs a collector. The node is at 84% CPU with memory
  limits already 105% overcommitted on a host in swap, and §3b is the
  evidence that "one more component" has become this project's default
  move rather than a considered one.
- **Cut Chaos Mesh (#64) from the near-term plan specifically.** It is the
  most tempting item on the list and the one I would drop first. This
  project already does chaos engineering better than most Chaos Mesh users
  — three fact packs that read as incident reports, with unplanned findings
  (selfHeal reverting the fault in 2 minutes; Kafka OOMing under backlog)
  that a declarative experiment runner would not have produced. Replacing
  hand-run chaos with a controller + daemonset + dashboard trades the
  differentiated asset for an undifferentiated one, and costs 200–400m
  that does not exist. Revisit if #128's sre-agent v2 ever genuinely needs
  a programmatic re-trigger — that is the only argument for it that holds.
- **Cut the VPA follow-through to its cheap half.** #101's own AC offers
  "a scheduled report reading `.status` directly" as an alternative to a
  `customResourceState` bridge. Take the cheap one; the expensive one is
  RBAC and config for a report nobody reads.
- **Do not start M12 or any new application service.** ADR 0031's gate is
  the project's own rule and is still not clear (#91, #94). §3c has the
  fuller reasoning.
- **Do not relitigate Mimir/Beyla removal.** #120 records an explicit owner
  decision verbatim. #127 proposes the forward-looking rule only. Mimir's
  OOM loop is a *fix it or accept it* question (#125), not a removal
  argument.
- **Do not respond to §1 by adding more alerts.** Coverage is 19/19 with
  19/19 runbooks. The one genuine coverage gap is the restart class (#125);
  everything else in §1 was detected correctly and on time. Adding signal
  to a system whose signal went unread for 33 hours is the wrong reflex.
- **Do not fix the three §1 root causes quietly.** The write-up is worth
  more than the fixes, and it is perishable — the firing alerts, the empty
  refdata directory, the hot-looping consumers all disappear the moment the
  work is done. Capture first (#89's own standing step), then fix.

## 9. The appeal test

The 2026-08-09 review established this section as a standing check, on the
owner's own stated constraint that the project must remain genuinely
interesting to work on. A plan that reads as "stop building, go do chores"
would fail it regardless of being correct. Checked deliberately:

- **The most novel thing in the backlog moves up, not down.** #128 puts the
  sre-agent third-from-top and gives it a corpus twice the size ADR 0039
  scoped it against — including a genuinely hard multi-cause incident with
  documented wrong turns, which is a much more interesting thing to grade
  an agent on than three configuration bugs.
- **The headline work is an incident, not a chore.** #122 is a live,
  three-root-cause, 33-hour production incident found by an independent
  review of a running system. That is the most interesting single day of
  work available to this project right now, and it exists only because the
  cluster was rebuilt from scratch a day and a half ago — which was itself
  the highest-stakes thing the project has ever deliberately done.
- **Publishing is the loop-closer.** Three reviews have now said objective 4
  is the binding gap; the draft is finished and sitting in the repo. Getting
  a real URL is the single most motivating thing on this list and takes two
  hours.
- **NetworkPolicy work (#126) is genuinely interesting**, not hygiene — it
  continues a track that has already produced a real upstream Cilium bug, a
  `toFQDNs`→`toCIDR` workaround with real ARIN/RDAP verification, and a
  policy-enforcement footgun found by `cilium-dbg`. Kafka's unrestricted
  ingress is a real security finding, not a checkbox.
- **What is honestly lost**: the pleasure of installing something new. That
  is a real cost and this review is deliberately imposing it, because §3b's
  evidence is that it has been the project's default for a week and it is
  the one activity that moves none of the four objectives while consuming
  the CPU that constrains all of them.

---

## 10. Review of this review (2026-08-11, before merge)

Every load-bearing claim in §1 was read directly off the live cluster
during this review, and every claim about the repos was checked against the
files rather than inherited from the briefing. Findings from that pass,
including corrections to this review's own working assumptions:

1. **The "multi-month operational history" premise is false and was
   dropped.** The briefing for this review suggested real multi-month
   history as a candidate differentiator. `git log --reverse` across all
   four repos returns a first commit of **2026-07-18** — the project is
   **24 days old**, with 492 commits and 380 merged PRs. That is an
   extraordinary build rate and it is *not* operational tenure. §3a is
   written accordingly: tenure is the thing the project does not yet have,
   which is exactly why §2 recommends starting to accumulate it rather than
   claiming it. #94's SLO-over-time report, due ~2026-09-06, will be the
   first artifact that legitimately makes a duration claim.
2. **Prometheus history really did survive the rebuild — checked, not
   assumed.** Queried `count(up)` at 1/2/3/4/5/6/7/10/14-day offsets
   against the live instance: 36/32/32/31/21/21/21/0/0. Real data back
   ~7–9 days, nothing at 10. #94's 30-day clock (from 2026-08-07) is intact.
   This was checked specifically because §1's other findings made the
   restore look worse than it was, and it would have been easy — and wrong
   — to let that colour the retention claim.
3. **The `#50` critique was softened after re-reading the item.** The first
   draft of §4b.4 read as "#50 was closed prematurely." Re-reading the full
   entry, every flow in its own stated minimum list is genuinely live and
   verified, through a real upstream bug and three emergency rollbacks. The
   finding is not that the item was closed wrongly; it is that its *title*
   ("default-deny per namespace") describes a state the cluster is not in,
   at 5 of 28 non-system namespaces. That is a documentation-accuracy finding, and
   #126 is framed as continuation rather than correction.
4. **One claim this review wanted to make does not survive checking.** An
   earlier draft said the four §1 alerts prove the ntfy notification path
   had regressed. It hasn't:
   `alertmanager_notifications_failed_total{integration="webhook",...}` is
   `0` across every reason and `alertmanager_notifications_total` is `189`.
   The delivery layer is provably fine, which makes the finding stronger,
   not weaker — the alerts were delivered and not acted on. Corrected
   before it reached §1.
5. **The `clinvar-service` refdata claim was verified two ways** rather
   than inferred from a stack trace: the trace shows `FileNotFoundError` on
   `/data/clinvar/current/clinvar.vcf.gz`, and a direct `ls -la` plus
   `du -sh` on the live PVC shows the directory empty at 4.0K with an
   `Aug 10 08:59` mtime. Both were needed, because the trace alone is also
   consistent with a path/symlink bug, which would be a different item.
6. **What this review looked for and did not find**: any *new* security
   exposure of the #107 class (a stated protection defeated by the
   repository) — the cross-repo sweep #107 performed still holds, and #88
   remains descoped so there is no public surface at all. No secret material
   was read at any point during the live inspection; the one place it would
   have been needed (verifying `clinvar_variant_index`'s row count directly)
   was skipped in favour of the stack trace, which already proves the index
   is populated because the code reached the VCF-open step with real
   candidate coordinates in hand.
7. **The one thing this review could not check.** Whether the owner
   actually received the 189 ntfy notifications on a real device, or
   whether they were delivered to a topic nobody is subscribed to. That is
   an owner-only observation and it materially changes #122's story —
   "delivered and ignored" and "delivered into a void" are different
   findings with different fixes. Stated as a real gap rather than assumed,
   per this project's own norm, and #122's AC asks for the answer.
