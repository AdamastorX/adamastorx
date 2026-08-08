#!/usr/bin/env bash
set -euo pipefail

# backlog #97(a): fails if a live custom-service Application (this
# project's own code, deployed from an in-repo `kubernetes/<name>`
# manifest path) isn't mentioned anywhere in
# docs/architecture/overview.md. This is the mechanical generalization
# of #83's real, twice-recurring failure -- overview.md claiming M13's
# five services "do not exist yet" while they were live -- catching "a
# whole component is entirely unmentioned", not full narrative
# correctness (which no cheap CI check can verify).
#
# Roster = Applications in platform/argocd/apps/*.yaml whose
# spec.source.path is set (an in-repo raw manifest -- this project's
# own service, not a third-party Helm chart) AND whose name doesn't end
# in -ingress/-issuers/-backup (helper resources for an
# already-narrated component, not a component of their own). Both
# rules are structural, derived from how Applications are actually
# built -- not a manually maintained allow/deny list of component
# names that could itself silently drift the same way overview.md did.
# Third-party infra (Prometheus, Grafana, Redis, ...) is deliberately
# excluded: this project's docs correctly refer to those by their
# product name in prose, not by their lowercase Helm release name, so
# requiring a literal-string match would be noise, not signal.
#
# backlog #109: a second, optional check -- a live component older
# than a grace period should also be mentioned in the Grafana
# dashboard file and in ADR 0020's SLO table, "closing the loop
# instead of relying on the template alone" (that item's own AC). Same
# "mentioned anywhere" mechanism as the overview.md check above, which
# doubles as the exemption path: CONTRIBUTING.md's own new checklist
# line asks a component with no real dashboard/SLO row to state why in
# the same files (ADR 0020's "Components without their own row"
# section; grafana.yaml's own top-of-file comment) -- a stated reason
# is found by the exact same grep as a real entry, no separate
# exemption list to maintain or let drift.

PLATFORM_DIR="${1:?usage: check-roster-drift.sh <platform-repo-path> <overview.md-path> [<grafana.yaml-path> <adr-0020-path> <grace-days>]}"
OVERVIEW_MD="${2:?usage: check-roster-drift.sh <platform-repo-path> <overview.md-path> [<grafana.yaml-path> <adr-0020-path> <grace-days>]}"
GRAFANA_YAML="${3:-}"
ADR_0020="${4:-}"
GRACE_DAYS="${5:-14}"

if ! command -v yq >/dev/null 2>&1; then
  echo "yq is required (https://github.com/mikefarah/yq)" >&2
  exit 1
fi

fail=0
shopt -s nullglob
files=("$PLATFORM_DIR"/argocd/apps/*.yaml)
shopt -u nullglob

if [ "${#files[@]}" -eq 0 ]; then
  echo "No ${PLATFORM_DIR}/argocd/apps/*.yaml files found -- nothing to check." >&2
  exit 0
fi

for f in "${files[@]}"; do
  src_path=$(yq eval '.spec.source.path // ""' "$f")
  [ -z "$src_path" ] && continue

  name=$(yq eval '.metadata.name' "$f")
  case "$name" in
    *-ingress | *-issuers | *-backup) continue ;;
  esac

  if ! grep -qF -- "$name" "$OVERVIEW_MD"; then
    echo "::error file=${OVERVIEW_MD}::live component '${name}' (${f}) is not mentioned anywhere in overview.md" >&2
    fail=1
  fi

  if [ -z "$GRAFANA_YAML" ] || [ -z "$ADR_0020" ]; then
    continue
  fi

  # git log's own real first-commit timestamp for this file -- requires
  # full history (fetch-depth: 0), not the shallow clone actions/checkout
  # defaults to. A file with no history yet (just added, not committed)
  # has nothing to check age against -- skip silently, the grace period
  # exists precisely so a brand-new component isn't flagged instantly.
  first_commit_epoch=$(git -C "$PLATFORM_DIR" log --follow --format=%ct -- "argocd/apps/$(basename "$f")" 2>/dev/null | tail -1 || true)
  [ -z "$first_commit_epoch" ] && continue

  age_days=$(( ($(date -u +%s) - first_commit_epoch) / 86400 ))
  if [ "$age_days" -lt "$GRACE_DAYS" ]; then
    continue
  fi

  if ! grep -qiF -- "$name" "$GRAFANA_YAML"; then
    echo "::error file=${GRAFANA_YAML}::live component '${name}' has existed for ${age_days}d (past the ${GRACE_DAYS}d grace period) with no dashboard entry and no stated reason (backlog #109)" >&2
    fail=1
  fi
  if ! grep -qiF -- "$name" "$ADR_0020"; then
    echo "::error file=${ADR_0020}::live component '${name}' has existed for ${age_days}d (past the ${GRACE_DAYS}d grace period) with no SLO-table row and no stated reason (backlog #109)" >&2
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "One or more live components are missing from overview.md, or (past the grace period) from the dashboard/SLO surface with no stated reason (backlog #97a/#109)." >&2
  exit 1
fi

echo "Every live custom-service component is mentioned in overview.md, and (where past the grace period) has a dashboard/SLO entry or a stated reason."
