# Phase 9 baseline profiler

Synthetic / sanitized engineering measurements only. **Not** host-performance
certification and **not** predictive validation.

`hostPerformanceCertified` is always `false`.

## Reproducible full matrix (local / docs artifact)

```bash
python -m pip install -e ".[dev]"
python benchmarks/baseline/profile_baseline.py \
  --board-sizes 100 1000 4000 10000 \
  --world-sizes 64 128 512 2048 10000 \
  --players 8 \
  --out docs/benchmarks
```

Sizes ≥10 000 are auto-skipped when `/proc/meminfo` MemAvailable looks too low.

## CI / harness smoke (light)

```bash
python benchmarks/baseline/profile_baseline.py --smoke --out /tmp/dcm-baseline-smoke
```

CI continues to run the existing light `python -m dcm.runtime.benchmark --sizes 100 1000`
job; this baseline full matrix is intentionally **not** required on every PR.

## Outputs

- `docs/benchmarks/baseline_profile_YYYYMMDD.json`
- `docs/benchmarks/baseline_profile_YYYYMMDD.md`

## Profiled stages

1. BoardStore index build + query
2. Compact SoA / FeatureMatrix / ParameterMatrix ops
3. CFB `simulate_joint_cfb_event_worlds` distribution path
4. Synthetic LRU + Dag reuse/invalidation counters
