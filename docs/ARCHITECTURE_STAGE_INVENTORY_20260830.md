# DCM ML-architecture stage inventory — 2026-08-30

Canonical line: `integration/v6-ml-architecture-20260830` (PR #10), stacked on PR #5 `263c6f4` + #6 `63f5f5a` + #7 `8bd9526` + #8 `505d38e` + #9 `04742d5`.
Do **not** use `main` (`d68fa772`, stale). V1 hash remains `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`. LR000000 / predictive NONE.

Statuses: COMPLETE | PARTIAL | STUB | MISSING | INCORRECT | OBSOLETE.

Audit pack `audit/runs/RUN_60612c8a7bcf7df1` is a **regression fixture, not a gold standard**. It proves the Python freeze pathway and split cert flags, but the Bonner PLAYABLE card is INCORRECT (PLAYER_STATUS_UNCERTAIN + event already started). Do not delete the pack.

`locksCertified` is **retired from canonical runtime/audit state**. Primary flags are the split set (`modelRunCertified`, `selectionCertified`, `evidenceCoverageCertified`, plus archive/temporal/root/predictive). The compatibility helper `locks_certified()` may derive the historical combined condition for old callers, but the field is not serialized.

| Stage | Status | Evidence |
| --- | --- | --- |
| HAR | COMPLETE | `dcm/ingest/har.py` + `dcm/ingest/prizepicks.py`; sanitized live HAR fixtures; PR #4/#5. |
| board extraction | COMPLETE | `dcm/ingest/board.py` `freeze_board` / `BOARD_JSON_V2_ASOF_2026-08-28`; `eventStartTime` from PrizePicks `start_time`. |
| accounting | COMPLETE | `accounting_from_rows` + `dcm/research/classify.py` `accounting_classify`; test_e2e_runner accounts every row. |
| identity | COMPLETE/PARTIAL | `dcm/identity/resolve.py` freezes HAR `new_player` ids; `identities/map.json`; P8 writes `identities/player_index.json` grouping every playerId → offers/events/teams (`nameIsNotId=true`). CFB official-id map remains league-specific. |
| PlayerOfferSets | COMPLETE | `dcm/research/player_offer_set.py` groups by playerId+eventId; runner writes `player_offer_sets.json`; Paige-style N markets → 1 set. |
| research population | COMPLETE | `dcm/research/population.py` `ResearchPopulationManifest` (eligible events/teams/players/market_definitions/offers, dependentOfferCount, fan-out priority). Account/classify path always emits `research_population_manifest.json`. |
| EntityGraph | COMPLETE | First-class `dcm/research/entity_graph.py` (`entity_graph.json`). Nodes: Sport/League/Event/Team/Player/PlayerOfferSet/Offer/MarketDefinition + research packets. Opponent edges **reuse** the same Team node / TeamResearchPacket (no OPPONENT scope). Distinct from EvidenceGraph. `host_plan.py` entityGraph dict remains a planning view. |
| source research | PARTIAL/COMPLETE | File/Bundle/Fixture providers + `authority.py`; basketball SourceAdapters: Player/GameLog/Team/TeamGameLog/Split/Lineup/OnOff + `ESPNStatusAdapter` + `OfficialWNBAAdapter`/`OfficialNBAAdapter` + PrizePicks. Gridiron PFR/CFB adapters. Live fetch opt-in `DCM_LIVE_FETCH`. Model code does not parse host pages. MLB/other sports still missing adapters. Fixture TEAM `pace_multiplier=1.0` is a labeled prior (`FIXTURE_TEAM_PRIOR`), not research. |
| normalized stats | PARTIAL/COMPLETE | Basketball aliases COMPLETE (`dcm/research/gamelog.py`). Gridiron aliases COMPLETE (`dcm/research/gridiron_gamelog.py`: pass_att/pass_yds/rush_*/targets/rec/snaps/off_pct). Does not invent routes from targets. MLB/other sports still incomplete. |
| EvidenceGraph | COMPLETE | First-class `dcm/research/evidence_graph.py` (`evidence_graph.json` + content hash). Nodes: SourceDocument/EvidenceClaim/Player/Team/Event/MarketDefinition/Offer/NormalizedStat. Edges: supports/derived_from/applies_to/conflicts_with. `trace_selection` resolves Selection→SourceDocument. jsonl remains the transport. |
| FeatureStore | COMPLETE | `dcm/ml/feature_store.py` cutoff-immutable records (entity/eventId/featureName/value/asOf/sourceHashes/transformationVersion/featureSchemaVersion, family in ROLE/OPPORTUNITY/EFFICIENCY/MATCHUP/CONTEXT). Runner writes `feature_store.jsonl` + `feature_store_manifest.json`; L3/L5/L10/L15/L20/season means from the full log. P8 adds TEAM pace/ortg/drtg MATCHUP features and Pass-B same-opponent CONTEXT features. Observations only — no trained-model claim. |
| Role / availability | COMPLETE/PARTIAL | `RoleEpochBuilder.v2-20260830` basketball + gridiron modes. P8 `availability_mixture` records PLAY/SIT weights; QUESTIONABLE/DOUBTFUL/OUT remain PLAYABLE-hard-excluded (Bonner/P0). PROBABLE/QUESTIONABLE sit-worlds are sampled when `pPlay < 0.97`; ACTIVE is not mixed. Mixture is recorded on every ParameterSnapshot. True teammate-availability joint reallocation beyond residual minutes is still PARTIAL. |
| ParameterSnapshots | PARTIAL/COMPLETE | Basketball path consumes claims; P8 optionally overlays Team/Event/Opponent packet fields (ortg/drtg/pace, `teamEvidenceUsed`, `paceFromTeamPacket`) without mutating hashed claims. Fixture 1.0 pace is never reported as research. Gridiron path calls `RoleEpochBuilder` + `GridironOpportunityModel`/`GridironEfficiencyModel`/`TeamEventModel`. Opponent pass/rush defense missing → fail-closed, not PLAYABLE. MLB still sketched. |
| Joint EventWorld | PARTIAL/COMPLETE | `dcm/model/event_world_joint.py`: ≥2 modeled teammates share one EventWorld. WNBA team minutes target 200 / NBA 240 via proportional rescale then residual-adjust (unmodeled residual pool when <5 modeled). Team FGA Dirichlet residual allocation (negative correlation). Single-player path unchanged. Discrete regimes / all-sports joint still PARTIAL. |
| PrimitiveStatLedger | PARTIAL/COMPLETE | Basketball MC worlds write a PrimitiveStatLedger dict. Football EventWorld + PrimitiveStatLedger (`dcm/sports/football/ledger.py`) remains the conservation path (dropbacks, attempts, completions, targets, receptions, rushes, yards, TD opportunities). Identities enforced. |
| market derivation | PARTIAL/COMPLETE | Basketball registry unchanged. Gridiron `PP_FOOTBALL_MARKET_V1_2026-08-30`: pass_yds, rush_yds, receptions, rec_yds, pass_rush_yds, rush_rec_yds. Unknown → fail closed. PrizePicks football settlement map (`dcm/sports/football/settlement_map.py`) is stub-free for those markets. TD/kicking/IDP remain fail-closed. |
| distributions | COMPLETE | `dcm/model/distributions.py` `from_worlds`: P(Higher)+P(Lower)+P(Push)=1. |
| More / Less / Push | COMPLETE | Runner evaluates both offered sides independently; missing sides fail closed (`OFFERED_SIDE_UNKNOWN`). |
| uncertainty | PARTIAL | `dcm/model/uncertainty.py` probability_bundle (epistemic/aleatoric/reliability/false-sign). Freeze `probabilityContract` documents Reliability ≠ probability; slim rows keep separate keys (`selectedP`, `evidenceSafeP`, `lowerBound`, `reliability`, `dataQuality`, `volatility`, `fragility`, `oodRisk`, `falseSignRisk`, `monteCarloSE`, `epistemicUncertainty`). Ranking still composes a selectionScore from those fields. |
| calibration | PARTIAL | `apply_calibration` is INACTIVE without chronological settlements (`INACTIVE_INSUFFICIENT_CHRONOLOGICAL_SETTLEMENTS`); `build_challenger_cells` is shadow-only. `evaluate_calibration_readiness` (MIN_N=200, ECE threshold) reports only — it does not flip LR or activate cells. |
| grading | COMPLETE | `dcm/model/grade.py` PLAYABLE/LEAN/PASS/TRAP; Demon demotion-only. |
| line surfaces | COMPLETE | `dcm/model/line_surface.py` unclamped offered/break-even/playable-break/tolerance/elasticity/robustness_area. P4 emits those fields on slim() PLAYABLE/LEAN top25 and card rows. |
| ranking | COMPLETE | `rank_candidates` always writes `top25_ranked.json` (PR #8). |
| portfolio | COMPLETE | `dcm/selection/portfolio.py` `build_card` 0–6, unique player, event/team caps, composite overlap. |
| PropExplanation | COMPLETE | `dcm/model/explanation.py` `build_prop_explanation`; drivers from encoded snapshot vs league-prior diffs (empty-list-ok). Runner writes `prop_explanations.jsonl` for top25 + strict_card. Human text optional from the object only. |
| freeze | PARTIAL | Hash-verified `freeze.json` / `frozen_forecast.json`. P4 binds software, git commit (if available), schema hash, featureStoreHash, HAR sha, board hash, evidence graph hash, parameter snapshot hashes, model config, calibration, decision cutoff, top25, card, explanations hash (`freezeBinds`). Final status/start strip runs immediately before portfolio freeze. PR #9 freeze remains a regression fixture, **INCORRECT on Bonner**. |
| Top25 | COMPLETE | `top25_ranked.json` always; `top25_qualified.json` unpadded (PR #8). |
| 0–6 PLAYABLE | COMPLETE/PARTIAL | PR #8 `modeledPlayable` / `strict_card.json`; P0 status/start hard gates (Bonner `PLAYER_STATUS_UNCERTAIN` + started event cannot be PLAYABLE). Empty card is legal. Production-certified layer stays empty (`V6_ROOT_OF_TRUST_MIGRATION_ACCEPTED=false`). |
| audit | PARTIAL | `dcm/runtime/github_archive.py` uses split cert flags; `locksCertified` is retired from canonical state. Pack includes universal research artifacts, explanations, EvidenceGraph and feature-store manifest when present; never raw HAR or Cookie/Set-Cookie files. Git push remains optional (`--no-archive-push`). |
| settlement | COMPLETE/PARTIAL | `dcm/learning/postgame.py` `settle_run` + `python -m dcm.settle --dest --outcomes` settle the full modeled population (`full_population.jsonl` / `population_full`) to `settlements.jsonl` + `settlement_summary.json` (counts by result/grade/market). PrizePicks results: WIN/LOSS/PUSH/VOID/DNP/REBOOT/UNKNOWN_PLATFORM_RULE. Card-only subset via `--card-only`. Does not invent outcomes. Lineup economics remain PARTIAL (entry contract required). |
| LearningLedger | PARTIAL | `dcm/learning/sidecar.py` append-only sqlite + `learning_ledger.jsonl`. Freeze writes FrozenForecast; settle appends one Settlement per modeled prop and never rewrites the frozen forecast. P6 dataset builder joins settlements into `training_dataset.jsonl` + manifest (supervised WIN/LOSS/PUSH vs audit VOID/DNP/UNKNOWN/REBOOT). No full-season multi-slate production trainer. |
| training | PARTIAL | `dcm/learning/dataset.py` builds `training_dataset.jsonl` + manifest from settled dests (never invents labels). `walkforward.py` evaluates frozen calibratedP/selectedP on chronological folds (Brier/logloss/hitRate/ECE). Optional tiny shadow logistic is SHADOW, no sklearn, no .pkl. No trained production weights. |
| champion / challenger | PARTIAL | `dcm/learning/registry.py`: champion = software+LR000000; `register_challenger` status=SHADOW only; `propose_promotion` returns BLOCKED; `promote()` hard-refuses LR/predictiveClaim change even if `DCM_ALLOW_LR_PROMOTE=1`. No auto-promote. |
| LR | COMPLETE (locked) | `VERSION.json` + `dcm/version.py` LR000000 / predictive NONE. Not promoted. |
| portable wheel release | PARTIAL/COMPLETE | `dcm/release.py` + `scripts/build_portable.py` emit wheel (via `python -m build` when deps exist), COMPLETE_PROJECT_SOURCE.txt (per-file + bundle sha256), RELEASE_MANIFEST.json with required gitCommit, INSTALL_SHA256.txt, HASHES.json, CAPABILITY.json, RUNTIME_PROMPT.md under `artifacts/release` or `dist/`. Not a published PyPI release. Clean-env `python -m dcm --help` is the install gate. |
| full-season packets | COMPLETE/PARTIAL | `dcm/research/player_packet.py` basketball full current-season packet (L3/L5/L10/L15/L20 derived from full log, support_n from usable logs, PRA identity). `seasonPageSnapshot` populated from the player-season adapter; G-mismatch flagged; claimed G never papers over empty logs. One packet reused across a PlayerOfferSet. Not a training FeatureStore / multi-slate ledger. |
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

P5 (this line): portable release builder emits a real wheel + COMPLETE_PROJECT_SOURCE + required gitCommit; archive copies explanations/graph when present and rejects Cookie/Set-Cookie; settle_run covers the full modeled population (not only the 6-card) with LearningLedger Settlement sidecars. LR000000 / predictive NONE unchanged. V1 hash unchanged.

P6 (this line): training-dataset builder + chronological walk-forward of frozen probabilities; shadow-only champion/challenger registry; calibration readiness report (does not flip LR); settle_run attaches heuristic failureClass with permanentPatch always False. LR000000 / predictive NONE unchanged. V1 hash unchanged. No .pkl / no claimed trained superiority.

P7 (this line): gridiron (NFL/CFB) production plugin — SourceAdapters + canonical gamelog + RoleEpoch gridiron mode + opportunity/efficiency/team-event models + ledger identities + versioned market/settlement maps. productionCapable NFL/CFB: pass_yds, rush_yds, rec_yds, receptions, pass_rush_yds, rush_rec_yds. Fail-closed: pass_td/rec_td/targets/fg_made/def_tackles/CFL/NFLP-as-production and unknown labels. Basketball remains the reference sport. Do not claim MLB production. LR000000 / predictive NONE unchanged. V1 hash unchanged.

P8 (this line): Team/Opponent/Event research packets + first-class EntityGraph + player_index + staged Pass A/B + research cache + ESPN/official adapters + remaining B-R team/gamelog/split/lineup/on-off adapters + lineup/on-off shrinkage (max abs 0.08) + team ORtg/DRtg/pace overlay on ParameterSnapshots + Points coverage minutes+FGA+3PA+FTA + fixture 1.0 pace is not coverage + availability mixture sit-worlds (QUESTIONABLE still PLAYABLE-blocked). Opponent is TEAM-scoped reuse. One Dallas packet serves every Dallas player. LR000000 / predictive NONE unchanged. V1 hash unchanged. Do not merge to main.

## P8 remaining (explicit, not hidden)

- Independent quarter-state worlds still Dirichlet-split from full-game pts/minutes (not four independently simulated quarter ledgers for attempts/makes).
- Availability sit-worlds do not yet reallocate teammate opportunity beyond the existing joint residual-minute pool.
- Pass B writes overlays + feature-store MATCHUP rows; it does not launch a second SERIOUS/CEILING world pass by itself (governor already escalates serious candidates).
- MLB remains SHADOW.
- Live ESPN/official/B-R fetches remain opt-in (`DCM_LIVE_FETCH`); default path is fixture/file/bundle.
- V1 hash gate closed; production root closed.


## P9 universal-core migration — PR #11 child tranche (2026-08-31)

This branch adds the first canonical sport-neutral research layer required by the universal DCM directive.

- **SubjectOfferSet — COMPLETE (core contract):** `subject_offer_sets.json` groups `Subject + Event`; PLAYER is one SubjectType, not the core identity.
- **Universal entity contracts — COMPLETE (container layer):** Sport, Competition, Event, Affiliation, Subject, Counterparty, Environment, MarketDefinition and Offer are first-class. Sport-specific concepts remain adapter/plugin vocabulary.
- **ResearchPopulationManifest V2 — COMPLETE (population construction):** canonical `research_population_manifest.json` contains sports, competitions, events, affiliations, subjects, counterparties, environments, marketDefinitions and offers. Legacy TEAM/PLAYER planner output is isolated in `research_population_manifest_legacy.json`.
- **ResearchDependencyGraph — COMPLETE (first version):** `research_dependency_graph.json` contains only universal entity types and fan-out dependencies. It deliberately contains no Team or Player nodes.
- **Legacy PlayerOfferSet — COMPATIBILITY ONLY:** generated from canonical SubjectOfferSet for existing basketball/gridiron consumers. Non-player subjects are never fabricated as players.
- **Existing EntityGraph / player/team research packets — PARTIAL migration:** still used by current basketball/gridiron adapters and model consumers. They are sport-specific compatibility projections, not the universal core.
- **Universal SourceAdapter/ResearchSchema consumption — PARTIAL:** providers still request legacy TEAM/PLAYER scopes. Next migration should make the planner/provider interface consume AFFILIATION/SUBJECT/COUNTERPARTY/ENVIRONMENT directly, with sport plugins translating to source-specific adapters.
- **Model physics unchanged:** no second engine; probability, EventWorld, primitive ledger, grading, ranking, portfolio and freeze paths are unchanged in this tranche.
- **Governance unchanged:** LR000000, predictive NONE, V1 expected hash unchanged, production root closed.
