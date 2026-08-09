# Staff-engineer review — 2026-08-09

Independent review of all four repos (`adamastorx`, `platform`, `services`,
`observability`) against the owner's four stated objectives:

1. An observability pipeline fed with real data
2. Microservices / distributed systems depth
3. A lab/playground for state-of-the-art and established technologies
4. Articles (blog/Medium) to grow a public SRE reputation

Scope of evidence: all 38 ADRs, the roadmap/backlog (1,149 lines), the four
repos' CI pipelines (`adamastorx` now has one — see §7), the ArgoCD
app-of-apps (36 Applications), the alert rules in `argocd/apps/
prometheus.yaml` (18 alerts, 18/18 with runbooks — up from 11 and partial
coverage on 2026-08-06), the chaos fact packs, `docs/WHY.md`, and the
service source layout. Unlike the 2026-08-06 review, this one also used
live cluster access (`kubectl`) and live GitHub repo-settings access (`gh
api`) — several of this review's findings only exist because of that and
are noted as such.

---

## 1. Verdict

The project kept its own discipline under real velocity: 87 PRs merged
across the four repos since the last review (40 `adamastorx`, 33
`platform`, 8 `services`, 6 `observability` — see §10, the brief itself
that seeded this review undercounted this by more than half), in under
three days, and the standard of evidence didn't drop. Three real bugs
found live in Mimir, a real OOM found live in Beyla via `dmesg`, and a
wrong architecture decision on Faro caught and reverted before merge and
recorded honestly rather than silently fixed — that's the same culture
the 2026-08-06 review named as the actual product, still intact at this
pace.

The risks have shifted shape, not gone away:

- **Doc drift recurred a fourth time, and in a form the automation built
  specifically to stop it structurally cannot catch.** `overview.md`'s
  top-of-file status line still says M14/M15 are "not started" — false,
  M14 closed 2026-08-06 and M15 is ~85% closed. That's the instance the
  review brief flagged. This review found **two more, independent, stale
  claims in the same file**, neither previously flagged: it says "there's
  no kube-state-metrics on this cluster" (false since #92, 2026-08-07)
  and "3-day retention" for Prometheus (false since #94, 2026-08-07). All
  three are invisible to `check-roster-drift.sh` for the identical
  reason — it verifies component names are *mentioned*, not that prose
  claims about them are still *true* — and #97's own item text says so
  explicitly, in advance, as a deliberate scoping choice (§7.1-3, §10).
- **The drift-prevention CI itself isn't gating anything on
  `adamastorx`.** `adamastorx#102` shipped real structural checks
  (backlog numbering integrity, roster-mention drift) with real
  self-tests against the exact historical corruption shapes that produced
  them. Branch protection on `adamastorx`'s `main` has no required status
  checks at all — confirmed live, not assumed (§7.4). The fix for
  "process has failed twice" is currently advisory-only on the one repo
  it was built for.
- **M7's blocker changed shape, not size.** #104/ADR 0035 decided the
  real path (2 interim VM agents on the existing laptop, not a wait for
  hardware with no date) — genuine progress in decision-making. But #48,
  the Terraform work to actually provision them, is still P0 and
  completely untouched, and #49–#52/#59–#62 (Cilium, NetworkPolicy,
  replicated storage, node-loss drills, the whole Istio track) are still
  fully blocked behind it. "Blocked indefinitely on a purchase" became
  "blocked on a scoped, undone task with no date either" — better, but
  still the single largest concrete gap against objective 2.
- **Objective D's central gap is unchanged, and the pile behind the door
  is now much bigger.** #88 stays deliberately descoped; nothing is
  publicly reachable. Everything in this review's §2 — three real Mimir
  bugs, a real Beyla OOM, a reverted-and-corrected ADR — is real,
  differentiated content sitting behind `*.local.adamastorx.test` where
  no article can link it.
