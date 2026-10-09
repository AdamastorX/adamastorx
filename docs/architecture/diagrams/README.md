# Architecture diagrams (for the talk)

Two diagrams, each meant to fit one slide. Both are checked against the code and the live cluster, not drawn from memory;
the longer ASCII version and the reasoning live in [`../overview.md`](../overview.md).

| File | Slide idea |
|---|---|
| `system-overview.{mmd,svg,png}` | The whole system in five seconds: how code gets in (GitOps), what runs, and what watches it. |
| `event-flows.{mmd,svg,png}` | The interesting part: three stories told by the Kafka topics. |

Regenerate the images after editing a `.mmd` (Chrome is used so no Chromium download is needed):

```bash
echo '{"executablePath":"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}' > /tmp/pptr.json
for n in system-overview event-flows; do
  npx -y @mermaid-js/mermaid-cli@11 -p /tmp/pptr.json -i $n.mmd -o $n.svg -b white
  npx -y @mermaid-js/mermaid-cli@11 -p /tmp/pptr.json -i $n.mmd -o $n.png -b white -w 2200 -s 2
done
```

## System overview

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Helvetica, Arial, sans-serif', 'fontSize': '20px', 'lineColor': '#475569', 'primaryTextColor': '#0f172a'}, 'flowchart': {'curve': 'basis', 'nodeSpacing': 45, 'rankSpacing': 80, 'htmlLabels': true, 'padding': 18}}}%%
flowchart TB

  USER(["Users<br/>browser · API clients"])

  subgraph DEL["GitOps delivery: the only way in"]
    direction LR
    GH["GitHub<br/>4 repos"] --> CI["CI gates<br/>tests · Trivy CVE scan<br/>event-schema checks"]
    CI --> REG[("ghcr.io<br/>tag = commit SHA")]
    GH --> ARGO["ArgoCD<br/>app-of-apps · selfHeal"]
  end

  subgraph K8S["One k3s node  ·  Cilium eBPF networking + NetworkPolicies"]
    direction LR
    EDGE["Traefik<br/>TLS · CORS · API key<br/>rate limit"]
    API["api<br/>canary + automated<br/>SLO gate"]
    STATE[("PostgreSQL<br/>Redis")]
    KAFKA{{"Kafka<br/>event backbone"}}
    WORK["workers<br/>autoscaled on lag"]
    CLIN["ClinVar<br/>ingestion · watchlist"]
    MKT["Market pipeline<br/>prices + news<br/>→ sentiment → aggregates"]

    EDGE --> API
    API --- STATE
    API <--> KAFKA
    KAFKA --> WORK
    KAFKA <--> CLIN
    KAFKA <--> MKT
  end

  OBS["Observability<br/>Prometheus · Grafana<br/>Loki · Tempo<br/>Pyroscope · Mimir<br/>OpenTelemetry"]

  USER ==>|"requests"| K8S
  DEL ==>|"sync"| K8S
  K8S -.->|"telemetry"| OBS

  classDef ext fill:#f1f5f9,stroke:#94a3b8,color:#334155
  classDef svc fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e
  classDef mkt fill:#ecfccb,stroke:#65a30d,color:#1a2e05
  classDef state fill:#fef3c7,stroke:#d97706,color:#451a03
  classDef bus fill:#fde68a,stroke:#b45309,color:#451a03,stroke-width:4px
  classDef obs fill:#f3e8ff,stroke:#9333ea,color:#3b0764
  classDef del fill:#fee2e2,stroke:#dc2626,color:#450a0a
  classDef edge fill:#dcfce7,stroke:#16a34a,color:#052e16

  class USER ext
  class API,WORK,CLIN svc
  class MKT mkt
  class STATE state
  class KAFKA bus
  class OBS obs
  class GH,CI,REG,ARGO del
  class EDGE edge
```

## Event flows

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Helvetica, Arial, sans-serif', 'fontSize': '20px', 'lineColor': '#475569', 'primaryTextColor': '#0f172a'}, 'flowchart': {'curve': 'basis', 'nodeSpacing': 34, 'rankSpacing': 60, 'htmlLabels': true, 'padding': 16}}}%%
flowchart TB

  subgraph F1["ClinVar: a weekly release invalidates caches and notifies subscribers"]
    direction LR
    NCBI(["NCBI<br/>ClinVar VCF<br/>(weekly)"]) --> CLIN["clinvar-service<br/>diff vs previous release"]
    CLIN --> T1{{"clinvar.<br/>ingestion.completed"}}
    T1 -->|"drop changed<br/>cache keys"| API2["api · Redis"]
    T1 -->|"notify<br/>subscribers"| WATCH["watchlist-service"] --> NTFY(["ntfy.sh<br/>phone"])
  end

  subgraph F2["Work items: guaranteed delivery with an outbox"]
    direction LR
    API["api<br/>+ outbox table"] -->|"relay"| T2{{"work-items"}} --> WORK["workers<br/>KEDA scales on lag"]
  end

  subgraph F3["Market data: prices and news become one live view"]
    direction LR
    FIN(["Finnhub<br/>websocket"]) --> MDI["market-data-<br/>ingestor"] --> T3{{"stock.price.tick"}}
    RSS(["WSJ · MarketWatch<br/>RSS"]) --> NEWS["news-ingestor"] --> T4{{"news.article.<br/>published"}} --> SENT["sentiment-<br/>analyzer"] --> T5{{"news.sentiment.<br/>scored"}}
    T3 --> AGG["aggregator<br/>Kafka Streams"]
    T5 --> AGG
    AGG -->|"GET /aggregates"| VIS["visualizer"]
  end

  F1 ~~~ F2
  F2 ~~~ F3

  classDef ext fill:#f1f5f9,stroke:#94a3b8,color:#334155
  classDef svc fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e
  classDef mkt fill:#ecfccb,stroke:#65a30d,color:#1a2e05
  classDef topic fill:#fde68a,stroke:#b45309,color:#451a03,stroke-width:3px

  class NCBI,NTFY,FIN,RSS ext
  class CLIN,API,API2,WATCH,WORK svc
  class MDI,NEWS,SENT,AGG,VIS mkt
  class T1,T2,T3,T4,T5 topic
```

## What is deliberately not on the slides

- **Network policies** are drawn as "NetworkPolicies", not "default-deny everywhere": backlog #126 is still rolling them
  out, and the M13 and `watchlist` namespaces are not covered yet.
- **Beyla** (eBPF auto-instrumentation) and the Mimir remote-write path are experiments with open questions (#145, #135),
  so Mimir appears only in the observability list and Beyla is left out.
- **Versions, hostnames and the node's size** are omitted on purpose: they change and are not the point of a slide.
