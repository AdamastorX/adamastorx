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
