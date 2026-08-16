# Milestones

Ordered by goal, not a hard gate — an item starts when *its own* listed
dependencies in `backlog.md` are met, not when every item in the previous
milestone is closed. M3's OTel instrumentation (#16) only depends on
Kafka (#13, done); it doesn't need to wait on Redis (#15, still open in
M2) just because of the table row it happens to sit in. Observability is
meant to grow alongside the system it observes, not get bolted on after
the fact — see `docs/SESSION_STATE.md` for the current parallel-work
state.

| Milestone | Goal |
|---|---|
| **M0 Foundation** | Org, repos, docs, workflow, backlog exist and are usable. |
| **M1 Platform Bootstrap** | k3s cluster up, ArgoCD as GitOps entrypoint, ingress/TLS, CI pipeline with security scanning. |
| **M2 Distributed Application** | Gateway + API + workers running, wired to Kafka, PostgreSQL, Redis. |
| **M3 Observability** | Full telemetry pipeline (OTel → Prometheus/Mimir, Loki, Tempo) with baseline dashboards. |
| **M4 Reliability** | SLOs, alerting, runbooks, failure testing — the system can be operated, not just run. |
| **M5 Clinical Variant Annotation** | Real ClinVar/gnomAD-backed variant lookup, added alongside the work-item domain (ADR 0018) — the project's first skewed cache access pattern, invalidation-on-write, and data-provenance story. |
| **M6 Real Demand and Progressive Delivery** | Continuous, shaped traffic replaces an idle cluster, and deploys become canaries gated on the SLOs that traffic finally makes real. |
| **M7 Multi-Node Substrate** | Rebuild on the dedicated host as a real multi-node cluster — Cilium/Hubble, the project's first NetworkPolicies, replicated storage, the drain/node-loss exercises one node cannot produce, and an Istio ambient mesh (mTLS + traffic control) layered on *after* Cilium so failures stay attributable to one layer. |
| **M8 Application Logic: Delivery Semantics and Stream State** | New services chosen for the operational shapes the project lacks — guaranteed fan-out delivery, long-running async jobs, and stateful stream processing. |
| **M9 New Signal Classes** | Continuous profiling and admission-time policy — one new class of evidence, one new class of control, each grounded in an incident that already happened. |
| **M10 Platform Automation: Elastic Scaling, Chaos, and Cost** | KEDA event-driven autoscaling on Kafka lag, Chaos Mesh formalizing the manual chaos exercises, and Kubecost cost visibility — capabilities that earn their keep once load is real and workloads are diverse. |
| **M11 AI-Assisted SRE** | An `sre-agent` over the project's own Loki/Tempo/Prometheus/events/Alertmanager signals — a real incident-triage agent, evaluated honestly against the human-written fact packs. |
| **M12 Bioinformatics Workloads (reopened)** | The bio-pipeline milestone ADR 0021 closed, reopened by ADR 0025 for the changed goal — a Metadata API, MinIO, real Nextflow pipelines, a saga-shaped Kafka lifecycle, a Notification service, and real licensed public data. |
| **M13 Real-Time Market Sentiment Pipeline** | Real, continuously-flowing external market data — live stock prices and financial news sentiment for a fixed watchlist, decomposed into five Kafka-backed services (ADR 0029) — the flagship real-workload demo for the M7 hardware substrate; revives #55's stateful stream processing on a friendlier domain. |
| **M14 Reach and Packaging** | The project becomes publicly presentable: the top-level narrative doc a first-time reader can land on (#31), public read-only access to the live system, and an article-asset habit. No new runtime components (ADR 0031). |
| **M15 Consolidation: Operate What You Built** | Close the gaps the expansion phase opened — every shipped service gets its dashboards/SLOs/alerts including the pipeline freshness SLO, Kafka durability is re-decided against the system that exists now, long-term retention enables SLO reporting over time, and dependency/backup/secrets hygiene is automated. No new application services (ADR 0031). |
| **M16 Canary + SLO Operational Maturity** | Exercise and calibrate the canary-deployment and SLO machinery that already exists (#46, ADR 0020) — a recurring, dated drill cadence, real threshold calibration once #94's 30-day retention window closes, and an article evidence pack. Zero new components (ADR 0043). |

M6–M9 are the expansion phase (ADR 0022). The goal changed — breadth and
novelty, on top of the tight core ADR 0021 produced — and ADR 0022 states
explicitly which of ADR 0021's cuts stand (gnomAD, HGVS/liftover,
`gateway`, `whoami`, solo postmortems, burn-rate policy) and which are
reopened *in changed form* because their stated premise changed
(#34 → #45, #23b → #52). The remaining M4 work (#23 scenario 3, #23a,
#21d, #21e, #42, #43, #44) and the cross-cutting items (#31, #32) are
not superseded by any of this and mostly gate it: **#23a in particular is
a hard prerequisite for all of M7** — migrating hosts without a proven
restore is how this project loses its data.

M6 has no new dependencies and unblocks the rest: chaos scenario 3
(consumer lag) is not meaningfully testable until #45 produces a
sustained produce rate, and both #46's canary analysis and #57's profiles
are meaningless against an idle cluster. M7 is gated on hardware and on
#23a. M8 and M9 can run in parallel with each other.

M7 also carries the Istio ambient mesh (ADR 0024, backlog #59–#62),
sequenced *after* Cilium (#49) on purpose: Cilium is the CNI and rides the
rebuild, Istio is layered on separately so a broken dataplane is
attributable to one layer, not two. The mesh closes ADR 0010's stated
"no in-cluster auth" gap (mTLS) and adds the traffic-control layer — fail-
fast timeouts, circuit breaking — the two live chaos scenarios showed the
project needs, which is why ADR 0024 overturns ADR 0023's mesh exclusion.

M10–M12 extend the expansion phase further. M10 (KEDA, Chaos Mesh,
Kubecost) and M11 (the `sre-agent`) mostly gate on #45's real traffic and
can run alongside M8/M9. **M12 (bioinformatics workloads, ADR 0025) is the
deliberate reopening of the milestone ADR 0021 closed** — reopened because
the goal shifted (ADR 0022) and health-tech roles make real licensed
domain data an asset, not the "bio coat of paint" liability it correctly
was for a tight SRE portfolio. M12 lands after M7's multi-node/replicated-
storage substrate (#48/#51), which its data volume needs.

**M13 (Real-Time Market Sentiment Pipeline, ADR 0029) also gates on M7,
for a different real reason than M12.** M12 needs M7's substrate for data
volume; M13 needs it for CPU headroom. #77's real accounting (closed
2026-08-02, platform#81) found this single node's CPU allocatable already
at 63% requested (2545m of 4000m) after every existing over-provisioned
request in the cluster was trimmed down to real observed usage — roughly
1.4 real free cores, not enough room for the four to five new always-on
Kafka producer/consumer services (backlog #78-#82) this milestone adds on
top of everything M8-M12 already carries. Its services are ordinary Kafka
producers and consumers and so inherit ADR 0011's ephemeral-broker-storage
constraint the same way #55 already flagged for the shape it revives —
#81 (the `aggregator`, superseding #55) is where that conflict is
actually resolved, not deferred a second time.

**Gate overridden by the owner, 2026-08-02** — development starts on the
current laptop, not the M7 substrate. The reasoning above stands (CPU is
real and finite); the response is incremental live deployment with a
real headroom check before each service, not disbelief in the constraint.
See backlog.md's M13 section for the exact stated tradeoff. M13 can run
alongside M8-M11; nothing in M8-M11 blocks it or is blocked by it.

**M13 is Done as of 2026-08-04** — all five services (#78-#82) built,
merged, and live on the real cluster, each with real end-to-end
verification (backlog.md's M13 section has the per-service detail,
including two real live-only bug classes found and fixed along the way,
#84/#85). This is the first M8-M13-range milestone to close under this
relaxed-sequencing rule, closed on its own real dependencies rather than
waiting on M7.

**M14 and M15 (ADR 0031) are the post-expansion consolidation phase**,
driven by the 2026-08-06 independent staff-engineer review
(`docs/reviews/2026-08-06-staff-engineer-review.md`). **M14 goes first on
purpose and is days, not weeks**: the project's reputation goal is
blocked on packaging, not on more engineering — #31's narrative doc, a
publicly reachable read-only Grafana, and an article-asset habit. **M15
closes the standard-of-care gaps the expansion phase opened** — most
visibly that M13 shipped with scrape configs but no dashboards and no
SLO-table rows, against the standard ADR 0017/0020 set for everything
before it — re-decides ADR 0011's ephemeral-Kafka premise against the
system that exists now rather than the one it was written for, and adds
the retention window SLO reporting needs. A gate applies: **no new
application services until backlog #90–#97 close** — the standard-of-care
subset of M15, not the whole milestone. ADR 0022's "new operational
shape" test is currently failed by every candidate, because the marginal
new shape per service has dropped below the doc/CI/alert tax each
addition carries. #98–#103 (Renovate, off-node backups, secrets, VPA,
Beyla, Faro) sit in M15 for sequencing but are deliberately *outside* the
gate: they are new surface themselves, not expansion-phase debt, and
gating future work behind them would contradict the gate's own reasoning. **M11 (`sre-agent`) is sequenced after M15
deliberately, not cancelled** — its honest evaluation needs the retention
window and richer signals M15 delivers. M7's hardware gate is unaffected;
#104 records the explicit dedicated-host-vs-VM-interim decision so the
gate is decided, not drifted.

A milestone is Done (Definition of Done, `.claude/PROJECT.md`) when every
item in it is closed — that gate is unchanged. What's relaxed is only the
assumption that work on the *next* milestone can't begin until then;
individual items can start as soon as their own dependencies clear.

**M16 (ADR 0043) follows M15 in the table above but is not gated on M15
closing as a whole** — the same relaxed-sequencing rule applies here
without a new exception. Its drill-cadence item (#136) depends only on
#46 and #45 (both Done) and starts immediately. Its calibration and
article items (#137/#138) hard-depend on #94's real 30-day retention
window, which does not close until ~2026-09-06 regardless of when M16
opens — a calendar floor, not a milestone-ordering one. M16 deliberately
adds no new component and does not gate M11 (`sre-agent`), which stays
sequenced after M15 per ADR 0031 for its own, unrelated reason.
