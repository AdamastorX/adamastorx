#!/usr/bin/env python3
"""backlog #97(b): structural integrity of docs/roadmap/backlog.md.

Two real, distinct corruptions motivate this, both found by the
2026-08-06 staff-engineer review and neither caught by the #32/#83
"process fix" (a PR-checklist reminder) because neither is a content
problem a human skimming the diff naturally notices:

- #87 was duplicated verbatim as a top-level heading -- a bad `Edit`
  anchor in an unrelated commit an hour earlier re-emitted the whole
  neighbouring block.
- #79's own `**79.` heading was destroyed entirely, swallowed into the
  tail of #78's `Priority:` line -- the file had no `**79.` heading at
  all for an unknown period.

Both are structural, not narrative -- three cheap checks catch them:
every item number appears exactly once, the set of numbers used has no
gaps, and no non-heading line contains an embedded `**<number>.`
fragment (the #79 shape).
"""

import re
import sys
from collections import Counter

HEADING_RE = re.compile(r"^\*\*(\d+)\.")
EMBEDDED_HEADING_RE = re.compile(r"\*\*(\d+)\.")
REQUIRED_LABELS = ["Purpose", "Acceptance Criteria", "Dependencies", "Priority"]
# Items closed/superseded/compressed to freeform prose (heading itself
# says so) legitimately drop the four-label template -- real,
# consistent convention across ~10 items (e.g. #16, #23, #33, #56), not
# corruption. Only the label-based structure check is skipped for
# these; duplicate/gap/embedded-heading checks still apply to every
# item regardless of format.
CLOSED_HEADING_RE = re.compile(r"— (Done|CLOSED|MERGED|superseded)|~~")


def check(path):
    lines = open(path, encoding="utf-8").read().split("\n")

    headings = [(i, int(m.group(1))) for i, line in enumerate(lines) if (m := HEADING_RE.match(line))]
    errors = []

    counts = Counter(n for _, n in headings)
    for n, c in sorted(counts.items()):
        if c > 1:
            errors.append(f"item #{n} appears {c} times as a top-level heading (expected exactly once)")

    if headings:
        lo, hi = min(counts), max(counts)
        missing = [n for n in range(lo, hi + 1) if n not in counts]
        if missing:
            shown = ", ".join(f"#{n}" for n in missing)
            errors.append(f"backlog numbering has gaps between #{lo} and #{hi}: missing {shown}")

    for idx, (line_no, n) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        block = lines[line_no:end]

        if not CLOSED_HEADING_RE.search(block[0]):
            for label in REQUIRED_LABELS:
                if not any(l.startswith(f"- {label}") for l in block):
                    errors.append(f"item #{n} (line {line_no + 1}) is missing a '- {label}' line")

        # #79's own real corruption was a heading swallowed into the
        # *previous* item's Priority line specifically -- the AC's own
        # stated detection method. Scoping to just Priority lines (not
        # the whole block) avoids flagging legitimate prose that
        # discusses another item's number by name (e.g. this very
        # item's own Purpose paragraph, which quotes "#79" as history).
        for offset, l in enumerate(block):
            if not l.startswith("- Priority:"):
                continue
            for m in EMBEDDED_HEADING_RE.finditer(l):
                errors.append(
                    f"item #{n}: line {line_no + offset + 1}'s Priority line contains an embedded "
                    f"'**{m.group(1)}.' fragment -- looks like a heading swallowed into it (#79 shape)"
                )

    return headings, errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/roadmap/backlog.md"
    headings, errors = check(path)

    if errors:
        for e in errors:
            print(f"::error file={path}::{e}", file=sys.stderr)
        print(f"\n{len(errors)} backlog structural integrity error(s) found (backlog #97b).", file=sys.stderr)
        sys.exit(1)

    nums = sorted(n for _, n in headings)
    print(f"backlog.md structural integrity OK: {len(headings)} items, #{nums[0]}-#{nums[-1]}, no gaps, no duplicates, no swallowed headings.")


if __name__ == "__main__":
    main()
