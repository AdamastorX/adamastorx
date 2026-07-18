# GitHub Project

One org-level project, shared across all 4 repos. Single board, not one per
repo — the whole point is seeing platform/backend/observability work in one
place instead of four disconnected views.

## Columns

| Column | Meaning |
|---|---|
| Inbox | Newly filed, not triaged |
| Ready | Triaged, has acceptance criteria, unblocked — pickable |
| In Progress | Actively being worked |
| Review | PR open, awaiting review |
| Done | Merged and verified |

## Rules

- An issue only moves to **Ready** once it meets Definition of Ready
  (`.claude/PROJECT.md`).
- An issue only moves to **Done** once it meets Definition of Done, including
  docs — see `.claude/WORKFLOW.md`, documentation is never skipped.
- `blocked` label + a comment linking the blocker, not a separate column —
  a "Blocked" column just hides the same information the `blocked` label
  already gives you, one more place for a card to go stale in.
