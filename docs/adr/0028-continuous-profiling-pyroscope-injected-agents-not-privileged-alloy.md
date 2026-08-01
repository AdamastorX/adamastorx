# 0028. Continuous profiling: Pyroscope, instrumented via unprivileged init-container agent injection, not a privileged cluster-wide profiler

Status: Accepted

## Context

Backlog #57 asked for a continuous profiler as the fourth signal pillar
(metrics/logs/traces already exist), motivated by a real incident that
was invisible to all three: the #35 95-minute `CrashLoopBackOff`, where
`kubectl top` showed `api` pegged at 498m/500m CPU during JVM cold start
but nothing showed *which code* was burning it. The AC's suggested tool
(Pyroscope) was re-verified rather than assumed still current, and it
still is — it remains a real Grafana datasource
(`grafana-pyroscope-datasource`), bundled with Grafana >=12.3.0, and this
cluster's Grafana chart is already on 12.8.0.

The AC's suggested *instrumentation* path — an in-app SDK/javaagent baked
into each service's image — turned out to have a real dependency this
item could not satisfy inside one session: it needs a services-repo code
change *and* a merged, CI-published GHCR image (the services repo's
`build-publish.yml` only runs `on: push: branches: [main]`, not on a PR
branch) before a single profile could exist. This project's own review
discipline is to open PRs and let a human merge, not to merge its own
work — so an in-app-SDK-only design would have shipped zero live
evidence this session.

The alternative considered first was **not** an in-app SDK at all:
Grafana Alloy, already running here for log collection
(`argocd/apps/alloy.yaml`), ships `pyroscope.java` (async-profiler,
attaches to a running JVM's PID from outside the container) and
`pyroscope.ebpf` (eBPF, supports Python natively) — both external-attach
profilers needing no cooperation from the target process. This was
prototyped, but both require the Alloy DaemonSet to run
`securityContext.privileged: true`, as root, inside the host PID
namespace, plus a hostPath mount of `/sys/kernel/tracing` — a real,
meaningful escalation from Alloy's current unprivileged, log-only
footprint, cluster-wide, for every future workload this DaemonSet ever
runs alongside. That is not a decision to make unilaterally inside one
feature item's session budget; it deserves its own deliberate review
(closer in shape to #58's own "a validating webhook is a new single
point of failure, exercised deliberately" framing than to a profiling
side-quest).

## Decision

**Deploy Pyroscope (`argocd/apps/pyroscope.yaml`, chart 2.2.0,
single-binary, own namespace) and instrument `api`/`clinvar-service` with
the real Pyroscope Java/Python SDKs, injected via an unprivileged
init-container pattern instead of baked into a rebuilt image.**

Concretely (`kubernetes/api/rollout.yaml`,
`kubernetes/clinvar-service/deployment.yaml`): an ordinary, non-root init
container fetches the real published agent (Java: `pyroscope-java` v2.8.0
jar from its GitHub release; Python: `pyroscope-io` from PyPI) into a
shared `emptyDir`, and the main container picks it up with no image
rebuild — `JAVA_TOOL_OPTIONS=-javaagent:...` for `api` (the JVM reads
this env var automatically, no `ENTRYPOINT` change), and a Kubernetes
`command` override wrapping the existing `uvicorn app.main:app` call with
one `pyroscope.configure()` line for `clinvar-service` (the image's own
`ENTRYPOINT` is untouched in the services repo).

This is a middle path, chosen explicitly over the two ends it sits
between:

- Over the AC's literal in-app-SDK-in-a-rebuilt-image path: avoids the
  services-repo-merge dependency that would have blocked any live
  profile this session.
- Over the privileged cluster-wide Alloy path: avoids escalating a
  shared, already-running DaemonSet to root/privileged/hostPID for every
  workload on the node, a decision this item's own scope shouldn't make
  unilaterally.

## Consequences

- **Real, stated cost**: the profiling agent's version now lives in a
  platform-repo manifest (`rollout.yaml`/`deployment.yaml`), not in
  services' own dependency lockfile (`pom.xml`/`requirements`) — a real
  drift risk between what the platform repo fetches at pod start and
  what a human reviewing the services repo would expect to see. A real
  follow-up, once the services-repo-merge dependency stops being a
  same-session blocker, is to fold this into each service's own build
  (the AC's original suggestion) and delete the init-container fetch.
- **Profile-to-trace span correlation is a stated gap, not shipped**:
  Grafana's own "traces to profiles" feature needs a language-specific
  OTel span-processor *bridge package* running inside the profiled
  process (Java: `io.pyroscope:otel`; Python: `pyroscope-otel`), adding a
  `pyroscope.profile.id` span attribute. That is a real in-app
  integration, not something an init-container can retrofit — it needs
  to be wired into each service's own OTel tracer setup in code. The
  Grafana datasource's `tracesToProfiles` block is wired up
  (service.name/namespace tag mapping to the new Pyroscope datasource),
  a real prerequisite for that follow-up, but the actual clickable
  span-to-flamegraph link is not proven working this session.
- **Session-level constraint, stated directly**: this session's shell
  access could validate every manifest against the real cluster's API
  server (`kubectl apply --dry-run=server`, real schema-valid response)
  and render the real Helm chart locally against the pinned version
  (`helm template`, clean output, confirmed single StatefulSet + real
  4040 Service + the configured 3Gi PVC/resources), and used real,
  freshly-read `kubectl describe node`/`kubectl top`/`df -h` numbers to
  size everything conservatively — but could not apply anything to the
  live cluster (blocked by this session's own tooling policy on
  cluster-mutating commands, not a design choice). See the platform PR
  description for the exact commands a human should run post-merge to
  complete the live proof (deploy confirmation, the #35 CPU-limit
  reproduction + flame graph capture, a real `clinvar-service` ingestion
  profile, and real PVC growth-vs-retention numbers).
- If Alloy's own external-attach profilers are revisited later (e.g. once
  this project has a real reason to profile a workload with no SDK of its
  own, or decides the privileged-DaemonSet tradeoff is worth taking
  cluster-wide), this item's own prototyping already confirms the River
  config shape (`discovery.kubernetes` -> `discovery.process(join=...)`
  -> `pyroscope.java`/`pyroscope.ebpf` -> `pyroscope.write`) — not
  wasted, just not what shipped.
