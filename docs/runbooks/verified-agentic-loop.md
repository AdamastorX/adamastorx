# Verified Agentic Loop — Eight Preconditions and Per-Layer Matrix

**Status:** This discipline lives in ADR 0046. Read it first.

A bounded verification loop is a named technique available during Implement/Test
stages. It is not a general-purpose agent iteration; it is a scoped, 
precondition-gated way to automate a single falsifiable check on one vertical 
slice of one issue.

## Eight preconditions — all must hold

**1. A single falsifiable, executable check exists, is committed, and has been 
observed to FAIL on the current tree.**

The RED observation is recorded in the starting commit message or PR body. 
"Unobserved red" is not red.

**2. The check terminates in a process exit code with no human judgement and no 
live mutation.**

**Permitted checks:**
- `./mvnw test` (any test module)
- `pytest`
- `terraform fmt -check -recursive`, `terraform init -backend=false`, 
  `terraform validate`
- `kubeconform -strict`
- `helm template` + `kubeconform`
- `scripts/*.sh` CI assertions (e.g., `check-resource-limits.sh`, 
  `check-roster-drift.sh`, `check_backlog_structure.py`)
- Prometheus rule validation: `promtool check rules <file>`

Render-time and plan-time only. No runtime inspection (`kubectl get`), no 
cluster mutation, no manual plan review.

**3. One loop per vertical slice.**

One failing check, one concern. Never one loop per backlog item spanning 
several slices. The `tdd` skill's own anti-pattern list names writing all 
tests up front as *horizontal slicing*; a loop over a pre-written suite is 
exactly that. The project is least confident in this rule; it is subject to 
re-evaluation after five real recorded runs (ADR 0046 §8).

**4. A `git worktree` off a freshly-fetched `origin/main`, never a shared 
checkout.**

Isolation matters: if the loop creates a .local state file (`.claude/ralph-loop.local.md`)
in a shared directory and an interrupted session leaves it behind, the next 
unrelated session in that directory has its exit blocked and the dead loop's 
prompt re-fed.

**5. No `KUBECONFIG` in the loop's environment.**

