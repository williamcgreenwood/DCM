# Engineering Pass: CFB source-catalog capabilities

- **Pass ID:** `20260905T111500Z_codex_cfb-source-catalog-capabilities`
- **Starting branch/SHA:** `main` @ `e018d1a93113b8f52750a7346235e44b96599983`
- **Ending branch:** `codex/cfb-source-catalog-capabilities-20260905` (commit pending)
- **Objective:** make CFB source selection derive from the versioned capability
  catalog while preserving stable route IDs used in acquisition telemetry,
  checkpoints, and circuit breakers.

## Implementation

- Added explicit CFB official-athletics and public-weather source capabilities
  with access, rate-limit, freshness, licensing, failure-mode, and fallback
  declarations.
- Added `source_health_seeds`; it converts catalog records into health seeds.
- Changed `default_cfb_source_health` to use those seeds and preserve legacy
  runtime IDs (`CFB_OFFICIAL_GAMEBOOK`, `CFB_SPORTS_REFERENCE`, `CFB_STATUS`,
  `WEB_SEARCH`) while retaining each `catalogSourceId` for lineage.
- Added regression coverage for catalog-to-router derivation and event/weather
  routing. No live web calls, raw source pages, HAR data, credentials, or
  automatic background scraping are introduced.

## Validation

- `pytest -q tests/test_source_catalog.py tests/test_cfb_semantic_completion.py tests/test_cfb_freeze_gate.py` — **45 passed**.
- Official inventory generator and stale check — **PASS**.

## Honest state and next work

This is a source capability/routing consumer, not a claim that every CFB source
has a live parser. The next dependency-ready work is the host-executed
acquisition/import loop and concrete adapter probes with permitted public
sources; platform offered-side metadata remains an authorized-board-data issue,
not a web-research claim.
