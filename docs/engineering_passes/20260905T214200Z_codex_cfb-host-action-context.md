# Engineering Pass: CFB host action context

- **Pass ID:** `20260905T214200Z_codex_cfb-host-action-context`
- **Starting branch/SHA:** `main` @ `ce69ffeda1cfdcff6415e0cba9999fdb1e22c00d`
- **Ending branch:** `codex/cfb-host-action-context-20260905` (commit pending)
- **Objective:** make selected host research actions actionable without making
  the DCM core a web scraper or exposing private HAR data in repository files.

## Implementation

- Added one canonical host-task projection in `dcm.research.batch`.
- Selected task records now include their non-secret request context, source
  family, ranked capability-derived source candidates, preferred source ID, and
  a bounded one-observation acquisition instruction.
- Both CELF-packed batch tasks and the flattened task view use the same
  projection, so a host no longer receives only opaque IDs after selection.
- The host remains responsible for permitted public fetch/search and returns
  simple observations to the existing canonical importer; no second evidence
  or probability engine was added.

## Validation

- `pytest -q tests/test_research_store.py tests/test_cfb_research_os.py tests/test_host_native.py` — **24 passed**.
- Regression asserts a selected event task includes event context, source
  family/candidates, and the acquisition instruction.

## Honest state and next work

The next deterministic step is to execute the source-aware batch with
timestamped permitted public observations, then recompute coverage and model
only when contracts close. No raw HAR values, player identifiers, source-page
archives, root-certification bytes, learning revision, predictive claim, or
performance certification are changed by this pass.
