# 0042. The project board's status stops being a manual step

Status: Accepted

## Context

`docs/roadmap/project-board.md` defines a real, five-column shared board
across all four repos (Inbox, Ready, In Progress, Review, Done), each
with a stated rule for when a card is allowed to move into it. In
practice it went unmaintained almost from the start: of 146 cards on the
board, only 12 have ever had a status set, and all 12 are from the
initial bootstrap issues in each repo. Every card filed since — 134 of
them, effectively this project's entire real working life — has sat with
no status at all, not stuck in a column, just never touched. This was
found live while auditing the project's own documented engineering
process against what actually happens (see the 2026-08-15 article draft
in `docs/articles/`), the same audit that also found the five
`.claude/agents/` personas were never delegated to through the mechanism
`.claude/WORKFLOW.md` names for exactly that.

The pattern in both cases is the same: `docs/roadmap/backlog.md` is this
project's real, well-maintained source of truth, and every status update
the board needed was also a status update the backlog already had, in
prose, with real evidence attached. Updating the board was a second,
purely mechanical step with no independent value once the backlog already
carried the same information — and a manual step with no independent
value is exactly the kind of step that gets skipped by default, every
time, without anyone deciding to skip it. The lesson this project keeps
re-learning (`review-before-merge` survived because skipping it has real
consequences; the board didn't, because skipping it doesn't) is that a
process survives in proportion to how much friction it takes to skip it,
not how well-reasoned it was when written down.

Checked live before deciding anything: this org's shared Project (`gh api
graphql`, `organization(login: "AdamastorX") { projectV2(number: 1) {
workflows } }`) already has **six native GitHub Projects v2 workflows**
defined and available, a real, built-in automation mechanism this project
had simply never turned on:

| Workflow | Trigger | Currently |
|---|---|---|
| Auto-add sub-issues to project | a sub-issue is created under a tracked issue | **Enabled** |
| Item added to project | an issue/PR is added to the board | Disabled |
| Pull request linked to issue | a PR references/closes a tracked issue | Disabled |
| Pull request merged | a linked PR merges | Disabled |
| Item closed | the issue itself is closed | Disabled |
| Auto-close issue | a linked PR merges | Disabled |

Only the first was ever turned on (almost certainly a default, not a
deliberate choice — nothing in this project's own history references
it). The five that would have kept the board honest were available the
entire time and never enabled.

Real, confirmed API limitation, checked before writing this decision
rather than assumed: the GraphQL API's mutation type exposes
`deleteProjectV2Workflow` and nothing else — no create/update/enable
mutation for `ProjectV2Workflow` exists. Turning these on and setting
each one's target status is only possible through the GitHub web UI
(Project → `...` menu → Workflows), a real, one-time, few-minutes manual
step this ADR hands to the owner directly rather than pretending it can
be scripted.

## Decision

Enable four of the five currently-disabled native workflows, each set to
the target status that matches `project-board.md`'s own column
definitions:

- **Item added to project** → `Inbox`. Matches the column's own stated
  meaning ("Newly filed, not triaged") exactly — every new card starts
  where the board's own rules already say it should.
- **Pull request linked to issue** → `Review`. In this project's real,
  documented workflow (branch → commit(s) → `gh pr create` → wait), a PR
  is opened specifically to be reviewed — there is no separately
  observable "In Progress, no PR yet" state a native trigger can detect,
  so a linked PR is the first mechanically-detectable signal, and it
  already means "awaiting review" in practice, not just "started."
- **Pull request merged** → `Done`.
- **Item closed** → `Done`. Covers the real cases that don't go through a
  merged PR at all — `Won't do (superseded)`, duplicates, `Blocked`
  closures — the same real statuses this backlog already uses honestly
  in prose (`#48`, `#51`) and that a PR-merge-only trigger would silently
  miss.

**`Auto-close issue` stays disabled, deliberately, not by oversight.**
This project's own Definition of Done requires docs updated and the
change verified, not just merged (`.claude/PROJECT.md`) — a merged PR is
necessary but not always sufficient, and this project has real, recorded
cases of a merge needing a fast-follow fix before the work was actually
done (the Beyla/alertmanager `policy-enabled: egress` gap, caught and
fixed after its own initial merge, is one). Auto-closing the issue at
merge time would silently skip that real verification gap. Status moving
to `Done` on merge is a useful, low-stakes default (a status column is
findable and reversible; a closed issue takes an extra step to reopen);
closing the issue itself stays a deliberate action.

**`Ready` and `In Progress` are not covered by any native trigger**, and
that is accepted rather than worked around. Both columns exist to encode
a real judgment call — `project-board.md`'s own rule is "an issue only
moves to Ready once it meets Definition of Ready," which is exactly the
kind of decision this project's own process should keep making
deliberately, not the kind that should be automated away. Automation
covers the two mechanical, judgment-free ends of a card's life (it
exists; it's finished); the middle stays a real kanban-drag a human does
on purpose, matching the same distinction ADR 0031's Definition of Ready
already draws.

No CI-based enforcement (e.g. a check requiring a `Persona:` commit
trailer on architecture-labeled PRs, considered as an alternative
mitigation for the personas half of the same audit) is adopted alongside
this. Reasoning recorded rather than left implicit: a trailer-presence
check only verifies a label was typed, not that the delegation it claims
actually happened through an isolated agent context — real friction
against forgetting to *claim* the right process, no real friction against
skipping the process itself. The project-board fix above is preferred
specifically because it's the opposite: a mechanism that makes the
correct outcome (an accurate board) happen automatically, rather than one
that makes the incorrect outcome (an unmaintained board) merely harder to
get away with.

The related, harder question this same audit raised — whether the five
`.claude/agents/` personas can be made genuinely invocable through the
Agent tool's `subagent_type` mechanism `.claude/WORKFLOW.md` already
assumes, rather than role-played through a generic reviewer every time —
is deliberately **not** resolved here. Investigated in the same pass: the
persona files themselves are a real, correctly-formatted, documented
Claude Code feature; the most likely reason they don't appear as
available subagent types in a live session is that the file-watcher that
discovers `.claude/agents/*.md` only covers directories that already
existed when the session started, which would mean a session restart
fixes it — a real, testable hypothesis, but not one this ADR can verify
without ending the long-running session that produced this decision.
Left as real, open, future work rather than assumed solved.

## Consequences

**Real, immediate:** the board's status field stops requiring anyone to
remember it. New cards land in `Inbox` on creation; a merged PR or a
closed issue moves its card to `Done`; a linked PR moves it to `Review`.
`Ready`/`In Progress` remain a deliberate human step, matching their own
stated definitions. This does not change `docs/roadmap/backlog.md`'s role
as the real source of truth in any way — the board becomes an accurate
reflection of it, not a competing one.

**Real, honest gap:** enabling these four workflows requires the owner to
act directly in the GitHub UI — this ADR documents the decision and the
exact target-status mapping; it cannot execute the change itself given
the real API limitation recorded above. Until that step happens, this
ADR records an intended state, not yet a live one — the same honesty this
project's own "Done, not yet verified live" convention already applies
elsewhere.

**Deferred, on purpose:** the persona-delegation half of the same audit
(five roles defined, never actually staffed) gets no mitigation in this
ADR. A CI-based trailer check was considered and rejected above as real
friction against the wrong thing. The session-restart hypothesis for
fixing native subagent discovery is recorded as the real next thing to
test, not attempted here.
