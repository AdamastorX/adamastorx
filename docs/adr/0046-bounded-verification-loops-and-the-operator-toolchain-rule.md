# 0046. Bounded verification loops as an Implement-step technique, and a rule for the operator toolchain

Status: Proposed

## Context

On 2026-09-30 a four-stage agentic pipeline was tested for real against
backlog **#156** (`market-data-ingestor`'s `FinnhubWebSocketClient` not
resetting `messageBuffer` on websocket reconnect). The stages: (1) a
`grilling` interview that maps a task as a design tree and refuses to
proceed while an answer is open, from `mattpocock-skills@mattpocock`;
(2) verification-first — write the falsifiable check before the
implementation and make it, not the model's self-assessment, the stop
condition; (3) a Ralph Wiggum loop (`ralph-wiggum@claude-code-plugins`,
Anthropic's own marketplace) whose `Stop` hook blocks session exit and
re-feeds the same prompt with fresh context; (4) the branch → PR → human
review → merge outer loop this project already mandates.

The run: an isolated `git worktree` off a freshly-fetched `origin/main`;
`FinnhubListener` made package-private (visibility only, matching that
class's own existing test-seam convention); one failing regression test
committed as the loop's starting point, confirmed RED (`Wanted but not
invoked`; module suite 38 tests, 37 green); the loop restricted to
editing `FinnhubWebSocketClient.java`, forbidden from consulting other
branches/PRs, required to run `./mvnw -q -pl market-data-ingestor -am
test` to exit 0 before emitting its promise, `--max-iterations 15`.
Result: converged in **1 iteration**, 1 file, 3 lines
(`messageBuffer.setLength(0);` first in `FinnhubListener.onOpen`), no
out-of-scope edits, no-peeking constraint obeyed, **≈ $0.37** computed
from the session's own transcript at Sonnet 5 list prices, and the diff
**identical in mechanism and position** to the independently-written,
already-open PR `services#83` it never saw.

The owner asked whether this becomes the project's standing working
model, and raised one objection: *"quanto ao TDD tenho dúvidas se será
aplicável, visto que tenho muita infra e HCL ou YAML."*

The independent assessment is
`docs/reviews/2026-10-01-agentic-working-model-assessment.md`. Its three
load-bearing findings, each verified against real files on this machine
rather than carried from the experiment's own report:

1. **The owner's caveat is correct and decisive.** The loop converged in
   one iteration *because* stages 1–2 had removed every degree of
   freedom. The experiment measured the cost of a well-specified task
   ($0.37 is a floor, not an estimate) and says nothing about
   long-horizon looping. The untested, most dangerous case is a loop that
   *cannot* make its check pass and spends its iteration budget
   degrading the tree.
2. **This project already practises verification-first and already has
   its own name for it** — the deliberately-broken fixture (#96, #97,
   #109, #147). `adamastorx`'s CI runs `check_backlog_structure.py`
   against four fixtures and fails the build if the checker *passes* a
   broken one; `check-roster-drift.sh` does the same.
   `platform/scripts/check-resource-limits.sh` is a `yq` assertion over
   YAML written because the absence of one let `api`/`workers` ship
   without a CPU limit for months. The owner's objection is right about
   the `tdd` skill's vocabulary (seams, mocks, public interfaces do not
   exist in HCL) and wrong about the project: the discipline is already
   here. The gap is coverage, not practice — verified:
   `check-resource-limits.sh` has **no self-test** and its
   `kubernetes/*/deployment.yaml` glob **silently does not check `api`**,
   the workload its own header names, because `api` became an Argo
   Rollout (`kubernetes/api/rollout.yaml`) under M6/#46. `api` is
   compliant today; the check has been vacuous for it since. A
   glob-scoped assertion that can pass vacuously is exactly the wrong
   thing to hand an unattended loop as a stop condition.
3. **"Identical to `services#83`" is a consistency result, not a
   correctness one.** Read off local `main`: `messageBuffer` is a field
   of the *outer* class, referenced only inside `FinnhubListener.onText`,
   and a fresh `FinnhubListener` is constructed per `connect()`.
   Declaring the buffer inside the listener is a diff of the same size
   and makes the bug class impossible by construction, instead of
   resetting after the fact across a shared, unsynchronised
   `StringBuilder`. Two independent agents converged on the same *patch*
   and neither raised the *design* question — because grilling was aimed
   at the task, not at the fix, and verification-first then froze the
   design. The human review gate is what catches this.

Context that shapes the decision rather than the analysis: the owner
presents this project in a talk the week of 2026-10-05; work was
interrupted ~1 month (last `main` commit 2026-08-31, the #154 cutover)
leaving ~9 implementation PRs parked and unreviewed, including #142–#151;
ADR 0044 §6 already committed the project's first Claude Code toolchain
investment (#149/#150/#151), whose PRs are open and unmerged; and both
plugins are currently enabled at project scope in `adamastorx` and
`services` via new, **uncommitted** `.claude/settings.json` files.

## Decision

### 1. Adopt narrowed: a bounded verification loop is an Implement-step technique, not a working model

`WORKFLOW.md`'s `Understand → Design → Validate → Implement → Test →
Document → Review` **is not superseded and is not replaced.** What is
adopted is one named technique available inside Implement/Test, plus a
rename of a discipline already in production. The four stages are
decided separately because they are not one thing:

| Stage | Decision |
|---|---|
| `grilling` | Adopted, optional-to-recommended (§2) |
| Verification-first | Already mandated; renamed, not adopted (§4) |
| Ralph loop | Adopted, bounded by §3's eight preconditions |
| Human outer loop | Unchanged, and explicitly load-bearing (§3.8) |

**`Status: Proposed`, not `Accepted`, deliberately.** The evidence is
n=1, on a 3-line single-file Java fix, in the one work class where this
technique is best understood industry-wide, with a known-good reference
answer already existing. That licenses a bounded trial with a review
date (§8). It does not license a standing practice, and nothing —
including the talk — should cite this ADR as one.

### 2. `grilling` is adopted for Design, and does not touch the architect rule

`grilling` is stateless, writes no files, and produces an answered
question list. It is recommended before any item whose Acceptance
Criteria are not yet written to falsifiable precision, and before any
item heading to the `architect` agent.

**`WORKFLOW.md`'s architect rule is unchanged and restated rather than
implied**: design decisions with rejected alternatives worth remembering
go through the `architect` agent; the driving session does not make them
inline. Grilling **feeds** that agent and cannot replace it — the ADR is
still the artifact. The failure mode to guard against, named here so it
is not discovered later: a grilling session that reaches "shared
understanding" and then goes straight to implementation, skipping the
ADR, because the understanding felt settled.

### 3. The eight preconditions for starting a loop — all mechanically checkable

A loop may be started only when **all** of these hold. They live in full
in `docs/runbooks/verified-agentic-loop.md`; `WORKFLOW.md` carries the
mandate and the pointer, not the list.

1. **A single falsifiable, executable check exists, is committed, and has
   been observed to FAIL on the current tree.** The RED observation is
   recorded in the starting commit message or the PR body. Unobserved-red
   is not red.
2. **The check terminates in a process exit code with no human judgement
   and no live mutation.** Permitted: `./mvnw test`, `pytest`,
   `terraform fmt/validate`, `kubeconform`, `helm template` +
   `kubeconform`, `scripts/*.sh` CI assertions,
   `check_backlog_structure.py`, `check-roster-drift.sh`. Render-time and
   plan-time only.
3. **One loop per vertical slice.** One failing check, one concern. Never
   one loop per backlog item spanning several slices, never per epic. The
   `tdd` skill's own anti-pattern list names writing all tests up front
   as *horizontal slicing*; a loop over a pre-written suite is exactly
   that. This is the rule this ADR is least confident in (§8).
4. **A `git worktree` off a freshly-fetched `origin/main`**, never a
   shared checkout.
5. **No `KUBECONFIG` in the loop's environment** (§5).
6. **An explicit edit allowlist in the prompt**, and the loop's actual
   diff checked against it by a human before any PR.
7. **`--max-iterations` set explicitly and ≤ 15.** The plugin's default
   is `0`, which means unlimited; the default is forbidden.
8. **Branch → PR → human review → merge, unchanged.** The human re-runs
   the check and reads the diff; the loop's self-report and its promise
   are never the evidence of record. **"The test went green" is not a
   merge criterion** — §Context.3 is the evidence for why.

**Forbidden outright:** any loop whose stop condition needs a real
cluster or network mutation; any loop over docs/ADR/backlog *prose*
judgement (the structural checkers are loopable, the prose is not); any
loop with `--max-iterations 0`; any loop in a shared checkout; and any
loop making a design decision — §2's architect rule is not delegable to
a loop.

### 4. The HCL/YAML answer: name what exists, repair one script, add exactly one mechanism

The discipline is already here under the name **deliberately-broken
fixture**; that name is adopted as the project's term for it in
preference to "TDD", which does not survive contact with YAML.

| Layer | Existing, loopable | New | Call |
|---|---|---|---|
| Terraform | `fmt -check -recursive -diff`, `init -backend=false`, `validate` | `terraform test` (`.tftest.hcl`) | **Not now.** One `null_resource` SSH provisioner; no variable-driven branching to assert on. Trigger to revisit: the first real module with conditionals, i.e. #51/#52's multi-node substrate |
| Helm-sourced Applications | `scripts/render-helm-charts.sh` + `kubeconform` on rendered output | `helm unittest` | **Wrong tool.** It tests charts you author; this repo authors none, it consumes upstream charts via `valuesObject`. The right escalation is a `yq` assertion over `rendered-charts/*.rendered.yaml` — the shape `check-resource-limits.sh` already is |
| Hand-written manifests | `kubeconform -strict`; `check-resource-limits.sh` | `conftest`/OPA | **Gold plating and a new dependency class.** Extend the existing `yq` script instead; that also makes #142's render-time half a legitimate loop target |
| Dashboards + alert rules | not assessable from this machine (local `observability` checkout is ~2026-08-06) | `promtool check rules`, `promtool test rules` | **The one new mechanism worth it.** Three real defects of exactly this class already shipped: #145's `job=` selector that renders nothing, #91's `source=` blend trap, #143's missing recency gate. One static binary, zero runtime cost. **Rides #143/#144's AC**, not a new item |
| Docs/ADR/backlog | `check_backlog_structure.py` (4 fixtures), `check-roster-drift.sh` | nothing | Structural only; prose never |

**Mandatory for infra loop targets:** no render-time check may serve as a
loop stop condition unless it has itself been observed to fail — the
broken-fixture bar, promoted from idiom to rule. `check-resource-limits.sh`
is repaired accordingly (self-test fixtures; all workload kinds including
`Rollout` and `CronJob`; header comment corrected), filed as a new backlog
item and the natural home for #142's render-time half.

### 5. The live-verification boundary: credential absence is the gate, #149 is the gate for widening

Live verification — #142's `kubectl get pod -o jsonpath` proof, #123's
business-path acceptance, #153/#155's drill checklists, the standing
"verify live before marking Done" rule — is **not** a loop target.

Prose alone is not sufficient, but **not** for the usual reason. The risk
is not that a loop decides to run `kubectl apply`; it is that a loop
**removes the human from the turn boundary**, which is where
`WORKFLOW.md`'s trust-based safety rule actually gets its enforcement
today. The rule degrades from *trusted but observed* to *trusted and
unobserved*.

Therefore, **two gates, not one**:

- **Starting gate — available today, nothing to merge: deny the
  credential, not the command.** A loop runs with no `KUBECONFIG` in its
  environment (§3.5). A loop with no credential cannot mutate a cluster
  regardless of what it tries, and the check is mechanical. This is a
  stronger control than a command deny-list, which is a pattern match on
  strings.
- **Widening gate — #149's hook, with a widened AC.** Required before any
  loop whose prompt could plausibly want cluster access. Under the
  starting gate that set is empty, so **#149 is explicitly NOT a
  precondition for starting**. Making it one would manufacture pressure
  to merge an unreviewed security hook in the week of a talk, which this
  ADR refuses on the merits.

**#149's AC is widened by three patterns: `gh pr merge`, `git push
--force`, `helm upgrade/install/uninstall`.** Its current scope
(mutating `kubectl`/`terraform`) does not cover the rules a loop is most
likely to break unobserved — "the agent never merges" is a Definition of
Done rule enforced today only by prose. A widening is preferred to a
sibling hook because two hooks in the same `PreToolUse` Bash matcher
invite a merge-vs-overwrite collision — a collision this ADR can point at
concretely, since the enabled `mattpocock-skills` bundle contains
`git-guardrails-claude-code`, a model-invocable skill that writes
`.claude/settings.json`, installs a hook in that same slot, and blocks
`git push` — which would break this project's mandated branch → PR flow.

### 6. The operator toolchain gets its own rule, separate from the approved stack

`PROJECT.md`'s approved stack and its "Explicitly excluded" list (Vault,
Crossplane, Backstage) are about **runtime platform components**. Claude
Code plugins are not that: zero cluster surface, not ArgoCD-manageable.
Filing them there is a category error that would weaken both lists. They
get a new, short `PROJECT.md` section, **Operator toolchain (Claude
Code)**, with this rule:

1. **Project scope only**, in a committed `.claude/settings.json`. Never
   user scope — invisible to review, drifts per machine, and a project
   whose thesis is that configuration lives in Git should not keep its
   operator toolchain outside it. The two currently-uncommitted files are
   committed as the reviewed artifact.
2. **Enabled only where a real loop target exists**: `adamastorx` and
   `services` today. **Not** `platform`, **not** `observability` — blast
   radius in `platform` is the cluster, and symmetry is not a reason.
3. **Versions recorded, refreshes reviewed.** Read off disk 2026-10-01:
   `ralph-wiggum` 1.0.0, `mattpocock-skills` 1.2.3. A marketplace refresh
   can change an executing shell script with no PR and no CI; it is
   treated as a reviewable change on the same footing as a Renovate minor
   bump.
4. **A sanctioned-skill allowlist.** One `enabledPlugins` line enables
   **37 skills**. Sanctioned: `grilling` (and `grill-me`), `tdd` as
   reference vocabulary only, optionally `pr` for its one-way/two-way-door
   and blast-radius framing. Everything else is unsanctioned — reaching
   for one is a decision, not a default.
5. **Forbidden classes, named:** any model-invocable skill that writes
   `.claude/settings.json` or installs hooks
   (`git-guardrails-claude-code`, §5); any skill that merges PRs;
   `loop-me` (creates `workflows/*.md` and `NOTES.md` as new top-level
   workspace surface).
6. **`.claude/ralph-loop.local.md` is gitignored in all four repos.**
   Verified: every repo gitignores only `.claude/worktrees/`, so the loop
   state file is currently one `git add .` from being committed — the
   identical shape to the 2026-08-21 audit's own stray-swap-file finding.

**Vendoring is rejected, with a stated counter-condition.**
`grilling/SKILL.md` is 28 lines of prompt; the Ralph `Stop` hook is 178
lines of bash. Vendoring makes this project the owner of a
security-relevant shell script with no upstream fixes and imports
licence/provenance tracking for a net loss at that size. Vendor if the
marketplace entry changes hands, loses its licence, or the hook starts
doing anything beyond re-feeding a prompt. A **project-owned `grilling`
successor** (grill, then hand the answered tree to the `architect` agent
and write the ADR — something the generic skill structurally cannot do)
is recorded as a candidate, **not** a commitment: ADR 0044 already has
three unmerged toolchain items, and building two more before those land
is the gold plating this project's own principles forbid.

### 7. #149/#150/#151 are not subsumed; two need AC changes, one of which is a real conflict

- **#149 — stays P1, AC widened by §5's three patterns**, and is now
  named as the widening gate.
- **#150 — genuine conflict with §5, must change before its parked PR is
  reviewed.** Its AC currently requires a `SessionStart` hook that
  **exports `KUBECONFIG`**. That hands cluster credentials to every
  iteration of every loop in the repo and breaks §3.5 outright. #150
  should **surface the kubeconfig path** and the gremlin list rather than
  export the variable. #150 also **gains a real safety function it does
  not currently claim**: surfacing a stale `.claude/ralph-loop.local.md`,
  since that file is cwd-relative and removed only on the hook's own exit
  paths — an interrupted session leaves it, and the next, unrelated
  session in that directory has its exit blocked and the dead loop's
  prompt re-fed.
- **#151 — content unaffected, kind reframed.** Both Skills (canary
  drill; verify-live-Done / post-rebuild) encode **human-gated live
  procedures** and are explicitly not loop targets. That sentence goes
  **inside the skill files**, so a future session cannot innocently wrap
  them in a loop.
- **The agent-delegation table does not change.** A loop is a technique
  available to the delegated agent or to the main session on the
  lightweight path. It is not a persona and gets no table row; adding a
  "loop" agent would be a framework for a problem this project does not
  have.

### 8. This decision has a review date, set by the project's own rule

ADR 0044 §4 requires that "keep" be a dated decision rather than a
default. Applied here: this ADR is re-decided — to `Accepted`, to a
narrowed scope, or to `Rejected` — after **five real recorded loop runs**
logged in `docs/operations/` (the #124 operations log already exists and
is the right home) **or 2026-12-01, whichever comes first**. Each run
records: the check used and its observed RED, iteration count, measured
cost, whether human review found a defect the check missed, and whether a
promise was ever emitted falsely. The explicit trigger for narrowing to
`Rejected`: a run in which the loop exhausted its iteration budget
degrading the tree — the case this experiment did not test and the one
`--max-iterations` bounds the frequency of, not the occurrence of.

**The talk is named as a pressure and refused in two specific places**,
so this is on the record rather than in the air: (a) merging #149/#150's
parked PRs unreviewed to complete the story — refused (§5); (b) enabling
the plugins in all four repos so the adoption reads as uniform — refused
(§6.2). And the honest general version: this model is unusually
demo-friendly, which is a reason to be *more* suspicious of it, not less.
A $0.37 one-iteration convergence matching a human PR is a good slide and
a thin dataset.

## Consequences

- **`WORKFLOW.md` gains three small amendments and no new stage** —
  Design (grilling, optional, architect rule restated), Implement/Test
  (the loop named as an allowed technique with a pointer), Safety (no
  credential in a loop's environment, no live-verification stop
  conditions, `--max-iterations` mandatory). The eight preconditions live
  in a new `docs/runbooks/verified-agentic-loop.md` — the first real
  tenant of a folder whose README has reserved itself for org-level
  process runbooks since M0.
- **The project gains a name for something it already did.** The
  deliberately-broken fixture becomes the stated bar for any check used
  as a loop stop condition, and `check-resource-limits.sh`'s verified
  gaps (no self-test; vacuous for `api` since the Rollout migration) are
  filed as real work rather than left as an idiom nobody checked.
- **One new mechanism enters the toolchain, not four.** `promtool test
  rules`, riding #143/#144. `terraform test`, `helm unittest`, and
  `conftest`/OPA are rejected now with named triggers to revisit.
- **A parked PR's spec changes before it is reviewed.** #150 as specified
  would defeat §5's control; that is the single most actionable finding
  this decision hands the stalled review queue.
- **`PROJECT.md` gains a toolchain section and the approved-stack list is
  left alone** — plugins are governed, but not as runtime components, so
  neither list is diluted.
- **Four `.gitignore` lines and two committed `settings.json` files**
  close verified gaps at the smallest possible cost.
- **The evidence's limits are on the record.** No multi-iteration run, no
  infra/YAML loop run, no cost measurement above one iteration, and a
  verified case (§Context.3) where the loop produced the obvious patch
  rather than the better fix — and so did the human PR it matched. The
  human review gate stays mandatory precisely because of that, and the
  review date in §8 exists because n=1 is not a practice.
- **This ADR does not edit `docs/roadmap/backlog.md`.** The AC changes to
  #149/#150/#151, the `check-resource-limits.sh` repair item, and the
  `promtool` additions to #143/#144 are minted by a follow-up pass using
  this ADR's text as their source, per ADR 0044's own convention.
