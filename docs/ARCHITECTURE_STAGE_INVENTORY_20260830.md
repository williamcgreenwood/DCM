# DCM ML-architecture stage inventory — 2026-08-30

Canonical line: `origin/feat/e2e-0830-python` @ `04742d5` (PR #9), stacked on PR #5 `263c6f4` + #6 `63f5f5a` + #7 `8bd9526` + #8 `505d38e`.
Do **not** use `main` (`d68fa772`, stale). V1 hash remains `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`. LR000000 / predictive NONE.

Statuses: COMPLETE | PARTIAL | STUB | MISSING | INCORRECT | OBSOLETE.

Audit pack `audit/runs/RUN_60612c8a7bcf7df1` is a **regression fixture, not a gold standard**. It proves the Python freeze pathway and split cert flags, but the Bonner PLAYABLE card is INCORRECT (PLAYER_STATUS_UNCERTAIN + event already started). Do not delete the pack.

`locksCertified` is a **retired derived alias only**. Primary flags are the split set (`modelRunCertified`, `selectionCertified`, `evidenceCoverageCertified`, plus archive/temporal/root/predictive). Alias is true only if modelRunCertified AND selectionCertified AND evidenceCoverageCertified.

| Stage | Status | Evidence |
| --- | --- | --- |
| HAR | COMPLETE | `dcm/ingest/har.py` + `dcm/ingest/prizepicks.py`; sanitized live HAR fixtures; PR #4/#5. |
| board extraction | COMPLETE | `dcm/ingest/board.py` `freeze_board` / `BOARD_JSON_V2_ASOF_2026-08-28`; `eventStartTime` from PrizePicks `start_time`. |
| accounting | COMPLETE | `accounting_from_rows` + `dcm/research/classify.py` `accounting_classify`; test_e2e_runner accounts every row. |
| identity | PARTIAL | `dcm/identity/resolve.py` freezes HAR `new_player` ids; `identities/map.json`; no full player-index packet. |
| PlayerOfferSets | MISSING | Props exist as board rows / OFFER claims; no named `PlayerOfferSet` abstraction grouping a player's markets. |
| research population | PARTIAL | `classify_rows` + `plan_research` + `host_research_plan.json` (PR #5 classify-before-research). Not a reusable full-season packet. |
| EntityGraph | PARTIAL | `host_plan.py` emits `entityGraph` dict (`test_research_efficiency.py`); not a first-class graph type. |
| source research | PARTIAL | File/Bundle/Fixture providers + `authority.py` SourceAuthorityRegistry; live fetch is host-driven, not automatic. |
| normalized stats | PARTIAL | PR #7 `dcm/research/gamelog.py` basketball aliases (MP/TRB→minutes/reb) COMPLETE for basketball; other sports alias coverage incomplete. |
| EvidenceGraph | PARTIAL | `claims` + conflict ledger + `coverage.py` + jsonl transport (`evidence_bundle.jsonl`); `evidence_graph_hash` in lineage schema; **no first-class graph object / `evidence_graph.json`**. |
| FeatureStore | MISSING | `IndexedStore` sqlite is append-only run records, not a cutoff-safe feature store. |
| Role / availability | STUB | `dcm/research/role_epoch.py` `RoleEpochBuilder.stub` ("Partitions only when starter/bench/teammate-out claims exist"). Availability is a status string on the snapshot. |
| ParameterSnapshots | PARTIAL | `dcm/model/parameters.py` five scopes + `parameters/snapshots.json`; opportunity vs efficiency split (PR #7); role-epoch constructor is stub. |
| Joint EventWorld | PARTIAL | Shared `generate_event_contexts` (`worlds.py`); player worlds still independent. Joint **team minute conservation** MISSING. Quarter worlds MISSING. |
| PrimitiveStatLedger | PARTIAL | `contracts/schemas.py` + football `ledger.py` + basketball `minimal.py`; runner MC path uses dict worlds, not always the ledger. |
| market derivation | PARTIAL | `value_from_stats` composites from one world; PRA/PR/PA/RA identities in basketball conservation. Not all markets share one joint ledger. |
| distributions | COMPLETE | `dcm/model/distributions.py` `from_worlds`: P(Higher)+P(Lower)+P(Push)=1. |
| More / Less / Push | COMPLETE | Runner evaluates both offered sides independently; missing sides fail closed (`OFFERED_SIDE_UNKNOWN`). |
| uncertainty | PARTIAL | `dcm/model/uncertainty.py` probability_bundle (epistemic/aleatoric/reliability/false-sign). Not fully separated from ranking score. |
| calibration | PARTIAL | `apply_calibration` is INACTIVE without chronological settlements; `build_challenger_cells` is shadow-only. |
| grading | COMPLETE | `dcm/model/grade.py` PLAYABLE/LEAN/PASS/TRAP; Demon demotion-only. |
| ranking | COMPLETE | `rank_candidates` always writes `top25_ranked.json` (PR #8). |
| portfolio | COMPLETE | `dcm/selection/portfolio.py` `build_card` 0–6, unique player, event/team caps, composite overlap. |
| freeze | PARTIAL | Hash-verified `freeze.json` / `frozen_forecast.json`. PR #9 freeze is proof of pathway but **INCORRECT on Bonner** (see below). |
| Top25 | COMPLETE | `top25_ranked.json` always; `top25_qualified.json` unpadded (PR #8). |
| 0–6 PLAYABLE | PARTIAL | PR #8 `modeledPlayable` / `strict_card.json` exist; **status/start hard gates were incomplete** (this P0). Production-certified layer stays empty (`V6_ROOT_OF_TRUST_MIGRATION_ACCEPTED=false`). |
| audit | PARTIAL | PR #6 `dcm/runtime/github_archive.py` split cert flags. `locksCertified` may still appear as a **derived alias**; retire misleading primary use. |
| settlement | PARTIAL | `dcm/learning/postgame.py` `settle_run` + `platform/prizepicks/settlement.py`. Not wired to every freeze automatically. |
| LearningLedger | PARTIAL | `dcm/learning/sidecar.py` append-only kinds (FrozenForecast/Settlement/Audit/PatchProposal/PromotionDecision). No full-season ledger. |
| training | MISSING | No training loop / full-season packets. |
| champion / challenger | PARTIAL | Postgame `REGISTER_SHADOW_CHALLENGER_ONLY`; no promotion path; LR never auto-advances. |
| LR | COMPLETE (locked) | `VERSION.json` + `dcm/version.py` LR000000 / predictive NONE. Not promoted. |
| portable wheel release | PARTIAL | `dcm/release.py` + `scripts/build_portable.py` + `test_release_freshness.py`. Not a published wheel of the full production stack. |
| full-season packets | MISSING | No multi-slate / season-scale research packet reuse. |
| joint team minute conservation | MISSING | WNBA≈200 / NBA≈240 team-minute conservation not enforced across players in an EventWorld. |
| quarter worlds | MISSING | Board ids 1H/2H exist on ingest; no quarter-level EventWorld. |

## Known P0 defects (PR #9 freeze)

- **Bonner INCORRECT:** `strict_card.json` of `RUN_60612c8a7bcf7df1` lists DeWanna Bonner pts 6.5 MORE as `grade=PLAYABLE`, `modeledPlayable=true`, `blocker=PLAYER_STATUS_UNCERTAIN`, `ROLE:ATL:questionable`, event MIN @ ATL, freeze cutoff `2026-08-30T19:43:12Z`. Status-uncertain + started event must not land on the modeled card.
- **Cause:** `is_modeled_playable` ignored `PLAYER_STATUS_UNCERTAIN` / OUT / eventStartTime vs cutoff. ParameterSnapshot already set the blocker (`parameters.py`) but the selection path did not honor it for modeled PLAYABLE.
- **Archive flags PARTIAL:** split flags exist; `locksCertified` remains a derived alias for old readers (`github_archive.compute_certification`).

## Out of scope for this P0

FeatureStore, first-class EvidenceGraph, PlayerOfferSets, RoleEpochBuilder production constructor, joint minute conservation, quarter worlds, champion promotion, LR advance, V1 hash rewrite, merge to main.
