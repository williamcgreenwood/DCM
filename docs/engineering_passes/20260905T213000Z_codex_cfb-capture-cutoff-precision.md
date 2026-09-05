# Engineering Pass: CFB capture-cutoff precision

- **Pass ID:** `20260905T213000Z_codex_cfb-capture-cutoff-precision`
- **Starting branch/SHA:** `main` @ `70dea4a23b74fd927b8ea3a922d9feeb1ed5b2c7`
- **Ending branch:** `codex/cfb-capture-cutoff-precision-20260905` (commit pending)
- **Objective:** preserve the exact temporal boundary when a host derives its
  forecast cutoff from a private HAR capture.

## Defect and implementation

The fresh-wheel current-CFB run derived a whole-second cutoff from a capture
end that included milliseconds. The final HAR board records were then
correctly compared, but incorrectly classified as later than that rounded
cutoff. This was a producer/consumer contract bug, not a missing research
source.

- `dcm.runtime.cutoff._fmt` now retains fractional UTC seconds when present.
- A regression asserts a `21:24:07.344Z` capture end remains exactly that value
  when `--cutoff-from-capture` is used.
- Explicit operator cutoffs are unchanged, and temporal comparisons remain
  fail-closed for genuinely post-cutoff claims.

## Validation

- `pytest -q tests/test_version_cutoff.py tests/test_offer_metadata.py tests/test_cfb_guarded_launch.py` — **12 passed**.
- A clean-wheel private-HAR run before the repair produced a safe receipt:
  82 requested platform-side recoveries were all rejected solely as
  `CAPTURE_AFTER_CUTOFF`; no side was invented and no raw HAR content was
  retained in this record.

## Honest state and next work

Rerun the private current HAR on the repaired fresh wheel, then import only
permitted, timestamped shared research evidence through the host contract.
Do not claim a final Top100/Top25/freeze until coverage and final gates pass.
Root-of-trust, learning revision, predictive claim, and host-performance
certification are unchanged.
