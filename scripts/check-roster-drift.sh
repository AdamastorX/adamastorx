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

PLATFORM_DIR="${1:?usage: check-roster-drift.sh <platform-repo-path> <overview.md-path>}"
OVERVIEW_MD="${2:?usage: check-roster-drift.sh <platform-repo-path> <overview.md-path>}"

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
done

if [ "$fail" -ne 0 ]; then
  echo "One or more live components are missing from docs/architecture/overview.md (backlog #97a, recurrence of #83)." >&2
  exit 1
fi

echo "Every live custom-service component is mentioned in docs/architecture/overview.md."
