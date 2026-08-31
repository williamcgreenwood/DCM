# DCM ML-architecture stage inventory — 2026-08-30

Canonical line: `integration/v6-ml-architecture-20260830` (PR #10), stacked on PR #5 `263c6f4` + #6 `63f5f5a` + #7 `8bd9526` + #8 `505d38e` + #9 `04742d5`.
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
| PlayerOfferSets | COMPLETE | `dcm/research/player_offer_set.py` groups by playerId+eventId; runner writes `player_offer_sets.json`; Paige-style N markets → 1 set. |
| research population | COMPLETE | `dcm/research/population.py` `ResearchPopulationManifest` (eligible events/teams/players/market_definitions/offers, dependentOfferCount, fan-out priority). Account/classify path always emits `research_population_manifest.json`. |
| EntityGraph | PARTIAL | `host_plan.py` emits `entityGraph` dict (`test_research_efficiency.py`); not a first-class graph type. |
| source research | PARTIAL | File/Bundle/Fixture providers + `authority.py`; basketball SourceAdapters (`BasketballReferenceGameLogAdapter`, `BasketballReferencePlayerAdapter`, `PrizePicksOfferAdapter`). Live fetch opt-in (`DCM_LIVE_FETCH`); CI uses HTML fixtures. Other sports adapters still missing. |
| normalized stats | PARTIAL | PR #7 `dcm/research/gamelog.py` basketball aliases (MP/TRB→minutes/reb) COMPLETE for basketball; other sports alias coverage incomplete. |
| EvidenceGraph | COMPLETE | First-class `dcm/research/evidence_graph.py` (`evidence_graph.json` + content hash). Nodes: SourceDocument/EvidenceClaim/Player/Team/Event/MarketDefinition/Offer/NormalizedStat. Edges: supports/derived_from/applies_to/conflicts_with. `trace_selection` resolves Selection→SourceDocument. jsonl remains the transport. |
| FeatureStore | COMPLETE | `dcm/ml/feature_store.py` cutoff-immutable records (entity/eventId/featureName/value/asOf/sourceHashes/transformationVersion/featureSchemaVersion, family in ROLE/OPPORTUNITY/EFFICIENCY/MATCHUP/CONTEXT). Runner writes `feature_store.jsonl` + `feature_store_manifest.json`; L3/L5/L10/L15/L20/season means from the full log. Observations only — no trained-model claim. |
| Role / availability | COMPLETE | `dcm/research/role_epoch.py` `RoleEpochBuilder.v2-20260830` (not a stub): GS/starter flags, minutes change-points, teammate-out epochs, role-comparable sample, hierarchical shrinkage weights. Availability remains a status string on the snapshot. |
| ParameterSnapshots | PARTIAL | `dcm/model/parameters.py` five scopes + `parameters/snapshots.json`; opportunity vs efficiency split (PR #7). Basketball path calls `RoleEpochBuilder` + `OpportunityModel`/`EfficiencyModel`; comparable_logs drive minutes/fga/tpa/fta/reb/ast; shrinkage weights (`roleWeight`/`playerWeight`/`priorWeight`) on the snapshot. Thin role support (`support_n` < 3) does not set `evidenceUsed`. Joint minute conservation is wired when ≥2 teammates share an event (see Joint EventWorld). |
| Joint EventWorld | PARTIAL/COMPLETE | `dcm/model/event_world_joint.py`: ≥2 modeled teammates share one EventWorld. WNBA team minutes target 200 / NBA 240 via proportional rescale then residual-adjust (unmodeled residual pool when <5 modeled). Team FGA Dirichlet residual allocation (negative correlation). Single-player path unchanged. Discrete regimes / all-sports joint still PARTIAL. |
| PrimitiveStatLedger | PARTIAL/COMPLETE | Basketball MC worlds write a PrimitiveStatLedger dict (`as_primitive_ledger`: minutes, fgm/fga, tpm/three_pm, tpa/three_pa, twopm/twopa, ftm/fta, oreb/dreb/reb, ast, stl, blk, tov, pf, pts). Identities enforced per world (`PRIMITIVE_CONSERVATION_FAILURE`). Schema dataclass still used by football/e2e lineup. |
| market derivation | PARTIAL/COMPLETE | `dcm/model/market_derive.py` versioned basketball registry (Points/Rebounds/Assists/PRA/Pts+Rebs/Pts+Asts/Rebs+Asts/3PTM/3PTA/FGM/FGA/2PM/2PA/FTM/FTA/Turnovers/OREB/Steals/Blks+Stls). `derive_market(ledger, key)` identities only; unknown → fail closed; Fantasy Score fail-closed (no PrizePicks scoring version registered). Runner `value_from_stats` wired to the registry for basketball. |
| distributions | COMPLETE | `dcm/model/distributions.py` `from_worlds`: P(Higher)+P(Lower)+P(Push)=1. |
| More / Less / Push | COMPLETE | Runner evaluates both offered sides independently; missing sides fail closed (`OFFERED_SIDE_UNKNOWN`). |
| uncertainty | PARTIAL | `dcm/model/uncertainty.py` probability_bundle (epistemic/aleatoric/reliability/false-sign). Freeze `probabilityContract` documents Reliability ≠ probability; slim rows keep separate keys (`selectedP`, `evidenceSafeP`, `lowerBound`, `reliability`, `dataQuality`, `volatility`, `fragility`, `oodRisk`, `falseSignRisk`, `monteCarloSE`, `epistemicUncertainty`). Ranking still composes a selectionScore from those fields. |
| calibration | PARTIAL | `apply_calibration` is INACTIVE without chronological settlements; `build_challenger_cells` is shadow-only. |
| grading | COMPLETE | `dcm/model/grade.py` PLAYABLE/LEAN/PASS/TRAP; Demon demotion-only. |
| line surfaces | COMPLETE | `dcm/model/line_surface.py` unclamped offered/break-even/playable-break/tolerance/elasticity/robustness_area. P4 emits those fields on slim() PLAYABLE/LEAN top25 and card rows. |
| ranking | COMPLETE | `rank_candidates` always writes `top25_ranked.json` (PR #8). |
| portfolio | COMPLETE | `dcm/selection/portfolio.py` `build_card` 0–6, unique player, event/team caps, composite overlap. |
| PropExplanation | COMPLETE | `dcm/model/explanation.py` `build_prop_explanation`; drivers from encoded snapshot vs league-prior diffs (empty-list-ok). Runner writes `prop_explanations.jsonl` for top25 + strict_card. Human text optional from the object only. |
| freeze | PARTIAL | Hash-verified `freeze.json` / `frozen_forecast.json`. P4 binds software, git commit (if available), schema hash, featureStoreHash, HAR sha, board hash, evidence graph hash, parameter snapshot hashes, model config, calibration, decision cutoff, top25, card, explanations hash (`freezeBinds`). Final status/start strip runs immediately before portfolio freeze. PR #9 freeze remains a regression fixture, **INCORRECT on Bonner**. |
| Top25 | COMPLETE | `top25_ranked.json` always; `top25_qualified.json` unpadded (PR #8). |
| 0–6 PLAYABLE | PARTIAL | PR #8 `modeledPlayable` / `strict_card.json` exist; **status/start hard gates were incomplete** (this P0). Production-certified layer stays empty (`V6_ROOT_OF_TRUST_MIGRATION_ACCEPTED=false`). |
| audit | PARTIAL | PR #6 `dcm/runtime/github_archive.py` split cert flags. `locksCertified` may still appear as a **derived alias**; retire misleading primary use. |
| settlement | PARTIAL | `dcm/learning/postgame.py` `settle_run` + `platform/prizepicks/settlement.py`. Not wired to every freeze automatically. |
| LearningLedger | PARTIAL | `dcm/learning/sidecar.py` append-only kinds (FrozenForecast/Settlement/Audit/PatchProposal/PromotionDecision). No full-season ledger. |
| training | MISSING | No training loop / full-season packets. |
| champion / challenger | PARTIAL | Postgame `REGISTER_SHADOW_CHALLENGER_ONLY`; no promotion path; LR never auto-advances. |
| LR | COMPLETE (locked) | `VERSION.json` + `dcm/version.py` LR000000 / predictive NONE. Not promoted. |
| portable wheel release | PARTIAL | `dcm/release.py` + `scripts/build_portable.py` + `test_release_freshness.py`. Not a published wheel of the full production stack. |
| full-season packets | PARTIAL | `dcm/research/player_packet.py` basketball full current-season packet (L3/L5/L10/L15/L20 derived from full log, support_n from usable logs, PRA identity). One packet reused across a PlayerOfferSet. Not a training FeatureStore / multi-slate ledger. |
| joint team minute conservation | PARTIAL/COMPLETE | WNBA≈200 / NBA≈240 enforced in `reconcile_team_minutes`; runner writes `event_worlds_meta.json` (allocation mode, team minute sum mean, conservation flags). |
| quarter worlds | PARTIAL | `dcm/model/quarter_worlds.py`: Dirichlet split of full-game points/minutes into 4 quarters that sum to game totals; Qtrs w/3+ Pts counts thresholds. 1H/2H/Qn pts derived from the split. Other quarter stats fail closed (`QUARTER_PLUGIN_INCOMPLETE`) rather than a full-game Gaussian. |

## Known P0 defects (PR #9 freeze)

- **Bonner INCORRECT:** `strict_card.json` of `RUN_60612c8a7bcf7df1` lists DeWanna Bonner pts 6.5 MORE as `grade=PLAYABLE`, `modeledPlayable=true`, `blocker=PLAYER_STATUS_UNCERTAIN`, `ROLE:ATL:questionable`, event MIN @ ATL, freeze cutoff `2026-08-30T19:43:12Z`. Status-uncertain + started event must not land on the modeled card.
- **Cause:** `is_modeled_playable` ignored `PLAYER_STATUS_UNCERTAIN` / OUT / eventStartTime vs cutoff. ParameterSnapshot already set the blocker (`parameters.py`) but the selection path did not honor it for modeled PLAYABLE.
- **Archive flags PARTIAL:** split flags exist; `locksCertified` remains a derived alias for old readers (`github_archive.compute_certification`).

## Out of scope for this P0

Joint minute conservation, quarter worlds, champion promotion, LR advance, V1 hash rewrite, merge to main.

P1 (this line): PlayerOfferSets COMPLETE, EvidenceGraph COMPLETE (minimal first-class), full-season packets PARTIAL (basketball), SourceAdapters basketball-first.

P2 (this line): RoleEpochBuilder COMPLETE (production constructor, not stub); FeatureStore COMPLETE (observations, no trained models); ParameterSnapshots PARTIAL (role-comparable minutes + hierarchical shrink wired on basketball).

P3 (this line): Joint EventWorld PARTIAL/COMPLETE (basketball team minutes + FGA residual); PrimitiveStatLedger PARTIAL/COMPLETE on the MC path; market derivation PARTIAL/COMPLETE (versioned registry, fail-closed unknown/fantasy); quarter worlds PARTIAL (pts/minutes Dirichlet split + threshold counts). LR000000 / predictive NONE unchanged. V1 hash unchanged.

P4 (this line): line surfaces COMPLETE on PLAYABLE/LEAN slim rows; PropExplanation COMPLETE (machine-readable, freeze jsonl); freeze binds + probability-contract documentation COMPLETE; joint EventWorld + derive_market already wired in P3 remain engaged. LR000000 / predictive NONE unchanged. V1 hash unchanged.
