# External Donor Five-Repository Audit

**Base:** `main` `98cb698cf000b963e24ca47b3c1e4e18722bda96`  |  **Schema:** `dcm.external_donor_five_repo_matrix.v1`

Sanitized source audit of the five named public upstream repositories; no donor source was installed, executed, copied, or committed.

## Decisions

| Repository | Main SHA | Meaningful areas reviewed | Disposition | Runtime change |
|---|---|---|---|---|
| [sports-betting](https://github.com/georgedouzas/sports-betting) | `eb4cedf376663fac68f508e50b83fd832e74dfd4` | sportsbet/dataloaders and sources; sportsbet/evaluation; sportsbet/cli and sportsbet/mcp; sportsbet/execution | DCM_NATIVE_EQUIVALENT, REJECT_POOR_FIT | None |
| [scikit-ai](https://github.com/georgedouzas/scikit-ai) | `aaee46f9b8de1af2b20fe41dbcb82ee06c5b80a7` | skai/base/llm and skai/llm/_openai.py; skai/base/rl | REJECT_DUPLICATE, REJECT_POOR_FIT | None |
| [imbalanced-learn-extra](https://github.com/georgedouzas/imbalanced-learn-extra) | `9e523b84af629f5a7dc85c419528d835a5774bce` | imblearn_extra/gsmote/geometric_smote.py; imblearn_extra/clover | BLOCKED_RIGHTS | None |
| [scikit-complexity](https://github.com/georgedouzas/scikit-complexity) | `2fe89a8d1b046ac50c0e7bfd586df597c0863db6` | skcomplex/base.py and skcomplex/spaces/_euclidean.py; skcomplex/physics/_classical_mechanics.py | REJECT_POOR_FIT | None |
| [copier-modern-python](https://github.com/georgedouzas/copier-modern-python) | `46bc1835e256f94f6a08cb290da61c071a2fa2b3` | project template, pyproject.toml, noxfile.py, CI and pre-commit templates | ALREADY_PRESENT_VERIFIED | None |

## Component findings

### sports-betting

- License: MIT (root LICENSE and pyproject agree)
- Rights: `CLEAR_FOR_REVIEW; NO CODE COPIED`
- Runtime/dependencies: Python >=3.11,<3.14; pandas, sklearn, cloudpickle, BeautifulSoup, aiohttp, Pandera, PyArrow; optional MCP and Playwright execution
- README SHA-256: `9e4c6de24d180b1641f867d793199a43a1bcc5205e7b5836b779442779a2e109`; pyproject SHA-256: `886bd3f146750a2fc81030dfdcca514eee2396f8a98748a8e78dd85a33bc129d`; LICENSE SHA-256: `c8367bc49b1df477e68e4cbb198a7472cffeced655fe752860f8534db997c6f1`
- Current release tags seen: 0.15.1; latest commit: `2026-07-28T08:36:29+03:00 chore: Release 0.15.1`
- Entrypoints: `sportsbet.cli:main`, `sportsbet.mcp:run`

#### `sportsbet/dataloaders and sources` — `REJECT_POOR_FIT`

- Function: External sports stats/odds acquisition, schema and team-name resolver
- DCM mapping: DCM-native Insights/HAR accounting, typed research adapters, exact-offer authorization and evidence graph
- Decision/risk: No data/provider rights or exact DCM offer contract; would create duplicate source/identity stack. No source imported.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/dataloaders/test_leakage.py`, `tests/evaluation/test_model_selection.py`, `tests/cli/test_execution.py`, `tests/mcp/test_mcp.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

#### `sportsbet/evaluation` — `DCM_NATIVE_EQUIVALENT`

- Function: sklearn bettor estimator, odds strategy, TimeSeriesSplit backtest and grid search
- DCM mapping: DCM-native EventWorld, walkforward, chronological event-grouped calibration and payout gates
- Decision/risk: TimeSeriesSplit orders rows by date but does not establish event-disjoint groups, point-in-time label availability, DCM offer authority or platform payout semantics. Reused the audit as a validation requirement; no code copied.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/dataloaders/test_leakage.py`, `tests/evaluation/test_model_selection.py`, `tests/cli/test_execution.py`, `tests/mcp/test_mcp.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

#### `sportsbet/cli and sportsbet/mcp` — `REJECT_POOR_FIT`

- Function: Data, model, backtest, bet, execution and browser MCP surfaces
- DCM mapping: Canonical dcm.runner / dcm.chat and governed Research OS
- Decision/risk: Parallel orchestration and offer/data namespaces; not needed for DCM.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/dataloaders/test_leakage.py`, `tests/evaluation/test_model_selection.py`, `tests/cli/test_execution.py`, `tests/mcp/test_mcp.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

#### `sportsbet/execution` — `REJECT_POOR_FIT`

- Function: Bookmaker API/browser login and real-money placement
- DCM mapping: No authorized DCM consumer
- Decision/risk: Explicitly excluded real-money execution and account/browser control.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/dataloaders/test_leakage.py`, `tests/evaluation/test_model_selection.py`, `tests/cli/test_execution.py`, `tests/mcp/test_mcp.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

### scikit-ai

- License: MIT (root LICENSE and pyproject agree)
- Rights: `CLEAR_FOR_REVIEW; NO CODE COPIED`
- Runtime/dependencies: Python >=3.11,<3.14; scikit-learn, OpenAI SDK, python-dotenv; RL base also requires Gymnasium when used
- README SHA-256: `10c9457529b98389ec4030e5ace746765c3fc997d266192dd2c1975e450fd388`; pyproject SHA-256: `9bc8b4ac305e3b22ac2cfb72ef1f108f84ea5b943d52da5fcb7b782db11aa53d`; LICENSE SHA-256: `1d87f14145a0aef762e292d2d6764796f44861b35434ed7962589283f81b49d7`
- Current release tags seen: none; latest commit: `2025-07-13T07:18:31+03:00 docs: Fix badges URLs`
- Entrypoints: none

#### `skai/base/llm and skai/llm/_openai.py` — `REJECT_DUPLICATE`

- Function: sklearn-style LLM classifier; OpenAI API prompt/completion interface
- DCM mapping: No remote research classifier consumer; DCM uses typed deterministic research actions/evidence contracts
- Decision/risk: Remote inference is not authorized for private/restricted inputs and does not add verified fact authority. OpenAI dependency and model output cannot be a truth/probability oracle.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/base/llm`, `tests/llm`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

#### `skai/base/rl` — `REJECT_POOR_FIT`

- Function: Abstract RL agent contract
- DCM mapping: No RL-based product requirement or DCM consumer
- Decision/risk: No evidence that RL can safely improve current under-labeled, chronological DCM targets; no RL functionality is inferred beyond inspected base abstraction.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/base/llm`, `tests/llm`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

### imbalanced-learn-extra

- License: Conflicting evidence: root LICENSE says Apache-2.0; project metadata says MIT; GeometricSMOTE source header says BSD-3-Clause
- Rights: `BLOCKED_RIGHTS; no redistribution or installed dependency pending authoritative clarification`
- Runtime/dependencies: Python >=3.10,<3.14; SciPy, NumPy, imbalanced-learn, MiniSom, typing-extensions; DCM requires Python >=3.11 and NumPy only
- README SHA-256: `8b136cd5ea3e8fd71f07ea6b599e42a4ecedcafa8782f42dde37308c248ddea0`; pyproject SHA-256: `d4b2aa0d0f7c7ce900e00362a810c76fdf71f733a12e62c2ec08b6fc34075c5c`; LICENSE SHA-256: `048a5823560eef70950a79f1143cdb66ff42cda1367543164e0a8752a923566e`
- Current release tags seen: 0.2.10; latest commit: `2025-10-20T09:11:49+03:00 chore: Release 0.2.10`
- Entrypoints: none

#### `imblearn_extra/gsmote/geometric_smote.py` — `BLOCKED_RIGHTS`

- Function: Geometric SMOTE for synthetic minority classification samples
- DCM mapping: No eligible DCM historical target population; native walkforward and class-prior/shrinkage baselines
- Decision/risk: Three incompatible license signals across package/license/file header. No source copied or dependency installed; no synthetic data used as observed history.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/gsmote/test_geometric_smote.py`, `tests/clover/over_sampling/test_cluster.py`, `tests/clover/over_sampling/test_gsomo.py`, `tests/clover/distribution/test_density.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

#### `imblearn_extra/clover` — `BLOCKED_RIGHTS`

- Function: Clustering-based SOMO/KMeans-SMOTE and density distributor
- DCM mapping: No eligible target and no event/team/role/season/temporal neighbor-boundary proof
- Decision/risk: Same package license conflict; oversampling could cross related-prop/event boundaries and distort probability calibration.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/gsmote/test_geometric_smote.py`, `tests/clover/over_sampling/test_cluster.py`, `tests/clover/over_sampling/test_gsomo.py`, `tests/clover/distribution/test_density.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

### scikit-complexity

- License: MIT (root LICENSE and pyproject agree)
- Rights: `CLEAR_FOR_REVIEW; NO CODE COPIED`
- Runtime/dependencies: Python >=3.12,<3.13 (DCM >=3.11); SageMath imports in base/physics/spaces; LAMMPS declared dependency
- README SHA-256: `37ef956ae2fd83cda080d9f4f341fe206b36232b1da1926a8760f0012679c1a7`; pyproject SHA-256: `6e34ba081f6ea93a9cac67f8fca68fbd59a1ceda7002662db9ba8f4e55ec36b8`; LICENSE SHA-256: `95fdd0ccab793ad40dbe22b90b97c91077e47301746b8c27f26dcde6e7b94ab7`
- Current release tags seen: none; latest commit: `2024-09-03T23:05:20+03:00 chore: Add lammps dependency`
- Entrypoints: none

#### `skcomplex/base.py and skcomplex/spaces/_euclidean.py` — `REJECT_POOR_FIT`

- Function: SageMath-backed abstractions for spaces and system components
- DCM mapping: DCM EventWorld and NumPy primitives already model sport-specific shared outcomes/conservation
- Decision/risk: No validated mapping from classical mechanics/Euclidean geometry to game outcomes; heavyweight/incompatible runtime with no benchmarked numerical advantage.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/test_classical_mechanics.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

#### `skcomplex/physics/_classical_mechanics.py` — `REJECT_POOR_FIT`

- Function: Point-particle forces, potentials and classical mechanics simulation
- DCM mapping: No coherent DCM consumer; sport EventWorld is probability/conservation based
- Decision/risk: Would model unrelated physical phenomena. SageMath/LAMMPS not added to canonical runtime.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: `tests/test_classical_mechanics.py`; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

### copier-modern-python

- License: MIT (root LICENSE)
- Rights: `CLEAR_FOR_REVIEW; TEMPLATE ONLY; NO GENERATION OR COPIED CODE`
- Runtime/dependencies: Copier template; supports UV/PDM, Nox, pytest, Ruff, mypy, dependency/security and docs configuration; no DCM runtime package
- README SHA-256: `bc6636254c3833210a60aa6cb652113d2aaf65f1aa0ca1431307501cacbe9a24`; pyproject SHA-256: `4171269fd01f3619a6171134c759ed922875ea0babc5b3323dd049339636fd6a`; LICENSE SHA-256: `95fdd0ccab793ad40dbe22b90b97c91077e47301746b8c27f26dcde6e7b94ab7`
- Current release tags seen: 2.0.2; latest commit: `2026-10-11T22:09:12+03:00 docs: Update changelog for version 2.0.2`
- Entrypoints: none

#### `project template, pyproject.toml, noxfile.py, CI and pre-commit templates` — `ALREADY_PRESENT_VERIFIED`

- Function: Modern Python packaging, local test/check recipes, type/lint/security checks and CI patterns
- DCM mapping: Existing DCM uv workflow, pytest, protected python-dcm CI, policy validator, inventory generator, AGENTS and canonical package
- Decision/risk: Inspected as engineering pattern. No missing guardrail justified a tool/config change; no Copier run or destructive layout regeneration.
- Producer → consumer: No donor producer wired into canonical src/dcm → No donor consumer wired; mapped equivalent or absent consumer stated above
- Source hashes: none
- Tests: ; INSPECTED_ONLY; donor code/tests not executed or installed
- Benchmark: `NOT_RUN_NOT_ADOPTED`; config/model parameters: none; copied code: none

## Acceptance trials

- **sports-betting** — Compare TimeSeriesSplit date ordering with DCM chronological_folds and same-event exclusion; inspect donor feature/odds temporal leakage tests and execution APIs. **DONOR_INSPECTED; DCM regression test added for event disjointness; donor tests not executed.**
- **imbalanced-learn-extra** — Rights-gate three conflicting license signals; assert no runtime dependency or import; do not sample without event/role/season boundaries and untouched folds. **BLOCKED_RIGHTS; exclusion path enforced by audit test; no oversampler executed.**
- **scikit-ai** — Inspect authorized vs denied research-classification boundary; reject remote classifier absent explicit authorized inputs and a verified DCM consumer. **REJECT_DUPLICATE/POOR_FIT; exclusion path enforced by audit test; no remote inference.**
- **scikit-complexity** — Compare its SageMath/LAMMPS physical system against sport EventWorld; require coherent observable and numerical parity/benefit before adoption. **REJECT_POOR_FIT/BLOCKED_DEPENDENCY; exclusion path enforced by audit test; no simulation claimed.**
- **copier-modern-python** — Safe-diff check existing uv/pytest/Ruff/policy/inventory/protected CI; no Copier regeneration or package-layout mutation. **ALREADY_PRESENT_VERIFIED; exclusion/no-layout-change path enforced by audit test.**

## Cross-cutting result

- Five upstream `main` trees were shallow-cloned at the listed SHAs and their README, project metadata, license, source modules, tests, workflows, branches and tags were inventoried. External code/tests were not installed or executed.
- The sports-betting model-selection and data-leakage code is useful as a review comparator. Its ordinary `TimeSeriesSplit` does not by itself establish event-group disjointness, label-availability-at-cutoff, exact DCM offer provenance or payout semantics. DCM already has its own chronological/evidence splitters; one event-disjointness gap was fixed in the canonical walk-forward path.
- No GeometricSMOTE/CLOVER code was copied. The LICENSE file is Apache-2.0; pyproject metadata says MIT; `geometric_smote.py` carries a BSD-3-Clause header. Rights remain unresolved.
- scikit-ai code inspected is a remote OpenAI-backed classifier and base RL interface; neither can establish sporting facts or replace DCM acquisition/evidence controls. No remote inference was run.
- scikit-complexity code uses SageMath in its abstract base/physics/spaces layers and declares LAMMPS; no sport-native simulation was found or benchmarked.
- Copier is a template. Current DCM already has a uv-driven, protected `python-dcm` workflow, pytest, policy checks, static inventory and one `src/dcm` package. No generator/config rewrite was justified.
- DCM runtime dependency set unchanged (`numpy` required; no donor libraries added). Seven capability gates, `LR000000`, predictive claim `NONE`, and production certification gates remain unchanged.

## Required blockers and resume

- The user-provided 10/13 image-only PDF contains a submitted six-selection entry and completed event result showing 3/6 hits and a Loss. It supplies realized outcomes only: there is no DCM frozen probability packet, timezone-qualified cutoff, or complete canonical feature/offer lineage. The 10/14 image-only pages do not provide a DCM forecast-to-settlement packet. PDF creation metadata is treated as export time, not a forecast cutoff.
- imbalanced-learn-extra has unresolved license conflict (Apache-2.0 LICENSE, MIT pyproject, BSD-3-Clause source header); do not copy or install.
- No qualifying event-disjoint settled DCM labels for a rare-event oversampling challenger.
- No authorized external LLM classifier inference or third-party text transfer.
- scikit-complexity targets Python 3.12 only and imports SageMath; no coherent sport-specific benchmark target.

Machine-readable, source-hashed component ledger: `EXTERNAL_DONOR_FIVE_REPO_MATRIX.json`. The manifest records exact upstream path hashes and distinguishes inspected donor tests from DCM tests actually executed. No raw betting data, HAR, account material, private fantasy content, or copied donor source is included.

## Canonical DCM update and acceptance

- Added `ALG-ML-TIME-009` for the DCM-native event-disjoint chronological walk-forward splitter. Settled rows retain `eventId`; the splitter uses only labels available before the test cutoff and excludes earlier rows from an event currently being tested. If `eventId` is missing, it returns `BLOCKED_MISSING_EVENT_ID` rather than claiming an event-disjoint evaluation.
- Runtime consumer path: `dcm.learning.dataset.build_dataset` → `dcm.learning.walkforward.chronological_folds` → `dcm.learning.walkforward.run_walkforward`. Reports identify the algorithm ID and record its execution/block state and input hash.
- Focused validation passed: `uv run --extra dev pytest -q tests/test_p6_learning.py tests/test_external_donor_decisions.py tests/test_advanced_modeling_execution.py` (29 tests, including UTC-offset chronology), `python scripts/export_algorithm_registry.py --check`, `python scripts/build_code_inventory.py --check`, and `python scripts/validate_dcm_policy.py`. The full post-change suite passed (exit code 0); CI is pending.
- Synthetic implementation benchmark: 5,000 rows, 50 cutoffs, 49 event-disjoint folds, 1.263140 s wall time; this measures fold construction only and makes no predictive-performance claim.
- The seven-gate empty-input audit receipt is `docs/audits/20261014_five_repo_empty_input_seven_gate_receipt.json` (`RUN_FIVE_REPO_AUDIT_20261014`). It evaluates all seven capabilities with no forecasts or portfolio; full modeling execution is false. KDE is not applicable; SVD and Monte Carlo are blocked by missing data; calibration is readiness-only; portfolio correlation is not applicable; payout EV is blocked by the missing canonical entry contract. The receipt has `LR000000`, predictive claim `NONE`, and no production certification. It does not consume the user screenshots.
- No seven-capability mathematical implementation was replaced. The change strengthens chronological validation only; it does not certify calibration or create forecast probabilities.

## User-provided source evidence

- The 10/13 attachment contains a submitted six-selection entry and completed event screen. It establishes one realized entry result (3/6; Loss) for audit only. It is not evidence of DCM forecast probabilities or model skill. The displayed placement time is local and no timezone is established.
- The 10/14 attachment is image-only research/board material in the inspected content; it does not provide a canonical DCM forecast packet with verified feature timestamps, offer authority, and settlement lineage.
- Raw screenshots, OCR text, account identifiers, platform account data, event/team identifiers, individual selections, and stake amounts remain in local quarantine and are not committed.

## Cross-project fantasy source access

- **Fantasy Football:** Drive folder metadata was visible, but the connector marked source visibility `not_shared`; no roster, waiver, or outcome contents were read. No other-project chat search capability was available.
- **Fantasy Basketball:** the accessible starter validation manifest says it contains no NBA folders or league data. It provides no roster, waiver, or outcome evidence.
- **Project chats:** other project chat transcripts were not exposed by a supported connector in this session. They were not assumed or used as evidence.
