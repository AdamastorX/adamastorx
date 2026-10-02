# The agentic working model: what the experiment actually proved, and the scope it licenses — 2026-10-01

Sixth in the review series (`2026-08-06-staff-engineer-review.md`,
`2026-08-09-staff-engineer-review.md`,
`2026-08-09-hardware-constrained-strategy.md`,
`2026-08-11-staff-review-differentiation-and-article-strategy.md`,
`2026-08-15-operate-followthrough-and-m12-reality.md`,
`2026-08-21-staff-engineer-full-audit.md`). The previous five audited the
system. This one audits **how the system gets built** — a single owner-set
question: should the four-stage agentic pipeline tested this session become
the project's standing working model?

**Method and honest scope of evidence.** This review read the real repos on
this machine, the real plugin source on disk, and the real CI workflows. It
did **not** have cluster access and did **not** re-run the experiment. Two
things it is important to say up front, because they bound several findings
below:

1. **The experiment itself is taken on the owner's report.** The loop
   transcript, the RED run, the $0.37 cost computation, and the existence of
   PR `services#83` were not independently verified here. What *was* verified
   directly: the bug is still present on the local `services` `main`
   (`FinnhubWebSocketClient.java`, no `messageBuffer` reset in `onOpen`), and
   `FinnhubListener` is still `private final class` — so the visibility change
   the setup describes is real and was genuinely necessary.
2. **The local `platform` and `observability` checkouts are stale.**
   `.git/logs/HEAD` in both shows the last pull at epoch `1786047899` /
   `1786047910` — approximately **2026-08-06**, ~two months behind `main`.
   The local `observability` tree carries 6 runbooks; the 2026-08-21 audit
   counted 24. So **every CI-inventory claim below about `platform` and
   `observability` is as-of-2026-08-06 and must be re-checked against `main`
   before being acted on.** The `#117` runbook-coverage check the audit names
   as CI-enforced is not visible in either local tree; that is a limit of this
   review's evidence, not a claim that it is missing.

What this review verified first-hand: the plugin source and versions on disk
(`ralph-wiggum` 1.0.0, `mattpocock-skills` 1.2.3), the 37-skill bundle
inventory, the `.gitignore` state of all four repos, the
`check-resource-limits.sh` scope gap, the `kubernetes/` manifest inventory,
and the application-code finding in §9.

---

## 1. Verdict

**Adopt, narrowed — as a bounded technique for the Implement/Test steps, not
as a working model.** The pipeline's four stages are not one thing and should
not be adopted as one thing:

| Stage | Verdict | Why |
|---|---|---|
| 1. `grilling` (pre-convergence interview) | **Adopt, optional-to-recommended** | Genuinely new capability for this project; cheap; stateless; writes nothing |
| 2. Verification-first | **Already mandated — rename, don't adopt** | The project has done this since platform#35 and calls it the broken-fixture bar (#96/#97/#109/#147). The gap is coverage, not practice |
| 3. Ralph loop | **Adopt, tightly bounded** | The one real experiment is strong evidence for a narrow case and no evidence at all for the case it is usually sold for |
| 4. Human outer loop | **Unchanged, and load-bearing** | Already mandated by `WORKFLOW.md`. §9 is the evidence that it must stay |

The reason this is not "adopt" full-stop is the owner's own caveat, which is
correct and which I will not soften: **the loop converged in one iteration
because stages 1–2 had already removed every degree of freedom.** That is a
finding about stages 1–2, not about stage 3. The experiment measured the cost
of a *well-specified* task, and the answer — $0.37 — is a floor, not an
estimate. Nothing here licenses the "let Ralph run overnight" framing, and the
project's own coding principles ("no gold plating", "boring over novel") cut
against importing it.

The reason it is not "reject" is equally plain: the technique cost cents,
produced a diff identical to a human PR it had never seen, obeyed a
no-peeking constraint, and touched no file outside its allowlist. That is not
a thing to ban. It is a thing to bound.

## 2. The thing the experiment actually proved — and the thing it quietly disproved

Proved: **a task reduced to one falsifiable, machine-checkable assertion
converges in one iteration for cents.** That is a real result and it is worth
recording.

