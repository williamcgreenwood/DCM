# Algorithmic Constitution inheritance receipt

This repository inherits the Pillars DCM Permanent Algorithmic Constitution.

```text
constitution_version: DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903
prompt_declared_constitution_sha256: bba7b082bf67e12d87e675ac58d5b6f96d9cbad9b6a487a0aa157bf7cef9e599
committed_constitution_sha256: computed at load time from docs/architecture/DCM_ALGORITHMIC_CONSTITUTION.md
registry: configs/algorithm_registry.json
consumption_law: docs/engineering/ALGORITHM_CONSUMPTION_LAW.md
consumption_lock: EXACT_INDEX→CACHE_CELF→DAG→TWO_REP→NUMPY_EVENTWORLD→REGISTRY_ML
schema: schemas/AlgorithmRequirement.schema.json
trace: docs/requirements/ALGORITHM_TRACE_MATRIX.md
runtime: dcm.algorithms
adr: docs/architecture/ADR-ALG-CONST-001-r0.md
chatgpt_native_fallbacks: REQUIRED
silent_algorithm_retirement: PROHIBITED
google_drive_primary_durable_store: REQUIRED_WHEN_AVAILABLE
github_secondary_durable_versioned_store: REQUIRED_WHEN_APPLICABLE
local_promoted_fallback: REQUIRED
future_prompt_inheritance: REQUIRED
learning_revision: LR000000
predictive_claim: NONE
```

Any future master prompt, architecture pass, SportPlugin, or release derived from this repository SHALL preserve this receipt or record a superseding constitution under an ADR. Silent omission is a build failure.
