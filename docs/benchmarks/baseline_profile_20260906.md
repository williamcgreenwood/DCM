# DCM Phase 9 baseline profile

- Schema: `pillars_dcm.baseline_profile.v1`
- Captured (UTC): `2026-09-06T04:53:24Z`
- Host: `Linux-6.12.94+-x86_64-with-glibc2.41` / Python `3.13.5`
- `hostPerformanceCertified`: **False**
- Certification blocker: `SYNTHETIC_BASELINE_NOT_PRODUCTION_CERTIFICATION`

## Reproducible command

```bash
python benchmarks/baseline/profile_baseline.py --board-sizes 100 1000 4000 10000 --world-sizes 64 128 512 2048 10000 --players 8 --out docs/benchmarks
```

## BoardStore build + query

| offers | build wall s | build CPU s | peak RSS B | query wall s | sqlite B | outputHash |
|---:|---:|---:|---:|---:|---:|---|
| 100 | 0.0464 | 0.2547 | 41152512 | 0.0008 | 57344 | `b591b228c58e…` |
| 1000 | 0.1083 | 0.1083 | 46284800 | 0.0019 | 237568 | `10da7cba54c9…` |
| 4000 | 0.4328 | 0.4328 | 65888256 | 0.0029 | 843776 | `bbb1620543d3…` |
| 10000 | 1.1117 | 1.1116 | 105463808 | 0.0027 | 2084864 | `5f66b2d64bd8…` |

## Compact matrix ops

| offers | from_rows wall s | SoA line_sum s | dict line_sum s | speedup | FM pack s | PM pack s |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.0019 | 0.000426 | 0.000362 | 0.84924477268572 | 0.0004 | 0.0015 |
| 1000 | 0.0173 | 0.000507 | 0.001900 | 3.747081074986492 | 0.0034 | 0.0145 |
| 4000 | 0.0727 | 0.000721 | 0.007702 | 10.683629932256633 | 0.0153 | 0.0584 |
| 10000 | 0.1874 | 0.001082 | 0.021859 | 20.197722976072853 | 0.0360 | 0.1496 |

## CFB EventWorld / distribution path

| worlds | players | wall s | CPU s | worlds/s | peak RSS B | outputHash |
|---:|---:|---:|---:|---:|---:|---|
| 64 | 8 | 0.1604 | 0.1604 | 398.8914980097179 | 105463808 | `01516a19fc3a…` |
| 128 | 8 | 0.3306 | 0.3306 | 387.1385274569074 | 105463808 | `90a5283afe46…` |
| 512 | 8 | 1.3319 | 1.3318 | 384.4249611212741 | 105463808 | `67bea661ba7f…` |
| 2048 | 8 | 5.0194 | 5.0190 | 408.01780584994253 | 105463808 | `2a59e0730bb0…` |
| 10000 | 8 | 24.6643 | 24.6611 | 405.4445511101871 | 230580224 | `ad168048a095…` |

## Cache / DAG counters (synthetic)

- LRU hits=94 misses=26; reusedNodes 120→116; invalidated=4

## Top hotspots for Phase 11 EventWorld accel

### 1. `CFB_EVENTWORLD_JOINT_SAMPLE`

- Module: `dcm.cfb.event_worlds.simulate_joint_cfb_event_worlds`
- Evidence: simulate_joint_cfb_event_worlds players=8 worlds=10000: wall=24.6643s cpu=24.6611s (405.4 worlds/s)
- Recommendation: Phase 11: NumPy-vectorize team play / residual allocation and per-player sample_football draws first; C ABI challenger only after a measured NumPy win on the same synthetic matrix.

### 2. `BOARDSTORE_BUILD_INDEXES`

- Module: `dcm.board_store.BoardStore`
- Evidence: BoardStore build n=10000: wall=1.1117s cpu=1.1116s sqliteBytes=2084864
- Recommendation: Keep SoA posting lists; avoid reintroducing per-row JSON payload. Further accel only if representative CFB boards (>4k offers) show build dominating end-to-end wall.

### 3. `COMPACT_MATRIX_PACK_AND_REDUCE`

- Module: `dcm.compact`
- Evidence: CompactNumericBoard.from_board_rows n=10000: wall=0.1874s; line_sum SoA=0.001082s vs dict=0.021859s (speedup=20.197722976072853)
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
- No HAR bytes committed. No C++ / native extension in this phase.
- Deterministic `outputHash` values use `content_hash` over stage fingerprints.
