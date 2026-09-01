# Engineering Pass — P380X donor Tranche A/B

- **Timestamp:** 2026-09-01T19:44:00Z
- **START_SHA:** `8311b2aaeef16b508b6ef21c01c22ad990b9ad5d`
- **END_SHA:** `6cf8a15d40e839748ce6f76c0d980da70fb448df`
- **BRANCH:** `chatgpt/p380x-signal-integration-20260901`
- **PR:** #16
- **FILES_CHANGED:** 21 in the implementation commit; this immutable record and final report CI update follow as governance-only changes
- **REQUIREMENTS_COMPLETED:** Tranche A 58/58 donor accounting; Tranche B typed operator contract, lifecycle registry, compiler, integration gate, semantic signatures, overlap groups, dependency DAG, executor, FeatureStore consumer, Draft 2020-12 schema, critical rejection enforcement
- **REQUIREMENTS_PARTIAL:** no exact 1,500+ source-definition compilation because original donor ZIP bytes are unavailable; no donor capability is production-active without a real producer/consumer/activation proof
- **TESTS:** 19 targeted signal-governance tests passed; GitHub Actions complete repository run #195 passed, including install, CLI/host/synthetic smokes, full pytest, official inventory stale-check and benchmark smoke
- **CI_STATUS:** GREEN — workflow `DCM v6 branch CI`, run #195, code head `6cf8a15d40e839748ce6f76c0d980da70fb448df`
- **PERFORMANCE:** representative 58-candidate compile 12.52 ms wall, 279,712-byte traced peak allocation, 58,639-byte approximate registry artifact; deterministic registry hash `9a5fa3e2bd4f94c9df5b7fc48066b6783d93d02a07e500e9ef377ecd07a0d0ff`; host performance remains uncertified
- **NEW_BLOCKERS:** none for bounded Tranche A/B
- **EXTERNAL_BLOCKERS:** exact donor archive bytes unavailable; archive extraction/hash/quarantine cannot be claimed
- **NEXT_EXACT_TRANCHE:** P380X Tranche C — Research Truth Integration

## Donor accounting

All 58 principal candidates have a recorded disposition. None is active. The matrix remains documentation/quarantine data and is not packaged into the runtime wheel.

Disposition counts: PORT_NATIVE 17; MERGE_WITH_EXISTING 14; REINTERPRET 6; REJECT 6; GENERALIZE 4; REFERENCE_ONLY 2; and one each for DEFER_SPORT_PLUGIN, GENERALIZE_HOST_NEUTRAL, PORT_AS_DIAGNOSTIC, PORT_AS_EVIDENCE, PORT_FUTURE_ONLY, REIMPLEMENT_CORE_IDEAS, REJECT_AS_PROBABILITY_TRANSFORM, REJECT_IF_FORCING and REJECT_NAME_AND_IMPL.

## Signal-governance result

The compiler fails closed on unsupported SportPlugin/MarketDefinition bindings, unavailable normalized fields, unit mismatch, post-cutoff inputs, missing/non-executable dependencies, cycles, semantic duplicates, unregistered consumers, missing activation tests, unauthorized hard gates and forbidden behavior classes. Registry hashes and execution order are source-order deterministic. Exact semantic duplicates cannot execute twice; related signals retain overlap groups and are not automatically summed.

The only new canonical runtime consumer is `dcm.ml.feature_store.signal_evaluation_feature_records`, which converts only `ACTIVE_FEATURE` evaluations into cutoff-immutable feature records with evaluation-hash lineage. It does not change probability or hard eligibility.

## Claims unchanged

- Learning revision: `LR000000`
- Predictive superiority: `NONE`
- Production root certified: false
- Host performance certified: false
- Tranche C+ implemented: false

## Clean handoff

Begin Tranche C only from PR #16's final green head after review. Reuse StatePack, ResearchStore, EvidenceGraph and adaptive freshness. Do not create a parallel truth store or freshness engine. Implement claim-specific authority, lineage-aware fusion, contradiction state and MaterialFactResolution with explicit canonical consumers and cutoff-safe tests.
