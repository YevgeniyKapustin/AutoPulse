# Domain model

## Listing lifecycle

```
raw → enriching → enriched → priced
                 ↘ failed → (retry) → dlq
```

## Core entities

### RawListing

Inbound auction/listing snapshot. May include opaque `raw_payload`.

### EnrichedListing

Extends raw with:

- `options` — packages, features, tags, owner_count
- `defects` — CV labels with confidence
- `llm_done` / `cv_done` — aggregation gates

### PricingResult

Dealer-facing metrics:

- `bid_price` — reference ask / auction bid context
- `recommended_dealer_bid` — suggested max buy
- `estimated_turnover_days` — expected days to resell
- `price_low` / `price_high` — confidence band

## LLM extraction goals

Pull hidden value signals from free text, e.g.:

- M-Sport / AMG / S-line packages
- Panorama roof, Harman/Kardon, heated seats
- Single owner, service history, no accidents (claimed)

## CV goals (MVP)

- Resize / normalize images off the event loop
- Flag obvious damage regions or empty/garbage photos
- Optional: plate blur (privacy) — later

## Margin rules (baseline)

```
effective_margin = base_margin + defect_penalty - option_bonus
recommended_bid = ask * (1 - effective_margin)
turnover_days = base_days + f(defects)
```

Replace with a learned model later without changing `PricingService` API.