- **Renovate is deployed but not yet functionally proven, for a second
  reason its own status note doesn't name.** `#98`'s own honest note
  already flags one blocker (Actions can't create/approve PRs, a
  classifier-blocked setting). Live-checked: that's still `false` on all
  four repos. Also still `false` on all four, and not mentioned anywhere
  in the item: GitHub's repo-level "Allow auto-merge" setting, which
  `platformAutomerge: true` in `renovate.json` also depends on (§7.7).
  Zero Renovate-authored PRs exist yet on any repo.

## 2. What is genuinely strong (and should be named in articles)

- **The Mimir experiment is the best single piece of new content this
  window produced.** Three real bugs, found live, in sequence, on the
  same deploy: a `CreateNamespace` sync gap, `ingester.ring
  .replication_factor` silently defaulting to 3 in a mode that can only
  ever run 1, and a per-tenant series cap (150,000) below this cluster's
  real measured series count (~186,604) — plus a fourth, smaller gap
  found and *deliberately left unfixed* as documented evidence
  (`server.address` label rejected by Mimir's stricter remote-write
  validation) rather than quietly patched around. The write-up's
  conclusion — "not yet worth it as a standing piece of this cluster's
  real architecture" — is a real, negative result, kept deployed anyway
  as the completed experiment rather than torn down to match its own
  verdict. This is hypothesis-falsification-as-habit (the 2026-08-06
  review's own §2 framing) still working at full strength.
- **Beyla's OOM (backlog #102, `platform/argocd/apps/beyla.yaml`) is a
  real incident, not a demo.** Root cause confirmed by reading the
  owner's own `dmesg`, not guessed; a live `kubectl patch` was silently
  reverted by ArgoCD's own selfHeal mid-diagnosis (a real, previously
  seen gremlin class recurring in a new context); a second live patch
  chased a red herring (AppArmor ptrace-DENIED noise) before the real
  fix (limit → 1Gi) was committed to git, because the live patch alone
  didn't stick. Verified stable post-fix, not assumed.
- **The Faro decision was wrong once, and that's recorded, not
  papered over.** ADR 0037's own "First pass (reverted)" section states
  plainly that the first analysis concluded self-hosting needed new
  Loki/Tempo infrastructure without checking `platform/argocd/apps/
  {loki,tempo,alloy}.yaml` — which already existed — first. Caught before
  merge, corrected, and the wrong reasoning kept in the ADR rather than
  silently replaced with the right one. Genuinely rare in any real
  engineering org, let alone a portfolio project.
- **#97's build quality is the right way to fix a doc-drift class.**
  Both checks (`check_backlog_structure.py`, `check-roster-drift.sh`) are
  proven against fixtures reproducing the *actual* historical corruption
  (#87's duplicate heading, #79's swallowed heading, #83's unmentioned
  component) before being trusted against the real files — the same bar
  #96 (event-contract schemas) sets for itself. The item's own text is
  explicit about what it chose *not* to build (a fuzzy "milestone marked
  Done vs. still-called-unbuilt" NLP-ish cross-check) and why — and that
  stated boundary is exactly where this review's own drift finding (§1,
  §7) landed. A scoping decision that predicted its own future gap in
  writing is worth naming as good practice, not just a miss.
