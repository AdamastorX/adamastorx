# Engineering Workflow

Every issue moves through:

```
Understand → Design → Validate → Implement → Test → Document → Review
```

- **Understand** — read the issue, the linked epic, and any relevant ADR.
  Ask if acceptance criteria are ambiguous, don't guess.
- **Design** — decide the approach. Optionally, use `grilling` (via
  `mattpocock-skills`) to map open questions as a decision tree before
  writing acceptance criteria to falsifiable precision. For anything touching
  architecture or introducing a new tool, write the ADR here, before
  implementing. Design decisions with rejected alternatives worth remembering
  (per `docs/adr/README.md`) go through the `architect` agent — the session
  driving the issue does not make those calls inline, even when it has an
  opinion. **Grilling feeds the `architect` agent and cannot replace it** — a
  grilling session that reaches "shared understanding" and skips the ADR is a
  failure mode to guard against. "It's in the approved stack" exempts the
  tool choice, not the pattern/topology/strategy decisions made while using
  it.
- **Validate** — sanity-check the design against constraints that matter:
  does it fit the approved stack, does it respect repo boundaries, is there
  a simpler way.
- **Implement** — write the change on a branch, one concern. Never commit
  directly to `main` — see Branching & PRs below. A bounded verification loop
  (see `docs/runbooks/verified-agentic-loop.md`) is an allowed technique for
  a single falsifiable check on this vertical slice only, subject to eight
  preconditions.
- **Test** — prove it works. Automated where possible; for infra, that means
  actually applying/destroying, not just `plan`. Render-time checks (`terraform
  validate`, `kubeconform`, Prometheus rule validation) are loopable stop
  conditions when they have themselves been observed to fail; run-time checks
  are never loopable.
- **Document** — architecture doc, ADR, or runbook, whichever applies. Never
  skipped — an undocumented change isn't done.
- **Review** — open a PR and stop. Merge only after the human owner reviews
  and approves — see Branching & PRs below.
- **Post-merge sweep** — after a merge with architectural or operational
  impact, the `documentation-engineer` agent checks the `adamastorx` docs
  (`.claude/PROJECT.md` current-state sections, `docs/architecture/`) for
  staleness and fixes via its own PR. In-repo docs travel in the feature PR;
  cross-repo docs are what this sweep exists for.

## Branching & PRs

Every change, regardless of size, goes: branch → commit(s) → `gh pr create`
→ wait. Nothing gets merged by the agent that opened it — the human reviews
and merges (or requests changes) via GitHub. This applies even when the
"agent" doing the work is the main Claude Code session, not a delegated
subagent — there is no exception for "it's just me working solo."

Branch name: `<type>/<short-description>` (e.g. `feat/argocd-bootstrap`,
`fix/kubeconfig-perms`), matching the Conventional Commits type of the
change.

Claude Code worktrees (`.claude/worktrees/`) are gitignored in every
repo — they're local working state, not something to commit or clean up
by hand. If one is ever found tracked, that's a `.gitignore` gap to fix,
not a directory to delete.

## Agent delegation

Issues get routed to the persona whose `.claude/agents/<name>.md`
responsibility matches the issue's label, via the Agent tool:

| Label | Agent |
|---|---|
| `architecture` | `architect` |
| `platform` | `platform-engineer` |
| `backend` | `backend-engineer` |
| `observability` | `observability-engineer` |
| `documentation` | `documentation-engineer` |

The main session's job for a labeled issue is: Understand the issue, then
delegate Design/Implement/Test/Document to the matching agent (with the
issue's context — Purpose, Acceptance Criteria, Dependencies — passed in
full, not summarized). The agent works on its branch and opens the PR; the
main session does not re-do the work inline. Issues touching more than one
concern (e.g. `platform` + `observability`) get split into separate issues
per concern before work starts, or — if truly inseparable — go to whichever
agent owns the primary deliverable, with the other concern's agent pulled in
for review.

**Platform-impacting changes get an independent review pass** — a fresh
agent/context (not the one that designed and implemented the change)
checks it before merge, via the Agent tool with a matching persona
(`platform-engineer` for cluster/Helm/ArgoCD, `architect` for anything
crossing repo boundaries). The point is a second, unbiased read, not a
rubber stamp from the same context that already talked itself into the
approach — this didn't happen for services#3/#4's platform work and
should going forward.

## Lightweight path

For trivial issues (`good-first-issue`, typo fixes, doc corrections):
collapse Understand/Design/Validate into one quick pass, and skip agent
delegation — do it inline. Branch + PR still applies; ceremony scales with
risk, not with the fact that a workflow exists — see Coding principles in
`PROJECT.md`.

## Never skip

Documentation. A change without an updated doc/ADR/runbook where one applies
does not meet Definition of Done, regardless of how small the diff is.
Branch + PR + human review, likewise — regardless of how small the diff is.

