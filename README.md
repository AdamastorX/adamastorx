# AdamastorX

Open-source platform engineering project. The application is a vehicle; the real
subject matter is running distributed systems in production the boring, reliable way.

## Vision

Build and operate a small, realistic distributed system end to end — cluster,
GitOps delivery, a Kafka/Postgres/Redis-backed Spring Boot application, and a
full observability stack — using nothing but boring, well-understood tools.
The goal is to generate genuine platform engineering, SRE, and DevOps problems
worth solving, not to ship a product.

## Scope boundaries

Explicitly **out**: service mesh, Vault, Crossplane, Backstage, Cilium. If a
problem can be solved with what's already approved (see Technology decisions
below), that's the answer — new tools require a real, demonstrated need and an
ADR.

## Repository map

| Repo | Contents |
|---|---|
| [adamastorx](.) | Org landing page, docs, roadmap, backlog, Claude context (this repo) |
| [platform](https://github.com/AdamastorX/platform) | Terraform, Helm, ArgoCD, Kubernetes manifests, cluster bootstrap |
| [services](https://github.com/AdamastorX/services) | Gateway, API, workers, shared libraries (Spring Boot) |
| [observability](https://github.com/AdamastorX/observability) | Grafana dashboards/alerts, OpenTelemetry config, runbooks |

## Technology decisions

Approved stack: Kubernetes (k3s), Terraform, Helm, ArgoCD, GitHub Actions,
Kafka (KRaft), PostgreSQL, Redis, OpenTelemetry, Prometheus, Grafana, Loki,
Tempo, Mimir, Traefik, cert-manager, Trivy, Spring Boot.

Anything not on this list needs an ADR (see `docs/adr/`) before it's adopted.

## Roadmap

See `docs/roadmap/milestones.md` for the milestone plan and
`docs/roadmap/backlog.md` for the current issue backlog.

## Documentation

See `docs/` — architecture overviews, ADRs, runbooks, roadmap.

## Contributing

See `CONTRIBUTING.md`.

## License

MIT — see `LICENSE`.
