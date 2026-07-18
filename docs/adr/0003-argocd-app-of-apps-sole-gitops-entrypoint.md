# 0003. ArgoCD app-of-apps as the sole GitOps entrypoint

Status: Accepted (retroactive — decision shipped in platform PR #8 before
this ADR was written)

## Context

M1 needed a way to get workloads onto the k3s cluster that doesn't decay
into a pile of `kubectl apply` commands nobody can reproduce. Options
considered: manual kubectl / Helm-CLI-driven deploys (no source of truth,
drift invisible), per-app ArgoCD Applications applied by hand (Git holds
the manifests but the set of *Applications* itself is unmanaged — the same
drift problem one level up), or an app-of-apps root that makes Git
authoritative for everything including the Application list.

## Decision

One root `Application` (`platform/bootstrap/root-app.yaml`) watches
`argocd/apps/` on `main` with automated sync, `prune: true`,
`selfHeal: true`. Every new workload is one Application manifest added to
that directory via PR: merged to `main` means deployed, deleted from
`main` means removed, manual drift gets reverted.

Exactly one manual-kubectl exception is sanctioned: the initial bootstrap
(`bootstrap/install-argocd.sh` installs ArgoCD and applies the root app —
pre-GitOps by definition), which also covers ArgoCD version bumps via
re-run of the script. A second, temporary exception was used during PR
testing: flipping the root app's `targetRevision` to the feature branch to
verify end-to-end before merge, flipped back to `main` before merging.

ArgoCD itself is installed from the official upstream install manifests
pinned to a version tag (v3.4.5), **non-HA**, not the Helm chart:
single-node cluster, HA would be gold plating, and there is nothing to
templatize yet. Revisit (values-managed, self-managed Helm install) only
if ArgoCD ever needs real configuration.

## Consequences

- Adding or changing anything in the cluster is a PR to the platform repo;
  there is no faster path, by design.
- `prune` + `selfHeal` mean hand-applied experiments get deleted — the
  cluster cannot be used as a scratchpad.
- The branch-flip test procedure touches the live root app; it is
  acceptable only pre-merge and must always end pointed back at `main`.
- Upgrading ArgoCD is a bootstrap-script edit plus re-run, not a chart
  bump; if configuration needs ever grow, that install method gets
  revisited via a new ADR.
