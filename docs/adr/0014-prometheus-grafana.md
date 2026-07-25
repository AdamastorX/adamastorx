# 0014. Prometheus + Grafana: plain chart (no Operator), split scrape mechanism, 3-day retention

Status: Accepted

## Context

observability#2 (backlog #18): "Metrics from observability#1's
instrumented services (`gateway`/`api`/`workers`, all exposing
`/actuator/prometheus`) are queryable in Grafana via Prometheus;
retention policy documented." No dashboards yet (backlog #20, a
separate deliverable — "dashboards are code," not built speculatively
here) and no alerts (M4). Mimir was in this issue's original scope but
is explicitly out (backlog #18a) — this cluster has no long-term/
multi-tenant storage requirement yet, so bundling it here would gate
basic dashboards on infrastructure the AC doesn't call for. Nothing
existed yet: no Prometheus/Grafana anywhere in `platform`.

## Decision

- **`prometheus-community/prometheus` chart, not `kube-prometheus-stack`.**
  The stack bundles the Prometheus Operator (a new CRD surface —
  `ServiceMonitor`/`PodMonitor`/`PrometheusRule`) plus Alertmanager,
  node-exporter, and kube-state-metrics by default — none of which this
  AC needs. Same reasoning ADR 0011 already used to reject the Strimzi
  operator for Kafka: an Operator to manage one static Prometheus
  instance is disproportionate machinery for what's needed. The plain
  chart itself still bundles Alertmanager/kube-state-metrics/
  node-exporter/pushgateway as *optional* subcharts (confirmed by
  rendering it locally before committing to this) — all four disabled,
  leaving just the `server` component. Alertmanager is M4's concern, not
  this issue's; kube-state-metrics/node-exporter are K8s/host-level
  metrics outside this AC's "app metrics from the 3 services" scope;
  pushgateway has no push-based source here. Revisit
  kube-state-metrics/node-exporter when #20's dashboards actually want
  that data; revisit the Operator model if a fleet of Prometheus
  instances or self-service `ServiceMonitor`s ever becomes a real need —
  not before.
- **`grafana/grafana` chart, separately.** No credential shared with
  Prometheus — Grafana only needs Prometheus's Service DNS URL (no auth
  between in-cluster services, ADR 0010's existing trust model), and
  Grafana's own admin credential is self-contained (chart
  auto-generates a random password into its own Secret, same pattern
  Kafka/Postgres already use).
- **Separate `prometheus` and `grafana` namespaces**, not a shared
  `observability` one — matches this project's actual established
  pattern (Kafka, Postgres, the OTel Collector, Traefik, cert-manager
  are each their own namespace even where two components ship in the
  same issue/PR), rather than inventing a new "shared stack namespace"
  precedent for just this pair.
- **Scrape targets, two different mechanisms, deliberately.**
  `gateway`/`api` have stable Service DNS
  (`gateway.gateway.svc.cluster.local`, `api.api.svc.cluster.local`) —
  plain static `extraScrapeConfigs` entries targeting
  `/actuator/prometheus`, same "explicit over magic" style already used
  for the OTel Collector's own scrape config (ADR 0013).
  **`workers` has no Kubernetes Service at all** (ADR 0009/0011,
  deliberate: no business HTTP API, kubelet probes the pod directly) —
  nothing to point a static target at. Rather than reversing that
  decision just for metrics convenience, `workers` is scraped via
  Prometheus's Kubernetes pod-based service discovery
  (`kubernetes_sd_configs`, `role: pod`, `namespaces.names: [workers]`)
  — the same direct-to-pod mechanism kubelet's own probes already use.
  No extra relabeling needed: the `workers` namespace holds only
  `workers` pods (this project's per-component-namespace convention),
  and the Deployment already declares `containerPort: 8080`, so pod-role
  discovery sets `__address__` to `<pod-ip>:8080` automatically.
  `gateway`/`api` deliberately stay on static config rather than also
  switching to K8s SD "for consistency" — they have perfectly good
  stable DNS already, no reason to add discovery machinery there. RBAC
  for pod-role SD (`rbac.create`) is chart-supported out of the box,
  confirmed by inspecting the chart before choosing this approach. A
  fourth static target scrapes the OTel Collector's own self-monitoring
  metrics (`:8888`, already enabled by the chart default, ADR 0013) —
  cheap, and monitoring the telemetry pipeline itself is standard
  practice, not scope creep.
- **Retention: 3 days, not the chart's 15-day default.** A single-node
  dev cluster generating a handful of test requests per session has no
  benefit from 15 days of mostly-empty series — documented explicitly
  here since the AC asks for the retention policy to be stated, not
  left as an unexamined default.
- **Prometheus gets a real PVC** (2Gi, `local-path` StorageClass, same
  pattern as Postgres, ADR 0012) **— Grafana does not.** Prometheus's
  data has actual continuity value (that's what a retention policy
  means); losing it on every pod restart would make the setting
  pointless. Grafana's entire state here is code-provisioned (a
  datasource via Helm values, no manually-created dashboards yet) —
  nothing to lose on restart, so `emptyDir` is enough.
- **No dashboards, no alerts, built now.** Verification is "can a human
  query these metrics in Grafana" (Explore / an ad-hoc query), not a
  shipped dashboard. Backlog #20 is the dashboards-as-code deliverable,
  and the `observability-engineer` persona's own rule ("never ships a
  dashboard without the alert/SLO it's meant to support") is exactly
  why bundling a half-built dashboard into this issue would be the
  wrong call.

## Consequences

- `platform` gains its second PVC-backed workload (Prometheus, after
  Postgres) and its first use of Kubernetes-native service discovery
  (`kubernetes_sd_configs` + RBAC) rather than purely static config —
  a small step up in moving-parts, scoped to exactly the one case
  (`workers`) that genuinely needs it.
- Disabling kube-state-metrics/node-exporter/Alertmanager/pushgateway
  means this Prometheus currently only sees the 4 application-level
  targets configured above — no cluster-resource-level metrics (pod
  counts, node CPU/memory) are collected yet. That's a real gap if a
  future dashboard wants "cluster health" rather than "these 3
  services' health" — the trigger to revisit is #20 actually asking for
  that data, not built ahead of it.
- 3-day retention means any incident-lab evidence (backlog #23) that
  wants metrics from more than 3 days ago won't have them — acceptable
  for a dev cluster where labs are run and documented close to when
  they happen, not a production audit-trail requirement.
