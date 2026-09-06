# Engineering pass — Phase 9 baseline profiling

- Pass id: `20260906T045500Z_grok_baseline-profile`
- Branch: `perf/baseline-profile-20260906`
- Base: `main` @ `86dcd6065f32ac53c5ae552d919eb5f4dc854b4c` (PR #39 Compact SoA)
- Agent: grok
- Scope: measured synthetic baseline BEFORE native/C++ EventWorld accel

## What landed

1. `benchmarks/baseline/profile_baseline.py` — stage profiler (BoardStore build/query, compact SoA/matrix ops, CFB `simulate_joint_cfb_event_worlds`, LRU+Dag counters).
2. Results: `docs/benchmarks/baseline_profile_20260906.{json,md}` (also copyable under `artifacts/benchmarks/`).
3. Harness smoke: `tests/test_baseline_profile_harness.py` + `--smoke` CLI mode.
4. CI: light `--smoke` only; full board/world matrix remains local/docs artifact.

## Key timings (synthetic host; hostPerformanceCertified=false)

| Stage | Size | Wall s |
|---|---|---:|
| CFB EventWorld joint | 8 players × 10000 worlds | **24.66** |
| CFB EventWorld joint | 8 × 2048 | 5.02 |
| BoardStore build | 10000 offers | 1.11 |
| Compact from_rows | 10000 offers | 0.19 |
| SoA vs dict line_sum | 10000 (×50 iters) | ~20× SoA win |

## Top Phase 11 accel targets (evidence-ranked)

1. **CFB EventWorld joint sample** (`dcm.cfb.event_worlds.simulate_joint_cfb_event_worlds`) — dominates wall (~405 worlds/s @ 8 players). NumPy-vectorize team plays / residual allocation + `sample_football` draws first; C ABI later.
2. **BoardStore build** — secondary at 10k offers (~1.1s); keep SoA, no payload JSON.
3. **Compact matrix pack** — already strong SoA reductions; wire as primary numerical path where producers are already numeric.

## Explicit non-claims

- `hostPerformanceCertified=false` (still)
- No HAR commit, no C++, no RNG/forecast semantic changes
- Synthetic loads only — not production certification

## Repro

```bash
python benchmarks/baseline/profile_baseline.py \
  --board-sizes 100 1000 4000 10000 \
  --world-sizes 64 128 512 2048 10000 \
  --players 8 \
  --out docs/benchmarks
```
