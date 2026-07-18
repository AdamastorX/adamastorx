# Engineering Workflow

Every issue moves through:

```
Understand → Design → Validate → Implement → Test → Document → Review
```

- **Understand** — read the issue, the linked epic, and any relevant ADR.
  Ask if acceptance criteria are ambiguous, don't guess.
- **Design** — decide the approach. For anything touching architecture or
  introducing a new tool, write the ADR here, before implementing.
- **Validate** — sanity-check the design against constraints that matter:
  does it fit the approved stack, does it respect repo boundaries, is there
  a simpler way.
- **Implement** — write the change. Small PR, one concern.
- **Test** — prove it works. Automated where possible; for infra, that means
  actually applying/destroying, not just `plan`.
- **Document** — architecture doc, ADR, or runbook, whichever applies. Never
  skipped — an undocumented change isn't done.
- **Review** — PR review before merge.

## Lightweight path

For trivial issues (`good-first-issue`, typo fixes, doc corrections):
collapse Understand/Design/Validate into one quick pass. Ceremony scales
with risk, not with the fact that a workflow exists — see Coding principles
in `PROJECT.md`.

## Never skip

Documentation. A change without an updated doc/ADR/runbook where one applies
does not meet Definition of Done, regardless of how small the diff is.
