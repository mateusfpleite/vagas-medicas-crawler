# PCI Spider Freshness Filter

## Problem

The PCI spider returns ~200 cards per specialty page, but ~92% have expired inscription deadlines (dating back to mid-2025). This means:
- ~185 unnecessary detail page HTTP requests per specialty
- ~8 minutes wasted crawl time
- 2300+ vagas in DB that are no longer actionable for doctors

## Solution

Filter at the listing level using inscription deadline dates from `div.ce`.

### Key Discovery

Every listing card has a `div.ce` element containing the inscription deadline:
- `"05/03/2026"` (93.5% of cases)
- `"Reaberto até 12/02/2026"` (6%)
- `"23/03 a 22/04/2026"` (0.5%)
- Zero cards without a parseable date in production

### Changes

**1. New function `_parse_deadline(text: str) -> date | None`**
- Extracts the last `DD/MM/YYYY` date from the text
- Returns `None` if no date found

**2. Modified `parse_listing()`**
- Extract `div.ce` text from each card
- Parse deadline via `_parse_deadline()`
- Skip cards where deadline < today
- Fail-open: cards without `div.ce` or unparseable dates are kept

**3. New tests**
- `test_parse_deadline_*` for each format variant
- `test_parse_listing_filters_expired_cards`
- `test_parse_listing_keeps_card_without_deadline`

### Impact

- ~92% fewer detail page fetches
- Crawl time drops from ~10min to ~1min
- Only actionable vagas enter the DB
- Existing tests unaffected (fixtures without `div.ce` → fail-open)
