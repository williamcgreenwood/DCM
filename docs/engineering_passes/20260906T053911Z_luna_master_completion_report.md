# Engineering pass — Luna master completion (Phase 18)

- Pass id: `20260906T053911Z_luna_master_completion_report`
- Branch: `docs/algo-constitution-lock-completion-20260906`
- Base: `main` @ `e51d4ae1f0c3057c4f0431547c5cc869c3669332` (PR #42 Phase 15 synthetic E2E)
- Agent: grok
- Scope: Permanent Algorithmic Constitution consumption lock + honest Phase 18 completion matrix
- No HAR commit. No fake 10/10. No predictive claims.

## What landed

1. **`docs/engineering/ALGORITHM_CONSUMPTION_LAW.md`** — permanent hot-path order:
   exact-first BoardStore/BoardIndexes → cached facts → CELF/set-cover → true DAG
   descendants → two-rep (audit/SoA) → NumPy EventWorld default (C ABI after measured win)
   → ML/grouping/appending via registered constitution IDs only.
2. **AGENTS.md** + **CONSTITUTION_INHERITANCE.md** inherit the consumption lock.
3. **CI/governance**: `tests/governance/test_algorithm_constitution.py::test_algorithm_consumption_law_lock`
   + `scripts/validate_dcm_policy.py` require the law surface and known hot-path modules.
4. **Phase 13 leftover**: `dcm.selection.portfolio` selection-correlation uses NumPy when
   available, with pure-Python reference fallback (parity-tested).

## Main SHA and PR spine (#34–#42)

| PR | Merge SHA | Title |
|---:|---|---|
| #34 | `b0e44d5886adb98cb84dbf466ee3a3fc1fee28b1` | Close CFB source-aware host observation import loop |
| #35 | `c01724382f478ddb4221a098e37e98f55fcd9ffe` | Relocate production package to `src/dcm` |
| #36 | `3ab948a3abd84e51387715b9f5e2921827d7ba94` | Canonical requirement ledger v1 |
| #37 | `1fe6d21721cbc85fa54c77d06b3c4c6d38a0ad46` | Close Research OS loop (AcquisitionActionGraph + CELF) |
| #38 | `8fdd520c388bebcb6090fe1742a6d1d52d18e254` | True descendant DAG invalidation |
| #39 | `86dcd6065f32ac53c5ae552d919eb5f4dc854b4c` | BoardStore SoA + compact Feature/Parameter matrices |
| #40 | `a3e28fb82cabbecc69e70cff92c36c8db938a6f1` | Phase 9 baseline profiler |
| #41 | `2b021217a006847a6d79d27d77d571509f6065c4` | Phase 11 NumPy EventWorld (~2×, rng v1 parity) |
| #42 | `e51d4ae1f0c3057c4f0431547c5cc869c3669332` | Phase 15 CFB synthetic E2E (PATH_A/B/C) |

Verified live `main` HEAD before this branch: `e51d4ae1f0c3057c4f0431547c5cc869c3669332`.

## Honest completion matrix (Phase 18)

| Field | Status | Evidence |
|---|---|---|
| ENGINEERING_INTEGRATED | **PASS** | PRs #34–#42 merged to `main`; BoardStore, DAG, CELF closed-loop, NumPy EventWorld, synthetic E2E on declared CFB offline scope |
| CFB_OPERATIONAL | **PARTIAL** | Synthetic PATH_A/B/C green; live/current pregame HAR card remains EXTERNAL |
| RECOMMENDATION_ELIGIBLE | **DEFERRED** | No production-selectable live card; fixture/synthetic never production |
| HOST_PERFORMANCE_CERTIFIED | **FAIL** | `hostPerformanceCertified=false`; NumPy EventWorld ~2× on synthetic only; C ABI not earned |
| RECOVERY_CERTIFIED | **PARTIAL** | CFB-dominant capture recovery + metadata recovery merged (#30/#31); not live-ops certified |
| PREDICTIVE_CERTIFIED | **DEFERRED** | `predictiveClaim=NONE`; learning revision `LR000000` |
| UNIVERSAL_SPORT_COMPLETE | **FAIL** | CFB software path only; P10 full-sport coverage remains EARLY |

## HAR aggregates (no secrets / no raw bytes)

From `docs/PROGRAM_STATUS.json` `latestHarAccounting` (quarantined accounting only):

- sourceName: `CFB0905260254pst(3).har`
- sha256: `64a4929db9fc9209a6a65cc23bcd3db8b07e0a6bf138787e6792ce1b48281111`
- entries: 33; normalizedRows: 3886; cfbRows: 3886
- cfbGoblinRows: 855; cfbModelEligibleRows: 250; cfbMissingSideRows: 2745; cfbUnsupportedRows: 343
- cfbEvents: 35; cfbSubjects: 726; cfbTeams: 80
- rawCommitted: false; rawUploaded: false

## Research / E2E status

- Research OS closed-loop + CELF reschedule: merged (#37)
- Source-aware import: merged (#34)
- Synthetic E2E: PATH_A freeze with ≥1 PLAYABLE; PATH_B incomplete/conflicted abstention; PATH_C aggregates-only (#42)
- Top100 / portfolio: known only on **synthetic** PATH_A (portfolio 0–6; never pad). No live Top100 claim.
- Freeze: synthetic PATH_A reaches `FROZEN`; live freeze remains EXTERNAL pending fresh pregame HAR + host evidence

## Remaining requirements (software next)

1. Fresh **pregame** (not live/started) CFB HAR + host-acquired evidence → operational card path
2. Keep constitution consumption lock green; no silent algorithm retirement
3. Mixed-sport R1 remainder after CFB live acceptance
4. Host-performance certification only after measured real-evidence SLOs
5. Prospective settlements before any LR / predictive promotion

## External blockers

- Current live/stale HAR (`liveOrStarted>0`) cannot produce a production card
- Host-acquired permitted evidence for remaining research requests
- Drive credentials / licensed providers as optional capabilities
- Prospective chronological settlements for calibration / LR promotion
- Exact v5.4.1 production-root certification remains independently gated (`false`)

## Exact resume command (fresh pregame HAR → evidence-import)

```bash
# From an editable install of this repo (PYTHONPATH=src or `pip install -e .`):
# Place a FRESH PREGAME CFB HAR outside git (never commit raw HAR).

python -m dcm.chat doctor
python -m dcm.chat prepare \
  --har /path/to/FRESH_PREGAME_CFB.har \
  --run-root /path/to/runs \
  --cutoff-from-capture

# Note runId/runDest from prepare output, then:
python -m dcm.chat next-research --run /path/to/runs/<runId>
# Host performs EVENT/TEAM-first web research (not one-search-per-prop),
# writes host_observations.jsonl, then:
python -m dcm.chat evidence-import --run /path/to/runs/<runId> --input host_observations.jsonl
python -m dcm.chat coverage --run /path/to/runs/<runId>
# Repeat next-research → evidence-import → coverage until modelable flags are explicit, then:
python -m dcm.chat forecast --run /path/to/runs/<runId> --research bundle
python -m dcm.chat report --run /path/to/runs/<runId>

# Equivalent first hop when using the guarded CFB launcher:
python -m dcm.chat cfb-launch \
  --har /path/to/FRESH_PREGAME_CFB.har \
  --run-root /path/to/runs \
  --cutoff-from-capture \
  --research file
```

## Explicit non-claims

- No private HAR upload or commit
- No 10/10 completion score
- No predictive superiority / LR promotion
- No host-performance certification
- No live production picks / recommendation eligibility
