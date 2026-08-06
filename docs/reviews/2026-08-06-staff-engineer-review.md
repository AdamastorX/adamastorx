# Staff-engineer review — 2026-08-06

Independent review of all four repos (`adamastorx`, `platform`, `services`,
`observability`) against the owner's four stated objectives:

1. An observability pipeline fed with real data
2. Microservices / distributed systems depth
3. A lab/playground for state-of-the-art and established technologies
4. Articles (blog/Medium) to grow a public SRE reputation

Scope of evidence: all 30 ADRs, the roadmap/backlog, `SESSION_STATE.md`,
both CI pipelines, the ArgoCD app-of-apps (33 Applications), the alert
rules in `argocd/apps/prometheus.yaml`, the dashboards in
`argocd/apps/grafana.yaml`, the three chaos fact packs, the runbooks, and
the service source layout. Nothing here required cluster access — every
claim below is checkable against the repos.

---

## 1. Verdict

This is already a strong project — the discipline (ADRs with rejected
alternatives, live verification over assumption, honest recording of
falsified hypotheses, a real simplification pass) is the thing most
portfolio projects fake and this one doesn't. The engineering culture is
the product.

The main risks are no longer technical-depth risks. They are:

- **The highest-reputation-value work keeps losing to feature work.**
  Backlog #31 (the "what this project demonstrates" narrative doc) has
  survived three milestones unbuilt. Nothing is publicly reachable, so no
  article can link a live artifact. SLOs exist but are never *reported on*
  over time. The sre-agent (M11), the single most novel item in the
  backlog, is untouched.
- **M13 broke the project's own rules, quietly.** Five services shipped
  with scrape configs and one alert (`MarketDataStaleFeed`) but **no
  dashboards and no SLO-table rows** — the exact "never ship a service
  without its observability" standard ADR 0017/0020 enforced on everything
  before them. The streaming pipeline has no end-to-end freshness SLO,
  which is the one SLO a streaming pipeline actually needs.
- **Kafka's deliberate ephemerality (ADR 0011) is now a recurring tax, not
  a stated risk.** Since M13, topic-loss/provisioning-lag caused or
  complicated #79, #80, #84, and #85. The decision made sense for 3
  topics and a log-only consumer; the system now has 6+ topics, Kafka
  Streams changelog topics, and a stateful pipeline whose durability story
  depends on it.
- **Doc drift is confirmed systemic, not fixed.** #32's process fix did
  not prevent #83, and #83's fix has already regressed again (evidence in
  §7). Process has failed twice; only automation will close this.

## 2. What is genuinely strong (and should be named in articles)

Not exhaustive — the things that would survive a skeptical staff-level
reader:

- **Hypothesis falsification as a habit.** The Pyroscope flame graph that
  *didn't* confirm the C2-JIT hypothesis (ADR 0028), and the #47 re-run
  that proved the alert rules were fine and traffic was the gap. Both were
  recorded in the direction the evidence pointed, not the preferred one.
