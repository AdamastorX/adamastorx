# Full independent audit: what got fixed, what's still hiding, and the hardware call — 2026-08-21

Fifth in the review series (`2026-08-06-staff-engineer-review.md`,
`2026-08-09-staff-engineer-review.md`,
`2026-08-09-hardware-constrained-strategy.md`,
`2026-08-11-staff-review-differentiation-and-article-strategy.md`,
`2026-08-15-operate-followthrough-and-m12-reality.md`). The prior four
audited what was built, decided the project's direction under a hardware
ceiling, framed "build rate has outrun operate rate," and found the
discipline items repeatedly deferred. This one is a full independent pass
across ten owner-set questions: technical debt (especially the untracked
kind), observability quality, decommission candidates, implementation
practices, focus, workflow, AI/Claude-Code leverage, strengths/weaknesses,
and the hardware decision.

**Method.** This review holds itself to the project's own bar — "verify
live, don't assume." Every load-bearing claim below was read off the
running cluster, the live Prometheus API, or the real repos during this
review, not inherited from the briefing or the backlog's own prose.
Read-only throughout: no `apply`, `patch`, `delete`, `scale`, or sync.
Investigation was delegated to sub-agents for four bounded gathering tasks
(full-backlog status sweep, ADR topic index, a live observability audit,
and a code-quality spot-check); every sub-agent finding relied on below was
independently spot-checked against the live cluster before being trusted,
and the judgments, verdicts, and recommendations are this reviewer's own.
Cluster access: `KUBECONFIG=platform/terraform/kubeconfig`, node
`lmpeixoto-thinkpad-t460s` (i7-6600U, k3s v1.36.3, 11 days since the #49
rebuild).

---

## 1. What changed since 2026-08-15: the discipline batch actually got done

The single most important finding is a positive one, and it directly
answers the 2026-08-15 review's central criticism. That review's one-line
recommendation was: *"Do the four zero-CPU discipline items (#125, #123,
#124, #127) as a single deliberate batch before any more bug-hunting or
building."* Checked live, the batch was substantially executed:

| Item | 2026-08-15 status | 2026-08-21 status (verified) |
|---|---|---|
| **#125** restart/OOM alerts | 0 of 20 rules matched restart/OOM | **Done** — 2 rules live (`WorkloadRestartingFrequently`, `ContainerCrashLoopOrOOMKilled`), firing correctly on the real OOM class |
| **#123** post-rebuild acceptance checklist | open | **Done** — six real assertions in `flannel-restore.md`, all walked live PASS |
| **#124** standing operations log | open; `docs/operations/` did not exist | **Done** — two real cycles in `docs/operations/`; cycle 2 found #140 in the act of sweeping |
| **#91** pipeline freshness SLO | found stale | **Done** — corrected live, positive case proven |
| **#137** SLO threshold calibration | placeholder 1000ms | **Preliminary** — 500ms, ADR 0020 addendum, honestly marked pending #94 |
| **#136** canary drills | not started | drill 1 (clean, 3m00s) + drill 2 (abort, 3m01s), both 2026-08-16, matching the #46 baseline |
| **#98** Renovate | (not yet flagged) | **Done** — a real config bug fixed (was silently scanning zero repos); real digest PRs now merging (services#76/#77) |
| **#100** SOPS | (not yet flagged) | **Done** — a real DR gap fixed (stale encrypted recovery copy re-encrypted) |
| **#126** NetworkPolicy past 5 ns | 5 of ~28 namespaces | **kafka batch Done** live; M13/watchlist batches still open |

This is a real reversal of the pattern the last three reviews named. When
the owner set aside a stretch for the unglamorous work, it got done, with
the same live-verification rigor the project applies to bugs. That deserves
to be said plainly before the criticism starts: **the operate-gap the last
review called "structural" has visibly narrowed.**

The counterweight, equally real: the two highest-leverage items remain
owner-gated and unmoved — **#128** (sre-agent v1 real run, needs an API
key) and **#129** (publish anything). Zero articles are published after
five reviews and ~28 days; three drafts exist (§7).

## 2. Verdict

