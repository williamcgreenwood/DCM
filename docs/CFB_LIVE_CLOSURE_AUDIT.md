# CFB Live Closure Audit — 20260906T200000Z

## Live repository truth
- Repo: `williamcgreenwood/DCM`
- Main: `a4ff32af22b274ae0429862a33063aa22d4fe2a2` (start of this closure slice: `a4ff32a`, includes merged PR #54)
- Required CI: `python-dcm` green on PR #54
- In-flight: `_merge` game_logs field-union (Flanagan overwrite)

## Run identity
- Run: `RUN_d3271703636992cc`
- HAR SHA-256: `72f75ec7ee32035b5e5863e1a61a688350b49ca6c94da091437f5368a41ec5e2`
- Cutoff: `2026-09-06T15:30:00Z`
- State: `AWAITING_FRONTIER_RESEARCH`
- Raw HAR: not disclosed / not uploaded

## Board accounting
- Raw 686 · Goblin 131 · Demon 319 · Standard 236
- Prop states: {'UNSUPPORTED': 7, 'MODELED': 238, 'HELD_FOR_RESEARCH': 69, 'UNRESOLVED': 130, 'EXCLUDED_GOBLIN': 131, 'MODELED_DIAGNOSTIC': 46}
- Rejected survivor offers: 117

## Research effects
- Batch12: 47 obs imported, 0 rejected, 13 contracts closed, 169 offers changed
- Coverage: 450/484 complete (34 incomplete)
- PLAYER_STATUS_UNKNOWN: 23 → 0

## Consumer proof
- Status claims → cleared PLAYER_STATUS_UNKNOWN across 23 subjects
- Game-log/targets imports → reduced MINIMUM_OPPORTUNITY_SUPPORT_MISSING (65→66 after Flanagan restore from 67)
- PR #54 verified on tip: kicker logs normalize; store latest preserves game_logs under status
- Flanagan: richer logs restored operationally; software fix for `_merge` list replace in flight

## Full blocker table
| reason | after | class |
|---|---:|---|
| PLAYER_STATUS_UNKNOWN | 0 | cleared |
| MINIMUM_OPPORTUNITY_SUPPORT_MISSING | 66 | recoverable primitives/logs |
| CFB_ROLE_STATE_UNCERTAIN | 44 | soft/candidate fail-closed |
| HAR_SIDE_METADATA_ABSENT | 172 | terminal |
| MATERIAL_FACT_CONFLICT | 2 | limited |

## Output
- PLAYABLE: 1 (Caden Pinnick pass_yds 180.5 MORE P≈0.796875)
- Top25: {'LEAN': 18, 'PASS': 7}
- Top100: {'LEAN': 18, 'PASS': 41, 'TRAP': 41}
- No forced card

## Opportunity gap audit
{
  "trueEvidenceMissing": 26,
  "consumerGaps": 0,
  "marketPrimitiveMissing": 40,
  "legitimateInsufficient": 0,
  "total": 66,
  "reasonCounts": {
    "MARKET_PRIMITIVE_MISSING": 40,
    "NO_GAME_LOG_EVIDENCE": 26
  }
}

## Storage / recovery
- Drive: EXTERNAL_BLOCKED
- Local checkpoint: valid

## Unearned gates
- LR000000 · predictiveClaim NONE · productionRootCertified false · hostPerformanceCertified false

## Next exact command
```bash
python -m dcm.chat next-research --run /workspace/dcm-cfb-ops/runs_kickoff/RUN_d3271703636992cc --workspace /workspace/dcm-cfb-ops/ws
```
Then acquire only cutoff-safe team/event game logs / authoritative targets for remaining MARKET_PRIMITIVE_MISSING / NO_GAME_LOG_EVIDENCE; import → forecast --research bundle. Do not research Standard missing sides; do not soften *_candidate.
