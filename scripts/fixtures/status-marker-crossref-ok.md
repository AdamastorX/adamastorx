**1. First item, referenced elsewhere as done, and correctly marked itself**
- Purpose: testing.
- Acceptance Criteria: testing.
- Dependencies: none.
- Priority: P1. Labels: `test`. **Done (2026-01-01, test#1)** — real prerequisite work, verified.

**2. Second item, correctly depends on #1 and calls it done**
- Purpose: testing.
- Acceptance Criteria: testing.
- Dependencies: #1 (real prerequisite work, done).
- Priority: P1. Labels: `test`.

**3. Third item, referenced with a precondition phrase that must NOT be mistaken for a status marker (the #154 shape)**
- Purpose: testing -- this item is real, current, unstarted work.
- Acceptance Criteria: testing.
- Dependencies: none.
- Priority: P1. Labels: `test`.

**4. Fourth item, depends on #3 with a "complete" precondition describing what must happen first, not #3's own status**
- Purpose: testing.
- Acceptance Criteria: testing.
- Dependencies: #3 (cutover complete).
- Priority: P1. Labels: `test`.
