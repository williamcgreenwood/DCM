# DCM Phase 9 baseline profile

- Schema: `pillars_dcm.baseline_profile.v1`
- Captured (UTC): `2026-09-06T05:10:00Z`
- Host: `Linux-6.12.94+-x86_64-with-glibc2.41` / Python `3.13.5`
- `hostPerformanceCertified`: **False**
- Certification blocker: `SYNTHETIC_BASELINE_NOT_PRODUCTION_CERTIFICATION`

## Reproducible command

```bash
python benchmarks/baseline/profile_baseline.py --board-sizes 100 1000 4000 10000 --world-sizes 64 128 512 2048 10000 --players 8 --out docs/benchmarks --backend numpy --compare-backends
```

## BoardStore build + query

| offers | build wall s | build CPU s | peak RSS B | query wall s | sqlite B | outputHash |
|---:|---:|---:|---:|---:|---:|---|
| 100 | 0.0500 | 0.2073 | 41385984 | 0.0009 | 57344 | `b591b228c58e…` |
| 1000 | 0.1008 | 0.1008 | 46477312 | 0.0018 | 237568 | `10da7cba54c9…` |
| 4000 | 0.4273 | 0.4273 | 66260992 | 0.0032 | 843776 | `bbb1620543d3…` |
| 10000 | 1.0940 | 1.0939 | 105754624 | 0.0026 | 2084864 | `5f66b2d64bd8…` |

## Compact matrix ops

| offers | from_rows wall s | SoA line_sum s | dict line_sum s | speedup | FM pack s | PM pack s |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.0017 | 0.000458 | 0.000366 | 0.7988613961883425 | 0.0004 | 0.0015 |
| 1000 | 0.0181 | 0.000523 | 0.001755 | 3.3561842066602026 | 0.0035 | 0.0146 |
| 4000 | 0.0708 | 0.000750 | 0.006628 | 8.841232950232508 | 0.0139 | 0.0538 |
| 10000 | 0.1748 | 0.000987 | 0.020450 | 20.71718997265944 | 0.0379 | 0.1379 |

## CFB EventWorld / distribution path

- Backend: `numpy`

| worlds | players | wall s | CPU s | worlds/s | peak RSS B | outputHash |
|---:|---:|---:|---:|---:|---:|---|
| 64 | 8 | 0.0813 | 0.0813 | 787.4737045120966 | 105754624 | `946d7c56c662…` |
| 128 | 8 | 0.1503 | 0.1502 | 851.857869757435 | 105754624 | `d9daff902bbc…` |
| 512 | 8 | 0.6161 | 0.6161 | 831.012302747036 | 105754624 | `06cb14d908a3…` |
| 2048 | 8 | 2.4706 | 2.4705 | 828.9511409328536 | 105754624 | `59b3ae63c3c6…` |
| 10000 | 8 | 12.1345 | 12.1339 | 824.0986008126865 | 245764096 | `2e5261e1f200…` |

## EventWorld reference vs NumPy speedup

| worlds | players | reference s | numpy s | speedup | hash match |
|---:|---:|---:|---:|---:|---|
| 64 | 8 | 0.1569 | 0.0788 | 1.9924124368379568 | True |
| 128 | 8 | 0.3120 | 0.1549 | 2.0143467270918927 | True |
| 512 | 8 | 1.2327 | 0.6192 | 1.990800445186417 | True |
| 2048 | 8 | 4.9893 | 2.4849 | 2.007862406359602 | True |
| 10000 | 8 | 24.4823 | 12.2159 | 2.004132791143337 | True |

- Notes: Same seed + rngVersion v1; NumPy backend skips per-world share content_hash while preserving bitwise world ledgers.
- rngVersion: `dcm.cfb.event_world.rng.v1`

## Cache / DAG counters (synthetic)

- LRU hits=94 misses=26; reusedNodes 120→116; invalidated=4

## Top hotspots for Phase 11 EventWorld accel

### 1. `CFB_EVENTWORLD_JOINT_SAMPLE`

- Module: `dcm.cfb.event_worlds.simulate_joint_cfb_event_worlds`
- Evidence: simulate_joint_cfb_event_worlds players=8 worlds=10000: wall=12.1345s cpu=12.1339s (824.1 worlds/s)
- Recommendation: Phase 11: NumPy-vectorize team play / residual allocation and per-player sample_football draws first; C ABI challenger only after a measured NumPy win on the same synthetic matrix.

### 2. `BOARDSTORE_BUILD_INDEXES`

- Module: `dcm.board_store.BoardStore`
- Evidence: BoardStore build n=10000: wall=1.0940s cpu=1.0939s sqliteBytes=2084864
- Recommendation: Keep SoA posting lists; avoid reintroducing per-row JSON payload. Further accel only if representative CFB boards (>4k offers) show build dominating end-to-end wall.

### 3. `COMPACT_MATRIX_PACK_AND_REDUCE`

- Module: `dcm.compact`
- Evidence: CompactNumericBoard.from_board_rows n=10000: wall=0.1748s; line_sum SoA=0.000987s vs dict=0.020450s (speedup=20.71718997265944)
- Recommendation: Prefer CompactNumericBoard / FeatureMatrix on numerical hot paths; audit boundary conversion only at I/O edges.

## Skipped sizes

```json
{
  "board": [],
  "world": []
}
```

## Notes

- Synthetic/sanitized loads only — not production certification.
- No HAR bytes committed. No mandatory C++ / native extension in this phase.
- EventWorld NumPy backend keeps rngVersion v1 (no silent RNG semantic change).
- Deterministic `outputHash` values use `content_hash` over stage fingerprints.
