# 0034. SOPS+age recovery copy for selected secrets, over External Secrets Operator

Status: Accepted

## Context

Every secret this project provisions is generated out-of-band
(`bootstrap/create-stateful-secrets.sh`) and never committed to git —
safe from a real git-history leak on a public repo, but unversioned:
if the laptop this cluster runs on dies, every one of those secrets is
gone with no recovery path, the same exposure class ADR 0030 already
accepted and documented for Terraform's own local state.

This isn't new — `create-stateful-secrets.sh`'s own header comment
already weighed SOPS/sealed-secrets against the current approach once
and deferred: "a genuine new dependency... for a personal single-node
project with exactly 4 low-stakes credentials that never leave the
cluster. Worth reconsidering if the number of managed secrets or
rotation frequency grows." That trigger has arrived, not because the
count grew dramatically, but because real rotation has actually
happened now (the ntfy topic, backlog #107; per-tenant API keys,
backlog #56) — each one a real event where the *only* copy of a real
credential existed solely on this one laptop.

## Decision

**SOPS, with `age` as the encryption backend — not External Secrets
Operator, not sealed-secrets.**

### Rejected: External Secrets Operator (ESO)

ESO's whole value is syncing secrets *from* an external store (AWS
Secrets Manager, Vault, GCP Secret Manager, ...) *into* Kubernetes —
which means adopting it doesn't solve this project's actual problem
without also adopting a real external secret store, a second new
dependency riding on the first. That store would itself need an
account, credentials of its own, and its own recovery story — for a
personal single-node cluster, that's a disproportionate amount of new
infrastructure to protect a handful of low-stakes credentials, the
same "don't operate a new component to answer a question a simpler
mechanism already answers" reasoning ADR 0014 (Mimir vs. a retention
config value) and ADR 0032 (Strimzi vs. persistence) already applied
to this project's other tooling decisions. ESO also runs as an
in-cluster controller — a real, permanent addition to what's running,
for a problem that's fundamentally about *recovery*, not *live
syncing*.

### Rejected: sealed-secrets

Closer to right-sized than ESO (no external store needed, just an
in-cluster controller with its own keypair), but still a new, always-
on controller whose own private key becomes exactly the same "what if
the laptop dies" problem this decision exists to solve, one layer
down — sealed-secrets' own decryption key would need its own backup
story. SOPS+age has no in-cluster component at all: encryption and
decryption both happen at bootstrap-script-run time, on the operator's
own machine, with a private key that already has an obvious, simple
recovery answer (a password manager) rather than needing a new one
invented.

### Chosen: SOPS + age

- **No new in-cluster component.** SOPS is a CLI tool run at
  bootstrap-script time, `age` is a single small age-encryption
  library — both live entirely outside the cluster, matching this
  project's own established "boring, explicit over magic" bias.
- **The encrypted file itself is the recovery artifact.** Once
  committed to git, `bootstrap/secrets/<name>.enc.yaml` is safe to be
  fully public (it's ciphertext) and survives a laptop loss by
  definition — the only thing that needs a separate backup is the
  `age` private key itself, a single small text file, an obvious fit
  for a password manager (the same real answer this project already
  gives for the Finnhub API key and other human-held credentials).
- **`age` over PGP** (SOPS' other common backend): no keyring/web-of-
  trust ceremony, a single keypair, and the project's own operator has
  no existing PGP setup to reuse — starting fresh, the simpler option
  wins.

### What's actually migrated, and what deliberately isn't

**`ntfy-webhook-url` is the one secret migrated end-to-end as this
decision's own proof** (`bootstrap/create-stateful-secrets.sh`'s new
`sops_value()` helper) — chosen because rotating it is already a real,
low-stakes, previously-designed operation (the script's own README
already documented "delete the Secret and re-run" as supported), not
a new risk introduced to prove a point. Real round-trip proven: a
fresh topic generated, encrypted, decrypted back, and applied live —
see this ADR's own backlog item (#100) for the live verification
record.

**The 6 stateful DB-credential Secrets** (`postgresql`, `redis`,
`kafka-kraft`, `grafana`, `clinvar-postgresql`, `watchlist-postgresql`)
are **deliberately not migrated in this pass.** Rotating any of them
means changing a real, already-running container's actual
authentication — the same class of real, maintenance-window-shaped
operation backlog #73 needed for a single Postgres superuser password.
Bundling six of those into "prove the SOPS mechanism works" would risk
real, live credentials for a demonstration that doesn't need them —
`ntfy-webhook-url` proves the mechanism completely on its own.
Migrating the stateful DB credentials is real, valuable follow-on
work, tracked separately, not assumed done here.

## Consequences

- `bootstrap/secrets/*.enc.yaml` and `bootstrap/.sops-age-recipient`
  (the public key, safe to commit) are new, git-tracked files.
  `bootstrap/create-stateful-secrets.sh`'s own `sops_value()` helper
  falls back to today's plain-generation behavior if `sops`/the
  recipient file aren't present, so a fresh checkout without SOPS
  installed yet doesn't get blocked — a real, stated degradation path,
  not a hard new requirement.
- **The recover-without-laptop path, stated explicitly**: the `age`
  private key lives in the operator's own password manager (generated
  once, backed up immediately, never committed to git). Recovering
  this cluster's `ntfy-webhook-url` secret after a full laptop loss
  needs: a fresh checkout of this repo (the encrypted file is already
  there), `sops`/`age` installed, `SOPS_AGE_KEY_FILE` pointed at the
  restored private key from the password manager, then a normal
  `create-stateful-secrets.sh` run — `sops_value()` decrypts the
  existing file and recovers the exact same topic, no new rotation
  forced by the rebuild itself.
- **Rotation is unchanged in shape, improved in effect**: deleting the
  live Secret and re-running the script still generates a fresh value
  (as documented before) — the only difference is the new value also
  gets a fresh encrypted recovery copy written automatically, so
  rotation and "stay recoverable" are no longer in tension.
- Extending this pattern to the 6 stateful DB credentials, and to the
  remaining per-tenant API keys (backlog #56), is real, valuable,
  explicitly out-of-scope follow-on work — not silently assumed
  covered by this decision.
