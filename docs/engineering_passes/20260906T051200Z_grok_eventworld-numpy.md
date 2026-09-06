# Engineering pass — Phase 11 EventWorld NumPy acceleration

- Pass id: `20260906T051200Z_grok_eventworld-numpy`
- Branch: `perf/eventworld-numpy-20260906`
- Base: `main` @ `a3e28fb82cabbecc69e70cff92c36c8db938a6f1` (PR #40 Phase 9 baseline)
- Agent: grok
- Scope: NumPy-first CFB EventWorld accel; portable reference fallback; parity tests; benchmark delta

## What landed

1. Backend selector (`dcm.cfb.event_world_backend`): `reference` | `numpy` (default); env `DCM_EVENTWORLD_BACKEND`.
2. `simulate_joint_cfb_event_worlds_reference` + `event_worlds_numpy` SoA/team buffers; public `simulate_joint_cfb_event_worlds` / alias `simulate_cfb_event`.
3. `allocate_team_opportunity_fast` — hot path without per-world share `content_hash` (dominant Phase 9 hotspot).
4. `distributions.from_worlds` NumPy reduction + `from_worlds_reference` fallback.
5. Parity/property tests: `tests/test_eventworld_numpy_backend.py` (bitwise worlds, alloc match, env override).
6. Profiler `--backend` / `--compare-backends`; results under `docs/benchmarks/eventworld_numpy_accel_20260906.*` and `baseline_profile_eventworld_numpy_20260906.*`.

## Speedup (8 players × N worlds; rngVersion v1; hash match True)

| worlds | reference s | numpy s | speedup |
|---:|---:|---:|---:|
| 64 | 0.157 | 0.079 | ~2.0× |
| 10000 | 24.48 | 12.22 | ~2.0× |

Phase 9 committed 8×10000 reference wall was 24.66s → Phase 11 NumPy default ~12.13s on the same harness.

## RNG notes

- **No silent RNG semantic change.** Both backends consume `python.random.Random` seeded via sha256 prefix (`rngVersion=dcm.cfb.event_world.rng.v1`).
- Bitwise world-ledger parity vs reference under the same seed.
- A future alternate stream (e.g. NumPy Generator) requires an explicit version bump + statistical equivalence declaration.

## Remaining C ABI candidacy

- `sample_football` binomial/poisson loops
- Per-world dict materialization
- Only after representative real-evidence SLOs; still no mandatory compiler for correctness

## Explicit non-claims

- `hostPerformanceCertified=false`
- No HAR commit, no C++ required
- Predictive claim remains NONE / LR000000
