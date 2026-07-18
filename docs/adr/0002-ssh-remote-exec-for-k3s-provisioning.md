# 0002. SSH remote-exec for k3s provisioning, scoped sudoers over broad NOPASSWD

Status: Accepted

## Context

M1 needed k3s running somewhere, starting on the engineer's own machine and
moving to dedicated hardware later. Terraform's job here isn't provisioning
compute (the machine already exists) — it's installing and configuring k3s
on a target host, consistently, whether that host is `localhost` today or a
different box next month.

Two decisions needed making:

1. **How Terraform reaches the target host.** Options: `local-exec`
   (install runs on whatever machine runs `terraform apply`) vs. SSH
   `remote-exec` (install runs on a host reached over SSH, which can be the
   same machine or a different one without changing the module).
2. **How Terraform gets root on that host without an interactive password
   prompt**, since `remote-exec` has no TTY for `sudo` to prompt against.
   Options: broad `NOPASSWD: ALL` for the automation user vs. a narrow
   sudoers allowlist for exactly the scripts Terraform needs to run.

## Decision

- Use SSH `remote-exec` against `var.target_host` (default `127.0.0.1`),
  not `local-exec`. Moving to another host later is then a one-variable
  change plus repeating the one-time host prep (see
  `platform/terraform/README.md`) — the module itself doesn't change.
- Use a narrow sudoers allowlist: NOPASSWD scoped to exactly
  `~/.adamastorx/k3s-install.sh` and `/usr/local/bin/k3s-uninstall.sh`,
  nothing else. Rejected broad `NOPASSWD: ALL`, which would be simpler to
  set up once and never touch again, but means any process running as that
  user — not just Terraform — gets root with no prompt and no audit trail.

## Consequences

- The sudoers file (`/etc/sudoers.d/adamastorx-k3s`) is host state Terraform
  doesn't manage and doesn't know about — it's a documented one-time manual
  step, validated with `visudo -c` before and after, done by the human
  operator. This is a deliberate gap, not an oversight: scripting root-owned
  sudoers edits carries real lock-out risk for a step that isn't repeated
  work.
- If the install method changes (e.g. a different installer script, a new
  path), the sudoers allowlist has to be updated by hand to match. This is
  the accepted cost of the narrower, safer option.
- Any future Terraform-driven root action on the target host needs its own
  explicit allowlist entry — there is no blanket escape hatch, by design.
