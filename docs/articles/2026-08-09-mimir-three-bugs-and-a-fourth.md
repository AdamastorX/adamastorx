# Three bugs standing up Mimir on a single node — and a fourth I saw coming and shipped anyway

*A real incident log from a solo homelab SRE platform, published as-is: what broke, what I predicted would break later, and what actually broke the very next day.*

## Why this exists

I run a personal Kubernetes cluster on one laptop — a real, if small, distributed system: Kafka, Postgres, an OTel Collector, Loki, Tempo, Prometheus, and about thirty other components, all managed through GitOps (ArgoCD, everything as code, nothing clicked into existence by hand). One of the standing questions on my own backlog was simple: *is Grafana Mimir worth running on a single node, or is it solving a problem I don't have?*

The honest way to answer that is to actually run it, not to guess from the docs. So I did. This is the write-up — three real bugs found standing it up, and a fourth I flagged as a known limitation on day one that turned into a real production incident less than 24 hours later, complete with three failed fix attempts before I found the actual root cause.

Everything below is real: real error strings, real timestamps, real commits. Where I got something wrong along the way, I've left that in too.

## The setup

Mimir's own `mimir-distributed` Helm chart has no single-process mode at all — its `values.yaml` is built entirely around ten-plus separate components (distributor, ingester, querier, query-frontend, query-scheduler, store-gateway, compactor, ruler, and their query-path siblings), each becoming its own Deployment or StatefulSet at every sizing preset. That's disproportionate machinery for a one-node lab cluster asking one experimental question, so I skipped the chart and ran the real `mimir` binary (v3.1.2) in its own documented monolithic mode (`-target=all,alertmanager`) as a plain hand-written Deployment — the same "no operator for one instance" instinct I'd already applied to Kafka (Strimzi) and Prometheus (kube-prometheus-stack) elsewhere in this cluster.

Storage backend: `filesystem`, not S3/MinIO. Mimir's own startup log says this plainly, unprompted: *"-blocks-storage.backend=filesystem is for development and testing only; you should switch to an external object store for production use."* Standing up object storage to answer a one-node question would have been infrastructure in service of infrastructure, so I didn't.

Then I turned it on.

## Bug 1: the namespace that wasn't there, according to the sync that made it

First sync attempt failed outright:

```
namespaces "mimir" not found
```

ArgoCD's `CreateNamespace=true` sync option is supposed to make this a non-issue. It didn't — a manual sync operation triggered via `kubectl patch` on the Application object didn't route through the same code path that honors that flag the way a normal ArgoCD-initiated sync does. Fix: create the namespace directly, then let the Application sync into it. Small, mechanical, and a useful reminder that "sync options" aren't uniformly honored by every way of triggering a sync.

## Bug 2: a green readiness probe lying to my face

With the namespace fixed, the pod came up. `/ready` returned 200. Kubernetes was happy. Prometheus's remote-write to Mimir was not:

```
500 at least 2 live replicas required, could only find 1
```

Every single remote-write request was being silently rejected — silently in the sense that nothing in the pod's own health signals showed it. `ingester.ring.replication_factor` defaults to **3**, even in monolithic mode, even with one process. A single-replica deployment can only ever satisfy a replication factor of 1. Fix: set it explicitly. But the real lesson here is sharper than the fix — a component can pass every liveness and readiness check it exposes while quietly rejecting 100% of the writes it exists to accept, because "is this process alive" and "is this process doing its job" are different questions, and only one of them is usually wired to a Kubernetes probe.

## Bug 3: the ingest limit sized for someone else's cluster

Writes started landing. Most of them still didn't. Second real limit, this time closer to actually blocking real usage:

```
per-user series limit of 150000 exceeded
```

150,000 series per tenant is Mimir's default. This cluster's real, measured `prometheus_tsdb_head_series` at the time was **~186,604** — comfortably over the default, comfortably under a sane raised ceiling. Set to 300,000, with real headroom checked against real current cardinality, not a round number picked to make an error go away.

Three real, distinct bugs, each with a real fix, each verified live — not by checking the pod was `Running`, but by querying `up{job=...}` back out through Mimir's own `/prometheus`-prefixed API and confirming real, current data returned, and confirming Grafana's Mimir datasource health check reported `status: OK`.

## The fourth thing — flagged, not fixed, on day one

While chasing bug 3, I found a fourth, smaller issue and made a deliberate call to *not* fix it immediately: the OTel Collector's own self-monitoring metrics carry labels like `server.address` — valid, unremarkable labels as far as this Prometheus's own local storage and query path are concerned, but rejected outright by Mimir's stricter remote-write validation, which doesn't accept dotted label names.

I wrote it down as a known, stated limitation rather than silently patching around it — "real, concrete evidence for the write-up that Mimir's ingest path enforces rules plain Prometheus doesn't," per that day's own backlog note. It felt like a footnote. A curiosity for the write-up. Not urgent.

It became urgent the next day.

## The fourth bug, for real this time

