# Cross-repo rollout: `services` change → `platform` promotion

A `services` merge never reaches the cluster by itself (ADR 0009 —
manual SHA-bump PR, deliberately no auto-promotion). This is the
checklist for the second half: getting a built image live and proven.
Used manually every time so far (services#3 Kafka, services#4 Postgres);
writing it down so it doesn't depend on remembering the last time.

## Checklist

1. **`services` CI is green** on the merge commit — `build` (tests,
   including any Testcontainers-backed ones) and `scan` (image builds +
   boots + Trivy) for every affected module. Don't start the promotion
   PR before this; a red `main` in `services` means nothing to promote
   yet.
2. **Get the exact image reference.** `build-publish.yml` tags images
   `ghcr.io/adamastorx/<module>:<merge-commit-sha>` — use the full SHA
   from `git log` / the merge commit, not a shortened one, not `main`,
   not `latest` (ADR 0008 forbids floating tags on purpose).
3. **Open the `platform` PR**: bump the image tag in
   `kubernetes/<service>/deployment.yaml`, plus any new/changed
   manifests (new `argocd/apps/*.yaml`, new env vars, new
   `secretKeyRef`s). One concern per PR where reasonable — a pure SHA
   bump and a new dependency's manifests can be separate PRs if they're
   logically distinct changes landing at the same time.
4. **Config and Secrets, not just the image.** If the change needs new
   environment variables or credentials: confirm the source (plain
   value with an in-cluster DNS default, vs. `secretKeyRef` into a
   chart-generated Secret — never a plaintext credential in git). Check
   same-namespace constraints before assuming a `secretKeyRef` will
   resolve (Kubernetes Secrets don't cross namespaces).
5. **Validate before applying**: `kubectl apply --dry-run=client` for
   every changed/new manifest, and — for a new Helm-chart Application —
   render it locally with `helm template` against the exact
   `valuesObject` first. This has caught real bugs before they touched
   the cluster (a chart's `config` key silently replacing its entire
   generated defaults, a 404'd base image tag).
6. **Merge, then force an ArgoCD sync** rather than waiting for the
   default poll interval:
   ```
   kubectl patch application root -n argocd --type merge \
     -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
   ```
   then the same for the specific Application(s) touched, once `root`
   has picked up the new/changed Application definitions.
7. **Confirm `Synced` *and* `Healthy`**, not just `Synced` — a synced
   manifest with a crash-looping pod is not a successful rollout.
   `kubectl get application <name> -n argocd` and `kubectl get pods -n
   <namespace>`.
8. **Functional proof, not just health checks.** A green liveness probe
   proves the process started, not that the feature works. Exercise the
   actual change — `curl` the new endpoint through a port-forward,
   `psql`/`kafka-console-consumer.sh` into the backing store directly if
   there's one, check the specific log line that proves the code path
   ran. This has caught real bugs health checks missed (Flyway
   silently never running, a consumer group that never formed).
9. **Rollback path**: revert the `platform` PR (previous image SHA,
   previous manifest) and re-sync — same mechanism as step 6. Note
   whether the change is stateful (a new PVC, a new migration) before
   assuming a straight revert is enough; a schema migration doesn't
   un-apply itself.
10. **Update docs** — `docs/architecture/overview.md`'s "Live today"
    section, the relevant ADR's status/consequences if reality diverged
    from the plan, and `SESSION_STATE.md` if the rollout isn't fully
    finished yet. Skipping this is how `overview.md` ends up stale (it
    did, twice).

## What this doesn't cover

Automating step 2–3 (a bot that opens the bump PR automatically) is a
real future option but not built — ADR 0009's explicit revisit trigger
is "bump PRs are demonstrably rote toil (several per week)," which
hasn't happened yet. Don't add tooling ahead of that signal.
