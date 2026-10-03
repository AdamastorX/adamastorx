**S1. Remove the `gateway` service entirely; expose `api` directly**
- Purpose: testing -- same S1/S2 shape, but correctly marked this time.
- Acceptance Criteria: testing.
- Dependencies: none.
- Priority: P1. Labels: `test`. **Done (2026-01-01, test#1)** — `gateway` deleted, confirmed gone.

**S2. Remove the `whoami` proof app**
- Purpose: testing.
- Acceptance Criteria: testing.
- Dependencies: S1.
- Priority: P2. Labels: `test`. **Done (2026-01-01, test#2)** — `whoami` deleted, confirmed gone.
