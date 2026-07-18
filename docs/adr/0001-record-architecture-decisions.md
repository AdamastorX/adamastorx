# 0001. Record architecture decisions

Status: Accepted

## Context

Decisions about tooling and structure will be made by whoever (human or
agent) is doing the work at the time. Without a record, the reasoning gets
re-litigated every few months and nobody remembers why a technology on the
"no" list (service mesh, Vault, Crossplane, Backstage, Cilium) was excluded.

## Decision

Use lightweight ADRs (this format) for any decision that is hard to reverse
or introduces a new technology. Keep the approved-stack list in
`.claude/PROJECT.md` as the source of truth for "what's allowed"; use ADRs to
record "why we chose X over Y" or "why we're explicitly not doing Z".

## Consequences

- Every new technology proposal needs an ADR before adoption, not after.
- Rejected alternatives get recorded too — saves re-debating them later.