Not proved, and worth stating plainly because the write-up's headline invites
the wrong reading: **the "identical to `services#83`" result is a consistency
result, not a correctness result.** Two independent agents agreeing on a patch
is evidence that the patch is the obvious one, not that it is the right one.

And on this specific bug, the obvious patch is arguably the inferior fix. Read
off `services/market-data-ingestor/.../FinnhubWebSocketClient.java` on local
`main`:

- `messageBuffer` is a field of the **outer** class (line 97).
- It is referenced in exactly three places, **all inside
  `FinnhubListener.onText`** (lines 275, 278–279).
- A **fresh `FinnhubListener` is constructed per `connect()`** (line 175).

So the connection-scoped buffer is declared one scope too high. Declaring
`messageBuffer` inside `FinnhubListener` is a diff of the same size as
`setLength(0)` in `onOpen`, and it makes the entire bug class impossible by
construction rather than resetting after the fact. It also addresses something
the one-liner does not: a shared, unsynchronised `StringBuilder` mutated from
whatever thread the JDK's `WebSocket` delivers callbacks on, across
connection boundaries — the `onClose`/`onError` path calls
`scheduleReconnect()` while the dying socket's listener is still a live
object, so the one-line fix narrows the window rather than removing the class.

This is not a claim that `services#83` is wrong — it is in review and this is
input to that review. It is a claim about the *model*: **a loop pinned by a
single pre-written test converges to the minimal mutation that satisfies the
test.** The grilling stage was aimed at the task ("how do we prove this bug?")
and not at the fix ("where should connection-scoped state live?"), and the
verification-first stage then froze the design before that question could be
asked. The human review gate is what catches this. Which means:

> **"The test went green" is never a merge criterion.** The loop's stop
> condition is a gate on *the loop*, not a gate on *the PR*.