- **Incident-driven feature selection.** Rollouts (#46), Pyroscope (#57),
  `WorkersConsumerMissing` (#76), and KEDA's native-scaler choice (#63)
  each trace to a specific, dated incident. This is the correct way to
  build an observability portfolio and it shows.
- **CI that gates the right things.** Per-repo single required check (ADR
  0006), Trivy blocking merge pre-publish, image *boot* smoke tests
  (catches musl/glibc-class breakage — the exact class that later bit
  `aggregator` in #85), helm-render + kubeconform of rendered chart
  output, and the resource-limits linter. This is better CI than most
  production teams have.
- **The outbox-plus-relay work (#53, ADR 0026)** — crash-mid-delivery
  proven by force-killing a pod between persist and publish, and the
  Spring AOP self-invocation bug found because the "fix" was re-tested
  live. This is the single best engineering story in the project.
- **Chaos fact packs** with real timestamps, real commands, and unplanned
  findings (selfHeal reverting the fault in 2 minutes is a better finding
  than the planned one).

## 3. Objective A: observability pipeline fed with real data

The data is real (ClinVar, Finnhub, WSJ/MarketWatch, shaped synthetic
load) — the objective is met on ingestion. What's missing is on the
*retention, coverage, and reporting* side:

**A1. Give the M13 pipeline its own observability surface (P0).**
Five services, zero dashboards, one alert. Concretely:
- Golden-signal dashboards for `news-ingestor`, `sentiment-analyzer`,
  `market-data-ingestor`, `aggregator` (restore time, lag, window
  watermark), matching ADR 0017's precedent.
- **An end-to-end freshness SLO for the pipeline**: time from Finnhub
  trade timestamp → visible in `aggregator`'s `/aggregates`. You already
  carry both timestamps (`exchange timestamp, ingestion timestamp` per
  #78's AC). This is *the* SLO for a streaming system and the project
  doesn't measure it yet. `sentiment-analyzer` and `aggregator` also need
  consumer-lag alerts — `workers` got them; the new consumers didn't.
- Article angle: "SLOs for a streaming pipeline: freshness, not uptime."

**A2. Long-term metrics storage (P1) — the 3-day Prometheus retention
silently caps the SRE story.** You cannot show a 28-day error budget, a
month-over-month reliability trend, or a "30 days of SLOs on my homelab"
article against 3-day retention. Backlog #18a (Mimir) is scoped as an
experiment — run it now, and write it up. Mimir also answers the
multi-component query fan-out you'll hit as service count grows.
Cheaper alternative: raise Prometheus retention to 30–60d and accept the
single-node limits, recorded as an ADR either way.

**A3. Enable kube-state-metrics and node-exporter (P1 — cheap, unblocks
three open items).** Both are deliberately disabled in
`argocd/apps/prometheus.yaml`. That one flag flip is currently blocking:
#21d (node-disk alert — the *single most likely real outage* on a
one-node box with unenforced `local-path` quotas), #63's scale-to-zero
(which you deferred specifically because ksm was missing), and any
USE-method node saturation dashboard. The original exclusion rationale
("no K8s-level metrics needed yet") expired the day KEDA started making
scheduling decisions.

**A4. Synthetic blackbox monitoring (P1, high leverage).** Every "verified
live" in this project is a human or agent running `curl` once. The
Prometheus blackbox exporter probing the public Ingress paths — through
the real TLS + auth middleware chain — on a 30s interval would: catch
edge regressions continuously (the #56 post-merge `clinvar-viewer` stale-
revision gap would have been caught in minutes), generate probe-based
availability data independent of self-generated traffic (a second,
external vantage point on your SLOs), and is a genuinely established SRE
pattern the lab lacks. Tiny footprint.

**A5. Close the correlation triangle (P2).** Trace↔log pivot exists.
Missing: Prometheus exemplars → traces (#19a, already scoped) and
profile→trace correlation (the stated ADR 0028 gap). Either is a solid
"completing the observability triangle" article; exemplars are the
cheaper win.

**A6. Frontend observability (P2, new signal class).** `visualizer` and
`clinvar-viewer` are browser apps with zero telemetry. Grafana Faro (or a
one-line web-vitals beacollector) would add real-user monitoring — a
genuinely new pillar for the lab and a differentiating article topic, and
it would have caught the #82 pre-merge ping race as real user-visible
behavior.

## 4. Objective B: microservices / distributed systems

**B1. Re-decide Kafka durability now, not at M7 (P0).** ADR 0011's
ephemeral-storage decision was correct for 3 topics and a log-only
consumer. The system it protects against no longer exists: 6+
application topics, Streams changelog/repartition topics, a provisioning
Job whose non-re-run has now caused two separate M13 bring-up incidents
(#79, #80), and an OOM history (#75, #84). The honest options: persistent
storage for the broker (smallest change, kills the whole incident class),
or Strimzi (an operator earning its keep: declarative `KafkaTopic` CRs
would have prevented the #79/#80 topic-lag gremlins entirely — and a
"when does an operator earn its keep" ADR comparing this against ADR
0014's anti-Operator stance is exactly the kind of nuanced decision
record readers trust). Keeping the status quo is also defensible — but
then the topic-provisioning mechanism needs to stop being a manually
re-triggered Job. What isn't defensible is leaving ADR 0011 un-revisited
while its cost is being paid weekly.

**B2. Event contracts across the Java↔Python boundary (P1).** Events are
unversioned JSON; producer and consumer schemas drift independently
(#80's "the wire shape has no `summary` field" was found by *reading
merged code* — the exact failure contract testing exists to catch). With
cross-language producers/consumers now real (Java→Python, Python→Java),
options in ascending order of weight: versioned JSON Schemas in a shared
module + consumer-driven contract tests in CI, or Apicurio Schema
Registry. Full Confluent Schema Registry is defensible too but heavier
than this cluster needs. Article angle: "the bug class my homelab kept
having until I versioned my events."

**B3. M7 is the load-bearing milestone — de-risk the hardware gate (P0
for objectives 2 & 3).** Multi-node scheduling, PDBs, drains, Cilium/
Hubble, NetworkPolicy from *observed flows*, Istio ambient mTLS, and
node-loss exercises are all correctly scoped and all blocked on one
physical move. If the dedicated host slips, an interim is possible
without betraying the owned-hardware story: two k3s agent VMs on the
existing machine (multipass/lima, provisioned by the same Terraform
remote-exec path) would unblock #48–#52 and the Cilium/Istio learning
immediately. Not as good as real hardware — no real power-loss test —
but it converts a hard gate into a soft one. Worth an explicit decision
either way; the current state is "blocked indefinitely," which is how
labs stall.

**B4. Resolve the two documented-but-unresolved blocking-call decisions
(#43, HikariCP) (P2).** Both are real distributed-systems lessons
(fire-and-forget that blocks 60s; a pool acquisition that hangs 30s)
currently sitting as "documented, undecided." Deciding them *is* the
content — and if the answer is "Istio timeouts will fix it at the
dataplane (#60)," say that in the items and link them, so #60's fact pack
includes the before/after.

**B5. Give `workers` a real job or rename it honestly (P2).** It consumes
`work-items` and logs. It's now load-bearing test infrastructure (KEDA's
scaling target, the lag alert's subject) — which is fine, but say so, or
give it a real side effect (persist a processed result). A reviewer will
notice.

## 5. Objective C: lab/playground — technology breadth

The stack is already broad (KEDA, Rollouts, Pyroscope, Kafka Streams,
OTel, Loki/Tempo/Alloy). Gaps worth filling, chosen for learning-per-
component, not resume keywords:

- **Grafana Beyla (P2, state-of-the-art).** eBPF auto-instrumentation
  running alongside your *hand-instrumented* Micrometer/OTel services is
  a controlled A/B experiment almost nobody can run outside a lab:
  "Beyla vs. manual OTel on the same services — what do you actually
  lose?" is a genuinely novel article.
- **Renovate (P1, established, unglamorous, necessary).** 20+ pinned Helm
  charts, base images, Actions, and Python/Maven deps with no update
  automation. A homelab is where dependency rot goes to hide; Renovate
  with patch automerge is also the platform-engineering pattern your CI
  already implies. It will also catch the "deprecated chart repo" class
  you keep finding by hand.
- **VPA in recommendation mode (P2).** You hand-trimmed requests from
  observed usage (#77) — VPA's recommender automates exactly that loop
  and gives you the "my requests vs. its recommendations" comparison
  article. Natural pair with #65 Kubecost.
- **External Secrets Operator or SOPS (P1, small).** Secrets are
  script-generated out-of-band and never committed — safe, but
  unversioned and unrecoverable if the laptop dies (same exposure class
  as the local Terraform state). ESO + a free cloud secret store, or
  SOPS + age keys committed to git, is the established answer and closes
  a real (if small) DR hole.
- **Off-node backup copy (P1, cheap).** #23a's restore is proven but
  single-node; ADR 0030 accepts disk-loss honestly. One `restic`/`rclone`
  CronJob to a free-tier object store converts "accepted risk" into a
  real, measured off-site DR story — better content than the acceptance
  note.
- **Already well-chosen, don't add:** a second stream processor (Flink —
  correctly rejected), a service mesh before Cilium (correctly
  sequenced), Mimir before retention hurts (see A2 — it now hurts).

## 6. Objective D: articles & SRE reputation

The raw material is exceptional — the three chaos fact packs, the #35
95-minute incident, the outbox relay force-kill, the flame-graph
falsification, and the ADR 0018→0019 pivot are each a publishable article
*today*. The gap is packaging and reachability:

**D1. Do #31 now (P0).** It has survived three milestones. A hiring
manager or Medium reader currently cannot reconstruct the throughline
without reading 30 ADRs. One `docs/WHY.md`, linked from the README's
first screen. Half a day. Highest ROI item in the entire backlog.

**D2. Make something publicly reachable (P0).** Every hostname is
`*.local.adamastorx.test` — no article can link a live artifact, and
"trust me, it works" is the failure mode this project exists to refute.
A Cloudflare Tunnel (already named and parked in ADR 0020) in front of a
read-only Grafana (and maybe `visualizer`) sidesteps ADR 0004's no-
public-DNS constraint, costs nothing, and turns every future article's
screenshots into links. This is the single biggest reputation multiplier
available.

**D3. Publish the SLO report, not just the SLOs (P1, needs A2).** Nobody
writes "I ran SLOs against real traffic for 60 days and here's what the
numbers did" from a homelab — because nobody has the data. You will, once
retention allows it. This is your most differentiated prospective
article.

**D4. Build an article asset habit (P1).** The fact packs are 90% of an
article already; what they lack are the visuals (dashboards mid-incident,
the flame graph, the trace waterfall, Hubble flow maps once Cilium lands).
Add "capture 2–3 images into `docs/assets/`" to the chaos-scenario AC
template — producing an article becomes an afternoon of editing, not a
weekend of reconstruction.

**D5. M11 (`sre-agent`) is your most novel unbuilt item (P1).** "I built
an AI incident-triage agent over my own telemetry and graded it against
my human-written fact packs" is a genuinely fresh angle, and you
uniquely have the graded dataset (the fact packs) to evaluate it
honestly. Note the recursion worth naming in the article: the project was
built by an AI agent and is then observed by one.

**D6. Article sequencing already implied by the backlog** (each has its
evidence pack in-repo today): the outbox force-kill (ADR 0026) → the
canary that catches the 95-minute stall (#46/#35) → "my chaos test
failed because my GitOps healed too fast" (chaos 01) → the dark-metric
alert that can't fire (#76) → KEDA sizing against a real CPU ceiling
(#63/#77) → the M13 pipeline build series. That's six articles with the
hard part already done.

## 7. Concrete defects found during this review

Evidence for the doc-drift point (§1), reported per this project's own
convention:

1. **`docs/roadmap/backlog.md` contains item #87 twice** — verbatim, both
   marked Done (lines ~703 and ~709). Trivial, but it sits in the most
   carefully maintained doc in the org, which is the point: manual
   doc-sync fails even here.
2. **`docs/architecture/overview.md` is stale again, in the exact way
   #83 recorded and claimed to fix.** It states M13's five services "do
   not exist yet" — all five are merged, deployed, and live as of
   2026-08-04 per the same repo's backlog. This is the third recurrence
   of the same drift on the same file (#32 → #83 → now).
   **Recommendation: stop trying to fix this with process.** A CI check
   that derives the component list from `platform/argocd/apps/*.yaml` and
   fails if `overview.md`'s component roster diverges is ~30 lines of
   script and ends the recurrence class. The checklist-trigger approach
   has now failed twice; automate or accept a scheduled re-sync ritual.

## 8. Suggested sequencing (next ~90 days)

Ordered by reputation-ROI per unit effort, respecting existing
dependencies:

1. **#31 narrative doc + README surfacing** (D1) — half a day.
2. **Public read-only Grafana/visualizer via Cloudflare Tunnel** (D2) —
   a day, unblocks every article's live links.
3. **M13 observability surface: dashboards + pipeline freshness SLO +
   consumer-lag alerts** (A1) — closes the "shipped without its own
   standard" gap before it calcifies.
4. **Kafka durability re-decision + declarative topics** (B1) — stops the
   recurring M13 tax; strong ADR content.
5. **ksm + node-exporter, then #21d disk alert** (A3) — cheap, unblocks
   three items, covers the most likely real outage.
6. **Blackbox synthetic checks** (A4) — continuous live verification.
7. **Mimir experiment + first SLO-over-time report** (A2/D3).
8. **M7 hardware move (or the VM interim decision)** (B3) — everything
   in M7/M12 is hostage to this; decide, don't drift.
9. **Renovate + off-node backups + ESO/SOPS** (C) — hygiene that keeps
   the lab from rotting between articles.
10. **`sre-agent` (M11)** (D5) — once the above lands, this is the
    flagship novel piece.

## 9. What *not* to do

- Don't add more services until A1 closes — the marginal operational
  shape per new service has dropped below the marginal doc/CI/alert tax,
  which is ADR 0022's own gate applied to the current state.
- Don't resurrect #21b (burn-rate policy) — ADR 0022's reasoning still
  holds; A2's retention enables honest SLO *reporting*, which is the
  valuable 20% of that idea without the theatre.
- Don't build M12 before M7 — its gating reasoning (storage substrate,
  data volume) is still correct, and M13 already provides the "real
  external data" content thread meanwhile.

---

## 10. Review of this review (2026-08-06, before merge)

Every load-bearing claim above was re-checked against the real repos
before this document was merged, rather than accepted on the strength of
its own reasoning. **All of §1's findings held**: M13 has scrape configs
for four services, exactly one alert (`MarketDataStaleFeed` of 11 total),
and zero dashboards — confirmed in *both* `platform/argocd/apps/
grafana.yaml` and `observability/grafana/dashboards/` (the latter holds
only a README), so this is not a case of looking in the wrong repo.
`kube-state-metrics`/`node-exporter`/`pushgateway` are all
`enabled: false`; `retention: "3d"` is real; #31 is still P2 with an AC
that stops at M5; `overview.md` still claimed M13's services "do not
exist yet". The duplicate #87 is real.

Four things changed as a result of that re-check.

**1. The duplicate #87 was mis-attributed, and a second, worse defect
sat next to it.** The duplicate was not a checklist/process failure of
the #32/#83 kind — it came from a bad `Edit` anchor in the #86(a) commit
roughly an hour earlier, which re-emitted the whole neighbouring block.
Separately, and not found by this review: **item #79's heading does not
exist at all**, having been swallowed into the tail of #78's `Priority:`
line (`grep -c '^\*\*79\.'` returns `0`; of items 1–87, only 79 has no
heading). Neither defect is caught by a component-roster check, which is
what #97 originally proposed — so #97's AC was widened to add cheap
structural validation of backlog.md itself (each number appears exactly
once, numbering contiguous, four expected lines per item). Two of the
three real defects this review found would otherwise have gone on
recurring under the automation meant to end them.

**2. The gate was too wide.** As originally written it blocked all new
application services until *all* of M15 closed — including #98–#103
(Renovate, off-node backups, a secrets decision, VPA, Beyla, Faro). But
Beyla and Faro are new signal classes, not gaps the expansion phase left
behind: gating future work behind building them contradicts the gate's
own rationale (marginal shape per addition having fallen below the
doc/CI/alert tax). The gate now stops at #97. Mimir and the blackbox
exporter stay inside it, because retention and continuous verification
are real gaps; Beyla and Faro are labelled honestly as new surface
instead of being carried in on a justification they don't meet.

**3. "M13 broke the project's own rules" needed a fairer cause.** True
against the ADR 0017/0020 standard, but #78–#82's own ACs asked for
*metrics*, and real metrics were delivered — nothing shipped in
violation of its own AC. The defect is that no AC asked for the
dashboard/SLO row/alert/runbook. That makes it a template failure, and
the template is the thing to fix so M14/M15 don't repeat it.

**4. One finding this review missed, in a file it read.** §Scope lists
"the alert rules in `argocd/apps/prometheus.yaml`" as evidence examined.
That file's Alertmanager receiver states its threat model correctly —
*"ntfy topics are public-by-topic-name with no auth, so the only
protection is not being guessable"* — and then commits the topic name in
full, in the same file, in a **public** repository, defeating it
completely. Anyone can read the project's live alert stream or publish
into it. It is not a leaked credential (ntfy topics hold no secret),
which is exactly why secret scanning and a careful human read both
passed over it: the defect is a design whose own stated assumption the
repository invalidates. Filed as **#107**, sequenced before #88, since
#88 deliberately widens public reach. #88's AC also now has to pin down
— verified live, not assumed from a documented default — whether an
anonymous Grafana Viewer can reach Explore, because arbitrary PromQL
against the Prometheus datasource would expose #56's per-tenant
API-key labels and internal hostnames.

**A fifth drift instance was found in the file this PR set out to fix.**
`overview.md`'s M7 bullet still called backlog #23a (backup/restore) "a
hard prerequisite and itself still open"; #23a has been Done since
2026-08-04 (platform#62, ADR 0030). Corrected here. That the drift-fix
PR itself carried a fourth stale claim in the same document is the
strongest single argument in this review for #97 existing at all.