This is a credential-based gate, stronger than command deny-lists. A loop with 
no `KUBECONFIG` cannot mutate a cluster regardless of what its prompt tries, 
and the check is mechanical. If widened access is later needed, ADR 0046 §5's 
widening gate (#149) covers it.

**6. An explicit edit allowlist in the prompt, and the loop's actual diff 
checked against it by a human before any PR.**

Document the files/functions the loop is allowed to edit. Human review verifies 
the diff stays within it.

**7. `--max-iterations` set explicitly and ≤ 15.**

The plugin's default is `0`, unlimited. The default is forbidden. An iteration 
budget of 15 bounds the frequency of degradation, not its occurrence — that is 
what the human review gate (precondition 8) exists for.

**8. Branch → PR → human review → merge, unchanged.**

The human re-runs the check and reads the diff. The loop's self-report and its 
promise are never the evidence of record. **"The test went green" is not a 
merge criterion** — ADR 0046 §Context.3 explains why: two independent agents 
can converge on the same patch when both a simpler fix and a better-designed 
fix exist, if grilling aimed at the task (not the fix) and verification-first 
then froze the design.

## Forbidden outright

- Any loop whose stop condition needs a real cluster or network mutation
- Any loop over docs/ADR/backlog *prose* judgement (structural checkers are 
  loopable; prose is not)
- Any loop with `--max-iterations 0`
- Any loop in a shared checkout
- Any loop making a design decision (ADR 0046 §2: grilling feeds the `architect` 
  agent and cannot replace it)

## Per-layer mandatory rules

| Layer | Existing, loopable | New | Mandate |
|---|---|---|---|
| Terraform | `fmt -check`, `init -backend=false`, `validate` | `terraform test` (`.tftest.hcl`) | **Not now.** One `null_resource` SSH provisioner; no variable-driven branching to assert on. Revisit when: the first real module with conditionals (#51/#52 multi-node substrate). |
| Helm-sourced Apps | `scripts/render-helm-charts.sh` + `kubeconform` | `helm unittest` | **Not applicable.** Tests charts you author; this repo consumes upstream charts. Right escalation: a `yq` assertion over `rendered-charts/*.rendered.yaml` — the shape `check-resource-limits.sh` already is. |
| Hand-written manifests | `kubeconform -strict`; `check-resource-limits.sh` | `conftest`/OPA | **Not now.** Gold plating and a new dependency class. Extend `yq` script instead; that also makes #142's render-time half a legitimate loop target. |
| Dashboards + alert rules | Prometheus rule structure (not testable locally) | `promtool check rules`, `promtool test rules` | **The one new mechanism worth adopting.** Three real defects of exactly this class already shipped: #145 (selector rendering nothing), #91 (blend trap), #143 (missing recency gate). One static binary, zero runtime cost. Rides #143/#144's AC, not a new item. |
| Docs/ADR/backlog | `check_backlog_structure.py` (4 fixtures), `check-roster-drift.sh` | (none) | Structural only; prose never. |

**Mandatory for infra loop targets:** no render-time check may serve as a loop 
stop condition unless it has itself been observed to fail — the broken-fixture 
bar, promoted from idiom to rule. `check-resource-limits.sh` was repaired 
accordingly: self-test fixtures added, glob extended to all workload kinds 
(`Deployment`, `StatefulSet`, `DaemonSet`, `Rollout`, `CronJob`), header 
comment corrected to list them.

## Worktree procedure

```bash
# Start fresh from main
git fetch origin
git worktree add /tmp/ralph-loop-<issue-number>/ origin/main
cd /tmp/ralph-loop-<issue-number>/

# Write the failing check, commit it RED
# (verify: run the check, confirm it fails and reports RED)
git add .
git commit -m "backlog #<N>: failing check — RED observation [reason]"

# Start the loop with explicit flags:
# --max-iterations 15 (mandatory)
# --edit-allowlist <files> (mandatory)
# -l adamastorx (scope to this project, not user-wide)
claude-code loop-start \
  --max-iterations 15 \
  --edit-allowlist "path/to/file1.java,path/to/file2.yaml" \
  --prompt "Fix backlog #<N> by [one sentence task description]"

# Loop exits when:
# - Promised stop condition met (check passes, human reviews diff)
# - Iteration budget exhausted (--max-iterations 15)
# - User stops session (Ctrl+C)

# After loop exit:
git diff origin/main
# Human: does the diff stay within --edit-allowlist?
# Human: re-run the check manually, confirm it still passes
# If yes:
git add .
git commit -m "backlog #<N>: [fix] — loop run: check=[name], RED→GREEN, iterations=N, cost=$X [human re-ran check]"
gh pr create --base main --title "backlog #<N>: [title]" --body "[PR body with loop metadata]"
# Human review and merge
```

## Cost recording convention

If a loop produced the diff, the PR body includes:

```
**Loop metadata:**
- Check: [name of the failing check used as stop condition]
- Observed RED: [yes/no, explicit confirmation]
- Iterations: [N]
- Cost (Sonnet 5 list prices): $[X.YZ]
- Human re-ran check: [yes/no]
```

## "The promise is not evidence"

The loop emits a promise when its stop condition claims to be met 
(e.g., `✓ check passed, stopping`). The promise is not the evidence of 
record. Evidence is:

1. Human runs the check again in their own environment
2. Human reads the diff and verifies it matches the --edit-allowlist
3. Human review finds no defect the automated check missed

The reason: ADR 0046 §Context.3 gives a concrete case where two independent 
agents converged on the same *patch* when a different, better-designed *fix* 
existed. The patch worked (the check passed); the fix would have been more 
robust. The human review gate is what catches this — not because it is smarter, 
but because it asks a different question: "is this the shape we want?" instead 
of just "does it pass the check?"

## Review date

This technique is re-decided — to `Accepted`, narrowed, or `Rejected` — after 
**five real recorded loop runs** logged in `docs/operations/` (see the #124 
operations log) or **2026-12-01**, whichever comes first.

Each recorded run must include:
- The check used and its observed RED
- Iteration count
- Measured cost
- Whether human review found a defect the check missed
- Whether a promise was ever emitted falsely

Explicit trigger for `Rejected`: a run in which the loop exhausted its 
iteration budget degrading the tree — the case this experiment (backlog #156) 
did not test.

See ADR 0046 for full context and decision record.
