# 0037. Grafana Faro for frontend RUM, self-hosted on the existing Alloy/Loki/Tempo stack

Status: Accepted

## Context

`visualizer` and `clinvar-viewer` are the only two components in this
project with zero telemetry — plain static HTML/CSS/JS, no
instrumentation of any kind. Every backend service has real metrics,
traces, or both; the browser side of the system is invisible. Backlog
#82's own pre-merge ping race is exactly the shape of bug this gap
would hide: something a real user's browser would show immediately,
and nothing server-side would ever surface.

This decision was made twice, with two different answers, because the
first pass was wrong. It's recorded honestly below rather than
silently overwritten.

## First pass (reverted): self-hosting looked too expensive

The first analysis found that Grafana Alloy's `faro.receiver` — the
self-hosted collector component — has no metrics-only mode: it
requires Loki (logs) and/or an OTel trace backend downstream. Read in
isolation, that looks like "self-hosting needs a whole new logs+traces
stack," the same disproportionate-new-component pattern ADR 0014/0032/
0034 already reject elsewhere — so the first version of this decision
was **Won't do**, deferring to Grafana Cloud's free tier (blocked on a
real external account this agent can't create, same class as backlog
#99) or nothing.

That reasoning didn't check this repository's own current state first.

## What was actually missed

`platform/argocd/apps/{loki,tempo,alloy}.yaml` already exist —
observability#3 (ADR 0015) deployed a full Loki + Tempo + Alloy stack
for pod log shipping, entirely unrelated to this decision, well before
this item was picked up. Alloy is already running as a DaemonSet,
already writing to the real Loki instance (`loki.write "default"` in
its own River config). Adding `faro.receiver` here isn't standing up
new stateful infrastructure at all — it's one more block in a config
file that already exists, pointed at a Loki and a Tempo that are
already running.

## Decision

**Faro Web SDK in both frontends, self-hosted via the existing Alloy
DaemonSet's new `faro.receiver` — no new stateful component, no
external account.**

- `argocd/apps/alloy.yaml` gains `alloy.extraPorts` (a `faro`/12347
  port — the chart's own values.yaml carries this exact shape as its
  commented-out example, not invented) and two new River blocks:
  `faro.receiver "default"`, forwarding logs to the existing
  `loki.write.default.receiver` and traces to a new
  `otelcol.exporter.otlphttp "tempo"` pointed at the already-running
  Tempo's OTLP HTTP port (`tempo.tempo.svc.cluster.local:4318`).
- `kubernetes/alloy-ingress/` (a new, separate Application — same
  "standalone Ingress for a chart with no ingress key" pattern
  `alertmanager-ingress` already established) exposes this at
  `faro.local.adamastorx.test`, with a CORS Middleware allowing both
  frontend origins — the actual thing that makes a browser's Faro SDK
  able to reach this at all, not just an in-cluster wiring detail.
- Both `visualizer` and `clinvar-viewer` load `@grafana/faro-web-sdk`
  from a CDN `<script>` tag — the same "no build step, no bundler"
  shape their existing Chart.js `<script>` tag already uses (services
  repo, `Dockerfile`'s own header comment) — and initialize it against
  `https://faro.local.adamastorx.test/collect`, enabling the SDK's
  built-in web-vitals and error instrumentations.

## Consequences

- Genuinely zero new stateful infrastructure: Loki and Tempo's real
  storage/retention costs were already being paid for the log-shipping
  role; this decision adds pipeline wiring on top, not new components.
- A new public Ingress hostname (`faro.local.adamastorx.test`) is a
  real, if narrow, new attack surface — same TLS/cert-manager pattern
  every other public Ingress here uses, CORS-restricted to this
  project's own two frontend origins.
- **Privacy, stated plainly (this item's own AC)**: this is a
  single-operator lab project. Every session Faro records is the
  owner's own, or a synthetic generator's own (`workload-generator`)
  — there is no real third-party user population behind this data,
  and nothing here should be read as "real-user monitoring at scale."
- The reversal itself is the real lesson: the first pass reasoned from
  a general fact about `faro.receiver` without checking this
  project's actual current Application inventory first — precisely
  the kind of assumption-over-verification gap this project's own
  session discipline (and ADR 0031/#90's whole root-cause chain)
  exists to catch. Recorded here rather than quietly corrected,
  because the mistake is as informative as the decision.