- **18 alerts, 18 runbooks, 1:1** (`observability/runbooks/*.md` against
  `platform/argocd/apps/prometheus.yaml`'s `alert:` lines) — up from 11
  alerts and partial coverage on 2026-08-06. #22's original AC ("a real
  first-response doc per alert") is now actually met, not "partial" as
  `overview.md` still, correctly, describes it for the pre-M13 subset.
- **`docs/WHY.md` (#31) is good, not just done.** It distills four
  recurring bug classes across the project's real history (namespace-
  scoped PVCs hit twice, a Helm idempotency footgun, HikariCP/Kafka
  blocking-call hangs, the ArgoCD stuck-sync gremlin) rather than
  restating the README's feature list, and it's linked from the README's
  first screen. Half a day, as the prior review estimated, and it reads
  like it was worth exactly that.
- **`workers` scale-to-zero (#113) shipped with a race-safe gating
  expression, verified live and organically** — not a synthetic test:
  `minReplicaCount 1→0`, `WorkersConsumerMissing` re-gated on real
  replica count so a legitimate scale-to-zero can't false-positive as a
  stuck consumer, the exact gap #76/`overview.md` had named as the
  reason scale-to-zero was deferred in the first place.

## 3. Objective A: observability pipeline fed with real data

**A1 (M13's own surface) — closed for real.** #90 is genuinely done:
dashboards, consumer-lag alerts on `aggregator`/`sentiment-analyzer`, SLO
rows, and — a real bug found shipping the fix itself — a PromQL escaping
error (`\.` needing to be `\\.`) that silently left two new rules inert
while ArgoCD stayed green throughout, caught by querying `/api/v1/rules`
directly rather than trusting sync status. This is the right way to close
a gap the prior review called P0.

**A2 (long-term storage / SLO-over-time report) — real progress, still
not delivered, and now carries a live operational cost the backlog
doesn't name.** Retention config is real (`30d`, `platform#125`), but the
PVC resize needs a delete+recreate `local-path` doesn't support without
one, and the owner declined it (documented honestly in #94's own status
line). Live-checked, not assumed: the `prometheus` ArgoCD Application is
**currently, persistently `OutOfSync`** — `kubectl get pvc -n prometheus
prometheus-server` shows `2Gi` live against `16Gi` desired in git
(confirmed against `argocd/apps/prometheus.yaml` line 481). This isn't
just "the report needs 30 more days" — it's a standing GitOps drift with
no expiry, and there is no alert anywhere in `prometheus.yaml` for "an
Application has been `OutOfSync` for N hours," a genuinely new finding
this review's live cluster access surfaced. Given ADR 0003 makes ArgoCD
the sole GitOps entrypoint, an Application silently stuck out of sync
indefinitely is exactly the kind of thing the project's own standard
(never ship a component without its alert) would flag anywhere else.

**A3 (kube-state-metrics/node-exporter) — done, but `overview.md` still
says the opposite.** See §1 and §7.2.

**A4 (blackbox synthetic monitoring) — done** (`#93`,
`blackbox-exporter`, own dashboard, own runbook).

**A5 (correlation triangle: exemplars) — unchanged, still open.** #19a
is exactly where the 2026-08-06 review left it: unclaimed, P2, no status
note. Not a regression, just not picked up.

**A6 (frontend RUM / Faro) — done, and the ADR is honest about its own
limits.** ADR 0037 states plainly: "this is a single-operator lab
project... nothing here should be read as real-user monitoring at
scale." That's the right caveat, and it sharpens rather than closes
objective D's gap — Faro instruments real browser sessions, but every
session behind `*.local.adamastorx.test` is the owner's own or
`workload-generator`'s. The RUM *pipeline* is real; the *R* in RUM still
isn't, and can't be until #88 changes.

## 4. Objective B: microservices / distributed systems

**B1 (Kafka durability) — done, cleanly.** ADR 0032: persistent broker
storage chosen over Strimzi, verified live. Closes the #79/#80/#84/#85
incident class the prior review named as a recurring tax, not a one-off
fix.

**B2 (event contracts) — done, and CI-enforced, not just documented.**
`services/schemas/*.schema.json` (5 schemas) plus
`scripts/validate_contracts.py`, wired into `services/.github/workflows/
ci.yml` with the same "must fail on a broken fixture before trusting the
real check" discipline #97 and #96 both set. JSON Schema chosen over
Apicurio/Confluent Schema Registry, reasoning recorded (ADR 0033).

**B3 (M7 hardware gate) — decided, not executed; the remaining gap is
now purely a scoping/execution one, and it's the largest gap against this
objective in the whole project.** ADR 0035 makes the real call (2 local
VM agents, not an indefinite wait) — this is the right decision and the
prior review's own B3 suggested almost exactly this. But #48 (the
Terraform work itself) is untouched, P0, and gates five further items
(#49 Cilium/Hubble, #50 NetworkPolicy, #51 replicated storage, #52
node-loss drills, plus the whole Istio ambient-mesh track at #59–#62).
Nothing here is a criticism of the decision — it's a flag that "decided"
and "unblocked" are not the same state, and the backlog's own P0 marking
on #48 already says this.

**B4 (blocking-call decisions, #43/HikariCP) — closed.** #105: cross-
referenced to ADR 0024's own Context section rather than re-litigated —
the decision was already made there, this item just states it plainly
where #43/HikariCP could find it.

**B5 (`workers`' honest job) — closed, cleanly.** #106: `workers`'
README now states plainly it's a log-only consumer serving as KEDA's
scaling target and the lag alert's subject, not a component that quietly
looks unfinished. A real gap was found in closing it, too — the backlog
annotation for #106 was missing even though the work had merged
(`services#65`); found and fixed mid-session per PR #123's own commit
message.

## 5. Objective C: lab/playground — technology breadth

Genuinely broad additions this window, each landing as a real experiment
with a real result, not a checkbox:

- **Beyla (eBPF auto-instrumentation) vs. manual OTel/Micrometer** — a
  controlled A/B almost nobody gets to run, plus a real incident along
  the way (§2).
- **Mimir (monolithic long-term storage)** — three real bugs, an honest
  negative conclusion, kept deployed anyway (§2).
- **Faro (frontend RUM)** — real, with its own honest scope caveat (§3
  A6).
- **Renovate** — infra is real and well-built (per-repo dry runs found a
  real bug: the `argocd` manager needs explicit opt-in even with
  `managerFilePatterns` set — 0 deps detected before, 33 after, covering
  every one of `platform`'s real chart pins). Functionally unproven: zero
  Renovate-authored PRs exist on any of the four repos as of this
  review, and two separate repo settings (not one) currently prevent
  automerge from working at all (§1, §7.7).
- **SOPS+age (backlog #100, ADR 0034)** — a real DR gap (unversioned,
  unrecoverable secrets) closed for the secrets that matter most,
  reasoned against ESO/sealed-secrets and rejected for stated reasons.
- **VPA (#101) — still correctly deprioritized**, not neglected: #77
  already did this project's own version of that comparison by hand
  (99%→63% CPU trim), and the backlog's own note says to sequence it
  last among hygiene items. Still open, still fine to leave open.
- **Off-node backup (#99) — still correctly deferred**, not neglected:
  needs a real object-storage account/credentials this agent can't
  create on the owner's behalf, a provider choice was offered, the owner
  chose to defer. This is the same class of honest blocker as Faro's
  first-pass Grafana Cloud dead end, just correctly identified before
  any wasted work this time.

## 6. Objective D: articles & SRE reputation

**D1 (the narrative doc, #31) — done, and good** (§2).

**D2 (public reachability, #88) — still the single biggest gap, now with
much more content stacked behind it.** Deliberately descoped by the
owner on 2026-08-06 — a real decision, not neglect — but every item in
§2 of this review is additional, real, differentiated content that
joined the pile since then with nowhere to link a screenshot to. The
gap's size, not its cause, is what changed.

**D3 (SLO-over-time report) — still not published, closer but now with a
concrete blocker named for the first time: the PVC hasn't actually grown
yet** (§3 A2). The article this unblocks is real and worth the wait; the
wait itself now has a stated, live-verified reason rather than just "30
days haven't passed."

**D4 (article-asset habit) — done for future incidents, honestly
incomplete for past ones.** #89: the standing habit (`observability-
engineer` persona, `chaos/README.md`) is real and shipped. Retroactive
capture for the three existing fact packs and the ADR 0028 flame graph
was checked live, not assumed away — this environment has no browser and
Grafana has no image-renderer plugin installed (confirmed by checking
directly), so the three existing fact packs stay text-only. A real,
stated gap, correctly left open rather than faked with a placeholder
image.

**D5 (`sre-agent`, M11) — still the most novel unbuilt item, and the
case for building it next just got stronger.** Untouched since the prior
review. The real incident inventory it would be graded against has grown
substantially in six days of calendar time... sorry, under three: three
Mimir bugs found live in sequence, a real Beyla OOM diagnosed through a
selfHeal false start and a red-herring detour, and a reverted-and-
corrected architecture decision on Faro. An agent graded against this
specific, growing, human-labeled incident set is a stronger pitch today
than it was on 2026-08-06.

**New: the Mimir/Beyla/Faro trio is a three-part series with the hard
part already done**, in the same shape the prior review's D6 named for
the M13 series: "the SLO-report I couldn't publish, and the one live
config bug that's blocking it" (A2) → "eBPF vs. hand-rolled OTel: what
you actually lose" (Beyla, including its real OOM) → "I made the wrong
call on self-hosting RUM, and here's the ADR proving it" (Faro). All
three already have their evidence pack in-repo.

## 7. Concrete defects found during this review

1. **`docs/architecture/overview.md`'s top-of-file status line is stale
   — the fourth confirmed recurrence of the #32→#83→[2026-08-06 review's
   own PR]→now drift class.** It states "M14/M15 (ADR 0031...) are
   scoped in the roadmap, not started." M14's #31 has been Done since
   2026-08-06 (`WHY.md`, PR #89); M15 is closed on the large majority of
   its items (`docs/roadmap/backlog.md`, §M15). `check-roster-drift.sh`
   cannot catch this by design — it verifies component *mentions*, not
   prose *status claims* — and #97's own item text names this exact
   boundary in advance as a deliberate scoping choice, not an oversight.

2. **The same file, same drift class, previously unflagged: line ~145
   still says "there's no `kube-state-metrics` on this cluster."** False
   since backlog #92 (`platform#115`, merged 2026-08-07) —
   `platform/argocd/apps/prometheus.yaml` has `kube-state-metrics:
   enabled: true` and `prometheus-node-exporter: enabled: true`
   (confirmed by reading the live file).

3. **Same file, same drift class, previously unflagged: line ~174 still
   says "3-day retention"** for Prometheus. False since backlog #94
   (`platform#125`, merged 2026-08-07); the live config is `retention:
   "30d"`. Three independent stale claims in one file that was refreshed
   as recently as `e05ca90` (2026-08-09) — that commit fixed a different
   stale claim (Mimir "remains a separate experiment") in the same pass
   and didn't catch these two, because nothing mechanical is checking
   prose accuracy, only component presence.

4. **The CI built to end this drift class isn't required to pass on the
   one repo it was built for.** `gh api repos/AdamastorX/adamastorx/
   branches/main/protection/required_status_checks` returns 404
   ("Required status checks not enabled") — verified live, twice, before
   writing this. `adamastorx#102`'s `ci` job (aggregating
   `backlog-structure` + `roster-drift`) exists and is well-built (real
   self-tests against the actual historical corruption shapes), but a PR
   that fails it can currently still merge. `platform` and `services`
   both correctly require `ci`.

5. **`observability` has zero CI of any kind** — no `.github/workflows/`
   directory at all, and consequently no required status checks either
   (branch protection returns the same 404). ADR 0006 ("per-repo CI,
   single required check") never scoped `observability` — it predates
   the repo's current shape and only decided `platform`/`services`/
   `adamastorx`. Not a regression, but a real, previously unexamined gap:
   the repo holding the chaos fact packs and runbooks this project's
   articles will lean on hardest has no automated check of any kind, not
   even a markdown/link check.

6. **ADR 0006's decision was reversed without an addendum.** It states
   plainly: "`adamastorx` gets no CI... Add it when the repo grows
   something executable that CI could actually catch." It did (#97), and
   `adamastorx#102` added real CI — but ADR 0006 has no addendum
   recording that reversal (`grep` across `docs/adr/*.md` for references
   to 0006 turns up only unrelated forward-references from ADR 0007-9,
   nothing pointing back). This is the exact undocumented-decision-drift
   pattern the project treats as a defect everywhere else (ADR 0011's
   addendum superseding it via 0032, ADR 0023 vs. 0024, Faro's own
   reverted-and-recorded first pass in ADR 0037 itself) — just not
   applied to its own process ADR.

7. **Renovate's automerge is blocked by a second setting its own status
   note doesn't name.** Backlog #98 already documents one real blocker:
   "Allow GitHub Actions to create and approve pull requests" is
   classifier-blocked, confirmed still `false` on all four repos live
   (`gh api repos/AdamastorX/<repo>/actions/permissions/workflow --jq
   .can_approve_pull_request_reviews`). Separately, and not named
   anywhere in the item: `renovate.json`'s `"platformAutomerge": true`
   requires GitHub's repo-level "Allow auto-merge" setting, which is also
   `false` on all four repos (`gh api repos/AdamastorX/<repo> --jq
   .allow_auto_merge`, verified live). Fixing the first blocker alone
   will not make automerge work; both need flipping, and as of this
   review zero Renovate-authored PRs exist on any repo to have tested
   either.

8. **Live cluster, previously unexamined: `prometheus`'s ArgoCD
   Application is currently, persistently `OutOfSync`**, not because of
   the known/accepted Bitnami-Secret-regeneration pattern (the other five
   `OutOfSync` apps — `clinvar-postgresql`, `grafana`, `kafka`,
   `postgresql`, `redis` — are all that, confirmed by inspecting each
   Application's resource-level diff, all Secrets) but because
   `prometheus-server`'s PVC is `2Gi` live against `16Gi` desired in git
   — a direct, ongoing consequence of backlog #94's declined PVC
   recreation, with no expiry and no alert covering "Application stuck
   `OutOfSync`." See §3 A2.

## 8. Suggested sequencing (next ~2 weeks, given the pace this window set)

1. **Fix the three `overview.md` stale claims (§7.1-3) and make
   `adamastorx`'s `ci` job a required branch-protection check (§7.4)** —
   under an hour combined, and it's the difference between the drift
   automation being real and being decorative.
2. **`#48`: provision the interim VM agents via Terraform** — the single
   highest-leverage unblock in the backlog; five further P1 items and
   the entire Istio track wait on it, and the decision (ADR 0035) is
   already made.
3. **Force the Prometheus PVC recreation** the owner already declined
   once, once the owner is ready to lose the ~3 days of retained data —
   closes §7.8's live drift and starts the real clock on the SLO-over-
   time report (D3).
4. **Flip both Renovate-blocking settings** (§7.7) and let it run
   unattended for a week before trusting the "Done" status on #98 as
   more than infra-deployed.
5. **Add an `observability` CI check** — even a cheap one (markdown
   lint, link check, or a chaos-fact-pack structural check in #97's own
   style) closes §7.5 without inventing new ceremony.
6. **Add an ADR 0006 addendum** recording the CI reversal (§7.6) — five
   minutes, and it's the kind of small honesty this project's own
   culture depends on being applied consistently, including to its own
   process decisions.
7. **`sre-agent` (M11)** — the backlog dependencies (#45 traffic, #21
   alerts) are long since satisfied and the graded incident set (Mimir,
   Beyla, Faro, all three chaos scenarios) is now rich enough that this
   is no longer blocked on "not enough real incidents to grade against."
8. **Revisit `#88`** once #48 and the sre-agent both have something to
   show — the owner's 2026-08-06 descoping was a real decision, not a
   permanent one, and the case for it (D2) gets stronger every week
   content accumulates behind the closed door.

## 9. What *not* to do

- Don't build a fuzzier prose-staleness checker to catch §7.1-3 — #97's
  own text already reasoned through this tradeoff and chose the cheap,
  reliable mechanical check over a noisy NLP-ish one. The fix for §7.1-3
  is fixing the three lines and moving on, not more automation.
- Don't add more application services before #48 lands — M7's own
  sequencing logic (multi-node scheduling, PDBs, a CNI worth building
  policy on) doesn't change because the blocker's shape changed from
  "hardware" to "Terraform." The gate the 2026-08-06 review named still
  holds for the same reason.
- Don't chase Renovate's "Done" status further until it's produced at
  least one real merged PR under its own automerge — the infra is real,
  the proof isn't yet, and re-verifying that proof once both settings
  are flipped is cheap enough to just do rather than assume.

---

## 10. Review of this review (2026-08-09, before merge)

Every load-bearing claim above was checked against the real repos and,
where relevant, the real live cluster and real GitHub repo settings —
not accepted from the briefing that seeded this review, and not accepted
from this review's own first-pass reasoning either. Several things
changed as a result.

**1. The briefing that seeded this review significantly undercounted the
PR volume, and got the elapsed time wrong.** It described "roughly 40
merged PRs across the four repos... (14 platform, 20 adamastorx, 6
services)" over "six days." Counted directly (`gh pr list --state merged
--json mergedAt` filtered to `> 2026-08-06T22:15:38Z`, the real merge
timestamp of the PR that shipped the prior review): **87 merged PRs — 40
`adamastorx`, 33 `platform`, 8 `services`, 6 `observability`** — more
than double the stated total, with `platform` and `adamastorx` each off
by roughly 2x. And the elapsed time from the prior review's merge to now
is **under three days**, not six. Both numbers are corrected in §1 above.
Only the `observability` figure (6) matched exactly. This matters beyond
pedantry: a review that inherits a briefing's own unverified numbers and
repeats them is exactly the failure mode this project's culture exists to
catch, and it's worth naming plainly that the correction required
nothing more than running the same `gh pr list` command the briefing
itself said to use.

**2. The briefing's ADR count was off by one.** "ADR count went from ~30
to 39" — real count is **38** (`docs/adr/0001-*.md` through
`0038-*.md`, `ls docs/adr/*.md | grep -v README | wc -l`). Small, but
corrected in the scope line above rather than silently carried forward.

**3. One briefing claim about `overview.md` didn't hold up as stated,
and led to a better finding than the one described.** The briefing said
M14's #31-done status appears "a few lines below" the stale claim, in
the file's own body text. Reading the full file: there is no such
corroborating body text — the M14/M15 line is a single, isolated,
one-line status statement with no contradicting prose elsewhere in the
file. What *is* true, and stronger evidence than what was described: the
same file has **two entirely separate stale claims** the briefing didn't
mention at all (§7.2, §7.3), found by reading the file in full rather
than searching for the specific phrase the briefing pointed at. Chasing
the specific claim as written would have produced a weaker, arguably
inaccurate finding; reading the source directly produced three real ones.

**4. The "M7 blocker changed shape" framing was verified structurally,
not just narratively.** Read `docs/roadmap/backlog.md`'s M7 section in
full: #48 is real, P0, dependency-only on #23a (done), and five further
items (#49–#52, #59–#62) explicitly list #48 as a dependency in their own
`Dependencies:` lines. The "shape changed, size didn't" claim in §1 is
checkable against those dependency chains directly, not just against
prose.

**5. The live-cluster findings (§7.8, and the 93% CPU figure in §1's
predecessor context) were re-verified a second time before this document
was finalized**, specifically because they were the two claims most
likely to be stale by the time of writing (a live cluster can change
between the first check and the final one): `kubectl get pvc -n
prometheus prometheus-server` and `gh api .../branches/main/protection/
required_status_checks` were both re-run immediately before drafting §7,
not carried forward from an earlier check in this session. Both returned
the same result both times.

**6. What this review did not find, and looked for.** Checked whether
`observability`'s missing CI (§7.5) was itself a previously-recorded,
deliberate decision (an ADR excluding it, matching ADR 0006's pattern for
the other three repos) before flagging it as a gap — no such ADR exists,
confirmed by grepping all 38 ADRs for `observability` in a CI/workflow
context. Checked whether the `postgresql` Application's second
`OutOfSync` resource (a `ConfigMap`, not just the expected Secret) was a
new, separate finding worth its own defect entry — inspected it directly
and it fits the same known Bitnami-chart-checksum-annotation pattern the
other `OutOfSync` apps already show, not a new class; deliberately left
out of §7 rather than padded in as a fourth live-cluster finding that
doesn't add new information.
