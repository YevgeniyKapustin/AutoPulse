# ADR 001: Hybrid storage (MongoDB + MySQL)

## Status

Accepted

## Context

Listings arrive with irregular option sets, defect lists, and source-specific
payloads. Pricing outputs are fixed metrics that dealers query and aggregate.

## Decision

- **MongoDB** stores per-car enrichment state (raw + enriched document).
- **MySQL** stores `pricing_results` and future bid history.

## Consequences

- Enrichment schema can evolve without migrations for every new option key.
- Reporting/SQL joins stay simple on the pricing side.
- Cross-store consistency is eventual; use `external_id` as the join key.
- Agents must not invent a single-database shortcut that drops either store.