The project already has this rule (`WORKFLOW.md`'s Review step, the
Definition of Done's human-approval clause). It now needs restating, because
a loop is precisely the thing that makes it tempting to skip.

## 3. The HCL/YAML objection: the owner is right about the skill and wrong about the gap

The objection — *"quanto ao TDD tenho dúvidas se será aplicável, visto que
tenho muita infra e HCL ou YAML"* — is correct about the skill file and
incorrect about the project.

**Correct about the skill.** `mattpocock-skills`' `tdd/SKILL.md` is explicitly
built on vocabulary that does not exist in HCL or YAML: *"A **seam** is the
public boundary you test at"*, *"Test only at pre-agreed seams"*, *"mocks
internal collaborators"*. There is no function to call and no collaborator to
mock in `argocd/apps/loki.yaml`. The skill file does not port.

**Incorrect about the project.** The *discipline* does port, and this project
has been doing it for months under a different name. Read
`platform/scripts/check-resource-limits.sh`'s own header:

> *"This is what closes the actual gap — gateway/api/workers shipped with a
> memory limit but no CPU limit for months, and nothing caught it except an
> external review, not CI or code review."*

That is a falsifiable assertion over YAML, written because the absence of one
let a real defect live for months. And the project's own name for the stronger
version of this is already in the backlog's vocabulary: the
**deliberately-broken fixture**. `adamastorx`'s CI does not merely run
`check_backlog_structure.py` — it runs the checker against *four* fixtures
first (`valid.md`, `broken-duplicate-heading.md`,
`broken-swallowed-heading.md`, `broken-missing-label.md`) and fails the build
if the checker *passes* a broken one, with the comment *"the checker must
actually fail on the two real historical corruption shapes … before its
verdict on the real file is trusted."* `check-roster-drift.sh` does the same.
#96 set the bar, #97 and #109 met it, and #147's AC cites it by name.

**That is test-first for YAML and prose, already in production, already
CI-enforced.** The right move is not to adopt TDD. It is to name what exists
and notice where it is missing.

### Where it is missing, verified

`check-resource-limits.sh` is the counterexample sitting in the same repo as
the pattern:

1. **It has no self-test.** Unlike the two `adamastorx` checkers, nothing
   proves it can fail.
2. **It silently does not check `api` — the workload its own header names.**
   The glob is `kubernetes/*/deployment.yaml`. `kubernetes/api/` contains
   `rollout.yaml`, not `deployment.yaml` (`api` became an Argo Rollouts canary
   under M6/#46). Verified: `api`'s containers *do* set CPU and memory limits
   today (`rollout.yaml` lines 126–132 and 218–234), so this is a **coverage
   gap, not a live violation** — but the check has been vacuous for `api` since
   the Rollout migration, and its scope comment still claims otherwise. Every
   `CronJob` (the three postgres backups) is likewise unchecked.
3. **`nullglob` + the zero-files early `exit 0` means a layout change makes the
   whole check pass with no output anyone reads.**

This is the single most important technical finding in this review, because it
is exactly the failure mode of using a `yq` assertion as a loop's stop
condition: **a glob-scoped assertion can pass vacuously, and a loop pointed at
"make the check pass" is satisfied by a check that checks nothing.** For
infrastructure, the broken-fixture bar is not a nice-to-have. It is the only
thing that makes a stop condition trustworthy enough to hand to an unattended
loop.

### The per-layer answer: what exists, what is new, what is gold plating

| Layer | Already in CI (loopable stop condition) | Would be new | Verdict on the new thing |
|---|---|---|---|
| **Terraform** | `terraform fmt -check -recursive -diff`, `init -backend=false`, `validate` | `terraform test` (`.tftest.hcl`, `command = plan`, `assert` blocks) | **Gold plating now.** The Terraform here is one `null_resource` SSH provisioner — no variables-driven branching to assert on. Named trigger to revisit: the first real module with conditional logic, i.e. the multi-node substrate work (#51/#52) introducing node-count branching |
| **Helm-sourced ArgoCD Applications** | `scripts/render-helm-charts.sh` + `kubeconform` on rendered output — built *because* a Loki `replication_factor` and an otel-collector hidden-port misconfiguration both shipped undetected | `helm unittest` | **Wrong tool.** `helm unittest` tests charts you author; this repo authors none, it consumes upstream charts via `valuesObject`. The right escalation is a `yq` assertion over `rendered-charts/*.rendered.yaml` — which is what `check-resource-limits.sh` already is in shape |
| **Hand-written k8s manifests** | `kubeconform -strict` over `argocd/ bootstrap/ kubernetes/`; `check-resource-limits.sh` | `conftest`/OPA | **Gold plating, and a new dependency class.** Extending the existing `yq` script to assert `securityContext` fields across *all* workload kinds (fixing the glob gap in the same pass) does the same job with zero new tools — and makes the render-time half of **#142** a legitimate loop target |
| **Grafana dashboards + alert rules** | Could not verify current state (stale local checkout, see Method) | `promtool check rules` and `promtool test rules` | **The one new mechanism worth adding.** This is the single layer where the project keeps being bitten by errors only visible live: the `beyla-vs-manual` `job=` selector that renders nothing (#145), the #91 freshness-SLO `source=` blend trap, the stale-OOM recency gap (#143). `promtool test rules` is one static binary, zero runtime cost, and encodes exactly that class. Recommend it **rides #143/#144's AC**, not a standalone item — no gold plating, no new surface for its own sake |
| **Docs / ADRs / backlog** | `check_backlog_structure.py` (4 self-test fixtures), `check-roster-drift.sh` (self-tests incl. the #109 grace-period case) | nothing | Structural checks are loopable. **Prose judgement never is** — there is no falsifiable check for "is this ADR's reasoning right" |

So: **one new mechanism (`promtool test rules`, folded into existing items),
one real repair (`check-resource-limits.sh`), and nothing else.** The
preliminary answer's list of `terraform test` / `helm unittest` / `conftest` is
three new tool classes for problems this project does not have yet — which its
own coding principles forbid in those words.

## 4. The live-verification boundary, and why #149 is not the precondition

The boundary itself is not controversial: **#142's AC ("the pod comes up Ready
and its container `securityContext` is confirmed populated via `kubectl get
pod -o jsonpath`, not a manifest diff alone"), #123's business-path
acceptance, #153/#155's drill checklists, and the project's standing
"verify live before marking Done" rule are not loop targets.** They require a
real cluster, they mutate or observe real state, and their pass/fail involves
human judgement about what "came back".

The interesting question is what enforces that. Here I part from the
preliminary answer.

**Prose is not sufficient — but the reason is not the one usually given.** The
danger is not that a loop will decide to run `kubectl apply`. It is that a
loop **removes the human from the turn boundary**, which is where
`WORKFLOW.md`'s trust-based safety rule actually gets its enforcement today.
In normal operation a human reads every turn. Under a Stop hook that blocks
exit and re-feeds the prompt, nobody reads anything until the loop stops. The
rule degrades from *trusted but observed* to *trusted and unobserved*. That is
a genuine step change and it does need a non-prose control.

**But #149's hook is the wrong control to gate on, and making it a hard
precondition would be a mistake.** Three reasons:

1. **A stronger, cheaper control exists: deny the credential, not the
   command.** Run the loop in a `git worktree` with **no `KUBECONFIG` in its
   environment**. `SESSION_STATE.md` already records that `kubectl` on this
   machine does not default to a working config and that the stale
   `~/.kube/config` fails with real TLS errors. A loop with no credential
   cannot mutate a cluster regardless of what it decides to try, and the check
   is mechanical: `env | grep KUBECONFIG` is empty. A `PreToolUse` deny-list
   is a pattern match on command strings; absence of a credential is not.
2. **#149's scope is narrower than the loop's risk surface.** A deny-list on
   mutating `kubectl`/`terraform` verbs says nothing about **`gh pr merge`**,
   `git push --force`, `helm upgrade`, `rm -rf`, or a `curl` to the real ntfy
   topic. "The agent never merges" is a Definition-of-Done-level rule enforced
   today only by prose — and a loop is exactly the thing that would violate it
   unobserved. **Recommendation: widen #149's AC by three patterns (`gh pr
   merge`, `git push --force`, `helm upgrade/install/uninstall`) rather than
   filing a sibling hook** — a second hook in the same `PreToolUse` Bash
   matcher invites the merge-vs-overwrite collision §7 documents.
3. **Gating on #149 creates the exact pressure this review exists to refuse.**
   #149's PRs (`platform#202` + `adamastorx#332`) are open, unreviewed, and
   part of ~9 parked implementation PRs after a one-month interruption. Making
   the working model depend on them, in the week of a talk, manufactures a
   reason to merge an unreviewed *security* hook fast. No.

**The call: two gates, not one.** Credential absence is the gate for *starting*
(available today, no merge required). #149-widened is the gate for *widening* —
i.e. for any loop whose prompt could plausibly want cluster access. Under the
first gate, that set is empty, so nothing is blocked on the parked PRs and
nothing is rushed through review.

## 5. Relationship to the existing process — specifically

Vague "complements the existing process" is not useful, so:

**`WORKFLOW.md`'s loop is not superseded. It is amended in three named places
and otherwise untouched.**

- **Design** gains `grilling` as a named optional pre-step. It does **not**
  change the architect-agent rule, and this should be restated verbatim rather
  than implied: *"Design decisions with rejected alternatives worth
  remembering go through the `architect` agent — the session driving the issue
  does not make those calls inline, even when it has an opinion."* Grilling is
  stateless and writes no files; it produces an answered question list, not an
  ADR. It **feeds** the architect agent and cannot replace it. The failure mode
  to name explicitly: a grilling session that ends in "shared understanding"
  and then implements, skipping the ADR, because the understanding felt
  settled.
- **Implement / Test** gains the bounded verification loop as an *allowed
  technique*, with preconditions living in a runbook, not in `WORKFLOW.md`
  prose.
- **Safety** gains the loop clause (no credential in the loop's environment, no
  live-verification stop conditions, `--max-iterations` mandatory).

**The agent-delegation table does not change.** A loop is a technique available
to the delegated agent (or to the main session on the lightweight path). It is
not a persona and must not get a table row. Adding a "loop" agent would be the
framework-for-a-problem-you-don't-have-yet this project's principles forbid.

**#149 / #150 / #151 are not subsumed. Two of the three need their ACs
changed, and one of those is a real conflict between parked PRs and this
model:**

- **#149 — priority rises, AC widens.** It becomes the gate for widening loop
  scope (§4). Add `gh pr merge`, `git push --force`, and `helm
  upgrade/install/uninstall` to the deny list.
- **#150 — genuine conflict, must change.** Its AC currently says *"a
  SessionStart hook … that **exports KUBECONFIG** to
  `platform/terraform/kubeconfig` (verified: a fresh session can run `kubectl
  get nodes` without a manual export)"*. **That directly breaks §4's
  credential-absence control** — it would hand cluster credentials to every
  iteration of every loop in that repo. #150 should **surface the kubeconfig
  path** (and the gremlin list) rather than export the variable, or suppress the
  export when a loop state file is present. The first is simpler and better.
  This is the single most valuable concrete finding for the parked-PR review
  queue.
- **#150 also gains a reason it does not currently have.** The Ralph state file
  `.claude/ralph-loop.local.md` is cwd-relative and is deleted only on the
  hook's own exit paths; an interrupted session leaves it, and the *next,
  unrelated* session in that directory gets its exit blocked and the dead
  loop's prompt re-fed. Surfacing a stale state file at `SessionStart` is a
  real safety function, not a convenience — a better justification than the one
  #150 carries today.
- **#151 — unaffected in content, reframed in kind.** Both its Skills (canary
  drill, verify-live-Done/post-rebuild) encode **human-gated live procedures**.
  They are explicitly *not* loop targets, and that sentence belongs **inside
  the skill files**, so a future session cannot innocently wrap them in a loop.

**New work this review creates:** one backlog item for the
`check-resource-limits.sh` repair (self-test fixtures + all workload kinds,
§3), `promtool test rules` folded into #143/#144's ACs, and a
`.gitignore` line in four repos (§7). Nothing else. ADR 0044 already committed
four toolchain items whose PRs are unmerged; adding more before those land is
the gold plating the principles forbid.

## 6. Rejected alternatives

Recorded per `docs/adr/README.md`'s requirement, with the reason, not just the
rejection.

1. **Status quo — interactive prompting, no loops.** Rejected. The
   verification-first half is not a new practice to accept or decline; the
   project already does it (§3) and declining to *name* it is what let
   `check-resource-limits.sh` go vacuous for `api` unnoticed. And a technique
   that cost $0.37 and produced a human-equivalent diff is not bannable on this
   evidence — only boundable.
2. **Ralph loops without the grilling and verification stages.** Rejected on the
   experiment's own caveat: one-iteration convergence happened *because* stages
   1–2 removed the degrees of freedom. Without them, the published trade-off is
   $50–100+ per 50-iteration run against a gameable stop condition. Adopting
   stage 3 alone is adopting the expensive half and discarding the half that
   made it cheap.
3. **Build the project's own equivalents instead of adopting third-party
   skills.** Rejected now; kept as a named candidate for `grilling` **only**.
   The behaviour this project actually wants is "grill me, then hand the
   answered tree to the `architect` agent and write an ADR" — project-specific,
   and something the generic skill structurally cannot do. But ADR 0044 already
   has three unmerged toolchain items; building two more skills before those
   land is gold plating.
4. **Vendoring the third-party skills into the repos rather than installing from
   a marketplace.** Rejected. `grilling/SKILL.md` is 28 lines of prompt; the
   Ralph Stop hook is 178 lines of bash. Vendoring makes this project the owner
   of a security-relevant shell script with no upstream fixes, and imports
   licence/provenance tracking for a net loss at that size. **Named
   counter-condition:** vendor if the marketplace entry changes hands, loses its
   licence, or the Stop hook starts doing anything beyond re-feeding a prompt.
5. **`loop-me` and the rest of the 37-skill bundle.** Rejected. `loop-me`
   creates `workflows/*.md` and `NOTES.md` as top-level workspace directories —
   new repo surface for a workflow-design exercise the backlog already serves.
   `git-guardrails-claude-code` is actively incompatible (§7). The rest are
   unevaluated and unsanctioned.
6. **User-scope plugin installation (`~/.claude/settings.json`).** Rejected.
   Invisible to review, drifts per machine, and a project whose entire thesis
   is that configuration lives in Git should not keep its operator toolchain
   outside it. Project scope, committed, is the reviewable artifact.
7. **Making #149 a hard precondition for any loop use.** Rejected in favour of
   credential absence (§4) — a stronger control that is available today and that
   does not manufacture pressure to merge an unreviewed security hook before a
   talk.
8. **Running the loop in the shared repo checkouts.** Rejected; `git worktree`
   mandatory. `.claude/worktrees/` is already gitignored in every repo and is
   already this project's own pattern for exactly this.
9. **Enabling the plugins in `platform` and `observability` for symmetry.**
   Rejected. Blast radius in `platform` is the cluster. Enable where a real loop
   target exists and passes the preconditions, not for tidiness.

## 7. Risks, stated

Each of these was verified against the plugin source on disk, not inferred.

- **Cost.** $0.37 is a 1-iteration loop, 3-line diff, one Maven module. It is a
  floor. The real multiplier here is specific and worth naming: this project's
  natural Java stop condition is `./mvnw -pl <module> -am test`, and `-am`
  rebuilds dependencies — **iteration cost scales with module depth, not diff
  size.** Controls: `--max-iterations` ≤ 15, one loop per vertical slice.
- **The gameable promise.** Verified in `stop-hook.sh` lines 115–127: literal
  string compare after whitespace normalisation, first `<promise>` tag only. The
  anti-lying instruction is an `echo` in `setup-ralph-loop.sh` (lines 188–201)
  — advisory text, not a control. Control: the human re-runs the check; the
  promise is never evidence of record.
- **Unlimited is the default.** Verified: `MAX_ITERATIONS=0` is the initialised
  default and `0` means unlimited; the setup script's own output says *"WARNING:
  This loop cannot be stopped manually!"* Control: `--max-iterations` mandatory
  and explicit, never 0.
- **Stale state file hijacks the next session.** `.claude/ralph-loop.local.md`
  is read cwd-relative and removed only on the hook's own exit paths. An
  interrupted session leaves it; the next session in that directory has its exit
  blocked and the dead loop's prompt re-fed. Controls: `/cancel-ralph`, and the
  `SessionStart` surfacing in §5's #150 change.
- **An untracked file in `.claude/`, one `git add .` from being committed.**
  Verified: **no repo gitignores `.claude/ralph-loop.local.md`** — all four list
  only `.claude/worktrees/`. This is the identical shape to the 2026-08-21
  audit's own LOW finding about the stray editor swap file ("a swap file is one
  `git add .` away from being committed"), and `WORKFLOW.md` already states the
  principle for worktrees. Four one-line `.gitignore` additions.
- **Loops against infra.** §3's `check-resource-limits.sh` finding is the
  concrete risk: a vacuous assertion is a satisfied stop condition. Control: no
  infra check may serve as a loop stop condition unless it has been observed to
  fail — the broken-fixture bar, made mandatory rather than idiomatic.
- **Plugin and skill sprawl.** One `enabledPlugins` line enables **37 skills**
  (verified by count in the marketplace tree), several of which conflict with
  this project's own rules. The decision is per-bundle, not per-skill, which is
  itself the argument for a short *sanctioned* list and an explicit "everything
  else is a decision, not a default."
- **A third-party skill that rewrites this project's hook configuration.**
  `git-guardrails-claude-code` is model-invocable, writes
  `.claude/settings.json`, installs a `PreToolUse` Bash hook in **the same slot
  #149 needs**, and **blocks `git push`** — which would break this project's
  mandated branch → PR flow outright. This is the single sharpest supply-chain
  finding: not hypothetical, not a CVE, just a well-intentioned skill in an
  enabled bundle whose effect is to break a Definition-of-Done rule and collide
  with a parked PR.
- **Supply chain generally.** Both plugins execute as the operator with the
  operator's credentials — a strictly larger blast radius than any in-cluster
  component this project runs. The Ralph plugin's Stop hook executes on **every
  session exit** in any repo where the plugin is enabled, including when no loop
  is active (it early-exits 0 — verified, lines 15–18 — but it does run). A
  marketplace refresh can change that script with no PR, no CI, and no diff
  anyone reads. Controls: project scope only; versions recorded (`ralph-wiggum`
  1.0.0, `mattpocock-skills` 1.2.3, read off disk 2026-10-01); a refresh treated
  as a reviewable change on the same footing as a Renovate minor bump; enabled
  in two repos, not four.
- **The talk deadline.** It is a real motivation and it is distorting two
  specific decisions, which this review refuses on the merits: (a) merging
  #149/#150's parked PRs unreviewed to complete the story — refused in §4; (b)
  enabling the plugins in all four repos so the talk can claim uniform adoption
  — refused in §6.9. And the honest version of the general point: **this model
  is unusually demo-friendly, and that is a reason to be more suspicious of it,
  not less.** A $0.37 one-iteration convergence that matches a human PR is a
  great slide. It is also n=1 on the easiest possible task. The ADR is
  deliberately `Proposed`, not `Accepted`, so that the talk cannot cite it as
  settled standing practice.
- **Category risk in `PROJECT.md`.** The "Explicitly excluded — do not introduce
  without an ADR overturning this" list (Vault, Crossplane, Backstage) and the
  approved stack are about **runtime platform components**. Claude Code plugins
  are not that: they add zero cluster surface and cannot be ArgoCD-managed.
  Filing them into the approved stack would be a category error that makes both
  lists less useful. They need their own short section with its own rule — which
  is what ADR 0046 §Decision.6 specifies.

## 8. What the evidence does and does not license

**Licenses:**
- That a task reduced to one falsifiable, machine-checkable assertion converges
  in one iteration at trivial cost, in Java, in this codebase.
- That the no-peeking and file-allowlist constraints were honoured in this run.
- That stages 1–2 are the load-bearing part of the pipeline.

**Does not license:**
- Any claim about **multi-iteration behaviour**. Zero multi-iteration runs were
  observed. In particular the most dangerous case is entirely untested: a loop
  that *cannot* make the check pass and spends 15 iterations progressively
  degrading the codebase while looking for a way through. `--max-iterations`
  bounds how many times that happens, not whether it happens.
- Any claim about **infra or YAML targets**. None were tested. Every statement in
  §3 about render-time checks as loop targets is reasoning from the shape of the
  checks, not from a run.
- Any claim about **cost at scale** (§7).
- Any claim about **output quality**. §2 is the counterweight: the loop produced
  the obvious patch, not the better one, and so did the human PR.
- Any claim about **other work classes**. n=1, in the one class (Java unit tests)
  where this technique is best understood industry-wide, on a 3-line single-file
  fix, with a known-good reference answer already existing in a PR.

**The appropriate response to n=1 is a trial with a review date, not a standing
practice.** ADR 0046 §Decision.8 sets one: five real recorded runs in
`docs/operations/` (the #124 operations log already exists and is the right
home) or 2026-12-01, whichever comes first, recording iteration count, cost,
whether human review found a defect the check missed, and whether a promise was
ever emitted falsely. That is ADR 0044 §4's own rule — *"make 'keep' a dated
decision, not a default"* — applied to this project's own tooling instead of to
Mimir.

## 9. Where I disagree with the preliminary answer

Stated plainly, since this review's value is in the disagreements:

1. **"The discipline ports even though the skill file doesn't" — agreed, but
   incomplete.** The stronger and more useful claim is that **this project
   already named the discipline** (the deliberately-broken fixture, #96/#97/
   #109/#147) and the gap is *coverage*, not practice. Framing it as "we should
   start doing verification-first for infra" understates what exists and
   misdirects the work.
2. **The list of real equivalents is three-quarters gold plating.**
   `terraform test`, `helm unittest`, and `conftest`/OPA are all rejected for
   now, each for a specific structural reason (§3). Only `promtool test rules`
   survives, and it should ride #143/#144 rather than be filed as new work.
3. **`check-resource-limits.sh` is not purely the success story it was offered
   as.** It is also the counterexample: no self-test, and vacuous for `api`
   since the Rollout migration. That makes it the best possible teaching
   example for *why* the broken-fixture bar must be mandatory for infra loop
   targets — but the write-up has to include the second half.
4. **#149's hook is not the precondition for loop use.** Credential absence is
   stronger, available today, and avoids manufacturing pressure to merge an
   unreviewed security hook under a deadline. #149 is the gate for *widening*
   (§4).
5. **A conflict the preliminary answer did not surface: #150 as currently
   specified breaks the control §4 depends on.** A `SessionStart` hook that
   exports `KUBECONFIG` hands cluster credentials to every loop iteration.
   #150's AC must change.
6. **The experiment's headline result is weaker than it reads.** "Identical to
   `services#83`" is consistency, not correctness, and on this bug both agents
   picked the patch over the structural fix (§2).

## 10. Recommendations, ranked

1. **Adopt narrowed, per ADR 0046** — `Proposed`, with the §Decision.8 review
   trigger. One line each in `WORKFLOW.md`'s Design/Implement/Safety sections;
   the preconditions live in a new `docs/runbooks/verified-agentic-loop.md`,
   which is exactly what that folder's README reserves itself for.
2. **Four `.gitignore` lines** (`.claude/ralph-loop.local.md`). Smallest
   possible fix for a verified real gap, in the same class as a finding the
   project has already acted on once.
3. **Commit the two `settings.json` files** as the reviewed artifact, and do not
   create them in `platform`/`observability`.
4. **Change #150's AC before its PR is reviewed** — surface the kubeconfig path,
   do not export the variable; add stale-loop-state-file surfacing. This is the
   one parked PR whose spec the new model breaks.
5. **Widen #149's AC by three patterns** (`gh pr merge`, `git push --force`,
   `helm upgrade/install/uninstall`) and keep it P1 as the widening gate.
6. **Repair `check-resource-limits.sh`** — self-test fixtures, all workload
   kinds including `Rollout` and `CronJob`, header comment corrected. Natural
   home for #142's render-time half.
7. **Add `promtool test rules` to #143/#144's ACs**, not as a new item.
8. **Add the "not a loop target" line inside #151's two skill files** when they
   are written.
9. **Re-verify §3's `platform`/`observability` CI inventory against `main`**
   before acting on it — the local checkouts are ~2026-08-06 (see Method).

## 11. Review of this review

1. **Highest-confidence findings, verified directly by me:** the
   `check-resource-limits.sh` glob gap against `kubernetes/api/rollout.yaml`;
   the missing `.gitignore` entry in all four repos; the Ralph Stop hook's
   literal-string promise comparison and unlimited default; the
   `git-guardrails-claude-code` `git push` block and `settings.json` write; the
   37-skill bundle count; the `messageBuffer` scope finding in §2; the
   self-test-fixture pattern in `adamastorx`'s CI. All read off real files on
   this machine.
2. **Carried on the owner's report, not verified:** the loop transcript, the
   RED run, the iteration count, the $0.37 cost, and PR `services#83`'s
   existence and content. The §2 finding stands independently of all of them
   (it is a read of `main`), but the headline convergence claim does not.
3. **Two-month-stale evidence, flagged rather than glossed:** the `platform` and
   `observability` local checkouts (~2026-08-06). Every §3 claim about those
   repos' CI is as-of that date. The audit's `#117` runbook-coverage check is
   not visible locally and I make no claim about it either way.
4. **No cluster access.** Nothing in this review was read off the running
   cluster. Unlike the previous five reviews, this one does not meet the
   project's own "verify live" bar — which is appropriate, because its subject
   is a process, not a system, but it should be said.
5. **My biggest uncertainty.** Whether the one-loop-per-vertical-slice rule
   (ADR 0046 §Decision.3) survives contact with a task larger than three lines.
   The `tdd` skill's own anti-pattern list says writing all tests up front is
   **horizontal slicing** — so a multi-slice task either violates that rule or
   needs N sequential loops, and nobody has run the N case. That is precisely
   what the §Decision.8 review trigger exists to measure, and I would not
   defend the rule on anything stronger than the skill file's own reasoning
   today.
6. **Where I expect to be wrong, if I am.** On `promtool test rules`. I am
   recommending one new mechanism on the strength of three past alert-logic
   defects, without having seen the current `observability` tree. If that tree
   already has rule tests, recommendation 7 is redundant and should be dropped
   rather than built.
