# Session state (agent handoff notes)

Working notes for picking up where the last Claude Code session left off.
Not a design doc, not an ADR — a scratch log of in-flight work, open
threads, and things the next session shouldn't have to re-discover the
hard way. Prune/rewrite freely as work completes; this file describes
*current* state, not history (git history is the record of the past).

Last updated: 2026-10-03.

## Where things stand

**2026-10-03 pickup session — state of play (verified live, not recalled)**

- **Cluster reachable from the Mac**: kubeconfig is `~/.kube/nucbox-config`, API at
  `https://100.69.223.105:6443` (Tailscale node `adamastorx`, the single k3s node, Ready).
  The `nucbox-k8-plus` Tailscale entry is stale. Nothing in `platform` sets `KUBECONFIG`
  (per-machine path; platform#204 dropped the env entry) — export your own.
- **`adamastorx` `main` CI was red 2026-10-02/03 and is green again.** The failing job was
  `roster-drift`'s dashboard/SLO half (seven components past the 14-day grace period with no
  stated reason: six `*-network-policies` batches and `vpa-objects`; `mimir` SLO only), fixed
  by platform#222 + adamastorx#340. The "not mentioned in overview.md" lines in that log
  came from the checker's own self-tests, which fail on purpose. Lesson: merge the `platform`
  half first, the check reads `platform`'s `main`.
- **Merged this session**: platform#194 (OOM recency gate, #143 AC 1 — live, only `beyla`
  still holds the stale `137` gauge and stays silent), #196 (ClinVar dashboard + alert),
  #202 (PreToolUse guard), #204 (SessionStart brief), #223 (egress from `prometheus-server` to
  loki/tempo/pyroscope), #200, #203; adamastorx#327 (re-filed as #159), #330, #331, #332,
  #333, #340, #341; observability#36–#38, #40.
