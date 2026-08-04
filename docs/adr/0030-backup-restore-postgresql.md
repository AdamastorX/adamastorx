# 0030. Backup and restore for stateful PostgreSQL data: `pg_dump` CronJob per instance, node/disk loss an accepted risk

Status: Accepted

## Context

An independent staff-engineer audit (`docs/SESSION_STATE.md`) found a
genuinely uncovered gap: no stateful component in this project had a
documented or automated backup/restore path. `api`'s PostgreSQL
(`work_items`), `clinvar-service`'s dedicated PostgreSQL
(`clinvar_release`/`clinvar_variant_index`), Loki, and Tempo are each a
single node-pinned `local-path` PVC on the one k3s node this cluster
has, with no `pg_dump`, snapshot, or off-node copy anywhere — a disk
failure or an accidental `kubectl delete pvc`/`helm uninstall` meant
silent, total, unrecoverable data loss with no runbook to even attempt
recovery. Tracked as backlog #23a; #23b (a dedicated node-loss game day)
was folded into it by ADR 0021/S7, on the grounds that a separate
"kill the node" exercise is ceremony on a single-node laptop cluster —
the one genuinely distinct ask it carried, a real measured restore time
rather than an estimate, is satisfied by this item's own restore proof
below.

This ADR is the decision record for that gap; the mechanism, the full
comparison against the platform's own chart-native option, and the real
restore proof already live in `platform`'s
`docs/runbooks/backup-restore.md` (platform#62, merged and proven
2026-07-30) — this ADR exists to put the decision itself into this
project's own decision log (`docs/adr/`), discoverable from the
`adamastorx` repo without needing to cross into `platform` to find it,
and to record the alternatives considered against this project's actual
stakes rather than leave that reasoning implicit in a platform-repo
runbook. Backlog #81 (`aggregator`) already names this item as a real
prerequisite ("the state-store-recovery AC needs the same restore
discipline #23a already established") — a decision record that only
existed as platform-repo runbook prose was a real gap for that kind of
forward reference.

## Decision

**A daily `pg_dump` `CronJob` per PostgreSQL instance** (`postgresql`/
`api` namespace, `clinvar-postgresql`/`clinvar` namespace), each writing
to its own **second, separate** node-pinned `local-path` PVC —
deliberately not the database's own data PVC, so an accidental
`kubectl delete pvc`, a bad `helm uninstall`, or logical corruption in
the live database doesn't also take out the backup sitting on the exact
same volume. Credentials via this project's existing out-of-band Secret
pattern (`bootstrap/create-stateful-secrets.sh`) — the CronJobs
authenticate as each instance's existing least-privilege app user
(`api`/`clinvar`), the same credential each service already uses for
every request, not a new credential invented for backup. 14 days'
retention, pruned by the job's own script (`find … -mtime +14 -delete`),
staggered schedules (`03:00`/`03:15`) so the two dumps don't contend for
the single node's disk I/O. Full manifests: `platform`'s
`kubernetes/postgresql-backup/` and
`kubernetes/clinvar-postgresql-backup/`.

**Loki and Tempo are explicitly out of scope — a stated decision, not a
silent gap.** Both hold observability telemetry (logs, traces), a
byproduct of the system running rather than data anyone created or that
anything else depends on for correctness. Losing either's PVC costs a
gap in historical dashboard/trace lookups; the next request regenerates
fresh logs and traces immediately. That is a materially different risk
than losing `work_items` or ClinVar's release provenance, which have no
regeneration path (ClinVar's own upstream release could be re-ingested,
but the specific local `clinvar_release` history and indexed state as it
existed would not match). Spending real effort protecting regenerable
data isn't worth it for this project.

### What this protects against, and what it does not

This backs up against: an accidental `kubectl delete pvc`, a bad `helm
uninstall`, application-level logical corruption (a bad migration, a bad
manual `DELETE`), or simply wanting to inspect/restore a prior day's
state. **It does not protect against single node or disk loss, and that
is an accepted risk, stated explicitly, not an implicit assumption.**
Both the primary PVC and its backup PVC are `local-path` — node-pinned,
currently landing on the same physical disk on the one node this
cluster has. Losing that node or disk loses both at once. This is the
same acceptance already on record in ADR 0021/S7: a dedicated node-loss
game day is ceremony on a single-node cluster, since killing the node is
just killing everything on it, backup included, and nothing here could
survive that today. The moment this matters again is a real multi-node
migration (roadmap M7) — off-node backup replication is a fresh decision
for whatever storage substrate that migration lands on, not something to
half-build speculatively now.

### Alternatives considered and rejected

- **The Bitnami `postgresql` chart's own built-in `backup.enabled`
  CronJob** (chart 16.2.1, `helm show values` — checked directly, not
  assumed). Structurally the same shape this item asks for, so tried
  first. Rejected for a concrete, verified reason: it hardcodes
  `pg_dumpall` authenticating as the `postgres` superuser via the
  existingSecret's `postgres-password` key, and that credential does
  not actually authenticate against `api`'s live instance
  (`password authentication failed`, confirmed live 2026-07-30 —
  tracked separately as backlog #73, a latent, previously-undetected
  gap, not fixed as part of this read-only backup work). Depending on a
  credential known to be broken on at least one instance for a backup
  job's nightly success is the wrong foundation; a plain `pg_dump`
  CronJob authenticating as each instance's already-working app user
  sidesteps it entirely, and is also the strictly correct scope anyway
  — each instance owns exactly one database, so `pg_dumpall`'s
  whole-cluster/roles reach was never needed.
- **`pg_basebackup` / continuous WAL archiving (physical backup with
  point-in-time recovery)**. Rejected: PITR solves a problem this project
  doesn't have. The AC asks for a restore proven with row-count parity
  and a measured RTO, not recovery to an arbitrary moment in time — a
  periodic logical dump already gets within, at worst, one day's data
  loss (the CronJob's own schedule), acceptable for `work_items`
  synthetic data and a ClinVar release history that changes on its own
  much slower cadence. Standing up a WAL archiving target, replication
  slot management, and a continuous `archive_command` is real, ongoing
  operational surface for a recovery precision this project's actual
  stakes never asked for — exactly the gold-plating ADR 0021's "boring,
  well-understood tools" bias argues against.
- **An off-node object-storage target** (e.g. dumps shipped to a MinIO
  or S3-compatible bucket instead of a second local PVC). Rejected on
  two grounds: this cluster runs no object storage today — the one
  candidate (self-hosted MinIO for M6's FASTQ pipeline) was itself
  closed by ADR 0021 decision 4, so standing one up solely to hold a
  handful of dumps totalling single-digit-to-tens-of-MB
  (`work_items`: 4.4K; `clinvar`: 33M, both measured live) would be a
  whole new storage substrate introduced purely to serve backup, wildly
  disproportionate to what it protects. And it wouldn't even fully buy
  the thing it sounds like it buys: true off-node protection needs the
  copy to leave this one physical machine's network path during the
  exact failure it's meant to survive, which is a real multi-node/
  off-site design question this project doesn't have an answer for yet
  (the same "defer to the real M7 multi-node migration" reasoning as
  the node/disk-loss risk above), not something to bolt onto a single
  laptop as a false sense of coverage now.
- **Velero + CSI volume snapshots**. Rejected on a concrete
  infrastructure fact, not a preference: k3s's default `local-path`
  provisioner is a static hostPath-based provisioner with no CSI
  snapshot controller and no `VolumeSnapshotClass` — Velero's core value
  (crash-consistent volume snapshots) isn't reachable here without first
  swapping the cluster's storage provisioner entirely, a much larger,
  unrelated infrastructure change than a personal single-node backup
  item should trigger on its own. A `pg_dump` CronJob needs nothing the
  cluster doesn't already have.

## Consequences

- Two new `local-path` PVCs (`postgresql-backup`: 1Gi, sized against
  `work_items`' real measured ~4.4K dump with years of headroom;
  `clinvar-postgresql-backup`: 2Gi, sized against `clinvar`'s real
  measured ~33M dump) and two new CronJobs are a small, permanent,
  real addition to this cluster's resource footprint and ArgoCD-managed
  surface — accepted as proportionate to what they close.
- Real restore already proven live (2026-07-30, `platform`#62): dumps
  taken read-only from both live instances, restored into a throwaway
  scratch instance/PVC/namespace (never the live Applications, no
  ArgoCD involvement), row counts verified to match exactly
  (`work_items`: 15/15, `clinvar_variant_index`: 2,895,514/2,895,514,
  `clinvar_release`: 4/4) plus a content spot-check on a known row
  (`rs80357906`, BRCA1 — the same variant ADR 0018/backlog #24's
  integration test asserts against). Measured RTO, wall-clock, not
  estimated: **`api` → scratch, 0.31s**; **`clinvar` → scratch, 46.4s**.
  Scratch namespace/pod/PVC deleted afterward; live instances' restart
  counts and PVCs confirmed unchanged throughout. Full log:
  `platform`'s `docs/runbooks/backup-restore.md`.
- Backlog #73 (api's `postgres` superuser credential doesn't
  authenticate, found investigating the chart's built-in backup option)
  is a real, separate, currently-open finding this work surfaced but did
  not fix — out of scope for a read-only backup task, needs a real
  `pg_hba.conf` trust-mode maintenance window.
- No point-in-time recovery: restore is only ever to the last completed
  daily dump, up to ~24h of loss at worst. Stated as acceptable for this
  project's actual stakes, not revisited unless a real need for tighter
  RPO ever appears.
- No automated recurring restore drill: this was a proven, one-time,
  real exercise per #23a's own acceptance criteria, not a committed
  recurring game-day. A future repeat is a fine ad-hoc exercise, not a
  standing obligation.
- Backlog #81 (`aggregator`'s windowed correlation state-store recovery)
  can now cite a real, already-established restore discipline instead
  of an unresolved dependency.
