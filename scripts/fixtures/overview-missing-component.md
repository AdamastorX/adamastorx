# Fixture: overview.md that never mentions the ticker-price ingestor

This file deliberately omits one live custom-service component to
prove check-roster-drift.sh actually fails when a component goes
unmentioned (the #83 shape).

Mentions api, aggregator, clinvar-service, clinvar-viewer,
news-ingestor, sentiment-analyzer, visualizer, watchlist-service,
workers, workload-generator -- but never the real-time stock quote
service by its own name.
