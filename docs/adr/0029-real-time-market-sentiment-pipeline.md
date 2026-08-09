# 0029. Real-time market sentiment pipeline: domain choice, external data sources, lexicon-first sentiment, M7 gating

Status: Proposed

## Context

ADR 0022 set the bar for anything added in the expansion phase: a new
service must produce an operational shape this project does not already
have. M8-M12 filled in guaranteed fan-out delivery (#53), a long-running
async job control plane (#54), a saga-shaped Kafka lifecycle (M12), and —
still open — stateful stream processing (#55), which named a real,
unresolved conflict with ADR 0011's deliberately ephemeral Kafka storage
and has sat blocked behind #45's traffic and #23's chaos work ever since.

Separately, the owner asked for a new milestone whose data is genuinely
real and external, not self-generated — stated directly: *"ter sempre
dados a fluir e não dependentes de um utilizador"* (always-flowing data,
not dependent on a user). #45 (the workload generator) already lives by
that philosophy for synthetic traffic; this is the same philosophy
applied to data the project does not control the shape of. A
staff-engineer review this session weighed the options and converged on a
real-time stock market + financial news sentiment monitor, for two
concrete reasons:

1. **Non-bioinformatics.** M12 (ADR 0025) is explicit that its bio depth
   is bounded and justified for a health-tech audience specifically. A
   second bio-flavored milestone would repeat that audience bet rather
   than broaden it; a market-data domain is understandable to any
   reader, not just a bio-adjacent one — the "genuinely interesting home
   lab to publish about" audience ADR 0022 named is wider than either.
2. **Decomposes into genuinely new operational shapes**, not one more
   monolith: real external ingestion the project doesn't control the
   uptime of, multi-stream stateful correlation across two independently-
   arriving real-time feeds, and lexicon-based NLP under a real, current,
   measured CPU constraint (#77). None of the existing services do any of
   these three things.

This ADR records the domain decision, the real external data sources
chosen (each verified live this session, not assumed from a reference),
the lexicon-first sentiment-scoring decision, and the M7/CPU gating
decision. Backlog #78-#82 (new milestone M13) implement it; #82's
`aggregator` explicitly supersedes #55, carrying its unresolved ADR 0011
conflict forward onto this domain rather than leaving two open items
naming the same problem.

## Decision

### 1. Domain: real-time stock price + financial news sentiment for a fixed watchlist

Satisfies ADR 0022's operational-shape rule on three counts none of the
existing services cover:

- **External ingestion the project does not control.** Every other
  "continuous" data source here is either self-generated (#45) or a
  scheduled batch pull from a source with no real-time expectation
  (ClinVar). A live vendor feed that can drop, rate-limit, or change ToS
  at any time — and must be reconnected-to and resumed, not just
  retried once — is a genuinely new failure class.
- **Multi-stream stateful correlation.** #55 (superseded below) was
  scoped against a single existing topic. This milestone's `aggregator`
  joins two independently-arriving real-time streams (price ticks, scored
  news) into one windowed aggregate — a step up from anything shipped so
  far, and the reason #55's state-store-recovery question finally gets a
  real, continuously-arriving workload to be measured against instead of
  a low, bursty one.
- **Lexicon-based NLP under a real, current resource constraint** (#80,
  decision 3 below) — this project's first text-scoring workload of any
  kind, deliberately shaped by #77's measured CPU ceiling rather than
  built as if compute were free.

### 2. External data sources — real comparisons, each verified live this session (2026-08-02)

**Stock prices: Finnhub's free real-time trade websocket, chosen.**

| Source | Verified | Why chosen / rejected |
|---|---|---|
| **Finnhub (chosen)** | Free tier confirmed (finnhub.io docs/pricing, cross-checked against current third-party writeups): ~60 REST calls/min, free websocket streaming of real-time US trades, up to 50 symbols on the free tier (this watchlist needs 5-8), ~150ms latency. | A genuine push feed — no poll-interval to invent, the closest fit to "always-flowing." Real, accepted risk: a single vendor's free-tier ToS, which can change; reconnect-and-resume is a required, tested behavior (#78's AC), not assumed. |
| Twelve Data | Verified live via its own current pricing page: Basic/free plan = 8 API credits/minute, 800/day, real-time US equities included. | Rejected as primary: REST-poll only on the free tier, no websocket. 8 credits/min is a tight budget for a 5-8 ticker watchlist polled at any useful interval, with no headroom for retries — a worse fit for "always-flowing" than a push stream. Kept as the documented fallback if Finnhub's free tier ever tightens. |
| stooq.com free CSV endpoints | **Tested live this session, found currently broken for this purpose**: `https://stooq.com/q/l/?s=aapl.us&...` returned a real HTTP 404; `https://stooq.com/q/d/l/?s=aapl.us&i=d` returned a real HTTP 200 whose body is a JavaScript proof-of-work bot-challenge (`/__verify`, a SHA-256 hashcash puzzle), not a CSV. | Rejected. The "free, unauthenticated CSV, no real rate limit" reputation this endpoint carries in older references (blog posts, notebooks) does not hold today — exactly the kind of stale assumption this project's own discipline exists to catch (the same live-verification habit ADR 0014 used on the deprecated Grafana chart repo). |
| Alpha Vantage | Found during research, not seriously pursued: free tier is 25 requests/day (verified across multiple current sources). | Too low even for a small watchlist polled a few times an hour; noted for completeness, not compared further. |

**Financial news: WSJ Markets + MarketWatch RSS, chosen.**

| Source | Verified live (2026-08-02) | Why chosen / rejected |
|---|---|---|
| **WSJ Markets** (`feeds.content.dowjones.io/public/rss/RSSMarketsMain`) **+ MarketWatch top stories** (same domain, `/mw_topstories`) — chosen | Real HTTP 200, real content, articles dated the day of this research. | Both live, both real publishers, both reachable without auth or a bot challenge. |
| CNBC official RSS | Real HTTP 403 on a direct fetch. | Rejected — bot-blocked today, not a hypothetical. |
| Reuters public RSS | Real HTTP 301 to a now-dead/retired endpoint. | Rejected — the feed this project would have cited from an older reference no longer resolves to live content. |
| Yahoo Finance RSS | Real HTTP 429. | Rejected — rate-limited/blocked on a bare fetch. |
| Seeking Alpha `market_currents.xml`, investing.com `news_25.rss` | Both real HTTP 200, live content. | Verified viable, documented as a fallback if WSJ/MarketWatch ever go the way of CNBC/Reuters above — not built into v1, no reason to carry three sources for one watchlist yet. |

### 3. Sentiment scoring: VADER (lexicon-based) for v1, a transformer model recorded as an explicit deferred upgrade

`sentiment-analyzer` (#80) uses **VADER** (`vaderSentiment`), a mature,
well-known Python lexicon/rule-based scorer: sub-millisecond scoring, no
model download, no GPU, negligible steady-state CPU. This is weighed
directly against a FinBERT-style finance-tuned transformer, and decided
against **for v1** on a real, current, measured basis: **#77's CPU
accounting has this node at 63% of allocatable requested (2545m of
4000m) after every existing over-provisioned request on the cluster was
already trimmed down to real observed usage — roughly 1.4 real free
cores.** A CPU-only transformer's realistic inference footprint would
consume most of that remaining headroom for one of this milestone's five
new always-on services, before the other four are even scheduled. VADER's
known limitation for this domain (tuned on general/social-media text, not
finance-specific jargon) is accepted as a stated v1 gap, not glossed.

**A FinBERT-style model is recorded here as a real, explicit, deferred
upgrade** — revisited once M7's dedicated hardware exists and idle
capacity is actually measured against it, not silently dropped the way an
unstated deferral would be.

### 4. Language choices (ADR 0019's rule applied, not defaulted)

ADR 0019's rule: bioinformatics-domain logic earns Python with a stated
reason; everything else stays in whatever already fits, Java/Spring by
default. Applied here:

- **`market-data-ingestor` (#78) and `news-ingestor` (#79): Java/Spring
  Boot.** Both are generic websocket-client/HTTP-poll-plus-Kafka-producer
  messaging work — the same shape `api`/`workers`/`watchlist-service`
  already are. Neither has a domain-specific-tooling reason to leave
  Java, so neither does.
- **`sentiment-analyzer` (#80): Python.** Earns it the same way
  `clinvar-service` did in ADR 0019 — a real, stated ecosystem reason
  (VADER has no equivalent, equally-established zero-cost Java lexicon
  library), not Python by default.
- **`aggregator` (#81): Java/Spring, Kafka Streams.** Matches #55's own
  stated preference and the existing Spring/Kafka stack. Flink rejected
  for the same "boring, well-understood tools" reasoning every prior tool
  choice in this project has used — no stated need this project's
  existing toolchain can't already meet.
- **`visualizer` (#82): a static page, no backend**, reusing
  `clinvar-viewer`'s exact pattern (deploy-time `config.js`, no
  confidentiality boundary claimed, same Ingress convention) rather than
  inventing a second frontend architecture — deliberately the one place
  in this milestone that is *not* a new operational shape.

### 5. Gated on M7, for CPU headroom (not data volume, unlike M12)

**This milestone does not start until M7 (the multi-node/dedicated-host
substrate) lands.** #77's real, repeatedly-confirmed finding — CPU, not
memory, is this node's scarce resource, at 63% of allocatable already
requested after trimming everything found over-provisioned so far —
leaves roughly 1.4 free cores, not enough for four to five new always-on
Kafka producer/consumer services. Squeezing this milestone onto the
current single laptop would either starve existing services or arrive
already CPU-throttled, neither of which is the flagship real-workload
demo this is meant to be for the new hardware. `docs/roadmap/milestones.md`
records this gating explicitly, the same way it already does for M12
(gated on M7 for storage/data-volume reasons) — a different real reason
reaching the same conclusion, not a copy-pasted one.

## Consequences

- Two new Kafka event types (`stock.price.tick`, `news.sentiment.scored`,
  `news.article.published`) plus `aggregator`'s own changelog topics — a
  real, material growth in this cluster's topic count, on a broker whose
  ephemeral storage (ADR 0011) is now finally confronted for real by #81
  rather than left as a named-but-unresolved risk the way #55 left it.
- A live dependency this project does not control: Finnhub's free tier
  and the two chosen RSS feeds can change ToS, rate limits, or simply go
  offline (as CNBC's and Reuters' already effectively have for this
  purpose) with no notice. Accepted, in the same spirit ADR 0011 accepted
  RF=1 as a stated risk rather than an unexamined gap — #78/#79's AC
  requires the failure path (reconnect, skip-and-log) to be real and
  tested, not assumed away.
- Operational surface grows by five more always-on components once M7
  clears — more CI, more alert rules, more for #32 (canonical-doc drift)
  to catch. This is the point of the expansion phase (ADR 0022), not an
  accident of it.
- #55 is superseded, not left open twice — its backlog entry now points
  here, and #81 carries its exact state-store-recovery AC forward rather
  than restating a weaker version of it.
- This is a **new milestone number (M13)**, not a resurrection of any
  closed one — it shares no scope with M6 (#30, closed) or M12 (bio
  domain); the number is new because the domain and the reasoning are.

## Addendum (2026-08-09): the FinBERT-v2 trigger now means blocked-on-hardware, no date

Decision §3 above deferred a FinBERT-style transformer upgrade "once M7's
dedicated hardware exists and idle capacity is actually measured against
it." A live capacity re-measurement
(`docs/reviews/2026-08-09-hardware-constrained-strategy.md`) found the
planned M7 multi-node substrate does not fit this machine at any trim
level and closed as superseded (ADR 0035's addendum, the new ADR 0040) —
so that trigger now means **blocked-on-hardware, with no date**, not
blocked behind the dead VM interim plan. VADER stays the v1 (and, for now,
only) sentiment scorer; the FinBERT-v2 upgrade references ADR 0040 and the
real dedicated-host trigger going forward.
