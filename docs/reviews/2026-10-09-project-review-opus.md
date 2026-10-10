# Project review after the migration: a canary that saved production, a month nobody saw, and what a second node needs — 2026-10-09

Seventh in the review series (`2026-08-06-staff-engineer-review.md`,
`2026-08-09-staff-engineer-review.md`,
`2026-08-09-hardware-constrained-strategy.md`,
`2026-08-11-staff-review-differentiation-and-article-strategy.md`,
`2026-08-15-operate-followthrough-and-m12-reality.md`,
`2026-08-21-staff-engineer-full-audit.md`,
`2026-10-01-agentic-working-model-assessment.md`). It is the first general
review since the cutover to the NucBox (#154, 2026-08-30/31), and it starts
from three owner decisions taken as fixed inputs:

1. **Mimir stays** (#135): record the decision, keep or tighten the
   decommission trigger, do not propose removing it.
2. **The NucBox stays on its USB Wi-Fi dongle**: no cable and no router
   reservation. #162 is reframed from "get a cable" to "make the control
   plane tolerate this link".
3. **The Lenovo T460s becomes the second k3s node.** This reopens the
   multi-node work (#48's successor, #51, #52), scheduling, the Cilium
   policies, backups and resource requests.

**Method.** Read-only throughout: no `apply`, `patch`, `delete`, `scale`,
sync, `terraform`, or push to any repo other than this review's own
branch. Evidence came from `origin/main` snapshots of all four repos
(the local checkouts were on old branches, so they were not used), the
live cluster (`KUBECONFIG=~/.kube/nucbox-config`, node `adamastorx`,
v1.36.4+k3s1, 16 CPU, ~58.7GiB), the live Prometheus API, and `gh`.
Six evidence agents gathered material in parallel (one haiku for the
repo/CI/branch-protection inventory; five sonnet for backlog consistency,
docs/ADR drift, reliability, security, and multi-node readiness). Four of
them hit a 600s stream watchdog and returned partial reports after a nudge;
their gaps are listed in §9. Every finding below that I rank in the top
five I re-checked myself with the command shown. Findings I could not
support were dropped, and two agent claims were corrected (§9).

---

## 1. Verdict

The system is healthier at the application layer than at any previous
review: securityContext is on every hand-written workload (#142, verified
live), the Kafka heap is bounded (#161), ClinVar ingestion works end to end
(#160), the promtool gate is in CI (#143/#144), and backups have succeeded
for three nights running. The engineering inside a change is good.

What is weak is **everything between changes**: the order in which PRs
reach the cluster, the pipeline that should deliver dependency updates,
the signal that should say "the node has been gone for a month", and the
written record of what is true. Each of the top five findings below is a
seam between two things that each work on their own. That is the expected
failure shape of a project built by many short, well-behaved agent
sessions with one human merging: every session finishes its own job,
nobody owns the joints.

The T460s is a good next chapter, but not this week. It is **not ready to
join** (§6): the server address it would join is a DHCP Wi-Fi address,
Cilium is configured in a way that cannot work on an agent, nothing in the
repo constrains scheduling, and the laptop still carries the old server
install. All of that is fixable in Git, in order, and that order is the new
M19.

---

## 2. Top findings, ranked

### 2.1 The `api` Application is Degraded because of a cross-repo merge order — P0, verified

- platform#238 merged at **2026-10-09T03:00:57Z**, 60 seconds after
  services#96 (02:59:57Z). It removed the `pyroscope-agent-fetch` init
  container and pointed `JAVA_TOOL_OPTIONS` at `/app/pyroscope-agent.jar`
  (`platform/kubernetes/api/rollout.yaml:193`), but left the image at
  `api:e26a01e` (`rollout.yaml:138`), a 2026-08-15 commit
  (`git log -1 e26a01e`: "backlog #105: ...") that has no baked jar.
- Live: `kubectl get rollout api -n api` → `Degraded | RolloutAborted:
  Rollout aborted update to revision 4`. ReplicaSet `api-5665857745`
  (rev 4, created 03:02:35Z, no init container) is at 0; the stable rev 3
  pod `api-5698d97744-v4f5w` still runs `init=pyroscope-agent-fetch`.
  ArgoCD: `api Synced Degraded`.
- **A second trap is armed.** `api-network-policies` is manual-sync and
  `OutOfSync` (the only firing alert, `ArgoCDAppOutOfSync`), because #238
  deleted `api-pyroscope-agent-egress.yaml` from Git. Syncing it "to clear
  the alert" removes the GitHub egress the stable pod's init container
  needs, so the next restart of the only serving `api` pod would stick at
  `Init`. The order must be: image bump → canary Healthy → then sync.
- Backlog #159 says "Mechanism Done ... live confirmation still owed"; in
  reality the deploy failed. The canary did its job (production kept
  serving from the stable ReplicaSet). The review step did not: two PRs,
  each independently reviewed and correct in isolation, were merged a
  minute apart without anyone checking that the second needed an image
  built by the first. New item **#163**.

### 2.2 A month-long outage that nothing reported, and the 30-day history is gone — P1, verified

- `SESSION_STATE.md:150` records "NucBox offline 33 days, Tailscale node key
  expired post-cutover". Nothing paged: Alertmanager's only receiver is a
  webhook to `ntfy.sh` (`platform/argocd/apps/prometheus.yaml:118-142`),
  reached over the same Wi-Fi uplink, and there is no Watchdog/dead-man's
  switch (`ALERTS{alertname="Watchdog"}` is empty; 25 rules, none
  always-firing).
- Restart counters carry the scar: `node-exporter` 5356,
  `argo-rollouts` 3187, `cert-manager-cainjector` 3161,
  `kube-state-metrics` 3142 restarts on 40-day-old pods
  (`kubectl get pods -A`), with Prometheus showing almost none of them
  inside the last 7 days. I believe these accumulated while the node was up
  without a usable network, but the cause is **not verified** (the last
  terminated reason is `Unknown`, exit 255).
- **The asset ADR 0045 made a hard precondition is gone.**
  `prometheus_tsdb_lowest_timestamp_seconds` = 2026-10-03T16:09Z;
  `count(count_over_time(up[1d] offset 7d))` returns nothing, and Mimir
  returns nothing past 6 days either. The August history that #153/#154
  carried across with a careful PVC copy aged out under the 30-day
  retention while the node was dark. #94's SLO-over-time report was never
  written and now cannot be written from that window. This is the single
  most expensive consequence of having no off-box liveness signal.
- New items **#165** (off-box dead-man's switch) and **#166** (alerts on
  the uplink, API-server reachability, leader-election loss). #94 is
  annotated: its window restarts from 2026-10-03.

### 2.3 The dependency pipeline is silently broken, and the merge gate is policy only — P1, verified

- `gh pr list --repo AdamastorX/platform`: 10 open Renovate PRs
  (#197/#198 from 2026-08-24, #213–#220), **every one with 0 status
  checks**. #213 has had auto-merge enabled since 2026-08-31 and is still
  waiting for a `ci` check that will never arrive. Cause:
  `platform/.github/workflows/renovate.yml:32` runs Renovate with
  `secrets.GITHUB_TOKEN`, and events created with that token do not trigger
  other workflows. In `services`, 5 of 10 Renovate PRs show 0 checks, the
  other 5 show 14, consistent with manual re-runs. Pending: Cilium 1.20.2,
  cert-manager 1.21.2, Argo Rollouts, Loki, Grafana.
- Branch protection (`gh api repos/AdamastorX/<repo>/branches/main/protection`):
  `adamastorx`, `platform`, `services` require the `ci` check;
  **`observability` requires no check at all**; every repo has
  `required_approving_review_count: 0` and `enforce_admins: false`, and
  `observability` has no `renovate.json`.
- `WORKFLOW.md` says "Branch + PR + human review" is never skipped. GitHub
  enforces only the CI half. With a single owner who is also the PR author
  of record, a required review is not available, so the human gate is
  discipline. 2.1 shows what that discipline costs at 03:00. New item
  **#164**; the merge-order rule goes into #163.

### 2.4 The control plane rides a DHCP Wi-Fi link with no tolerance built in — P1, verified

- Live args (`kubectl get node adamastorx -o jsonpath='{.metadata.annotations.k3s\.io/node-args}'`):
  `--disable traefik --disable servicelb --flannel-backend none
  --disable-network-policy --disable-kube-proxy --tls-san 100.69.223.105`.
  No `--node-ip`, so k3s uses the DHCP address on `wlx0cef15d0626a`
  (now `192.168.1.7`, was `.10`).
- `node_network_carrier_changes_total{device="wlx0cef15d0626a"}`: 34
  lifetime, 11 in 7 days. `argo-rollouts` and `keda-operator` restarted 11
  times each in 7 days. Their previous logs show the mechanism, e.g.
  2026-10-09T04:17:37Z: `failed to renew lease
  argo-rollouts/argo-rollouts-controller-lock: context deadline exceeded`
  → `OnStoppedLeading`; keda one second later: `leader election lost`.
  Both run with default lease timings.
- Remaining hard-coded addresses: `platform/argocd/apps/traefik.yaml:68`
  `ingressEndpoint.ip: 192.168.1.10` (stale: Ingress status advertises an
  address the node no longer has); the stale host comment in
  `cilium.yaml:9`.
- With a second node, this link becomes the cluster's network, not just
  the operator's access path. #162 is reframed (§5): stable addressing via
  the Tailscale IP or a host-side static address, Wi-Fi power-save off,
  longer leader-election leases, and alerting from #166.

### 2.5 The written record lags the cluster by a migration — P2, verified

- `.claude/PROJECT.md:32-35`: "the owner's local machine ... moving to a
  dedicated host, if it ever happens, is now an open decision (#104)". The
  move happened six weeks ago (ADR 0045, #154). It also says k3s v1.36.3
  (live v1.36.4+k3s1), and `PROJECT.md:114` says default-deny policies are
  "enforced across every real namespace": `kubectl get cnp,netpol -A`
  finds policies in **8 of 29** namespaces with pods (§4.1).
- ADR 0045 decision 2: "the new host is confirmed as a genuine multi-node
  substrate". The cluster has had one node for 48 days; the second node
  only now exists, and it is the old host. ADR 0035 still reads
  `Status: Accepted` although its own addendum says it was falsified.
- `docs/architecture/overview.md` never names the NucBox or the T460s.
  `SESSION_STATE.md` "Still open, in priority order" (lines 110-135): five
  of six entries are already resolved (backups succeed nightly since
  10-07; platform#195/#201 merged; promtool shipped in observability#41;
  services#83 merged). Its "Cluster access" section (line 391) gives a
  Linux path that does not exist on the operator's Mac.
- Status markers overstate: #151 is "Done ... not exercised" while its AC
  requires each Skill be invoked once; #159 is "Mechanism Done" with a
  failed deploy; #158 says CI stood in for a "Verified live" AC. The
  checker (`scripts/check_backlog_structure.py`) passes all of these
  because any bolded "Done" reads as closed. New items **#167** and
  **#170**.

---

## 3. Reliability and operations (beyond the top five)

1. **Backups work again, on one disk.** `lastSuccessfulTime` 2026-10-09
   03:00:06Z / 03:15:11Z / 03:40:03Z for the three CronJobs. Dumps land on
   `local-path` PVCs on the NucBox's only disk; there is no off-node copy
   (#99 deferred) and Terraform state lives only on the operator machine.
   #157's October failure mode (`DeadlineExceeded`, no pod created) is
   still undiagnosed. The T460s gives an off-node (not off-site) target
   cheaply: **#176**.
2. **Manual-sync Applications drift.** 14 Applications have no `automated`
   policy; `cilium` is `OutOfSync` on ~30 resources and nobody has diffed
   it since 10-04. With a second node, a manual-sync CNI whose live state
   is not known to match Git is a risk. Covered by #173 AC.
3. **`kubectl top` is broken** (`Metrics API not available` although
   metrics-server runs). Not diagnosed. Folded into #175, because request
   sizing for the T460s needs it.
4. **Tempo restarted 28 times in 7 days** per Prometheus but shows no
   restarts on the current pod; most of it is the 10-06/07 OOM loop fixed
   by platform#235. Medium confidence, not re-investigated.
5. Alert-to-runbook coverage is 25/25 (`observability/runbooks`), which is
   good. The gap is not coverage; it is that no rule looks at the node,
   its link, or the API server.

## 4. Security posture

1. **21 namespaces with pods have no policy at all**: aggregator,
   argo-rollouts, beyla, blackbox-exporter, cert-manager, clinvar-viewer,
   grafana, keda, kube-system, loki, market-data-ingestor, mimir,
   news-ingestor, otel, pyroscope, sentiment-analyzer, tempo, traefik,
   visualizer, vpa, workload-generator (`comm` of pod namespaces against
   `kubectl get cnp,netpol -A`; no `CiliumClusterwideNetworkPolicy`).
   #126 covers the M13 batches only; traefik, the LAN edge, has none.
   **#168**.
2. **Frozen images.** Postgres (×3 and the backup jobs), Redis and Kafka run
   `docker.io/bitnamilegacy/*` (e.g. `postgresql:17.1.0-debian-12-r0`), an
   archive that gets no security fixes. The Trivy gate is PR-only
   (`services/.github/workflows/ci.yml`; `build-publish.yml` states it does
   not rescan) and nothing scans what is already running. **#169**.
3. **securityContext**: project workloads pass (agent check, consistent
   with #142's live verification). Gaps are third-party (alloy, mimir,
   otel-collector, node-exporter without any) and the three pg_dump
   containers (no read-only root). Not escalated: low marginal value.
4. **Secrets**: only `ntfy-webhook-url` is under SOPS+age; the age private
   key's only copy is in the owner's password manager, and the cutover
   already lost the topic once for want of it (#155). Unchanged risk,
   tracked by #100; not re-filed.
5. **LAN exposure**: Alertmanager, Prometheus, Hubble UI and Pyroscope
   Ingresses carry no auth middleware (annotation check only; in-app auth
   not verified). LAN-only; acceptable for a homelab, noted.
6. The GitOps mutation hook is wired in `platform` only, as `WORKFLOW.md`
   already states. No change proposed.

## 5. The owner decisions, applied

- **Mimir (#135)**: decision recorded and the trigger tightened rather than
  left open-ended. Evidence that matters for the trigger: Mimir currently
  holds 6 days of data (the outage emptied it too), so its long-term-storage
  role is nominal; it has 0 restarts since its 2026-10-06 resize. Trigger
  set to a dated review on **2026-12-01** (the same date ADR 0046 uses) with
  a concrete keep condition. #135 closes as Done with that recorded.
- **Wi-Fi stays (#162)**: AC rewritten from "wired link or reservation" to
  tolerance and mitigation that need neither: stable addressing on the host
  side, power-save off, leader-election lease tuning for `argo-rollouts`
  and `keda`, removal of the stale `192.168.1.10`, and the alerting in #166.
  Success is measured as restarts per lease-loss event, not as zero
  lease-loss events.
- **T460s as second node**: ADR 0047 (Proposed) records the shape; M19
  carries the work (§6, §8).

## 6. Multi-node readiness for the T460s

What the repo knows about the laptop: i7-6600U, 2 cores / 4 threads,
~19.5GB RAM, 233GB disk, 8GiB swap, previously the operator's daily driver
(`backlog.md` #48; `2026-08-09-hardware-constrained-strategy.md`). At
cutover k3s was only stopped (`hardware-migration-drill.md:344`), so the
old server, its datastore and old `local-path` data are probably still on
it (not verified on the host).

Blockers, each verified in the repo or the cluster:

1. **Join address.** `platform/terraform/main.tf:117` builds
   `K3S_URL=https://${var.target_host}:6443`; the agent must not join over
   the DHCP LAN address. The Tailscale IP `100.69.223.105` is already a
   cert SAN and is the obvious choice, at the cost of running the overlay
   inside WireGuard (MTU).
2. **Cilium cannot work on an agent as configured.**
   `argocd/apps/cilium.yaml:81-82` sets `k8sServiceHost: "127.0.0.1"` /
   `6443`, the platform#228 single-node fix. On an agent nothing listens
   there, and the 2026-10-04 `Init:CrashLoopBackOff` is the expected
   result. MTU and `devices` are autodetected over Wi-Fi.
3. **Policies assume one node.** API-server and node-port egress is written
   as `toEntities: host` (alloy, kube-state-metrics, prometheus-server);
   on two nodes the other node is `remote-node`.
4. **No scheduling constraints anywhere.** Zero `nodeSelector`, affinity,
   tolerations or spread constraints in `platform/kubernetes` and
   `platform/argocd`; the server has no taint. Requests are 21% CPU / 16%
   memory of the NucBox while limits are 110% / 44%, so the scheduler would
   see a 4-thread laptop as roomy and could place Kafka (4096Mi limit) or
   Tempo/Mimir (1536Mi) there. All 14 PVCs are `local-path`.
5. **Unpinned, unrehearsed join.** The agent install snippet
   (`terraform/README.md:83-84`) has no `INSTALL_K3S_VERSION`;
   `terraform/README.md:119` says the agent path is "Not yet rehearsed
   against real hardware"; the server install script is not in Git.
6. **PDB with zero disruptions.** `kafka-broker` PDB allows 0 disruptions,
   so a drain of the NucBox will block on it; that is a #52 finding to
   record, not a bug to fix first.

Asymmetry stance (ADR 0047): the NucBox stays the only server and the home
of everything stateful and memory-heavy; the T460s is a tainted worker for
an explicit allowlist of stateless workloads, a drain/node-loss target for
#52, and an off-node backup disk. Istio (#59-#62) stays superseded: a
200m/512Mi-per-node ztunnel on a 2-core laptop does not change ADR 0040's
math. #69 (Nextflow) stays blocked: it is a compute problem, and the
laptop adds little compute.

## 7. The AI-driven workflow, candidly

What works. The record-keeping is unusually honest: items say what was
not verified, reviews correct earlier reviews, and live evidence is the
norm. Agents find real root causes (the Kafka `MaxRAM` = host RAM finding
in #161, the ClinVar message-size split in #160, the unwinnable
`ClinVarInvalidationLag` comparison). The bounded-loop discipline (ADR 0046)
and the mutation hook are sensible, cheap guards.

What does not. Three patterns, all visible in this review's evidence:

1. **Sessions own tasks, nobody owns joints.** #163 is two correct PRs in
   the wrong order. #164 is a Renovate workflow that has looked fine for
   six weeks because nothing ever failed. The 33-day outage was noticed
   by a human trying to connect, not by the system.
2. **Prose grows faster than state changes.** `backlog.md` is 1,544 lines
   for 162 items; single items run to 1,500 words of narrative
   (#49, #50, #94). `SESSION_STATE.md` is 488 lines against a rule that it
   holds only current state. Long records are honest but expensive for the
   next session to read, and they hide stale claims: #135's "keep-reason
   inverted" note and PROJECT.md's "open decision" both survived several
   sessions that read past them.
3. **"Done" drifts toward "merged".** Several sessions had no cluster
   access and said so, correctly. The marker convention then recorded
   their work as Done anyway (#151, #159, #158). #170 adds the missing
   state.

On the human gate: `WORKFLOW.md` puts the owner's review at the end of
every change, and this project has the timestamps to test it. platform#238
was merged 60 seconds after its dependency, at 03:00 local time, in a
batch with observability#41 and services#96. I do not think the
answer is more ceremony; it is two cheap mechanical joints (#163's
same-PR rule for image-dependent manifests, #164's CI on bot PRs) and a
dead-man's switch (#165), so that the cost of a fast merge is a failed
check rather than a Degraded app.

Net: the workflow is good at producing correct units and weak at keeping a
coherent whole. That is worth saying in the talk, because it is the
interesting part.

## 8. Plan

Two new milestones, numbered after M17 (`milestones.md`):

- **M18 Operate on Wi-Fi: no silent failures** — #163 (P0), #164, #165,
  #166, #162 (reframed), then #167, #168, #169, #170. Order: #163 first and
  alone; then #165/#166 and #164 in parallel; the record and security items
  after. #157 stays open beside it.
- **M19 Two-node substrate: the T460s joins** — #171 → #172 and #173 →
  #174 → #175, #176; then #51 and #52 re-pointed from #48 to #174. ADR 0047
  (Proposed) records the shape. M19 does not start until #163 and #165 are
  done: a second node on a cluster that can go dark unnoticed doubles what
  can go dark.

Status markers updated in this PR (each verified as stated in §2/§3):
#135 (Done, trigger set), #159 (back to In progress: deploy failed), #151
(back to In progress: not exercised), #157 (evidence 10-07..10-09), #161
(0 restarts since 10-06), #162 (reframed), #94 (window reset noted),
#51/#52 (blocked on #174, not on hardware), #48 (successor named).
#143/#144 were already updated by observability#41 and are correct; #149
and #150's "In progress" markers are accurate and unchanged.

## 9. What was not verified, and what was corrected

Not verified:

- The cause of the 3000+ restart counts (inferred from the outage, not
  shown; last-terminated reasons are `Unknown`).
- The cause of the `api` rev-4 abort beyond the missing jar: the aborted
  pods are gone and no AnalysisRun exists for rev 4. The missing-jar
  explanation is strong (image predates the jar; JVM `-javaagent` on a
  missing file fails at start) but the container log was not seen.
- Anything on the T460s host itself (OS, NIC, Tailscale, leftover data).
  No SSH was used.
- The `cilium` `OutOfSync` diff; Grafana/ArgoCD in-app authentication;
  ntfy delivery counts; `#157`'s root cause; Kubernetes RBAC.
- The leader-election default timings for `argo-rollouts`/`keda` (taken
  from upstream defaults, not read from the binaries).
- Whether the 11 carrier changes line up one-to-one with the 11 controller
  restarts (counts match; timestamps were only checked for 10-09 04:17Z).

Corrected agent claims: the CI agent read "platform CI never visible on
main" from a run list filtered to Renovate; platform's `ci.yml` does run on
push to `main`, so the real finding is the bot-PR one in §2.3. The backlog
agent reported #155 as unmarked; its Done marker sits on the Dependencies
line, so it is closed.

## 10. Review of this review

1. **The three load-bearing claims were re-checked by me, not taken from
   agents**: the `api` Degraded state and its cause (ReplicaSet revisions,
   image commit date, PR merge timestamps), the Renovate PRs' zero checks
   and the token line, and the Prometheus/Mimir history floor. High
   confidence on all three.
2. **Where I may be wrong.** I attribute the lost history to the outage.
   The 30-day retention would also have expired the August data by
   ~2026-09-09 whatever happened; the outage is what prevented any
   replacement data from accumulating and the report from being written
   inside the window. Both are true; the second is the actionable one.
3. **Where I disagree with a prior review.** The 2026-08-21 audit called
   the hardware migration "the next chapter of the owned-hardware story"
   and ADR 0045 called the NucBox a multi-node substrate. The migration
   was right; the multi-node claim was premature by six weeks and two
   hardware decisions. The 2026-10-01 assessment narrowed agentic loops to
   a technique; nothing here argues for widening it.
4. **What I chose not to do.** No new runtime component is proposed
   except a heartbeat receiver outside the cluster. No Istio, no Longhorn
   commitment (#51 keeps the choice open; on a 2-core laptop NFS from the
   NucBox is the likely answer), no change to Mimir beyond the trigger.
5. **Biggest uncertainty.** Whether the T460s is still the operator's
   daily laptop. If it is, it is a poor node: lid, suspend, battery and
   browser memory all become cluster events. #171's go/no-go is where that
   gets answered, and ADR 0047 stays Proposed until then.
