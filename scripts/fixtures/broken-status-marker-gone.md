**S1. Remove the `gateway` service entirely; expose `api` directly**
- Purpose: testing -- reproduces the S1/S2 shape: a component confirmed
  gone from the live roster, with the removal item itself never marked
  Done.
- Acceptance Criteria: testing.
- Dependencies: none.
- Priority: P1. Labels: `test`.

**S2. Remove the `whoami` proof app**
- Purpose: testing.
- Acceptance Criteria: testing.
- Dependencies: S1.
- Priority: P2. Labels: `test`.
