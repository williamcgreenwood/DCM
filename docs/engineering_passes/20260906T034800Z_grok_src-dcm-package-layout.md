# Engineering Pass: src/dcm package layout relocate

- **Pass ID:** `20260906T034800Z_grok_src-dcm-package-layout`
- **Starting branch/SHA:** `refactor/src-dcm-package-layout` off `main` @ `b0e44d5886adb98cb84dbf466ee3a3fc1fee28b1` (PR #34 merged)
- **Objective:** behavior-preserving relocate of the installable production Python package from `artifacts/dcm_v6_workstream_ab` to `src/dcm`, without changing RNG/model/accel/probability/sport logic.

## Layout

- TypeScript operator UI moved `src/` → `web/src` (Vite/TanStack `srcDirectory: web/src`, `@/*` → `web/src/*`).
- Python package: `artifacts/dcm_v6_workstream_ab/dcm` → `src/dcm` (keeps `research/`).
- Compat package: `pillars_dcm` → `src/pillars_dcm`.
- Tests: `artifacts/dcm_v6_workstream_ab/tests` → top-level `tests/` (alongside existing `tests/governance`).
- `artifacts/dcm_v6_workstream_ab` remains a historical archive for fixtures/docs/configs/schemas; `ARCHIVE_NOTE.md` records that it is **not** the install root.
- `pyproject.toml`: `[tool.setuptools.packages.find] where = ["src"]`; pytest `testpaths = ["tests"]`, `pythonpath = ["src"]`.
- Added `dcm.paths` helpers (`repo_root`, `archive_root`, `default_workspace`) so fixture/config resolution stays behavior-preserving after the depth change.
- Inventory generator `PKG_ROOT` now points at `src`.

## Validation

- `pip install -e '.[dev]'` → import path `.../src/dcm/__init__.py`
- CLI help / doctor / synthetic smoke / full pytest green under CI world caps
- Algorithm registry check, policy validate, inventory `--check`, benchmark smoke green
- Did **not** commit `MOUNT_STATE.json`

## Honest state

- No RNG/model/accel/probability/sport behavior changes intended.
- Inventory module/symbol counts drop vs prior workstream-wide scan because tests/archive Python are no longer under `PKG_ROOT` (now `src` only).
- Learning remains `LR000000`; predictive claim `NONE`; no production-root certification.
