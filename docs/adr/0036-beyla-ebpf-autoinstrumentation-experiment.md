# 0036. Grafana Beyla as an eBPF auto-instrumentation experiment, alongside (not replacing) the manual OTel/Micrometer stack

Status: Accepted

## Context

`api`, `workers`, and `aggregator` already carry hand-built
Micrometer/OTel instrumentation (ADR 0013/0017 and the per-service work
that followed): explicit counters, timers, and consumer-lag gauges,
wired into Prometheus by hand, one metric at a time. That's the
project's own real, everyday cost of "manual" observability.

Grafana Beyla instruments HTTP/gRPC services via eBPF, with zero code
changes and zero redeploys — it attaches to a running process and
extracts RED metrics (rate, errors, duration) from the kernel's own
view of the traffic. Almost nobody gets to compare both approaches
against the *same real services* on the *same cluster* at the *same
time* — this project already runs both halves, so backlog #102 turns
that into an actual, honest experiment rather than a claim taken on
faith from either camp's marketing.

## Decision

**Deploy Beyla (`grafana/beyla` Helm chart, `grafana.github.io/helm-charts`
repo) as its own ArgoCD Application, in unprivileged/capability-scoped
mode, exporting directly to the existing Prometheus — no new
component beyond the DaemonSet itself.**

### Self-hosted, direct-to-Prometheus — not a new pipeline

Beyla's `prometheus_export` config serves metrics on its own `/metrics`
endpoint in plain Prometheus exposition format — the same shape every
other service in this project already exposes. This is the reason
Beyla was tractable here where backlog #103 (Grafana Faro) wasn't:
Faro's self-hosted receiver (Grafana Alloy's `faro.receiver`) has no
metrics-only mode and *requires* Loki and/or an OTel trace backend
downstream, a real new stateful component surface. Beyla needs none of
that — it's one more Prometheus scrape target, the same
`extraScrapeConfigs` static-target pattern `api`/`aggregator`/
`clinvar-service` already use (`argocd/apps/prometheus.yaml`).

### Unprivileged mode, capabilities stated honestly — not fully unprivileged

The chart's `privileged: false` mode does **not** mean the container
runs with no elevated access — checked live against the chart's own
`daemon-set.yaml` template before choosing it, not assumed from the
values.yaml comment alone. It grants a specific capability set instead
of the full `privileged: true` (host-device/full-breakout) grant:
`BPF`, `SYS_PTRACE`, `NET_RAW`, `CHECKPOINT_RESTORE`,
`DAC_READ_SEARCH`, `PERFMON`, `SYS_ADMIN`, plus `NET_ADMIN` (this
project enables `contextPropagation`, which needs it for HTTP/TCP
header injection). `SYS_ADMIN` in particular is broad — this is a real
gap against ADR 0028's own unprivileged-injection precedent (the OTel
auto-instrumentation init-container pattern needs no elevated
capabilities at all, because it works by injecting a Java agent at
container-build time rather than attaching to a live process from
outside). The rendered manifest (`helm template`, checked locally
before this ADR was written) also carries `hostPID: true` and
`hostNetwork: true` on the pod spec, independent of the capability
list — eBPF's need to observe every process and every socket on the
node, not a chart default that could be turned off without breaking
the feature. eBPF tracing structurally needs kernel-level access no
injected-agent approach does; `privileged: false` here means
"narrower than root-equivalent," not "no elevated access," and this
ADR states all three (capabilities, hostPID, hostNetwork) plainly
rather than overclaiming parity with ADR 0028.

### Cluster-wide, not scoped to three namespaces

Beyla's own service/process discovery has no first-class "only these
three Deployments" selector in this chart version — and this project's
single-node cluster has few enough real workloads that cluster-wide
discovery costs little extra (the chart's own default `filter.network`
already excludes `kube-system`/`prometheus`/`grafana`-shaped
infrastructure traffic). The comparison this item exists to run
(`api`/`workers`/`aggregator` specifically) is a **dashboard query
concern** — label-matched panels, not an admission-time scoping
concern — simpler than fighting the discovery config for a narrower
blast radius that buys nothing on a cluster this size.

## Consequences

- One new namespace (`beyla`), one new DaemonSet, one new Prometheus
  scrape target (`beyla.beyla.svc.cluster.local:80`, `/metrics`) —
  no new stateful component, no new external account.
- A `SYS_ADMIN`-carrying DaemonSet is a real, if bounded, increase in
  this cluster's privilege surface — accepted for a time-boxed
  experiment on a personal single-node lab cluster, not a default this
  project would reach for on a shared or production system without
  revisiting this ADR.
- The comparison dashboard and its honest write-up (including the
  legitimate outcome "manual instrumentation wins on X, Y") are the
  actual deliverable — the deployment alone answers nothing on its
  own.
- If the experiment's answer is "not worth the privilege cost," the
  rollback is deleting `argocd/apps/beyla.yaml` and its Prometheus
  scrape-config block — no data migration, nothing else in the cluster
  depends on Beyla being present.
