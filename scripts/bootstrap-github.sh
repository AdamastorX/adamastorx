#!/usr/bin/env bash
# One-time (and re-runnable) setup of the AdamastorX GitHub org from this
# local scaffold. Plain sequential `gh` calls — no framework, nothing to
# maintain beyond this file.
#
# Deliberately NOT automated here: GitHub Project v2 custom status columns
# (Inbox/Ready/In Progress/Review/Done) and issue creation from the backlog.
# Project field customisation via `gh` needs several fragile ID lookups for
# a step you do once; issue creation from docs/roadmap/backlog.md needs a
# parser for a format that hasn't been validated by real use yet. Both are
# cheap to do by hand once, expensive to build automation for prematurely.
#
# Requires: gh CLI installed and authenticated (`gh auth login`) with an
# account that has repo-creation rights on the AdamastorX org.

set -euo pipefail

ORG="AdamastorX"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"  # .../AdamastorX (repos root)
REPOS=(adamastorx platform services observability)
MILESTONES=("M0 Foundation" "M1 Platform Bootstrap" "M2 Distributed Application" "M3 Observability" "M4 Reliability")

command -v gh >/dev/null || { echo "gh CLI not found. Install it first: https://cli.github.com"; exit 1; }
gh auth status >/dev/null || { echo "Not logged in. Run: gh auth login"; exit 1; }

echo "This will create/update repos, labels, and milestones under github.com/$ORG."
read -rp "Continue? [y/N] " confirm
[[ "$confirm" == "y" || "$confirm" == "Y" ]] || exit 0

for repo in "${REPOS[@]}"; do
  full="$ORG/$repo"
  dir="$ROOT/$repo"

  echo "== $full =="

  if gh repo view "$full" >/dev/null 2>&1; then
    echo "repo exists, skipping create"
  else
    gh repo create "$full" --public --description "AdamastorX: $repo" --disable-wiki
  fi

  if [[ -d "$dir/.git" ]]; then
    (cd "$dir" && git remote get-url origin >/dev/null 2>&1 || git remote add origin "git@github.com:$full.git")
    (cd "$dir" && git push -u origin HEAD)
  fi

  echo "syncing labels"
  # labels.yml has a fixed 3-line-per-entry shape (name/color/description) —
  # parse it with awk instead of pulling in a YAML library for 3 fields.
  while IFS='|' read -r name color desc; do
    [[ -z "$name" ]] && continue
    gh label create "$name" --repo "$full" --color "$color" --description "$desc" --force
  done < <(awk '
    /^- name:/  { name=$0; sub(/^- name: /,"",name) }
    /^  color:/ { color=$0; sub(/^  color: /,"",color); gsub(/"/,"",color) }
    /^  description:/ {
      desc=$0; sub(/^  description: /,"",desc)
      print name "|" color "|" desc
    }
  ' "$ROOT/adamastorx/.github/labels.yml")

  # New repos come with GitHub's own default label set baked in — remove
  # anything not declared in labels.yml so it doesn't drift from our
  # single source of truth.
  for stock in "duplicate" "help wanted" "invalid" "question" "wontfix" "good first issue"; do
    gh label delete "$stock" --repo "$full" --yes 2>/dev/null || true
  done

  echo "creating milestones"
  for m in "${MILESTONES[@]}"; do
    gh api "repos/$full/milestones" -f title="$m" >/dev/null 2>&1 || true  # already exists -> ignore
  done
done

echo
echo "Done. Manual steps still needed (one-time, ~5 min):"
echo "  1. Create the org project:  gh project create --owner $ORG --title AdamastorX"
echo "  2. Edit its default 'Status' field to: Inbox, Ready, In Progress, Review, Done"
echo "  3. File the backlog issues from docs/roadmap/backlog.md (gh issue create),"
echo "     one per entry, with the listed labels/milestone."
