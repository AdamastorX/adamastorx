# Engineering Workflow

Every issue moves through:

```
Understand → Design → Validate → Implement → Test → Document → Review
```

- **Understand** — read the issue, the linked epic, and any relevant ADR.
  Ask if acceptance criteria are ambiguous, don't guess.
- **Design** — decide the approach. For anything touching architecture or
  introducing a new tool, write the ADR here, before implementing. Design
  decisions with rejected alternatives worth remembering (per
  `docs/adr/README.md`) go through the `architect` agent — the session
  driving the issue does not make those calls inline, even when it has an
  opinion. "It's in the approved stack" exempts the tool choice, not the
  pattern/topology/strategy decisions made while using it.
- **Validate** — sanity-check the design against constraints that matter:
  does it fit the approved stack, does it respect repo boundaries, is there
  a simpler way.
- **Implement** — write the change on a branch, one concern. Never commit
  directly to `main` — see Branching & PRs below.
- **Test** — prove it works. Automated where possible; for infra, that means
  actually applying/destroying, not just `plan`.
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
outside of read-only inspection and short-lived debugging), without
explicit human confirmation for that specific action. GitOps (ADR 0003)
means the cluster's steady state is defined in `platform` — a manual
`kubectl` change is either a debugging step that gets thrown away, or it
needs to become a PR, never a silent standing edit.

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