## Safety

Never run `terraform apply`/`destroy`, or make a persistent manual
change directly against the cluster (`kubectl apply`/`patch`/`delete`
outside of read-only inspection), without explicit human confirmation
for that specific action. GitOps (ADR 0003) means the cluster's steady
state is defined in `platform` — a manual `kubectl` change is either a
debugging step that gets thrown away, or it needs to become a PR, never
a silent standing edit.

**This is enforced, not just stated.** Backlog #149 turned the rule above
from trust-based prose into a mechanically enforced one: `platform`'s
`.claude/settings.json` wires a `PreToolUse` hook
(`.claude/hooks/gitops-mutation-guard.py`, matcher: `Bash`) that inspects
every `Bash` tool call before it runs.

- **Blocked by default**: kubectl
  `apply`/`patch`/`delete`/`scale`/`replace`/`edit`/`annotate`/`label`, and
  terraform `apply`/`destroy`.
- **Always allowed**, unconditionally: kubectl
  `get`/`describe`/`logs`/`top`/`explain`/`diff` and any other subcommand
  the hook doesn't recognize, terraform `plan`/`validate`/`show`/`output`,
  and anything invoked with `--dry-run` — read-only inspection is never
  blocked, token or not.
- **Confirmation token**: a blocked command is permitted only if the
  literal marker `ADAMASTORX_CONFIRM_MUTATION=1` appears in the exact
  command string being run, e.g.:

  ```sh
  ADAMASTORX_CONFIRM_MUTATION=1 kubectl apply -f manifest.yaml
  ADAMASTORX_CONFIRM_MUTATION=1 terraform apply
  ```

  The marker is per-command, not a session-wide switch — it has to be
  attached to the specific action being confirmed, matching this section's
  "confirmation for that specific action" wording. To ask Claude to run a
  mutating command, tell it to, and it will include the marker; typing the
  marker yourself in a command you paste has the same effect. A secondary
  path also honors the same-named variable if it's already set in the hook
  process's own environment (useful for the owner's own shell before
  starting a session doing a batch of confirmed maintenance operations) —
  not reachable by anything a model runs through the `Bash` tool, since
  `export`s inside Bash-tool commands don't propagate back to the hook's
  parent process.
- **Deliberately stricter than the old prose**: the previous wording
  exempted "short-lived debugging" kubectl mutations (e.g. deleting a stuck
  pod to force a restart). A hook sees only the command string, not why
  it's being run, so it can't tell "short-lived debugging delete" apart
  from a standing destructive change — both are `kubectl delete ...`. The
  hook therefore requires the token for every mutating verb uniformly,
  including ad hoc debugging deletes. That collapse of nuance is what makes
  the rule mechanically enforced instead of a judgment call left to the
  model.
- **Not a security boundary.** The model composes the very command string
  the hook inspects, so a model that decided to always prepend the marker
  would defeat this check — this guards against acting on habit or
  momentum without a human actually saying so, not against an adversarial
  or compromised model. That's an accepted trade-off for a single-owner
  personal project, not a multi-tenant security control.
- **Scope**: currently wired in `platform/.claude/settings.json` only,
  since that's where kubectl/terraform commands are run in practice today.
  Claude Code hooks are per-repo, so a session opened in `services/`,
  `observability/`, or `adamastorx/` doing ad hoc cluster debugging is
  **not** covered by this hook yet — a known, accepted gap, not an
  oversight, flagged for a possible fast-follow to mirror the hook into the
  other three repos if that gap turns out to matter in practice.
- Verified with a real test, not just a config diff:
  `platform/.claude/hooks/test_gitops_mutation_guard.sh` feeds the hook
  synthetic `PreToolUse` JSON on stdin and asserts a mutating command is
  blocked without the token, allowed with it, and that read-only commands
  are never blocked either way.

A bounded verification loop runs with no `KUBECONFIG` in its environment
— a credential-based gate stronger than command deny-lists. No loop may
have live-verification (cluster mutation/inspection) as a stop condition,
and `--max-iterations` is mandatory (≤15). All eight preconditions in
`docs/runbooks/verified-agentic-loop.md` must hold before starting.

## `SESSION_STATE.md`

`docs/SESSION_STATE.md` is a scratch log of *current* state — in-flight
work, open PRs, handoff notes, gotchas worth not rediscovering. It is not
where decisions live (that's an ADR) or where recurring operational
knowledge lives (that's a runbook, in `observability/runbooks/` for
alert-response or `adamastorx/docs/runbooks/` for org-level process, per
that folder's own README). If something written there stops being
"what's happening right now" and becomes "how we decided to do X" or "what
to do every time Y happens," it's graduated out and the scratch entry gets
deleted, not left to accumulate.
