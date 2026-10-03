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

backlog #147 extends this with a status-marker-consistency check: an
item referenced elsewhere as done/closed, or a component confirmed
gone from the live roster (via --gone, wired from
check-roster-drift.sh), whose own entry carries no closing marker.
See check_status_markers() below for the detection rule and its
deliberately-stated limits.
"""

import argparse
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

# --- backlog #147: status-marker consistency -------------------------------
#
# Broader than HEADING_RE on purpose: real items include lettered
# sub-items (#21a, #21b, ...) and lettered milestone actions (S1, S2,
# ...) that HEADING_RE's pure-\d+ pattern never matched (correctly --
# they're intentionally exempt from the numeric gap/duplicate check,
# which only makes sense for the contiguous top-level sequence). The
# status-marker check needs *every* real item, since #21a and S1/S2 are
# exactly the two shapes the 2026-08-21 audit found by hand.
ITEM_ID_RE = re.compile(r"^\*\*([A-Za-z0-9]+)\.")

# Whether an item's own block (heading line through its Priority line
# and any trailing notes, i.e. everything up to the next ITEM_ID_RE
# heading) carries a recognizable closing marker anywhere in it, not
# just the heading -- the doc's real convention is a bolded marker
# tacked onto the end of the Priority line (`**Done**`, `**Done
# (2026-08-07, ...)**`) or, for a handful of closed/superseded items, a
# `~~struck-through~~` heading. Deliberately generous (case-insensitive,
# scans the whole block): this side of the check exists only to avoid
# false positives, and a real block already carries one of these tokens
# in a bolded span whenever the item is genuinely closed in this doc's
# own convention.
#
# Known, stated limitations, both producing false *negatives* only (the
# safe direction -- an under-marked item goes unflagged, never the
# reverse):
#   1. A handful of items use a *negated* bolded phrase to explicitly
#      record they are still open (`**Still not marked Done**`, `**Not
#      Done**`, `**Also genuinely not done**`) -- this regex cannot
#      tell that apart from a real close, because doing so is exactly
#      the fuzzy negation-phrase detection backlog #147's own AC says
#      to leave out.
#   2. Because a whole heading line is itself wrapped in `**...**` by
#      this doc's own convention, a heading whose plain-English title
#      happens to contain one of these words as ordinary prose, not a
#      status marker, also reads as "marked" -- e.g. `**137. ... from
#      #94's closed 30-day window**` (the *window* closed, not #137)
#      or `**151. ... the verify-live-Done / post-rebuild checklist**`
#      (a proper noun, not a marker).
# Both only matter if some *other* item's Dependencies line separately
# asserts that item is done -- checked against the real file at review
# time and not currently the case for any item hitting either edge.
OWN_MARKER_RE = re.compile(
    r"\*\*[^*\n]*\b(?:Done|CLOSED|MERGED|Superseded|Won't do)\b[^*\n]*\*\*|~~",
    re.IGNORECASE,
)

# A cross-reference to another item, with a parenthetical note attached
# directly to the `#id` -- e.g. `#21a (real histogram/lag metrics,
# done)`. Deliberately scoped to *just* this shape (an id immediately
# followed by `(...)`), not "any line that mentions both an id and a
# status word anywhere", which is what produced #147's own real false
# positive during design (see DONE_KEYWORD_RE below).
DEP_REF_RE = re.compile(r"#([A-Za-z0-9]+)\s*\(([^)]*)\)")

# Keyword set is deliberately narrower than English "this is complete":
# it's exactly the vocabulary this doc's own OWN_MARKER_RE already
# treats as a closing marker (done/closed/merged/superseded), not a
# generic completeness word. "complete" was tried and dropped: real
# line `- Dependencies: #154 (cutover complete)` describes a
# *precondition* for #154 (the cutover being complete before #155 can
# start), not #154's own closed status -- #154 is real, current,
# unstarted M17 hardware-migration work. Telling that apart from a
# genuine "#N (done)" style reference needs exactly the sentence-level
# reading backlog #147's AC rules out, so the keyword list itself is
# narrowed instead, to the tokens this document has only ever used as
# literal status markers.
DONE_KEYWORD_RE = re.compile(r"\b(done|closed|merged|superseded)\b", re.IGNORECASE)

# `**S1. Remove the `gateway` service entirely; ...**` / `**S2. Remove
# the `whoami` proof app**` -- the structural shape both real S-actions
# use for "this item's entire purpose is removing a named component".
# Captures the first backticked name directly after "Remove (the)?" --
# not a scan for any backticked word in the heading (S1's own heading
# also backticks `api`, which must NOT be captured here).
REMOVE_HEADING_RE = re.compile(r"^\*\*[A-Za-z0-9]+\. Remove (?:the )?`([\w.-]+)`")


def _item_blocks(lines):
    """Map every item id (ITEM_ID_RE, broader than HEADING_RE) to its
    (start_line_index, block_text) -- block runs from its own heading
    up to (not including) the next item heading of any id."""
    headings = [(i, m.group(1)) for i, line in enumerate(lines) if (m := ITEM_ID_RE.match(line))]
    blocks = {}
    for idx, (line_no, iid) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        blocks[iid] = (line_no, "\n".join(lines[line_no:end]))
    return blocks


def check_status_markers(lines, gone=None):
    """backlog #147: an item referenced elsewhere as done/closed (the
    #21a shape), or named as a confirmed-gone component (the S1/S2
    shape, via --gone), whose own entry carries no closing marker.

    Deliberately narrow, per the AC's own instruction: no fuzzy
    NLP/negation-phrase detection anywhere in this function. Both
    sub-checks below are pattern-matching over a specific, stated
    textual shape, not a semantic read of the sentence.
    """
    errors = []
    blocks = _item_blocks(lines)

    # --- (a) #21a shape: cross-referenced as done, unmarked itself ---
    referenced_by = {}  # ref_id -> [1-based line numbers of the Dependencies line]
    for i, line in enumerate(lines):
        if not line.startswith("- Dependencies:"):
            continue
        for m in DEP_REF_RE.finditer(line):
            ref_id, paren = m.group(1), m.group(2)
            if DONE_KEYWORD_RE.search(paren):
                referenced_by.setdefault(ref_id, []).append(i + 1)

    for ref_id, dep_lines in sorted(referenced_by.items()):
        block = blocks.get(ref_id)
        if block is None:
            # Referenced id isn't a real item heading at all (e.g. a
            # non-backlog reference like a PR/issue number) -- nothing
            # of ours to check.
            continue
        _, block_text = block
        if not OWN_MARKER_RE.search(block_text):
            where = ", ".join(f"line {n}" for n in dep_lines)
            errors.append(
                f"item #{ref_id} is referenced as done/closed in another item's Dependencies "
                f"line ({where}) but its own entry carries no Done/CLOSED/MERGED/Superseded "
                f"marker (#21a shape, backlog #147)"
            )

    # --- (b) S1/S2 shape: confirmed-gone component, unmarked itself ---
    for name in gone or []:
        for line in lines:
            m = REMOVE_HEADING_RE.match(line)
            if not m or m.group(1) != name:
                continue
            item_id = ITEM_ID_RE.match(line).group(1)
            _, block_text = blocks[item_id]
            if not OWN_MARKER_RE.search(block_text):
                errors.append(
                    f"item #{item_id}: component `{name}` is confirmed gone from the live "
                    f"roster but the item's own entry carries no Done/CLOSED/MERGED/Superseded "
                    f"marker (S1/S2 shape, backlog #147)"
                )
            break  # first matching heading only -- a name is removed by one item

    return errors


def check(path, gone=None):
    lines = open(path, encoding="utf-8").read().split("\n")

    headings = [(i, int(m.group(1))) for i, line in enumerate(lines) if (m := HEADING_RE.match(line))]
    errors = []
    errors.extend(check_status_markers(lines, gone=gone))

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


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="docs/roadmap/backlog.md")
    parser.add_argument(
        "--gone",
        action="append",
        default=[],
        metavar="COMPONENT",
        help=(
            "component name confirmed removed from the live roster (backlog #147, "
            "S1/S2 shape) -- wired in from check-roster-drift.sh, which is the "
            "script that actually knows what's still live. May repeat."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    headings, errors = check(args.path, gone=args.gone)

    if errors:
        for e in errors:
            print(f"::error file={args.path}::{e}", file=sys.stderr)
        print(f"\n{len(errors)} backlog structural integrity error(s) found (backlog #97b/#147).", file=sys.stderr)
        sys.exit(1)

    if not headings:
        print("backlog.md structural integrity OK: no numeric top-level items found, status-marker checks passed.")
        return

    nums = sorted(n for _, n in headings)
    print(f"backlog.md structural integrity OK: {len(headings)} items, #{nums[0]}-#{nums[-1]}, no gaps, no duplicates, no swallowed headings, no status-marker drift.")


if __name__ == "__main__":
    main()
