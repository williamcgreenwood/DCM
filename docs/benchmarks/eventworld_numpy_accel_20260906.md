# Phase 11 — CFB EventWorld NumPy acceleration

- Captured (UTC): 2026-09-06T05:10:00Z
- Branch: `perf/eventworld-numpy-20260906`
- Base main: `a3e28fb82cabbecc69e70cff92c36c8db938a6f1` (PR #40 Phase 9 baseline)
- `hostPerformanceCertified`: **false** (synthetic only; no predictive claim)
- `rngVersion`: `dcm.cfb.event_world.rng.v1` (unchanged stream; no silent RNG semantic change)

## Before / after (8 players, same seed)

Phase 9 committed reference baseline vs Phase 11 NumPy default (profiler with tracemalloc):

| worlds | Phase 9 reference wall s | Phase 11 NumPy wall s | speedup | outputHash match |
|---:|---:|---:|---:|---|
| 64 | 0.1604 | 0.0813 | ~1.97× | yes (backend compare) |
| 128 | 0.3306 | 0.1503 | ~2.20× | yes |
| 512 | 1.3319 | 0.6161 | ~2.16× | yes |
| 2048 | 5.0194 | 2.4706 | ~2.03× | yes |
| 10000 | **24.6643** | **12.1345** | **~2.03×** | yes |

Same-run reference vs NumPy compare (this host, `--compare-backends`):

| worlds | reference s | numpy s | speedup | hash match |
|---:|---:|---:|---:|---|
| 64 | 0.1569 | 0.0788 | 1.99× | True |
| 128 | 0.3120 | 0.1549 | 2.01× | True |
| 512 | 1.2327 | 0.6192 | 1.99× | True |
| 2048 | 4.9893 | 2.4849 | 2.01× | True |
| 10000 | 24.4823 | 12.2159 | 2.00× | True |

Full JSON/MD: `docs/benchmarks/baseline_profile_eventworld_numpy_20260906.{json,md}`.

## What changed

- Backend selector: `reference` (mandatory portable Python) → `numpy` (default when available)
- Env: `DCM_EVENTWORLD_BACKEND=reference|numpy`
- Fast opportunity allocation skips per-world `content_hash` share audit bodies (dominant hotspot)
- Contiguous NumPy SoA buffers for team plays / residuals / opportunity + hot ledger fields
- Public API: `simulate_joint_cfb_event_worlds` / alias `simulate_cfb_event` unchanged conceptually
- `distributions.from_worlds` NumPy path with pure-Python fallback

## Remaining C ABI candidacy (not done this phase)

1. `sample_football` per-trial binomial / poisson loops (~20%+ of post-NumPy wall)
2. Per-world Python dict materialization of ledgers
3. Optional native challenger only after measured NumPy win on representative (non-synthetic) loads

## Explicit non-claims

- No HAR commit
- No mandatory C++ / compiler requirement for correctness
- `hostPerformanceCertified=false`
- Predictive claim remains `NONE` / LR000000
