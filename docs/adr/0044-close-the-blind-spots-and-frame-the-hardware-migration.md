# 0044. M17: close the blind spots the audit surfaced, and frame the hardware migration as an M7 restore drill — no new components

Status: Accepted

## Context

The fifth independent staff-engineer review
(`docs/reviews/2026-08-21-staff-engineer-full-audit.md`) landed on `main` on
2026-08-21. Unlike the four before it, this one was a full pass across ten
owner-set questions — technical debt (especially the untracked kind),
observability quality, decommission candidates, implementation practices,
focus, workflow, AI/Claude-Code leverage, strengths/weaknesses, and the
hardware decision — every load-bearing claim read off the running cluster,
the live Prometheus API, or the real repos, not inherited from the backlog's
own prose. This ADR is the roadmap response to it, written to the same bar:
every finding this ADR acts on was **re-verified live during this ADR's own
authoring**, not taken from the audit on trust.

**What the audit found, re-verified live for this ADR** (2026-08-22,
`KUBECONFIG=platform/terraform/kubeconfig`):

- The system is healthy by every structural measure — 48 ArgoCD Applications,
  all `Synced/Healthy` (the audit's one `Progressing` has since cleared),
  CPU requests re-trimmed to 79%, application code that holds up to a real
  read. The audit's headline is a positive one: the operate-gap the previous
  three reviews called "structural" has visibly narrowed, and the 2026-08-15
  discipline batch (#123/#124/#125/#91/#136 and more) actually got done. The
  project passes its own honesty bar.
- The remaining debt is concentrated in **three places the project's own
  tooling cannot see**, plus two forward-looking threads:
  1. **Security posture.** No `securityContext` on any hand-written
     application workload. Verified live: `api`, `workers`, `aggregator`,
     `news-ingestor`, `clinvar-service`, and `watchlist-service` app pods all
     return an empty container `securityContext`; only the third-party
     Bitnami Postgres pods (and the postgres-backup CronJobs) are hardened,
     because their chart does it. No `runAsNonRoot`, no
     `readOnlyRootFilesystem`, no `capabilities.drop:[ALL]`, no
     `seccompProfile` on the project's own manifests. On a project otherwise
     disciplined enough to run default-deny CiliumNetworkPolicies, this is
     the single most concrete unaddressed risk and it had no backlog item.
  2. **The observability stack cannot see its own backends.** Verified live:
     `count(cortex_build_info)`, `count(loki_build_info)`, and
     `count(tempo_build_info)` all return zero series — Prometheus scrapes no
     self-metrics from Mimir, Loki, Tempo, or Pyroscope, and there are **0
     recording rules** in the whole instance. The one component actively
     failing (Mimir, **71** restarts live, up from the audit's 70 and the
     review series' 11→24→29→70 trajectory) is also Prometheus's own
     long-term-storage target, with no failure alert. And the new #125
     `ContainerCrashLoopOrOOMKilled` alert is **crying wolf on a critical
     channel right now**: verified live, three instances firing — `mimir`
     (a true chronic positive) but also `prometheus-server` and `beyla`,
     each with one lifetime restart, OOMed once on 2026-08-18 and healthy
     since. Two of three currently-firing criticals are stale noise, three
     days after the alert shipped.
  3. **Record-keeping is drifting quietly.** Verified live: five ADR status
     headers are stale (`0010`/`0011` still say `Accepted` though both are
     superseded in the body; `0021`/`0022`/`0023`/`0025`/`0029` still say
     `Proposed` though every one is enacted and treated as settled fact by
     later Accepted ADRs), ~30 backlog items are complete-but-unmarked, and
     the doc-drift automation (#97) built to catch exactly this class does
     not validate either surface.
  4. **The AI/Claude-Code toolchain is underused.** Verified across all four
     repos: `.claude/` contains only `PROJECT.md`, `WORKFLOW.md`, and five
     persona agents. No hooks, no `settings.json`, no skills, no MCP, no
     project memory beyond the docs. The project models platform discipline
     while using ~20% of its own primary tool's capability — and its own
     documented pain points (the trust-based GitOps-mutation safety rule, the
     every-session KUBECONFIG footgun, the re-read-each-time canary/rebuild
     procedures) map almost one-to-one onto the features it isn't using.
  5. **The hardware decision.** The owner has new hardware. The audit's §11
     recommendation, whose reasoning this ADR independently checked and
     accepts, is to migrate the live platform off the T460s, run the
     migration itself as a first-class restore drill, and keep the T460s
     constraint as documented history rather than the live host.

Two audit findings need no roadmap action and are recorded here as resolved,
not carried forward: the LOW "stray editor swap file + untracked article
drafts" hygiene smell (§3.1) is **moot** — `docs/articles/` was removed from
the repo entirely on 2026-08-22 (owner decision, adamastorx#309, verified
live), so the drafts and the swap file are no longer in version control at
all; and the local-Terraform-state fragility indicator (§3.1) is already
covered by the still-open #99 (off-node backup of the pg_dump PVCs *and* the
Terraform state), not a new gap.

**The lineage this ADR sits in.** M16 (ADR 0043) was scoped narrowly and
deliberately to "zero new components" — exercising and calibrating machinery
that already exists rather than adding surface. The 2026-08-11 review's §3d
verdict that ADR 0043 upholds — "the project's next differentiating asset is
not a component; it is a dated series of real operational events with real
response times and honest outcomes" — is not spent by M16 closing; it is the
standing test every increment now passes through. This audit's findings are
almost entirely the same shape: no new always-on component, close real gaps
that already exist. This ADR therefore does **not** invent a new posture; it
extends M16's discipline into the specific domains the audit named, and
carries the same explicit "zero new steady-state CPU/memory" constraint into
the runtime-hardening work.

`docs/WHY.md`'s stated values — real incidents over inspection, honest
reporting of gaps rather than glossing them — are the voice the deliverables
below are held to, the same way ADR 0043 held M16's drills to them: a
security pass that has to leave one workload un-hardened for a stated real
reason records that, a Mimir decision that stays "keep" records the real
trigger rather than defaulting to indefinite, and a hardware migration is run
as a drill with an honest RTO, not a scramble smoothed into a clean story
afterward.

## Decision

### 1. A new milestone, M17, defined by the audit's own three-blind-spots verdict plus the toolchain investment — zero new always-on components

M17's goal is to **close the debt the project's own tooling can't see**:
application-workload security hardening, the observability stack's
own-backend blind spots and the alert already crying wolf, and the
record-keeping drift the doc-drift automation doesn't catch — and to invest
in the Claude Code hooks and skills that turn trust-based safety rules and
re-read procedures into enforced, loadable ones. It adds **zero** new ArgoCD
Applications, zero new namespaces, zero new always-on workloads, and zero new
steady-state CPU/memory requests — the same "total added CPU: zero" shape
M16 carried, because the audit found the same shape available across almost
its entire recommendation set.

M17 is not "M16 continued" — M16's goal is the canary+SLO domain
specifically, and none of these findings live there — but it inherits M16's
zero-new-component discipline deliberately and by name, so that discipline
reads as a standing property of the consolidation phase, not a one-milestone
exception.

This ADR does not edit `backlog.md`. A follow-up sonnet-tier pass mints the
items below contiguously from the current backlog maximum, using this ADR's
descriptions as their Purpose/Acceptance-Criteria source, and updates the
three existing items named in §5 rather than duplicating them.

The concrete items, grouped by the blind spot they close:

| Group | Item (working title) | New/Update | Priority | Can start |
|---|---|---|---|---|
| Security | `securityContext` on the app workloads | New | P1 | Immediately |
| Observability | Stale-OOM alert recency gate | New | P1 | Immediately (front of queue) |
| Observability | Backend self-monitoring (self-metrics + backend-down alert) | New | P1 | Immediately (Mimir arm gated on §5) |
| Observability | Fix-or-retire `beyla-vs-manual`, harvest the A/B article | New | P2 | Immediately |
| Observability | Clinvar-service dashboard | Update #29 | P1 | Immediately |
| Decommission | Mimir decommission trigger, re-tied to a calendar date | Update #135 | P2 | Owner decision |
| Decommission | Beyla/Faro/VPA conclusion criteria in the component ledger | Update #127 | P1 | Immediately |
| Record | One-time record reconciliation | New | P2 | Immediately |
| Record | Extend #97's automation to status-marker drift | New | P2 | Immediately |
| Record | Triage the stale adamastorx#242 | New | P3 | Immediately |
| Toolchain | `PreToolUse` GitOps-mutation safety hook | New | P1 | Immediately |
| Toolchain | `SessionStart` KUBECONFIG + gremlin hook | New | P2 | Immediately |
| Toolchain | Canary-drill and verify-live-Done Skills | New | P2 | Immediately |
| Bug | `messageBuffer` reset on websocket reconnect | New | P3 | Immediately |

### 2. Security: `securityContext` on the app workloads — the most concrete unaddressed risk, mechanical to fix

Every hand-written application manifest gets a pod- and container-level
`securityContext` matching what the Bitnami charts already apply to their own
pods: `runAsNonRoot: true`, an explicit non-root `runAsUser`/`runAsGroup`,
`allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, a
`seccompProfile.type: RuntimeDefault`, and `readOnlyRootFilesystem: true`
wherever the app doesn't need a writable root (with a tmpfs `emptyDir`
mounted for the paths that do, rather than dropping the flag wholesale). The
proof is live per workload — the pod comes up `Ready`, its container
`securityContext` is confirmed populated with `kubectl get pod -o
jsonpath`, and no app regresses — not a manifest diff alone. Deliberate,
recorded exclusions are allowed where a workload genuinely needs privilege:
Beyla (`SYS_ADMIN`/`hostPID` are intrinsic to its eBPF auto-instrumentation,
ADR 0036) is exempted with that reason stated in-manifest, not silently
skipped. This closes the audit's single most concrete untracked risk and is
the flagship hardening content for an SRE portfolio. It pairs with the
already-tracked, still-open #126 (the remaining M13/`watchlist`
NetworkPolicy batches) — together they are the security-posture close, which
is why M17's goal names security first even though this ADR files only the
`securityContext` half as new.

### 3. Observability: fix the alert that's crying wolf, then make the backends visible

- **Stale-OOM alert recency gate (front of queue).** The
  `ContainerCrashLoopOrOOMKilled` alert's OOM arm keys on
  `kube_pod_container_status_last_terminated_exitcode == 137` with no recency
  bound, so a single one-off OOM fires `severity: critical` indefinitely
  until the pod is recreated. Verified live for this ADR: three firing, two
  stale (`prometheus-server`, `beyla` — one lifetime restart each). The fix
  is one line — gate the exit-code arm on restart recency (`and
  increase(kube_pod_container_status_restarts_total[15m]) > 0` or a
  `last_terminated_timestamp` recency window) — and it is the highest
  signal-to-noise cost in the whole alert set, degrading trust in the one
  channel that pages, right now. It goes first. Note the interaction with §5:
  Mimir is a *true* positive (71 restarts, chronic), so the recency gate
  correctly keeps Mimir firing while silencing the two stale ones — which is
  itself another reason to resolve Mimir (§5), not a substitute for it.
- **Backend self-monitoring.** Add self-metric scrape configs for the
  telemetry backends that survive the Mimir decision (Loki, Tempo, Pyroscope
  unconditionally; Mimir only if §5 keeps it) and a backend-health alert on
  the storage path — a Prometheus→Mimir remote-write-failure alert if Mimir
  stays, or a `LokiDown`/`TempoDown`-class target-absent alert regardless.
  The worst combination the audit named — a component that can silently break
  #94's 30-day retention story being the one component with no health signal
  — is what this closes. Scoped explicitly to survive §5's outcome so the two
  items don't collide.
- **Fix-or-retire `beyla-vs-manual`, and harvest the A/B article.** Every
  Beyla-side panel queries `job="<ns>/<svc>"`; Beyla actually emits under
  `job="beyla"` with service identity in `service_name`/`k8s_deployment_name`,
  so the dashboard's entire reason to exist — the A/B comparison that is
  Beyla's stated justification (ADR 0036) — does not render. Either fix the
  selectors so the comparison renders and the A/B article gets written, or
  retire the dashboard and write the article from the captured `job="beyla"`
  metrics — but not keep paying ~800Mi for a comparison nobody can see. This
  is the "harvest" half of §5's Beyla decision; the "then decide" half is the
  #127 ledger update.
- **Clinvar-service dashboard (#29, existing).** The only backend with an
  ADR 0020 SLO row and no golden-signals dashboard, open since M5 and flagged
  in every review since 2026-08-11. Verified live: 12 dashboards, none for
  `clinvar-service`, while every newer M13 service got one. Re-flagged, not
  re-filed — #29 already carries the right scope; it needs to be done, not
  re-specified.

### 4. Decommission and the component ledger: make "keep" a dated decision, not a default

The mechanism for this already exists as #127 (a component budget and a
decommission rule) and is still open — this ADR feeds it rather than
inventing a parallel one.

- **Mimir (#135, existing).** The standing #120 "keep testing" override was a
  legitimate call and this ADR does not override it. But the audit's
  evidence — restarts accelerating to 71 (verified live), the artifact (the
  ADR 0038 write-up and article) already banked, Mimir now actively polluting
  the #125 critical alert, being unmonitored while being Prometheus's own
  LTS target, and #135's one stated keep-reason (the #128 grading corpus)
  having *inverted* now that 71 OOM events are a saturated corpus rather than
  a scarce one — makes the case materially stronger than at the last
  override. #135 is updated, not superseded: re-tie its trigger from the
  open-ended #128 dependency to a **near-term calendar date** (owner picks
  the date), because "keep until #128 no longer needs it" has quietly become
  "keep indefinitely," which #127's own AC exists to prevent. Decommission
  itself stays the owner's call and per ADR 0038's already-written rollback
  path; this ADR only makes the trigger real and checkable.
- **Beyla and Faro and VPA (#127, existing).** #127's AC already asks every
  experiment component for a stated conclusion criteria; this is the write-up
  of the three the audit named. Beyla: harvest-then-remove, tied to §3's
  dashboard-fix (once the A/B article is banked, Beyla enters the ledger with
  a removal trigger). Faro/frontend-rum: carries no data (the receiver runs
  for nothing) — ledgered as "remove or feed." VPA: shipped and consumed by
  nothing — ledgered with its real conclusion criteria, including the honest
  answer "keep in recommendation mode indefinitely, owner decision" if that
  is the real answer.

### 5. Record hygiene: reconcile once, then automate so it can't recur

- **One-time reconciliation (new).** Correct the five stale ADR status
  headers (`0010`/`0011` → `Superseded by NNNN` per the README convention;
  `0021`/`0022`/`0023`/`0025`/`0029` → `Accepted`), mark the ~30
  complete-but-unmarked backlog items (M0–M3 and much of M4–M6), and confirm
  the 2026-08-15 M12-mechanism correction (capacity/physics, not node count)
  actually landed in #67–#69's dependency text — the one instance of drift
  the audit flagged but did not itself re-verify. The failure mode here is
  benign (done work unmarked, not the reverse), but it makes the backlog's
  own "what's left" unreadable without cross-referencing.
- **Extend the doc-drift automation (new, follows #97).** #97 is Done — its
  CI check validates the component roster and the backlog's structural
  integrity (headings, contiguity, the four expected lines), but not that an
  item's status marker is consistent with its cross-references, which is the
  exact gap this audit found (#21a called "(done)" inside #45's dependency
  line but unmarked in its own entry; S1/S2 open despite the namespaces being
  gone). A new follow-on item extends #97's script to catch status-marker
  drift — closing the audit's §8(a) recommendation at the source rather than
  relying on the next review to find it by hand. New, not a reopening of the
  closed #97.
- **Triage the stale adamastorx#242 (new, P3, `good-first-issue`).** Open
  since 2026-08-10, CI green, orphaned — the project's own "open a PR and it
  moves" flow has one rotting exception (verified live). Close or merge it.

### 6. The Claude Code toolchain investment: turn trust-based rules into enforced ones

This is genuinely novel work for this project (zero hooks/skills/MCP today)
and gets the same rigor as any other item, not a vague "improve tooling"
placeholder. Three items, in the audit's own recommended order:

- **`PreToolUse` GitOps-mutation safety hook (P1).** `WORKFLOW.md`'s hard
  safety rule — never `kubectl apply/patch/delete` or `terraform
  apply/destroy` outside read-only inspection without explicit confirmation —
  is currently prose the model is trusted to honor. A `PreToolUse` hook in
  `.claude/settings.json` deny-lists mutating `kubectl`/`terraform` verbs
  unless a confirmation token is present, turning a trust-based safety story
  into an enforced one. This is the biggest miss the audit named and is
  itself article-worthy: "the platform is AI-built and AI-operated, with the
  safety rails themselves AI-enforced" is a fresh, owned angle for #129's
  queue. AC includes a real test — a mutating command is actually blocked
  without the token and actually allowed with it — not just a config diff.
- **`SessionStart` KUBECONFIG + gremlin hook (P2).** A `SessionStart` hook
  exports `KUBECONFIG` (the documented every-session footgun that "does not
  persist and is blocked from `~/.bashrc`") and surfaces the current
  known-gremlin list (e.g. the `root`-refresh ArgoCD tax) so it's read, not
  rediscovered. Removes a per-session friction the review series documents
  repeatedly.
- **Canary-drill and verify-live-Done Skills (P2).** Two of the project's
  most-repeated procedures become named, loadable Skills that encode the
  steps *and* the known gotchas: the canary drill cadence (#136 — literally a
  recurring, scripted procedure, with the whole-Service-scrape ambiguity
  gotcha) and the post-rebuild / verify-live-before-marking-Done discipline
  (#123, with the Cilium `toPorts`-uses-container-port trap and the
  `root`-refresh-first rule). Applied consistently instead of re-read each
  time.

MCP (a Prometheus/kubectl MCP server) and auto-memory are **deliberately out
of scope this milestone.** The audit ranks them below the three above, and
both add standing surface or a dependency — an MCP server is a new component
in spirit, which cuts against M17's zero-new-component discipline, and
`SESSION_STATE.md` already serves as a hand-maintained memory file adequately
for now. Recorded as considered-and-deferred, not overlooked.

### 7. The hardware migration: framed as an M7 restore drill, not folded into M17

The audit's §11 recommendation to migrate off the T460s is accepted on its
reasoning, re-checked here: the constraint's narrative dividend (ADR
0040/0041 — "my multi-node plan didn't survive `lscpu`," "my node's memory
is as tight as its CPU") is **already banked**, a story you cannot re-bank by
staying constrained; the ongoing cost is real and growing (memory 111%
overcommitted, 4–5Gi into swap at rest, Mimir OOMing every ~6h, #69's real
Nextflow pipeline permanently blocked); and — decisively — the *migration
itself is the next chapter of the exact story the constraint made valuable*
("I moved a live GitOps platform to new hardware — here's the RTO and what
didn't come back"), and it stays an owned-hardware story, so ADR 0035's
narrative survives. A cloud annex stays the wrong move for the reasons ADR
0040 §6 already gave.

**But the migration is not part of M17, and this is a deliberate structural
call.** M17 is "close the blind spots, zero new components." The migration is
the opposite shape: a major infra event that adds capacity and unblocks the
permanently-blocked M7 work (replicated storage #51, node-drain drills #52,
a real Nextflow pipeline #69, the Istio ambient mesh ADR 0040 named as a
"when hardware exists" benefit). Folding it into M17 would blur both. The
migration is therefore scoped as the **start of M7's own substrate arc** —
M7's long-standing "rebuild on the dedicated host" goal is what this is —
sequenced as a real drill, following the `flannel-restore.md`/#123 precedent
for how a risky infra change is planned before it is executed:

1. **Migration go/no-go decision + plan (P1, owner-gated, new).** The
   successor to #104's question, which PROJECT.md itself records as
   "open again in practice" after ADR 0040's capacity math superseded ADR
   0035's VM-interim decision. #104 stays Done (it recorded a real past
   decision); this new item records the current one. It decides go/no-go and,
   on go, pins down the one thing the audit left open: whether the new host
   is a genuine multi-node substrate (unblocking #51/#52 as well) or a single
   beefier node (which still retires the memory-pressure/OOM class and
   unblocks #69/mesh, but not the multi-node drills). Hard precondition, from
   the audit's §11 and non-negotiable: **preserve #94's 30-day Prometheus
   history across the move** — either migrate *after* #94's window closes
   (~2026-09-06) and its SLO-over-time report is written, or carry the PVC
   across with the same #49 PVC-copy discipline. A naive host move that
   resets that clock destroys the single most differentiated unpublished
   asset the project has.
2. **Pre-migration restore drill on the new host (P1, new).** The migration
   *is* a restore drill — run it as one, using #23a (Done) and the #123
   acceptance checklist, on the new host, before any cutover. Proves the
   restore path works on the new hardware and measures a real RTO, exactly
   the de-risking step the audit's two hard preconditions demand.
3. **Migration cutover (P1, new).** Execute the move — the live GitOps
   platform onto the new host, #94's history preserved per item 1's chosen
   method — conditional on the drill passing.
4. **Post-migration acceptance (P1, new).** Re-run #123's business-path
   acceptance checklist on the migrated cluster, confirm #94's retained
   history survived intact, and record the real end-to-end RTO and "what
   didn't come back" — the evidence pack for #129's migration article.

Items 2–4 are gated on item 1 landing "go" and on the new hardware being
physically available; item 3 on item 2 passing; all four on the #94-history
constraint in item 1. This is a complete planned sequence, not four items
that will definitely execute — the owner may collapse or re-sequence them,
but the drill-before-cutover discipline is fixed.

### 8. Sequencing: M17 opens now, item-by-item; the hardware arc is owner- and calendar-gated

- M17's runtime and record items have **no cross-milestone dependency** and
  start immediately, in parallel with whatever of M16 is still open. The
  front-of-queue quick wins are the stale-OOM alert gate (one line, live
  noise), `securityContext` (mechanical, highest concrete risk), #29
  (five reviews old, free), the record reconciliation (pure doc), and the
  `PreToolUse` safety hook (turns the core safety story real, article-worthy).
- The **Mimir decision (#135) and the hardware go/no-go (item 1)** are the
  two items with a real owner-decision component, not pure engineering, and
  are flagged as such so they don't stall silently behind the mechanical work.
- **M17 does not gate M11 (`sre-agent`)**, still sequenced after M15 per ADR
  0031 for its own reason, nor M16, which runs alongside. The one soft
  connection worth naming without making it a dependency: M17's hardware
  migration, once done, is what finally clears M7's hardware gate — and M7's
  substrate is what several long-blocked items (#51/#52/#69, the Istio mesh)
  have always waited on. That is stated as sequencing, not a new dependency
  either direction.

### 9. Explicitly out of scope, and why

- **A live error-budget / recording-rule layer.** The audit distinguishes
  "no burn-rate policy" (deliberate, closed under ADR 0021, restated under
  ADR 0031 §5 and ADR 0043 §6, and *not* reopened here — the traffic is still
  #45's self-generated workload-generator, the exact premise those closures
  were written against) from "no error budget computed at all." Computing an
  error budget you don't alert on, over self-generated traffic, is the same
  theatre burn-rate alerting would be; #94's SLO-over-time report is the real
  measurement deliverable and already exists. Deferred, considered.
- **A steady-state `api` latency alert.** Real gap (the recalibrated 500ms
  exists only as a canary gate), but traffic is ~0.4 req/s — a thin
  histogram — and the number it would use is what #137's #94-gated
  calibration produces. Naturally sequenced behind #94, not filed as a new
  M17 item; noted for #137's follow-through.
- **A Kafka broker-health dashboard/alert.** The 411 scraped `kafka_*` JMX
  series have no dashboard and under-replication/ISR/offline-partitions are
  invisible — a real idle-telemetry gap, but the audit's own §4 verdict ranks
  "make the existing signals consumable" (#29, beyla, backend health) above
  adding this, and it is lower value than the named three. Deferred, noted.
- **MCP and auto-memory** (§6) — deferred, considered, as stated above.
- **Extending Argo Rollouts to more services, Istio traffic canaries,
  reopening #21b** — all already ruled out for the consolidation phase by ADR
  0043 §6; unchanged here.

## Consequences

- **Zero added steady-state CPU/memory, zero new ArgoCD Applications** for all
  of M17 — the same shape M16 carried, extended into security, observability
  self-monitoring, record hygiene, and the toolchain. The hardware migration
  adds capacity, but it is scoped as M7's arc, not M17.
- **The project's own manifests get the hardening its third-party charts
  already have** — the `securityContext` gap the audit called the single most
  concrete unaddressed risk closes, with recorded exclusions where privilege
  is intrinsic (Beyla).
- **The one alert crying wolf stops** (recency gate), and the telemetry
  backends stop being a blind spot — the failing component (Mimir) no longer
  being the unmonitored one, whether it is kept-with-a-real-trigger or
  decommissioned.
- **`.claude/` gains its first hooks and skills** — the safety rule
  `WORKFLOW.md` states becomes enforced rather than trusted, and the
  most-repeated procedures become loadable. This is new capability for the
  project and a fresh, owned article angle for #129.
- **The record stops drifting silently** — a one-time reconciliation, then an
  automation extension so the next review doesn't have to find the same class
  of drift by hand. #97's remit widens to status-marker consistency.
- **#127, #135, and #29 are advanced, not duplicated** — the component
  ledger, the Mimir trigger, and the clinvar dashboard are existing items the
  audit re-motivated; this ADR feeds them rather than filing look-alikes.
- **The hardware constraint becomes documented history on a real cutover
  date** — the migration is planned as a restore drill with #94's history
  preserved as a hard precondition, and it is the next chapter of the exact
  narrative the constraint made valuable, executed as a drill rather than a
  scramble.
- **`docs/roadmap/backlog.md` is not edited by this ADR.** A follow-up pass
  mints the new items contiguously from the current backlog maximum and
  updates #29/#127/#135 in place, using this ADR's descriptions as the source
  rather than restating them from scratch.