**The system is healthy and well-built; the operating discipline has
genuinely improved; and the remaining debt is now concentrated in three
places the project's own tooling can't see — security posture, its own
observability blind spots, and its record-keeping hygiene.** The live
cluster is clean by every structural measure: 48 ArgoCD Applications, 47
`Synced/Healthy` and one `Progressing`, across 33 namespaces; CPU requests
at 79% (down from 86% — the #120 re-trim landed); application code that
holds up to a real read. The project passes its own honesty bar: the "Done"
markers I sampled map to real live state.

But an audit's job is to find what isn't tracked, and three things aren't:

1. **No `securityContext` on any of the 12 application workloads** (§6) —
   every app pod runs as root with default Linux capabilities, on a project
   otherwise disciplined enough to run default-deny CiliumNetworkPolicies.
2. **The observability stack cannot see its own backends** (§4) — Prometheus
   scrapes zero self-metrics from Mimir, Loki, Tempo, or Pyroscope, and the
   one component that is actively failing (Mimir, 70 restarts) is also
   Prometheus's own long-term-storage target with no failure alert.
3. **The record is drifting quietly** — five ADR status headers are stale,
   ~30 backlog items are complete-but-unmarked, and the doc-drift automation
   (#97) that was built to catch exactly this class doesn't validate either
   surface.

None is an emergency. All three are the kind of debt that compounds silently
because nothing fires when it grows — which is precisely why an audit has to
name them.

## 3. Technical debt and problems: a prioritized inventory

The tracked items are in `backlog.md`; the real value is what isn't. Ordered
by severity × how-hidden-it-is.

### 3.1 Untracked (not in the backlog as of #141)

- **[HIGH] No pod/container `securityContext` on any application workload.**
  Verified live: `securityContext` appears in exactly three manifests, all
  postgres-backup CronJobs. All 12 app Deployments/Rollouts (`api`, `workers`,
  `aggregator`, `clinvar-service`, the four M13 Java services, `watchlist-service`,
  the two static frontends, `workload-generator`, `mimir`) have none —
  `kubectl get pod -n api -o jsonpath='{...securityContext}'` returns `{}`.
  No `runAsNonRoot`, no `readOnlyRootFilesystem`, no `capabilities.drop:[ALL]`,
  no `seccompProfile`. The third-party Bitnami Postgres pods *are* hardened
  (the chart does it), which makes the gap the project's own hand-written
  manifests. This is the single most concrete unaddressed risk and it has no
  backlog item.

- **[HIGH] The `ContainerCrashLoopOrOOMKilled` alert generates stale critical
  pages.** Its OOM arm is `kube_pod_container_status_last_terminated_exitcode
  == 137` with no recency bound. That series stays `137` until the pod is
  recreated, so a single one-off OOM fires `severity: critical` indefinitely.
  Verified live *right now*: three instances firing — `mimir` (70 restarts,
  a true chronic positive) but also `prometheus-server` and `beyla` (**1
  lifetime restart each, OOMed once on 2026-08-18, healthy since**). **Two of
  three currently-firing criticals are stale noise.** The alert is three days
  old and already crying wolf on a critical channel. Fix is small (gate the
  OOM arm on `and increase(kube_pod_container_status_restarts_total[15m]) > 0`
  or a `last_terminated_timestamp` recency window) but it needs an item.

- **[HIGH] The observability stack has no visibility into its own backends.**
  Zero self-metrics scraped from Mimir/Loki/Tempo/Pyroscope (`count(cortex_*)`,
  `count(loki_*)`, `count(tempo_*)` all return 0 series live). No
  Prometheus→Mimir remote-write-failure alert. Mimir is both the chronic-OOM
  offender and the long-term-storage target: if it dies mid-compaction, #94's
  30-day retention story degrades silently and nothing pages. See §4/§5.

- **[MED] The `beyla-vs-manual` dashboard is broken.** Every Beyla-side panel
  queries `job="api/api"`, `job="aggregator/aggregator"`, `job="workers/workers"`.
  Verified live: Beyla emits everything under `job="beyla"` (101 series), with
  service identity in `service_name`/`k8s_deployment_name`. The `job="<ns>/<svc>"`
  selector matches nothing — 3 of 5 panels are blank. The dashboard's entire
  reason to exist (the A/B comparison that is Beyla's stated justification,
  ADR 0036) does not render. Doubly relevant because that comparison is the
  article that's supposed to redeem Beyla's ~800Mi footprint (§5).

- **[MED] Five ADR status headers are stale.** Verified by reading the headers:
  `0010` and `0011` still say `Status: Accepted` though both are superseded in
  the body (by 0021 and 0032 respectively); `0021`, `0022`, `0023`, `0025`,
  `0029` still say `Status: Proposed` though every one is enacted and treated
  as settled fact by later Accepted ADRs (e.g. 0040 executes 0023; 0026
  references 0029's `watchlist-service` as built). The README's own
  `Status: Superseded by NNNN` convention is violated by 0010/0011.

- **[MED] ~30 backlog items are complete-but-unmarked, and #97 doesn't catch
  it.** All of M0–M3 and much of M4–M6 carry no status marker despite being
  clearly shipped (e.g. #21a is called "(done)" inside #45's own dependency
  line but is unmarked in its own entry; S1/S2 "remove gateway/whoami" are
  open despite PROJECT.md and the live cluster both confirming the namespaces
  are gone). The doc-drift automation (#97/#109) guards `overview.md` and
  `grafana.yaml` roster drift but does not validate that a backlog item's own
  status marker is consistent with its cross-references — the exact gap
  visible here. The failure mode is benign (done work unmarked, not the
  reverse), but it makes the backlog's own "what's left" unreadable without
  cross-referencing.

- **[LOW] A stray editor swap file is committed-adjacent.**
  `docs/articles/.2026-08-15-...swp` sits untracked in a non-gitignored
  directory alongside two untracked article drafts — a hygiene smell, and a
  swap file is one `git add .` away from being committed.

- **[LOW] `messageBuffer` is not reset on websocket reconnect** in
  `market-data-ingestor`'s `FinnhubWebSocketClient` (§6) — a partial frame
  from a dead socket corrupts the next connection's first message. One lost,
  self-recovering message per reconnect. Real but minor.

- **[LOW] Terraform state is local with a `.tfstate.bak-before-fix` on disk**
  (§6) — evidence of past manual state surgery; single-operator-acceptable
  but a fragility indicator.

### 3.2 Tracked and genuinely open (the ones that matter)

- **#29 (P1, open since M5): `clinvar-service` still has no dashboard.**
  Verified: 12 live dashboards, none for `clinvar-service` — the only backend
  with an ADR 0020 SLO row and no golden-signals dashboard, while every newer
  M13 service got one. This has now been flagged in every review since
  2026-08-11 and is still open. The project's self-described "single most
  defensible portfolio content" is its least-instrumented backend.
- **#133 (P1, open): market-data watchdog can't distinguish "connected" from
  "receiving trades."** A real ~29h silent data gap already occurred; a human
  had to notice. Genuine reliability gap.
- **#126 (in progress): NetworkPolicy still incomplete.** kafka ingress
  batch done live; the four M13 app namespaces and `watchlist` still run
  without their own default-deny batches.
- **#127 (open): the component budget/decommission rule.** The mechanism that
  would force a decision on Mimir/Beyla (§5) is itself unbuilt.
- **Owner-gated: #128 (sre-agent run), #129 (publish), #88 (public access
  go/no-go), #99 (off-node backup credential).**

### 3.3 Blocked (correctly labeled, all hardware/capacity)

#51/#52 (multi-node, permanent on this hardware), #69 (Nextflow real-pipeline
compute, the genuine permanent block), #67/#68 (M12 metadata-service/MinIO,
capacity + ADR 0031 gate, non-permanent). The 2026-08-15 review's correction
— that M12's block is single-node *capacity/physics*, not node count — stands
and I agree with it. Worth confirming the correction actually landed in the
`#67`–`#69` dependency text; if it hasn't, that's another instance of §3.1's
record-drift.

## 4. Observability quality: is it actually good?

**Assessed live** — every alert expr and a sample of dashboard panels were
executed against the running Prometheus, not read from YAML. Net: **the alert
*logic* is genuinely good and evidence-calibrated; the gaps are structural.**

### What's genuinely good (verified)

- **23 alert rules, 24 runbook files (1:1 coverage + README), CI-enforced
  (#117).** The "never ship an alert without a runbook" standard holds
  literally, not just in spirit.
- **Every alert references a metric that exists live.** No alert would "never
  fire" from a typo'd or absent metric; healthy-state zeros
  (`watchlist_delivery_dlq_depth`, `market_data_stale_feed`, consumer lag) are
  correctly latent, not missing.
- **The #125 OOM-reason workaround is real and correct.** Confirmed live: all
  three OOMed containers report `last_terminated_reason="Error"`, never
  `"OOMKilled"` — a `reason="OOMKilled"` rule would fire on none of them. The
  exit-code-137 keying is the right call and it works. `WorkloadRestartingFrequently`
  (`increase(...[1h]) > 3`) is well-calibrated against mimir's real ~0.3/h
  background and correctly inactive now (all pods 0/h). This is careful work.
- **The M13 pipeline-freshness SLO (#91) is correct.** `AggregatorPriceFreshnessSlow`
  filters `histogram_quantile(0.95, ...aggregator_price_freshness_seconds_bucket
  {source="WEBSOCKET"}...) > 30`. Verified both `WEBSOCKET` and `POLL_FALLBACK`
  series exist live — so the ADR 0020 trap (blending them would inject a false
  30-min lag) is real, and the `source="WEBSOCKET"` filter genuinely avoids it.
  Live p95 0.167s vs a 30s threshold: measures exactly what it claims.
- **The 500ms api p95 recalibration (#137) is reasonable and honestly
  labeled.** Live p95 = 0.155–0.174s; 500ms is ~3× that, ~2× the clean-window
  p99 the ADR cites — generous but defensible, and marked preliminary pending
  #94's real 30-day window (~2026-09-06). Good discipline.

### The real gaps (verified)

- **Zero recording rules → no error budget or burn rate is computed
  anywhere.** Verified: `/api/v1/rules` returns 23 alerting rules and **0
  recording rules**. Every "SLO alert" is a single static threshold
  (`ApiHighErrorRate > 0.05`), not a multi-window burn-rate alert. The SLO
  *table* exists (ADR 0020) but no error budget is measured. This is partly
  by design — ADR 0021/0031/0043 deliberately kept #21b's burn-rate policy
  closed for self-generated traffic, and I agree that multi-window burn-rate
  on workload-generator traffic would be theatre. But "no burn-rate policy"
  and "no error budget computed at all" are different decisions; only the
  first was made deliberately. The SLO layer is currently a document, not a
  measurement.
- **No steady-state latency alert.** The recalibrated 500ms exists only as a
  canary gate in `analysistemplate.yaml`. A slow-but-not-erroring `api` in
  normal operation would not page. Given traffic is 0.4 req/s (workload-generator
  only), the histogram is thin — but the gap is real.
- **The backends are a blind spot** (§3.1, §5). No self-metrics from
  Mimir/Loki/Tempo/Pyroscope; no remote-write-failure alert on the Mimir path.
- **Idle telemetry:** Kafka broker JMX (411 `kafka_*` series scraped) has no
  dashboard and no broker-health alert — under-replication, ISR shrink, and
  offline partitions are all invisible; VPA recommender is scraped and consumed
  by nothing; Beyla's 101 series are consumed only by a broken dashboard.
- **Dead/dark dashboards:** `beyla-vs-manual` broken (§3.1); `frontend-rum`
  (Faro) likely carries no data (Loki empty for `{job="faro"}` over 24h — the
  receiver runs, no beacons land); `clinvar-service` has none (#29).

**Verdict on the owner's question:** the alerts are good — better-designed
and more honestly calibrated than most homelabs and many production shops.
The SLOs are half-built (defined, not measured). The dashboards are good for
the live app services and broken/absent exactly where the experiments and the
flagship older service are. The highest-value observability work is not more
signals — it's making the ones that exist consumable (#29 clinvar dashboard,
fix or retire `beyla-vs-manual`, a Mimir/remote-write health alert) and
fixing the one alert that's already crying wolf.

## 5. Decommission candidates: form an independent view

**Mimir — decommission, and my independent read is that the case is now
materially stronger than when the owner last overrode it.** The standing
override (#120/#135: "keep testing") was a legitimate call. But the evidence
has moved since:

- **The cost is accelerating, not stable.** Restarts across the review series:
  11 → 24 → 29 → **70** (verified live; exit 137, ~6h OOM cycle, on a 768Mi
  limit). This is not a static experiment sitting quietly.
- **ADR 0038's own verdict is already "not yet worth it as a standing piece."**
  The write-up — the actual deliverable — is complete and committed
  (`docs/articles/2026-08-09-mimir-three-bugs-and-a-fourth.md`). The artifact
  is the article and the ADR; the running pod is rent.
- **It is now actively polluting a real alert.** Mimir's chronic OOM is one of
  the reasons the new #125 critical alert fires, and its sticky-gauge behavior
  (§3.1) means the noise is structural, not incidental.
- **It's unmonitored (§4)** and it's Prometheus's own long-term-storage target
  — the worst combination: a component that can silently break the retention
  story is the one component with no health signal.
- **The one stated reason to keep it (#135) has inverted.** #135 ties Mimir's
  decommission to #128's grading corpus no longer needing Mimir-sourced
  bundles. But 70 recorded OOM events is a *saturated* corpus, not a scarce
  one — keeping Mimir running generates identical incidents, not new grading
  material. The corpus argument now argues *for* decommission.

I respect that this is the owner's standing decision and I'm not overriding
it. My recommendation is narrower and evidence-based: **either decommission
per ADR 0038's already-written rollback path, or re-tie #135's trigger to a
near-term calendar date instead of the indefinite #128 dependency** — because
"keep until #128 no longer needs it" has quietly become "keep indefinitely,"
which #127's own AC exists to prevent.

**Beyla — second candidate, harvest-then-remove.** ~800Mi (the heaviest idle
tenant after Prometheus/Kafka), broad `SYS_ADMIN`/`hostPID` privilege, and —
the new finding — the A/B dashboard that is its entire justification **is
broken** (§3.1, §4). The comparison it's supposed to enable literally doesn't
render. Either fix the dashboard, write the A/B article from the metrics that
do exist (`job="beyla"`), and *then* decommission — or decommission now and
write it from the captured evidence. Keeping it as-is is paying 800Mi for a
comparison nobody can see.

**Faro/frontend-rum — third, minor.** Carries no data (§4); the receiver runs
for nothing. Cheap (rides Alloy), so low priority, but it is decorative and
should be in #127's ledger as "remove or feed."

**Not decommission:** Pyroscope (69Mi, genuinely cheap, real SDK injection);
Cilium, Rollouts, KEDA, the M13 pipeline (all exercised for real). The
consolidation call is unchanged from 2026-08-15 and I concur: extract the
article-shaped depth from the experiments, then reclaim the two heaviest.

## 6. Implementation practices: is the code well-built?

**Spot-checked against real files, not the backlog's self-report. Verdict:
strong-to-excellent application code; adequate-with-one-systemic-gap
infrastructure.**

**Application layer (Java + Python + Kafka Streams) — strong.** Findings I
consider load-bearing:

- **The outbox+relay pattern (ADR 0026) is correctly implemented, including
  the hard parts.** Idempotency is at the DB level — `INSERT ... ON CONFLICT
  (subscription_id, release_id, variant_key) DO NOTHING` against a UNIQUE
  constraint (`DeliveryJpaRepository`), so a Kafka redelivery gets 0 rows, not
  a duplicate notification. Ack-after-durability is wired correctly
  (`MANUAL_IMMEDIATE`, ack only after the `@Transactional` commit). The relay
  claim is a single atomic `UPDATE ... WHERE status=PENDING`. This is the
  textbook-correct mechanism, not a best-effort dedupe.
- **The `@Transactional` self-invocation trap was hit live and fixed — then
  applied proactively.** `NotificationRelay` uses programmatic `TransactionTemplate`
  because `@Transactional` on a `this.`-called private method silently bypasses
  the proxy; the same fix was pre-applied to `api`'s `OutboxRelay` before it
  bit there. Real subtle-bug learning, correctly generalized.
- **The 500→409 subscription-delete fix (this session) is real with a real
  test** — the integration test creates a delivery through the real resolution
  service, asserts 409, and asserts the subscription survives, on Testcontainers
  Postgres + EmbeddedKafka.
- **The Kafka Streams `aggregator` (the most complex service) holds up** —
  immutable-record aggregates (no shared-mutation footgun), correct
  floored-window IQ reads with `InvalidStateStoreException` fallback, and the
  right decision to *not* KTable-join two differently-partitioned topics.
- **The `market-data-ingestor` self-heal is sound engineering, not a
  band-aid** — capped exponential backoff (5-min ceiling), an HTTP-429 penalty
  jump added after a real self-perpetuating lockout, a stale-data forced
  reconnect with a cooldown to prevent storms, and a `KafkaProducerLivenessHealthIndicator`
  that surfaces a wedged producer as an unready pod. The 34 live restarts
  reflect an unreliable free-tier upstream handled correctly. My earlier
  instinct to call it a band-aid was wrong on reading the code — but the 34
  unwatched restarts are exactly why #125's alert matters.
- **Cross-cutting hygiene is exemplary:** zero `TODO`/`FIXME`/`HACK` markers
  across `services/` and `platform/` (deferred work is prose with ADR/backlog
  refs and explicit "accepted v1 gap" framing), no swallowed exceptions in
  production code, dependency versions pinned with `==` and kept in lockstep,
  and consistent (cited, not copy-pasted) patterns across services.

**Infrastructure layer — adequate, one systemic gap:**

- **The `securityContext` gap (§3.1) is the one concerning systemic finding**
  — glaring precisely because everything around it is disciplined.
- Terraform: pragmatic single-`null_resource` k3s provisioning, no secrets
  leaked (`.tfstate*`/`kubeconfig` gitignored, verified), local state and a
  `.bak-before-fix` as the fragility markers.
- Manifests otherwise solid: probes correctly scoped (`tcpSocket` confined to
  the two static nginx frontends, real `httpGet` health groups on backends),
  resources right-sized against real `kubectl top` data, secrets via
  `secretKeyRef`, app images pinned by commit SHA. `replicas: 1` everywhere is
  a documented lab-scale choice, not an oversight (but means no PDBs and every
  service is an SPOF).

The self-reported "Done" quality is, for the application code, real. I went
looking for shortcuts and found very few.

## 7. Focus vs. dissipation: is effort concentrated well?

**Concentrated well on building; dissipating at the finish line.** The
positive: M13 and most of M15 are genuinely closed, M16 is narrowly scoped
(zero new components, ADR 0043) and its open items are cleanly gated on a
real calendar (#94, ~2026-09-06). There is no sprawl of half-built services —
the ADR 0031 gate held, and this session's work was a coherent discipline
batch (§1), not scattered new surface. That is real focus, and better than
the 2026-08-11 review's "least differentiated week" worry.

The dissipation is at the last mile, and it's the same shape four reviews
have named: **the two highest-leverage items are owner-gated and stalled
while zero-risk activity fills the time.** Concrete evidence:

- **Publishing:** three article drafts exist (`mimir-three-bugs` committed;
  `the-alerts-worked-i-didnt-for-33-hours` and `the-org-chart-i-wrote-and-didnt-follow`
  both **untracked** — not even committed), **zero published**. The 33-hour
  incident draft is, by the 2026-08-11 review's own reckoning and mine, among
  the best material the project will ever have, sitting uncommitted on disk.
- **The sre-agent (#128)** — the single most novel item in the backlog, v1
  built and tested, has never had a real run (needs an owner API key).

So the honest framing: effort is well-concentrated on the engineering and
the operating discipline, and poorly concentrated on converting either into
the reputation that is objective 4. That conversion is owner work, not
engineering work — which is exactly why more engineering won't fix it.

## 8. Workflow and process: is the loop actually working?

**Yes, and the discipline is real.** Verified against practice, not just
`WORKFLOW.md`: every change since 2026-08-15 went through a branch → PR →
merge cycle (17 merged PRs in `adamastorx`, 13 in `platform`, small and
single-concern), CI enforces a `backlog-structure` check and runbook-coverage
(#117), and the persona agent files are clean — concise, label-mapped, with
correctly scoped tools (the `architect` persona has no Bash/Edit and literally
cannot write production code; `documentation-engineer` has no Bash). The
branch/PR/human-review rule is followed even for solo work. This is a genuinely
functional engineering loop for a single operator.

Two process observations:

- **The `root`-refresh ArgoCD gremlin is a recurring tax** (documented live in
  `SESSION_STATE.md`): the app-of-apps `root` doesn't always detect a child
  Application's spec diff, so a child hard-refresh confirms stale state.
  Bit both the #125 and #126 work this session. It's documented, not solved —
  and it's the kind of recurring operational friction a hook or a small script
  could eliminate (§9).
- **A PR has been open and stale for 11 days** (`adamastorx#242`, "bake api's
  Pyroscope agent jar," CI green, orphaned). Minor, but the project's own
  "open a PR and it moves" flow has one rotting exception; close or merge it.

What I'd change is small: (a) add a CI check that a backlog item's status
marker is consistent with its cross-references (closes §3.1's record-drift at
the source, extends #97's own remit); (b) close the stale PR. The loop itself
doesn't need changing.

## 9. AI / Claude Code leverage: the genuinely underused surface

This project is built almost entirely through Claude Code sessions, and it
uses **exactly one** of Claude Code's capabilities: sub-agent delegation via
persona files. Verified across all four repos: `.claude/` contains only
`PROJECT.md`, `WORKFLOW.md`, and five persona agents. **No hooks, no
`settings.json`, no skills, no MCP servers, no `.mcp.json`, no project-level
memory beyond the docs.** The persona model is good — but it's the floor of
what's available, and the project's own documented pain points map almost
one-to-one onto the features it isn't using:

- **Hooks (the biggest miss).** `WORKFLOW.md`'s hard safety rule ("never
  `kubectl apply/patch/delete` outside read-only inspection without explicit
  confirmation") is currently prose the model is trusted to honor. A
  `PreToolUse` hook could *enforce* it — deny-list mutating `kubectl`/`terraform`
  verbs unless a confirmation token is present. A `SessionStart` hook could
  export `KUBECONFIG` (a documented every-session footgun that "does not
  persist and is blocked from `~/.bashrc`") and surface the current gremlin
  list. A `PostToolUse`/`Stop` hook could run `check_backlog_structure.py`
  and the roster-drift check automatically. The doc-drift automation (#97,
  which the backlog notes "failed twice") is fundamentally a hook/CI problem,
  and the backlog-status-marker gap (§3.1) is a five-line hook.
- **Skills.** The project has a growing library of exact, repeatable procedures
  that currently live as runbook prose the model re-reads each time: the canary
  drill cadence (#136 — literally a recurring, scripted procedure), the
  post-rebuild acceptance checklist (#123), the "verify live before marking
  Done" discipline, the flannel-restore path. Each is a natural Skill — a named,
  loadable procedure that encodes the steps *and* the known gotchas (the
  Cilium `toPorts`-uses-container-port trap, the `root`-refresh-first rule)
  so they're applied consistently instead of rediscovered.
- **MCP.** The observability audits in this review series repeatedly reach
  Prometheus via `kubectl exec ... wget`. A Prometheus MCP server (or a thin
  kubectl/Grafana one) would make live-querying a first-class, structured tool
  instead of a shell incantation — directly relevant since "verify live" is
  the project's core value and every review does it by hand.
- **Memory / background tasks.** `SESSION_STATE.md`'s recurring-gotcha log is
  effectively a hand-maintained memory file; the Boot-4-autoconfig and
  Cilium-DNS-proxy traps are exactly what auto-memory is for. And the drDR
  drills / long-running ingestions are natural background-task candidates.

Concretely, the three I'd build first, in order: (1) a `PreToolUse` safety
hook enforcing the GitOps mutation rule (turns a trust-based safety story
into a real one — itself article-worthy); (2) a `SessionStart` hook for
`KUBECONFIG` + gremlin surfacing (removes a per-session footgun); (3) a
"canary-drill" and a "verify-live-Done" Skill (encode the two most-repeated
procedures). This isn't generic AI-productivity advice — each item removes a
specific, documented friction this project hits repeatedly. That the whole
platform is AI-built and AI-operated, with the safety rails themselves
AI-enforced, is also the freshest unpublished article angle it owns (see the
final response, not this file).

## 10. Strengths and weaknesses (honest, not balanced-for-balance)

**Strengths (real):**

1. **The engineering culture is the product, and it's genuine.** "Re-test the
   fix live because it compiled is not proof," decision-reversals recorded not
   hidden (18 of 43 ADRs carry supersession/correction language), gaps reported
   honestly (`market-data-ingestor`'s injected-vs-organic data caveat, the
   #21e alert-limitation admission). This is rare and it holds up to a hostile
   read.
2. **The application code is genuinely well-built** (§6) — correct outbox
   idempotency, correct Streams state handling, real tests, zero TODO debt.
3. **The operating discipline improved this session** (§1) — the last review's
   central criticism was actioned.
4. **The measured-constraint narrative** (ADR 0040/0041) — deciding under a
   ceiling you actually measured, and killing a planned milestone honestly, is
   differentiated content most homelabs can't produce.
5. **Observability alert design is careful and evidence-calibrated** (§4).

**Weaknesses (real):**

1. **Zero published output after five reviews** — the reputation objective is
   entirely bottlenecked on an owner action nobody has taken, and the best
   drafts are uncommitted.
2. **Security posture is the blind spot** — no `securityContext` anywhere,
   PLAINTEXT in-cluster traffic (mesh deferred), an unrestricted-ingress
   remnant until #126 finishes. For an SRE portfolio, this is the most
   glaring hole.
3. **The observability stack can't see itself** (§4) — and the one failing
   component is the unmonitored one.
4. **Record-keeping is drifting** (§3.1) — stale ADR headers, unmarked backlog
   items, and the automation built to prevent this doesn't cover it.
5. **The AI toolchain is underused** (§9) — the project models platform
   discipline while using ~20% of its own primary tool's capability.
6. **Mimir is a standing cost with an inverted justification** (§5).

## 11. The hardware decision

The owner has new hardware and is deciding whether to migrate off the T460s
or keep "old laptop" as narrative. **My recommendation: migrate the live
platform to the new hardware, run the migration itself as a first-class fact
pack, and keep the T460s constraint as *documented history*, not as the live
host.** Reasoning, evidence-based:

**What the constraint has already produced — and why its dividend is banked,
not ongoing.** ADR 0040 and 0041 are written. The "my multi-node plan didn't
survive `lscpu`" and "my node's memory is as tight as its CPU" stories exist
in full, with real numbers. The 2026-08-11 review is right that these are
among the project's rarest assets — but they are *already captured*. Staying
constrained longer does not earn a second measured-ceiling article; the
marginal narrative value of continued constraint is now near zero. You cannot
re-bank a story you've already told.

**What the constraint now costs (verified live).** Memory limits are 111%
overcommitted with the host running 4–5Gi into swap at rest (ADR 0041,
reconfirmed this review). Mimir OOMs every ~6h (70 restarts) and pollutes a
real alert. M12's genuine core (#69 real Nextflow pipelines) is permanently
blocked — the machine can't complete a single ClinVar ingestion without OOM
refactoring. The constraint has stopped being a productive teacher and started
being an operational tax.

**What new hardware concretely unlocks:** the genuinely-blocked,
genuinely-differentiated work — real node-drain/rolling-upgrade drills (#52),
replicated storage (#51), a real Nextflow pipeline (#69, M12's whole point),
the Istio ambient mesh and the mTLS gap ADR 0040 named as a "when hardware
exists" benefit — plus it retires the memory-pressure/OOM-noise class outright.

**Why migrate rather than keep-for-story:** the differentiation argument that
justified staying (2026-08-11 §3a) rests on assets already produced; the
operational and roadmap costs are ongoing and growing; and — decisively — the
*migration itself is the next chapter of the exact story the constraint made
valuable.* "I moved a live GitOps platform to new hardware — here's the RTO
and what didn't come back" is the natural sequel to the rebuild-from-Git
article, and it's still an *owned-hardware* story, so ADR 0035's narrative
survives intact. A cloud annex (ADR 0040 §6) remains the wrong move for the
same reasons that ADR gave: it dilutes the owned-hardware story for imperfect
fidelity.

**Two hard preconditions, both to protect existing assets:**

1. **Re-prove restore on the new host before cutover.** #23a is Done and the
   #123 acceptance checklist exists — use them. The migration is a restore
   drill; run it as one, don't wing it.
2. **Preserve #94's retained Prometheus history across the move.** The 30-day
   SLO clock (started 2026-08-07, closing ~2026-09-06) is the single most
   differentiated unpublished asset the project has. A naive host move that
   resets it destroys that. Either migrate *after* #94's window closes and the
   report is written, or carry the PVC across with the same #49 PVC-copy
   discipline that preserved history through the last rebuild.

This is not a coin flip. The evidence points one way: the constraint's story
is told, its costs are compounding, and the move is itself the best remaining
chapter — provided it's executed as a drill, not a scramble.

## 12. Recommendations, ranked

Ordered by value-per-effort. Items 1–6 are low-risk and mostly zero new CPU.

1. **Fix the stale-OOM alert noise (§3.1, §4).** Three days old and already
   crying wolf on `critical`; gate the exit-code arm on restart recency. One
   line, highest signal-to-noise cost in the whole alert set.
2. **Add `securityContext` to the 12 app workloads (§3.1, §6).** The most
   concrete unaddressed risk; a mechanical, high-value hardening pass.
3. **Publish something (#129).** Two of the three drafts aren't even committed.
   This is the single highest-leverage action for objective 4 and it is owner
   work, not engineering. Commit the two untracked drafts today regardless.
4. **Decide Mimir with a real trigger (§5)** — decommission per ADR 0038's
   rollback path, or re-tie #135 to a calendar date. Either buys back ~734Mi
   and removes the OOM noise class.
5. **Close #29 (clinvar dashboard)** — five reviews old, the flagship service,
   free.
6. **Add a Mimir/remote-write-health alert and fix-or-retire `beyla-vs-manual`
   (§4/§5).** Make the backends visible; make Beyla's justification actually
   render or remove it.
7. **Reconcile the record (§3.1):** the five ADR headers and the unmarked
   backlog items, and extend #97 to validate status markers.
8. **Invest one session in Claude Code tooling (§9)** — the safety hook, the
   KUBECONFIG SessionStart hook, and the two Skills. Removes documented,
   recurring friction.
9. **Plan the hardware migration as a restore drill (§11)**, gated on
   preserving #94's history.

## 13. Review of this review (before merge)

Every load-bearing claim here was read off the live cluster or the real repos
during this review. Cross-checks and honest limits:

1. **The OOM-alert stale-firing finding was found independently and confirmed
   two ways** — I observed 3 firing instances and traced the sticky-gauge
   cause myself (`last_terminated_exitcode==137`, `for: 2m`, no recency bound),
   and the delegated observability audit independently reached the same
   conclusion with the 2026-08-18 OOM date. High confidence.
2. **The `securityContext` gap, the ADR header staleness, the Mimir restart
   count (70), the dashboard inventory, the 0-recording-rules fact, and the
   Beyla `job` label were each verified by me directly**, not taken from
   sub-agents — `kubectl get pod -o jsonpath`, header greps, `/api/v1/rules`,
   `count(...)by(job)`. High confidence.
3. **The code-quality verdict rests on a sub-agent's file-level read that I
   spot-checked structurally** (the `securityContext` count live, the manifest
   inventory) but did not re-read every cited file line-by-line. The
   application-code "strong" verdict is one level less directly verified than
   the infra findings — flagged as such.
4. **The Faro/`frontend-rum`-is-dead finding is medium confidence** — Loki
   returned empty for `{job="faro"}` over 24h across multiple label queries,
   but a Loki tenant/query nuance can't be fully ruled out without deeper
   inspection. Stated as "likely," not asserted.
5. **What I did not do:** re-verify all 141 backlog items (the status sweep was
   delegated and sampled, not exhaustively re-checked), execute the sre-agent,
   or read every ADR in full (five were read in full — 0020/0031/0038/0040/0041/0043
   — the rest via a topic index I spot-checked). The M12 dependency-text
   correction from 2026-08-15 I recommend confirming actually landed rather
   than asserting it did.
6. **Where I disagree with a prior review:** none materially — I *confirm* the
   2026-08-15 M12-mechanism correction and the 2026-08-11 differentiation
   thesis, and I *update* the operate-gap finding (it has narrowed, §1) and
   the Mimir call (the case has strengthened past "keep testing," §5). I part
   from the implicit "keep the constraint for narrative" lean on hardware
   (§11): the narrative dividend is banked and the migration is the better
   next chapter.
7. **My own biggest uncertainty:** whether the owner reads the publishing and
   sre-agent items as genuinely gated on their own time or as deprioritized —
   five reviews have recommended both and neither has moved, which at some
   point is data about priorities rather than a backlog gap. This review
   states it as the finding it is (§7) rather than recommending them a sixth
   time as if the recommendation were the missing piece.
