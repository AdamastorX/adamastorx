# 0023. Adopt Cilium (eBPF CNI) + Hubble, overturning its place on the excluded-tools list

Status: Proposed

## Context

`.claude/PROJECT.md` lists five tools as "explicitly excluded — do not
introduce without an ADR overturning this": **service mesh, Vault,
Crossplane, Backstage, Cilium.** That list was written to stop the
project accreting resume-driven infrastructure. It did its job. ADR 0022
reopens the question — not the list wholesale, but tool by tool, each
needing a real stated reason rather than novelty.

Four of the five are re-examined here and **stay excluded**:

- **Service mesh (Istio/Linkerd).** The three things a mesh is usually
  bought for are already solved here by cheaper means: golden signals and
  distributed tracing exist (ADR 0013/0017, real traces across a
  Java↔Python boundary), retries/timeouts are a handful of lines in two
  clients, and mTLS between four pods on hardware the owner physically
  controls secures nothing against a real threat. A mesh would add a
  sidecar (or ambient dataplane), a control plane, and a second source of
  truth for routing, to re-tell a story the OTel stack already tells
  better. The one genuinely uncovered piece — L7-aware policy — is
  available from Cilium below without a mesh. **Stays excluded.**
- **Vault.** There *is* real, recurring secret pain here: platform#34's
  Bitnami-generated Secret silently regenerated twice, and backlog #36
  is still open to fix its root cause. But Vault's actual root-cause fix
  is "stop letting a chart generate the password", which `existingSecret`
  plus an encrypted-in-Git secret (SOPS/age, or Sealed Secrets) achieves
  with **zero new runtime components**. Vault brings an unseal ceremony,
  its own storage backend and backup problem, and an injector webhook —
  a new SPOF in front of every pod start — to solve a problem a file
  format solves. If secret management is worth an experiment, it is worth
  it as SOPS/ESO under #36, not as Vault. **Stays excluded.**
- **Crossplane.** Its value is a Kubernetes-native control plane for
  *cloud* resources. This project provisions one thing — a k3s host — and
  Terraform already does it with a proven destroy/recreate cycle (#48
  exercises it again). Crossplane here would be a second, weaker
  Terraform managing nothing. **Stays excluded.**
- **Backstage.** A developer portal exists to solve discovery and
  self-service across many teams and many services. There is one
  operator. **Stays excluded** — this is the clearest "teaches nothing
  new at this scale" of the five.

**Cilium is different**, for three reasons that are specific to this
project rather than general enthusiasm:

1. **There is a stated, unclosed security gap.** ADR 0019's own
   correction records it plainly: no NetworkPolicy exists anywhere in
   `platform/kubernetes/` — not for `clinvar-service`'s NCBI egress, not
   between namespaces, not anywhere — and none was planned. Every
   component can reach every other component and the internet. That is
   currently the largest unaddressed gap in the platform.
2. **Network is the one signal class this stack does not have.** The
   project has metrics (Prometheus), logs (Loki), traces (Tempo), and is
   adding profiles (#57). It has *zero* visibility into flows: which pod
   actually talks to which, what was denied, what egressed to the public
   internet. Every incident so far was diagnosed from application-level
   evidence; several (the Kafka topics vanishing, the OTel collector port
   that was "running but nothing routing to it", the doubled `/v1/traces`
   404) are exactly the shape a flow map answers in seconds. Hubble is a
   genuinely new class of evidence, not a second rendering of an existing
   one.
3. **k3s's default flannel cannot be extended into either of those.**
   Flannel does not enforce NetworkPolicy at all; k3s's bundled
   kube-router netpol controller does, but offers no flow visibility, no
   L7 policy, and no identity-based (rather than IP-based) model. Getting
   both properties means replacing the CNI, which means a cluster
   rebuild — the exact operation the desktop-host move (#48) requires
   anyway.

## Decision

**Adopt Cilium as this cluster's CNI, replacing flannel, with Hubble
(and Hubble UI) enabled — as part of the multi-node rebuild in backlog
#48/#49, not as an in-place migration of the running laptop cluster.**

- k3s is installed with `--flannel-backend=none
  --disable-network-policy --disable-kube-proxy` (the kube-proxy
  replacement is Cilium's most-cited property and is free once the CNI is
  already being swapped), driven from the existing Terraform in
  `platform/terraform/` so the whole thing stays reproducible — the
  install flags are the change, not a new provisioning mechanism.
- Cilium is deployed as an ArgoCD Helm Application under
  `argocd/apps/cilium.yaml`, like every other platform component (ADR
  0003), with the explicit caveat that it is the **one component whose
  failure prevents ArgoCD itself from recovering the cluster** — see
  Consequences.
- Hubble's metrics are scraped by the existing Prometheus (ADR 0014's
  no-Operator, `extraScrapeConfigs` pattern) and Hubble UI gets an
  Ingress on the established `*.local.adamastorx.test` +
  `adamastorx-ca` pattern.
- The first real NetworkPolicies (#50) follow immediately, default-deny
  per namespace, with `clinvar-service`'s NCBI egress as the first
  explicit allow — closing ADR 0019's recorded gap with the tool that
  makes it observable rather than guesswork.

**This is deliberately timed to the hardware move.** Swapping a CNI is a
cluster rebuild; doing it on the laptop, in place, before the desktop
migration would mean paying for it twice and doing the riskier of the two
migrations first. #23a (backup/restore, still open) must land before
either.

## Consequences

- **Cilium becomes a hard dependency of the cluster's ability to
  network at all.** Unlike every other ArgoCD Application here, a broken
  Cilium sync is not "one service is down" — it is "no pod can reach the
  API server, including ArgoCD". The rollback path is therefore *not*
  GitOps: it is a documented, tested `k3s` reinstall-with-flannel
  procedure in a runbook, written **before** #49 is attempted, not after.
  This is the single largest risk this ADR takes on and it is accepted
  knowingly.
- Real memory cost: the Cilium agent (~200–300Mi per node) plus the
  operator, Hubble relay, and Hubble UI (~300–400Mi total). On the
  current laptop this is a meaningful fraction of remaining headroom;
  on the dedicated desktop it is not. This is a concrete example of the
  hardware move unlocking something, not a nice-to-have justification
  bolted onto it.
- eBPF ties the cluster to the host kernel in a way flannel does not.
  The desktop's kernel version becomes a real platform constraint worth
  recording in the Terraform variables, not an incidental detail.
- The excluded-tools list in `.claude/PROJECT.md` is amended: Cilium is
  removed from it; **service mesh, Vault, Crossplane, and Backstage
  remain**, now with the reasoning above on record rather than as a bare
  list. Anything reopening one of those four cites this ADR's specific
  argument against it.
- `docs/architecture/overview.md` gains a network-dataplane section it
  has never had, since until now there was nothing to say about it.
