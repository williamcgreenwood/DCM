# Pillars DCM Permanent Algorithmic Constitution

**Canonical constitution version:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`  
**Prompt-declared source SHA-256 (lineage only):** `bba7b082bf67e12d87e675ac58d5b6f96d9cbad9b6a487a0aa157bf7cef9e599`  
**Committed file SHA-256:** computed at load time from these exact bytes by `dcm.algorithms.constitution`. Do not hard-code a substitute hash.  
**Inheritance:** `MANDATORY / CI-GATED / ALL FUTURE DCM VERSIONS`  
**Superseding ADR:** none

This document is the permanent inherited architecture law for Searching, Indexing, Sorting, Grouping, Graph/Hypergraph, Optimization/Scheduling, Caching, Machine-Learning, Calibration, and Uncertainty algorithms in the Pillars DCM. It is not an optional optimization appendix.

Machine-readable registry: `configs/algorithm_registry.json`  
Requirement schema: `schemas/AlgorithmRequirement.schema.json`  
Trace matrix: `docs/requirements/ALGORITHM_TRACE_MATRIX.md`  
Runtime loader: `dcm.algorithms`

<!-- CANONICAL_CONSTITUTION_BODY_BEGIN -->
## PILLARS DCM PERMANENT ALGORITHMIC CONSTITUTION

The DCM Algorithmic Constitution is a permanent canonical requirement and SHALL NOT be treated as an optional optimization tranche.

Every DCM architecture, implementation prompt, Research OS specification, HAR processor, SportPlugin, MarketDefinition implementation, StatePack/ResearchStore design, Google Drive persistence design, GitHub release, audit, benchmark, runtime and subsequent DCM version MUST preserve and explicitly trace the canonical Searching, Indexing, Sorting, Grouping, Optimization and Machine-Learning algorithm registry.

No later DCM version may silently omit, simplify away, bypass or forget an algorithmic capability classified REQUIRED_CORE, REQUIRED_CONDITIONAL or PERMANENT_CHALLENGER.

Every algorithm shall have:

algorithm_id → algorithm family → lifecycle → applicability contract → input contract → implementation → runtime producer → runtime consumer → deterministic fallback where applicable → complexity/performance expectation → benchmark → tests → audit lineage → requirement trace.

REQUIRED_CORE algorithms execute wherever their applicability contract is satisfied.

REQUIRED_CONDITIONAL algorithms must remain implemented and automatically activate when their workload, scale, data-quality or runtime availability conditions are satisfied.

PERMANENT_CHALLENGER algorithms remain registered and benchmarkable against the production champion and may not disappear merely because they are not currently production-active.

No algorithm shall be forced into a semantically inappropriate task merely to claim compliance. The requirement is correct algorithm selection, not maximum algorithm count.

The DCM shall universally apply the governing computational sequence:

canonicalize → deduplicate → hash → group → index → establish graph/hypergraph dependencies → retrieve existing evidence → schedule marginal research → model → partially select frontier → deterministically rank → persist → content-hash → audit.

The runtime shall always choose the cheapest exact operation capable of answering a request before using a more expensive approximate, semantic, Drive, web or LLM operation.

Research shall never be planned as one independent search per prop when shared Event, Team, Player, Opponent, Participant, Market, Source or MaterialFact evidence can satisfy multiple props.

Weighted set-cover and submodular marginal-coverage optimization are permanent Research OS scheduling requirements.

Google Drive is the canonical durable object/run/research store where available; it is not the primary query engine. Research and run objects shall be indexed through canonical catalogs, bitemporal metadata, hashes, Bloom/shard indexes and local runtime indexes before Drive reads are issued.

GitHub is the canonical version-controlled source for code, schemas, registries, algorithms, tests, prompts, ADRs, manifests and requirement traces.

Every material object shall use deterministic canonical identity and cryptographic content addressing where appropriate.

Every frozen DCM run shall be reproducible from its HAR hash, DCM Git commit, Algorithmic Constitution version, algorithm-registry hash, research/evidence artifact hashes, ParameterSnapshot hashes and frozen forecast artifacts, with a Merkle root or equivalent cryptographic manifest where practical.

Every DCM release must include the current ALGORITHM_CONSTITUTION_VERSION and ALGORITHM_REGISTRY_SHA256.

CI MUST fail when a required algorithm, runtime consumer, fallback, test, benchmark requirement or requirement trace is removed without an explicit superseding Architecture Decision Record.

Algorithm retirement requires benchmarked evidence that the replacement is superior for the relevant DCM workload across correctness, predictive utility when applicable, CPU, memory, latency, token consumption, storage, portability and auditability. Silent retirement is prohibited.

Each major DCM architecture pass shall conduct an Algorithm Frontier Review covering information retrieval, indexing, sorting, grouping, graph/hypergraph algorithms, optimization, caching, tabular ML, time-series ML, causal ML, probabilistic modeling, calibration, uncertainty and foundation-model advances. New algorithms shall be classified ADOPT, BENCHMARK_CHALLENGER, MONITOR or REJECT and added to the permanent registry where appropriate.

ChatGPT-native execution remains the primary portability constraint. No production capability may require an unavailable GPU, proprietary remote endpoint, multi-gigabyte runtime download or optional native dependency without a deterministic ChatGPT-executable fallback implementing the same semantic contract.

The Algorithmic Constitution is inherited by all future DCM versions unless explicitly superseded by a newer constitution under an ADR. It must never disappear merely because a new implementation prompt omitted its text.
<!-- CANONICAL_CONSTITUTION_BODY_END -->

## Lifecycle mapping

- `REQUIRED_CORE` — execute wherever the applicability contract is satisfied.
- `REQUIRED_CONDITIONAL` — remain implemented; activate when workload/scale/data-quality/runtime conditions are met; emit evaluation telemetry when not activated.
- `PERMANENT_CHALLENGER` — remain registered and benchmarkable; may not disappear merely because they are not production-active.
- `fallback` is an implementation role, not permission to omit the family.
- `PROHIBITED_MISUSE` — do not force an algorithm into semantically inappropriate work merely to claim compliance.

## Retrieval cascade (cheapest exact first)

1. L0 Python hash
2. Existing current-run object
3. SQLite exact/composite index
4. Graph/hypergraph neighbor lookup
5. Bloom-filtered Drive catalog
6. Inverted/BM25 retrieval
7. Alias/fuzzy lookup
8. MinHash/LSH similarity
9. HNSW semantic retrieval
10. DiskANN/large ANN if configured
11. Google Drive object fetch
12. External web research

If a cheaper exact step answers the question, later steps SHALL NOT run.

## HAR processor law

No external research may begin until an `AlgorithmExecutionPlan` and the deterministic BoardGraph/MarketDemandGraph/RequirementGraph are created. R0 of this constitution pass implements the plan and registry. BoardGraph/RequirementGraph remain the next Research OS tranche and are not claimed complete by this document.

## Storage law

temporary local byte staging for serialization/hash only
→ Google Drive PRIMARY durable research/run/object store when available
→ GitHub SECONDARY durable/version-controlled store when artifact semantics, privacy, licensing and size permit
→ promoted LOCAL FALLBACK run store when remote durable storage is unavailable or unsuitable

Google Drive is never the primary query engine.

## Retirement law

An algorithm cannot be deleted because a later build thinks it is unnecessary. Retirement requires ReplacementBenefit > ExistingBenefit demonstrated through benchmark, correctness, CPU, memory, token, portability, auditability comparison, replacement implementation, ADR, and requirement-trace update. Otherwise removal is prohibited.

## This repository pass (R0)

R0 implements constitution-as-code: the document, machine-readable registry, schema, trace matrix, AlgorithmSelectionEngine, ChatGPT-native CORE algorithm implementations, HAR AlgorithmExecutionPlan emission, CI governance tests, and release-manifest fields. It does not claim the full Research OS, live HAR acceptance, or predictive superiority.
