# Daily Drops Deal Finder

Amazon Creators API research dashboard hosted on GitHub Pages. No retailer scraping or paid infrastructure.

## Amazon research

- Scheduled every hour (GitHub Actions schedules are best-effort, not guaranteed exact times).
- Rotates across 33 search/category combinations, using up to 24 search calls per run and 10 items per call.
- Rotates search result pages over time. This is *sampled discovery*, not exhaustive tracking of all bestsellers, new listings, or the full Amazon catalog.
- Parses `offersV2.listings.price.savingBasis` correctly. Labels the basis as Amazon supplies it; a list price is not a verified historical price.
- Keeps only qualifying 40%+ reference-price leads with offer snapshots under one hour old. Does not assert glitches or coupon stacks.
- Conservatively limits API calls and records errors. If Amazon reduces account quotas, lower `PER_RUN` and `MAX_DAILY_CALLS` in `amazon_scan.py`.
- Amazon's Creators API offer caching limit is one hour. Static public GitHub Pages is not a real-time checkout verification service.
- Public dashboard shows research-only direct product links. For affiliate attribution, use Amazon-provided tagged URLs without modification, according to the Creators API terms.

## Setup

Required GitHub Actions secrets: `AMAZON_CREATORS_CREDENTIAL_ID`, `AMAZON_CREATORS_SECRET`, `AMAZON_PARTNER_TAG`.
Workflow: Actions > Amazon automated deal research > Run workflow. Inspect `data/amazon-deals.json` for errors and results.

The community RSS workflow is separate and its leads are unverified. Walmart official API integration is not yet implemented.

## Important limitations

No automated checkout verification, price history, sales rank, newly-added catalog feed, coupon stacking validation, or guaranteed hourly execution. Only display discounts as comparisons to the stated reference basis. Never call an unverified price discrepancy a confirmed pricing glitch.
