# Contributing

## Principles

- Small PRs, incremental delivery.
- Simple architecture over clever architecture.
- Document the why, not just the what.
- No gold plating, no premature optimisation, no framework for a problem you
  don't have yet.

## Workflow

Every issue follows the loop in `.claude/WORKFLOW.md`:
Understand → Design → Validate → Implement → Test → Document → Review.

Trivial issues (typo, `good-first-issue`) can collapse the first three steps
into one — don't force ceremony where it adds no value.

## Before opening a PR

- [ ] Issue has clear acceptance criteria and is linked.
- [ ] Change is scoped to one concern (one epic, one repo where possible).
- [ ] Docs updated if behaviour, architecture, or operational procedure changed.
- [ ] New tool/dependency? Write an ADR first (`docs/adr/`).
- [ ] **New service?** Its AC names a golden-signal dashboard, an ADR 0020
  SLO-table row, and any consumer-lag/staleness alert with a runbook — or
  states explicitly why one doesn't apply (backlog #109; M13 shipped
  without this line and paid for it, backlog #90/#111). A stated reason
  goes in ADR 0020's own "Components without their own row" section (or
  the dashboard file's own comment) so `scripts/check-roster-drift.sh`'s
  grace-period check can find it the same way it finds a real row.

## Dependency updates

Renovate (self-hosted, `.github/workflows/renovate.yml`, one instance per
repo using that repo's own `GITHUB_TOKEN` — backlog #98) opens PRs for
Helm chart, Docker base image, GitHub Actions, Maven, and pip updates.
Patch/pin/digest updates automerge once the repo's required checks pass;
minor/major updates wait for manual review. The project owner shepherds
that PR stream — reviewing minor/major bumps is a normal maintenance
task, not a separate role. `observability` has no Renovate config: it
carries no dependency-manager files (docs/runbooks only), so there's
nothing for it to manage.

## Definition of Ready / Done

See `.claude/PROJECT.md`.

## Code of conduct

Be direct, be kind, assume good faith.