- **`ClinVarInvalidationLag` (platform#196) could never have fired as originally written**: a
  bare `>` between two vectors with different `job` labels matches no series (checked against
  the live Prometheus). Now `sum(...) > (sum(...) or vector(0))`.
- **The `PreToolUse` guard (#202) no longer emits `permissionDecision: allow`** with the
  marker present: that would skip the user's own permission prompt. With the marker it only
  stops blocking; the normal permission flow still decides.

**2026-10-04 follow-up — what was fixed, and the gremlins it exposed (all verified live)**

- **The node is on Wi-Fi with a DHCP address** (`wlx0cef15d0626a`, now `192.168.1.7`, was `192.168.1.10`).
  This explains the flaky reachability from the Mac (jitter 5-110 ms, `no route to host`,
  Tailscale picking a link-local path). Prefer an SSH tunnel to the node over the Tailscale or LAN
  IP when `kubectl` times out: `ssh -f -N -o ServerAliveInterval=5 -L 16443:127.0.0.1:6443 <node>` then
  `kubectl --server=https://127.0.0.1:16443` (the k3s cert accepts 127.0.0.1). The tunnel itself drops; re-open it.
- **`cilium`'s `k8sServiceHost` was a stale DHCP IP** (`192.168.1.10`). The running agent survived on an
  already-open API connection; the first restart (the memory-limit change) sent it to
  `Init:CrashLoopBackOff` for ~40 min. Now `127.0.0.1` (agent and operator are `hostNetwork`). Existing pods keep
  networking while the agent is down; new pods and policy changes do not. platform#228.
- **The `cilium` Application is manual-sync.** Merging a change to it does nothing live. Sync only the resource
  you changed (`operation.sync.resources` for the DaemonSet / operator Deployment); a full sync also rotates the
  Hubble mTLS certs (the standing benign `OutOfSync`). `kafka`, `prometheus` and most others auto-sync;
  `prometheus-network-policies`, `cilium` and the M13 Applications do not.
- **Container memory limits were sized for the old host and the node has ~60GB RAM, ~39GB free, swap unused.**
  The kernel (`journalctl -k`, no sudo needed) was memcg-OOM-killing `beyla` (1Gi, five times in 12h),
  `cilium-agent` (600Mi, working set peaked 599Mi) and `kafka-controller-0` (2560Mi, working set 96-99%).
  Raised: beyla 2Gi (platform#224), cilium-agent 1Gi (#225), kafka 4096Mi (#227).
- **Kafka's heap percentages are of the HOST's RAM, not of the limit** (corrected 2026-10-06; this bullet said
  the opposite on 10-04). `jcmd` showed the broker JVM with `MaxRAM` = 60GB (the host) and a 29.3GiB max heap in a
  4096Mi cgroup, so `InitialRAMPercentage/MaxRAMPercentage` bounded nothing; it now uses `-Xms1g -Xmx2g` (backlog #161).
  The other Java services respect their limits.
- **A stuck `Terminating` pod with a zombie process** (`Zsl`, one thread in `D`) held `beyla` for ~35 min after a
  rollout; it cleared on its own. `kubectl delete --force` is the usual remedy if it does not.
- **Mistake to avoid**: platform#223 duplicated egress rules that platform#201 already carried in the same file
  (written without reading the PR's own diff, and checked `origin/main` instead of the PR). The policy ended up with
  27 rules instead of 24 and the Application OutOfSync. Fixed by platform#226 (file restored to the synced revision).
  Read a PR's whole diff before writing a "this is missing" companion change.
- **Postgres backups**: the 03:00 runs of 2026-10-04 succeeded for all three databases, the first since 2026-09-09.
  The failures of 10-01..10-03 coincided with the node's recovery; backlog #157's wording ("after the host was
  powered off") is probably right but the root cause was never confirmed.
- **Done since**: platform#195 (securityContext on 11 workloads) was merged by the owner and rolled out and verified live on
  2026-10-04 (backlog #142); it exposed one real defect, fixed in platform#229 (api init container needs a numeric uid).
  `ClinVarIngestionFreshnessBreach` is explained by backlog #160 (ingestion is scheduled inside clinvar-service, Monday 03:00).

**2026-10-06 follow-up — measured, and what to know before touching these again**

- **Read a JVM's real sizes, do not infer them from flags.** The Kafka image is a JRE with no `jcmd`; use an ephemeral
  container with the broker's uid: `kubectl debug -n kafka kafka-controller-0 --target=kafka --image=eclipse-temurin:25-jdk
  --custom=<json with runAsUser/runAsGroup 1001, drop ALL> -- jcmd 1 VM.flags` (and `VM.native_memory summary`, NMT is on).
  It adds an ephemeral container that disappears with the pod. Never `kubectl exec` `kafka-topics.sh` in the broker pod:
  a second JVM in the same cgroup with the same flags.
- **The node's Wi-Fi drops the lease.** 2026-10-06 05:55Z: `BEACON-LOSS`, `Lost carrier`, `DHCP lease lost`, k3s
  `node IP not found in the host's network interfaces`, and `argo-rollouts`/`keda-operator` restart together
  (the same shape as 2026-10-04 04:23Z). Backlog #162 (needs a cable or a router reservation).
- **The Kafka provisioning hook was broken since #126.** The `kafka` CiliumNetworkPolicy selected
  `app.kubernetes.io/name: kafka`, which the chart's provisioning Job pod also has, so it got the broker's DNS-only egress
  (`EGRESS DENIED` in `hubble observe --namespace kafka --verdict DROPPED`) and the `post-upgrade` hook held the `kafka`
  sync open. Only visible on the first `kafka` sync after #126. Now selects `component: controller-eligible` (platform#233).
  If a `kafka` sync sits at "waiting for completion of hook batch/Job/kafka-provisioning", look at Hubble first.
- **ClinVar's weekly ingestion failed on 2026-10-05**: the completion event's `changedKeys` outgrew one Kafka message
  (`MSG_SIZE_TOO_LARGE`) after a six-week gap. Fix is services#94 (split across events), not deployed yet; backlog #160.
- **The image-scan gate keeps moving.** A new CRITICAL `spring-webmvc` (7.0.8, fixed 7.0.9) failed an unrelated PR two
  days after services#93 cleared the previous ones; overrides for Tomcat, Jackson, Netty and now spring-framework live in
  the parent pom with the CVEs named. Expect more until the Boot BOM catches up.
- **`prometheus_remote_storage_samples_dropped_total` is not a symptom here**: ~51 samples/min are dropped on purpose by
  `write_relabel_configs` (`otelcol_.*`). I misread it once as loss from a Mimir restart.
- **Mimir stays** (owner decision 2026-10-06, backlog #135); resized to 1536Mi limit / 768Mi request and its namespace
  `ResourceQuota` raised with it (the old quota would have rejected the new pod). The decommission trigger #135 asks for
  is still unset.
- **A `ResourceQuota` can veto a limit change.** Every app namespace has one sized for the rolling-update peak
  (`maxSurge=1` doubles the pod); check `kubectl get resourcequota -n <ns>` before raising a request or limit.

**Still open, in priority order**

1. **Postgres backups have failed every run since 2026-10-01** (all three CronJobs,
   `DeadlineExceeded` at 600s, *no pod ever created*; last success 2026-09-09). The node and PV
   affinity match and the pods are gone, so a read-only look can't name the cause: needs a
   one-off Job from the CronJob (cluster mutation, ask first) or watching tonight's 03:00 run.
   Tracked as #157, which undersold it ("after the host was powered off"): it is still failing
   days after the host came back.
2. **`services` CI blocks every PR on real HIGH/CRITICAL CVEs**: `aggregator`'s `app.jar` (13,
   3 critical) and alpine `libcrypto3`/`libssl3`/`pcre2` in the nginx frontends. Renovate PRs
   (Spring Boot 4.1.1, base-image digests, nginx v1.31.6) are the likely fix; CI was re-run
   on them. services#83 (#156) is only waiting behind this.
3. **platform#201 (#144) must not merge before `prometheus-network-policies` is synced** in the
   cluster (manual-sync Application; platform#223 added the egress rules). Otherwise the three
   new scrapes are blocked and `TelemetryBackendDown` fires immediately. Then runbooks and #201.
4. **platform#195 (#142 securityContext)**: its own description requires an independent
   `platform-engineer` review and per-workload live syncs gated on the owner. Several of the
   target Applications auto-sync, so a merge alone can change live pods
   (`readOnlyRootFilesystem` is the real regression risk). Not merged.
5. **`beyla` scrape target is down** (`up{job="beyla"}=0`, `connection reset by peer`, 29
   restarts, OOM `137` earlier today). The beyla-vs-manual dashboard (platform#200, #145) has
   no data to verify against until this is fixed.
6. #146/#147 landed (record reconciliation, status-marker check); #143 AC 2 (`promtool`)
   untouched; the `mimir` still-fires half of #143 AC 1 not yet seen live.

**Operator note**: Claude Code's auto-mode classifier intermittently blocks harmless reads
and `gh pr merge` (reasons `Merge Without Review` / `Self-Modification`); permission rules
don't override it, only an `autoMode.allow` entry in `settings.local.json` did (user-edited).

**ADR 0046 (bounded verification loops) adopted and merged across all four repos, 2026-10-02**
— after a ~1-month interruption (last commit 2026-08-31, the cutover), a staff-engineer (Opus)
review of the Ralph loop experiment (#156) concluded adoption narrowed to a named Implement/Test
technique with 8 mechanically-checkable preconditions, not a project working model. Status: Proposed,
with a 2026-12-01 review date or five recorded runs, whichever comes first. PRs merged in all four
repos: `adamastorx`#337, `services`#92, `platform`#221, `observability`#39. `.claude/settings.json`
files committed at project scope (correction 2026-10-03: `platform` had no `settings.json` on `main` until
the PreToolUse guard, platform#202, and the plugin lists described here are not there) (plugins: `ralph-wiggum@claude-code-plugins`, `mattpocock-skills@mattpocock`),
enabled in `adamastorx` and `services` only; not `platform` or `observability`. Backlog items #149/#150/#151
AC updated per the decision. New item #158 created for `check-resource-limits.sh` repair (self-test fixtures,
all-workload-kind glob, header corrected). Operator connectivity finding (resolved by
2026-10-03, see the pickup section above): NucBox offline 33 days, Tailscale node key expired post-cutover;
/etc/hosts wrong IP; no kubeconfig on this Mac.

**Backlog #49 (Cilium/Hubble, replacing flannel) and #50 (first
NetworkPolicies) are both Done and live, 2026-08-10** — the day's major
work: a real, live, deliberate single-node cluster rebuild, followed by
5 real `CiliumNetworkPolicy` batches (`clinvar`/`api`/`workers`/`alloy`/
`prometheus`), plus two ingress-enforcement follow-up fixes found and
applied during the closure itself (`alloy`, `alertmanager`) — across
`platform`#148–#162 and `adamastorx`#239–#249. `docs/roadmap/backlog.md`'s own #49/#50 entries
and `docs/architecture/overview.md`'s "Network dataplane" section have
the full, real account (including a genuine production incident and its
root cause) — this section only keeps the gremlins worth knowing before
touching this stack again, since a live Cilium/CiliumNetworkPolicy quirk
belongs here more than duplicated into the permanent record.

**Real, still-relevant gremlins from that work**:

- **Cilium's DNS proxy (`toFQDNs`/`rules.dns`) is genuinely broken in
  this cluster's exact config** (`routingMode: tunnel`/vxlan +
  `kubeProxyReplacement`/socket-LB, matches open upstream
  `cilium/cilium#46284`) — the moment any policy adds an L7 `rules.dns`
  selector, it drops **all** locally-originated pod DNS, not just the
  intended FQDN. Confirmed live, twice, independent of
  `dnsProxy.enableTransparentMode`. Worked around with `toCIDR` real IP
  ranges instead (pure L3, never touches the DNS proxy) for the three
  real flows that needed public egress (NCBI, GitHub, `ntfy.sh`). If a
  future policy seems to want `toFQDNs` again, check the upstream issue
  before assuming it's fixed — it wasn't as of this rebuild.
- **`CiliumNetworkPolicy` `toPorts` needs the real backend *container*
  port, not the Service's own port.** `clinvar-service`'s Service is
  port 80, its container listens on 8000 — Cilium evaluates policy on
  the post-DNAT packet, so a rule naming port 80 lets nothing through
  even though the Service "looks" reachable. Caused a real false-alarm
  emergency rollback mid-investigation once (the manual connectivity
  test used the wrong port, not an actual bug). Check
  `kubectl get svc -n <ns> <name> -o jsonpath='{.spec.ports}'` before
  writing a `toPorts` rule, or before concluding a policy is broken.
- **Cilium only enables per-direction policy enforcement when that
  direction has at least one real rule object.** An omitted or
  explicitly-empty `ingress:`/`egress:` key does nothing — that
  direction stays fully unenforced (real default-allow), even though
  the policy "looks" like default-deny. Bit two already-merged policies
  (`alloy`, `alertmanager`) before being caught by a deliberate audit
  pass. Check `cilium-dbg endpoint list`'s `policy-enabled` says `both`,
  not just one direction, whenever a policy is meant to enforce both.
- **`hostNetwork: true` pods share Cilium's `reserved:host` identity
  with no distinct endpoint of their own** (node-exporter,
  cilium-agent/cilium-operator, Beyla, confirmed live via
  `cilium-dbg endpoint list`) — a `CiliumNetworkPolicy` can't select
  them by pod label at all. Egress to them needs `toEntities: host`;
  they can't get their own ingress policy. Not a bug, a real Cilium
  constraint worth knowing before assuming a missing policy is an
  oversight.

## Where to look next

- #49/#50 themselves closed clean, nothing left mid-flight on that
  work specifically — check `gh pr list --repo AdamastorX/adamastorx`/
  `--repo AdamastorX/platform` for whatever's actually open right now,
  since this line goes stale the moment a new PR opens.
- `docs/roadmap/backlog.md` is the live source of truth for what's open
  next (currently #1–#159, structural integrity enforced by
  `scripts/check_backlog_structure.py` and CI's `backlog-structure`
  check on every PR).
- `.claude/PROJECT.md`'s "Current milestone" section is the stable,
  point-in-time picture of where the project stands overall — check it
  before this file for the big picture; this file is for tactical
  gremlins and in-flight state, not milestone status.

## Recurring gotcha worth knowing before touching this stack again

**Boot 4.1 modularized its autoconfiguration**: the client library
(`spring-kafka`, `flyway-core`, classic Jackson 2, `opentelemetry-exporter-otlp`)
and the `FooAutoConfiguration` classes that actually wire it into a
Spring context live in *separate* artifacts (`spring-boot-kafka`,
`spring-boot-flyway`, `spring-boot-micrometer-tracing` +
`-opentelemetry`). Adding the client library alone compiles fine and
then silently doesn't work at runtime — no error, the feature just
never activates. Hit this four separate times now (services#3, #4,
observability#1). If a future integration (Redis, anything else)
compiles clean but a Boot feature just isn't activating, check for a
matching `spring-boot-<name>` artifact before assuming the library
itself is broken.

**Boot property names move between major versions without a compile
error.** `management.otlp.tracing.endpoint` looked right (matches the
Boot 3.x docs pattern still floating around) but is deprecated at error
level since Boot 4.0 and silently binds to nothing — no startup
failure, no export failure, just a property nobody reads. Correct path:
`management.opentelemetry.tracing.export.otlp.endpoint`. When a
property "should" work and doesn't, check the actual
`spring-configuration-metadata.json` inside the relevant
`spring-boot-*` jar (`unzip -p <jar> META-INF/spring-configuration-metadata.json`)
before assuming the code is broken — it's often the property name that
moved.

**`OTEL_*`-prefixed environment variables are reserved by the
OpenTelemetry SDK itself**, independent of whatever Spring property
you meant them to override. Naming a Kubernetes Deployment env var
`OTEL_EXPORTER_OTLP_ENDPOINT` (seemed like the "correct, standard"
choice) made the OTel SDK's own `autoconfigure-spi` module pick it up
directly and build a second, conflicting exporter, doubling the
`/v1/traces` path into a silent 404. Any future OTel-adjacent
deploy-time override needs a name outside the `OTEL_*` namespace.

**Hand-built Spring beans bypass Boot's `*.observation-enabled`
properties.** `WorkItemProducerConfig`/`WorkItemConsumerConfig`
construct their own typed `KafkaTemplate`/listener container factory
(documented reason: Boot's auto-configured ones are untyped) —
`spring.kafka.template.observation-enabled`/`.listener.observation-enabled`
only wire into Boot's *own* auto-configured beans, so those properties
were silent no-ops here. Needed an explicit
`.setObservationEnabled(true)` call in the `@Bean` methods themselves.
Same likely applies to any other hand-built Spring integration bean
going forward — check whether a "just set this property" fix is
actually reaching the bean in use.

**`spring-boot-starter-actuator` alone does not expose
`/actuator/prometheus`.** Two separate things are needed, both easy to
assume are already covered: the `micrometer-registry-prometheus`
dependency (actuator brings Micrometer's core, not the Prometheus
registry), and `management.endpoints.web.exposure.include:
health,prometheus` (Boot doesn't expose non-default endpoints over HTTP
just because the registry is present). Both ADR 0013 and the first pass
of ADR 0014 assumed this endpoint "already existed" from actuator alone
— it took an actual Prometheus scrape returning 404 on all three
services to find it (observability#2).

**Helm chart `ports.*.enabled: false` can hide a port the process is
already listening on.** The otel-collector chart's own self-monitoring
metrics (`:8888`) are always active internally (default telemetry
config), but the chart's `ports.metrics.enabled` defaults to `false`,
so the generated Service never got a port for it — Service-DNS
connections just timed out (process running, nothing routing to it).
Fixable by `helm template`-ing the chart locally with the flag flipped
and diffing the rendered Service before assuming a scrape-target
timeout is a network/firewall problem.

**A chart's `deprecated: true` + a stated migration deadline is worth
checking against today's date before writing the manifest**, not
after. `grafana/grafana`'s stated migration deadline (Jan 30th 2026) had
already passed by the time this was deployed — verified
`grafana-community/helm-charts` was a real, actively-published
continuation (same values schema, newer version) before switching the
`repoURL`, rather than deploying an already-stale chart into a project
meant to model this discipline. Same finding recurred for Loki/Tempo/
Promtail (observability#3): `tempo`/`promtail` are `deprecated: true`
outright, `loki`'s original repo now serves GEL-enterprise only.

**A "ring: ACTIVE, /ready: ready" single-instance chart can still
0% work if `replication_factor` doesn't match replica count.** Loki's
chart defaults `common.replication_factor: 3` (inherited from its
multi-replica modes) — with one `singleBinary` replica, every query
500'd with "too many unhealthy instances in the ring," no startup or
readiness-probe failure at all. Only actually querying surfaced it.
Fixed with `commonConfig.replication_factor: 1`. Worth checking on any
future single-replica chart that was originally designed to scale out.

**GitOps branch-vs-stale-local-main trap**: creating a new branch from
a local `main` that hasn't been `git pull`ed since the last squash-merge
produces a branch whose history diverges from `origin/main` even when
the file content is identical — GitHub reports the PR as `CONFLICTING`
despite `git diff origin/main` showing a clean, minimal diff. Fix:
`git fetch && git rebase origin/main` before pushing. Always `git fetch
origin --quiet && git checkout main --quiet && git pull origin main
--quiet` immediately before branching for a new PR, not just at the
start of a work session.

**Kafka topics don't survive a broker pod restart** (ADR 0011,
deliberately ephemeral storage) — if `work-items` is suddenly
`UNKNOWN_TOPIC_OR_PARTITION` after having worked before, check
`kubectl get pods -n kafka` for a recent restart before assuming a
config regression; recreate the topic manually
(`kafka-topics.sh --create --topic work-items --partitions 3
--replication-factor 1`) to unblock testing, no chart-side provisioning
Job re-runs this automatically.

**A Bitnami chart's auto-generated password Secret can silently
regenerate and diverge from the live database/service's actual
credential** (found deploying services#5, tracked unresolved as
`platform`#34). Postgres never restarted, but its `postgresql` Secret's
`password`/`postgres-password` values stopped matching what the
container was actually started with (visible in the running pod's own
`POSTGRES_PASSWORD`/`POSTGRES_POSTGRES_PASSWORD` env vars, baked in at
container start and never changed). An already-running pod with an
established connection pool won't notice — only a *new* connection
attempt (a fresh pod, a rolling restart) fails with
`FATAL: password authentication failed`. If this recurs: compare the
Secret's current value against the target pod's own env
(`kubectl exec <pod> -- env | grep PASSWORD`) before assuming a config
regression — if they differ, `ALTER USER <role> WITH PASSWORD
'<current Secret value>'` inside the DB pod restores access (get
explicit confirmation first, this mutates live data). Suspected but
unconfirmed cause: ArgoCD's Helm rendering may not preserve
`common.secrets.passwords.manage`'s "reuse existing Secret" idempotency
the way a real `helm upgrade` would. Same auto-generation pattern is
used by Redis's password and Kafka's cluster ID — unconfirmed whether
they're equally at risk.

**A crash-looping pod's exponential backoff can take minutes to retry
even after the underlying cause is fixed.** `kubectl delete pod
<name>` (the Deployment/StatefulSet recreates it immediately) is a
safe, reversible way to force an immediate retry instead of waiting out
the backoff timer — not a persistent or destructive action, just a
faster feedback loop.

**Namespace scoping breaks PersistentVolumeClaims the exact same way it
breaks Secrets** (ADR 0012 already established this for Secrets; ADR
0019 hit it again for a PVC). `workers` tried to mount a PVC that only
existed in `api`'s namespace — pod stuck `Pending`,
`persistentvolumeclaim "X" not found`. Same root cause, same fix
shape: give the consumer its own namespace-scoped copy (its own PVC, or
in this case, redesign so only one component ever touches the volume
at all), don't try to share either resource type across a namespace
boundary.

**`tcpSocket` liveness/readiness probes can't detect a wedged
single-threaded app.** The kernel completes a TCP handshake into the
accept queue regardless of whether the application ever calls
`accept()` — a process fully blocked on CPU-bound synchronous work
(e.g. `clinvar-service`'s pure-Python VCF scan) can still pass a
`tcpSocket` probe indefinitely. Use a real `httpGet` health route
whenever the app has one; a TCP-only check is a last resort for apps
that genuinely don't expose HTTP, not a shortcut for ones that do but
haven't had their manifest updated yet.

**A step with no logging is invisible when it stalls, and "add a
progress log line" is cheap insurance worth adding proactively** for
any loop expected to run more than a few seconds over real (not
fixture-sized) data — `clinvar-service`'s per-record VCF scan had zero
log output for its ~90-second real-data runtime until this was fixed;
during the double-ingestion incident, this silence was the reason
`kubectl logs --previous` alone couldn't immediately show which step
was actually stuck.

## Cluster access (this machine)

Real, current kubeconfig, generated fresh by the 2026-08-10 cluster
rebuild:
```
export KUBECONFIG=/home/lmpeixoto/repos/AdamastorX/platform/terraform/kubeconfig
```
`kubectl` here does **not** default to it on its own — always set
`KUBECONFIG` explicitly, every session (not persisted in `~/.bashrc`,
blocked by the permission classifier).

**The older `~/.kube/config` is stale/pre-rebuild** — a review agent
that tried it during the rebuild's own follow-up work got real TLS
errors against it. Use the path above, not `~/.kube/config`.

## ArgoCD stuck-operation gremlin (if it recurs)

An `Application`'s `.operation` field (the in-flight sync request) can
get stuck holding a **stale** values snapshot from an earlier commit and
keep re-applying it on retry, ignoring that `.spec.source` has since
changed. Refresh annotations and restarting `argocd-repo-server`/
`argocd-application-controller` don't clear this. What works:
```
kubectl patch application <name> -n argocd --type merge -p '{"operation":null}'
```
Check `kubectl get application <name> -n argocd -o jsonpath='{.operation}'`
before assuming a "keeps reapplying the wrong thing" symptom is a
caching/chart problem — it might just be a frozen operation.

**A confirmed real trigger for this (2026-08-02, syncing `kafka` to pick
up backlog #79's new topic): setting `.operation.sync.revision` to
`"HEAD"` when manually patching a Helm-chart-sourced Application.**
`"HEAD"` is a git-ism, not a valid value for a Helm chart source's
revision (which needs a real semver constraint or an empty string to
fall back to `spec.source.targetRevision`) — the sync fails at manifest
generation (`ComparisonError: ... invalid revision ... improper
constraint: HEAD`), but the automatic retry doesn't cleanly re-fail: it
re-applied a **stale, previously-cached** `operation.sync.source` (an old
snapshot missing the new topic entirely), actually ran a real sync
against that stale manifest, and reported per-resource `Succeeded`
statuses in `status.operationState.syncResult.resources` even though the
overall `phase` was `Error` — genuinely misleading, easy to mistake for
a real (if oddly-labeled) success. Confirmed via
`status.operationState.operation.sync.source.helm.valuesObject` still
showing the old `provisioning.topics` list post-failure. **Fix: never set
`revision` in a manual sync patch for a Helm-sourced Application** —
omit the field entirely (`{"sync":{}}`) so the controller reads the
live `spec.source.targetRevision` fresh. (Note: this is specifically
about Helm-chart-sourced Applications — `"HEAD"` is fine, and was used
successfully throughout the 2026-08-10 NetworkPolicy work, for
git-path-sourced Applications like every `*-network-policies` one.)

## Namespace-per-component isn't absolute

Established pattern: each service/infra component gets its own
namespace (gateway, api, workers, kafka, otel). PostgreSQL broke that
pattern deliberately (ADR 0012) — it lives in `api`'s namespace, not
its own, because `secretKeyRef` can't cross namespaces and Postgres has
exactly one consumer here. The OTel Collector (ADR 0013) got its own
`otel` namespace like Kafka, not Postgres's treatment — three consumers,
no credential to worry about (open OTLP receiver, like Kafka's
PLAINTEXT). If Redis ends up needing credentials and has a single
consumer, the Postgres reasoning likely applies again — don't assume a
new namespace by default.

## Working via background agents (new pattern, this session)

For independent, parallelizable work (e.g. Redis + dashboards run
side by side), dispatch background agents that clone their own scratch
copies of whichever repos they need — never point them at the shared
`/home/lmpeixoto/repos/AdamastorX/*` checkouts, since a second
agent (or the primary session) may be using them at the same time.
Each agent should: read this file first, follow the same ADR/
verification discipline documented here, open PRs, wait for CI, then
**stop without merging** — every PR merge needs explicit human
confirmation, agents included, no exceptions. The orchestrating session
reviews the diff and handles the merge once a human confirms.

## `root`'s own refresh, not just the child's (found live, 2026-08-20, backlog #125)

Merging a PR to `platform/argocd/apps/prometheus.yaml` and hard-
refreshing the `prometheus` Application directly is **not enough** to
get a new alert rule live — confirmed the hard way, real delay (~10+
minutes lost narrowing it down). `root` (the app-of-apps root
Application, ADR 0003) manages every child `Application` under
`argocd/apps/` as one of *its own* tracked resources; if `root` itself
hasn't detected the git diff on the child's spec, the child's own
`spec.source.helm.valuesObject` stays stale no matter how hard you
refresh the child — refreshing the child just re-confirms it's
"Synced" against the stale spec it already has, not against `main`.

Symptom: `kubectl get application prometheus -n argocd -o json | yq
-p json '.spec.source.helm.valuesObject...'` shows old content even
after `refresh=hard` on `prometheus`, while `git log` confirms the
right commit is on `main`. Fix: `refresh=hard` on `root` itself first
— check `kubectl get application root -n argocd -o jsonpath='{.status.
sync.status}'` flips to a real `OutOfSync` (not already `Synced`), let
its own `automated`+`selfHeal` sync fire, *then* refresh the child.
This is the same class of finding `docs/runbooks/canary.md` already
recorded for a *manually patched* Application spec — this one hit the
same root-not-noticing-the-child's-diff shape from an entirely normal
git-merge path, not a manual patch, so it's a real, recurring risk for
any future alert-rule/dashboard change, not a one-off.