Twenty-four hours later, while doing unrelated work, I found Prometheus's remote-write to Mimir failing every one to two minutes, non-recoverably:

```
server returned HTTP status 400 Bad Request: received a series with an
invalid label: 'server.address' series: 'otelcol_exporter_send_failed_spans
{...}' (err-mimir-label-invalid)
```

The mechanism makes this worse than "one bad metric is missing": Prometheus batches many series into a single remote-write request. One invalid series doesn't get skipped — it fails the *entire batch*, non-recoverably, every single time that batch is sent. One dotted label on one self-monitoring metric was silently degrading Mimir's copy of *everything* this cluster measures, continuously, for who knows how long before I noticed.

What followed was three real attempts to fix it, in order, each one taught something the last one didn't:

**Attempt 1** — drop the offending metric by name before it's sent. I wrote a Prometheus relabel rule and shipped it. It didn't work — and worse, it *looked* like it worked, because I'd used the wrong config key. I'd written the Prometheus Operator's camelCase field name (`writeRelabelConfigs`) into a chart that isn't the Operator and doesn't recognize that key at all — it silently no-ops on an unknown field, and the real key needed is Prometheus's own native snake_case `write_relabel_configs`. A second pass, rendering the actual chart output and validating it with `promtool check config`, caught it: the bad config wasn't just inert, it was a landmine — the rendered `prometheus.yml` was invalid, meaning the *next* restart of the pod (crash, OOM, node reboot, take your pick) would have failed to start entirely, and nothing in CI would have caught it, because CI checks rendered manifests, not the Prometheus config embedded inside one of them as an opaque string.

**Attempt 2**, with the key fixed — drop that one metric name. Fixed within minutes: a *different* self-monitoring metric, `otelcol_processor_incoming_items`, tripped the identical failure. Widened the match to the whole `otelcol_exporter_*`/`otelcol_processor_*` family.

**Attempt 3** — even that wasn't enough. `target_info`, a synthetic per-target metadata metric the OTel Collector's Prometheus exporter emits automatically, isn't prefixed `otelcol_` at all, and it carries the same class of dotted resource-attribute labels (`host.name`, `k8s.node.name`, and friends). Matching by metric name was never going to keep up — new instruments, new metrics, same underlying problem, forever.

**The actual fix** stopped chasing metric names and matched what Mimir actually objects to: label *names* containing a dot, on any series. Prometheus has a primitive for exactly this — `action: labeldrop` operates on label names, not values, not metric names, and removes any matching label from every series, unconditionally, before the batch is sent. One general rule instead of an ever-growing exception list.

There was a subtlety even here: `labeldrop` alone can make two genuinely different series look identical once the label that distinguished them is gone. `otelcol_processor_incoming_items` uses a dotted `otel.signal` label (`logs`/`metrics`/`traces`) as its *only* real dimension — strip that label with nothing else changed, and two distinct series collapse into duplicate points at the same timestamp, which Mimir also rejects, just under a different error. The final shape keeps both defenses: a name-based drop for the one known family that actually relies on a dotted label as a real dimension, plus the general `labeldrop` for everything else, present and future.

Four real fix attempts, in one file, in about ninety real minutes, each one a genuine correction to the one before it — including a version that looked deployed and wasn't, and a version that "fixed" one incident while quietly writing a second one into the config. I'm publishing the whole sequence, not just the ending, because the failed attempts are the actually useful part: dotted OTel semantic-convention attribute names flowing straight into Prometheus's label space (a real consequence of Prometheus 3.x's native UTF-8 label-name support meeting a downstream system that still enforces the legacy rules) is not a Mimir-specific problem, and "match the metric name" is the wrong reflex the first time it happens, not just the third.

## So — was it worth it?

Measured, not guessed: this cluster's CPU requests already sit at roughly 93% of what one small laptop can give, and Mimir's `filesystem`-backed storage lives on the exact same disk Prometheus's own TSDB already uses — no independent failure domain, no durability this node's disk didn't already have. At this project's real, current, single-node scale, plain Prometheus's own 30-day retention already answers every question this cluster actually has. Mimir doesn't yet earn its keep as load-bearing architecture here, and I said so in the ADR the day I ran the experiment — "not yet worth it," stated as a legitimate outcome of running it, not a foregone conclusion I was steering toward.

And it's still running. A hardware-constrained strategy review I commissioned on this exact cluster later recommended tearing Mimir down to reclaim that capacity — a reasonable recommendation on its own terms, and I overrode it. I want to keep testing it. Four real, hard-won bugs in, it's the best-instrumented adversarial-testing target this cluster has, and the fourth one just went two rounds with production. That's worth more to me right now than the CPU it costs.

---

*Real evidence, for anyone who wants to check any of this rather than take my word for it: the deployment decision and honest cost/benefit write-up are in ADR 0038; the three initial bugs and the fourth's first sighting are recorded in backlog item #108; the incident and its four-attempt fix sequence are three real, sequential pull requests against this cluster's GitOps repo, each reviewed before merge, each correcting a real mistake in the one before it.*
