# Engineering pass — ChatGPT-native runtime governance and universal research contract

- Agent: ChatGPT
- Date: 2026-08-31
- Starting integration branch: `integration/v6-ml-architecture-20260830`
- Exact starting SHA: `c9e75c7259d176d3014af8fc9163706e5589d139`
- Child branch: `chatgpt/progress-native-runtime-governance-20260831`
- Pull request: #13
- Pre-log implementation/specification head validated by CI: `2a16565ef0cda0c0943eb5b6ada4cb3c138ac8a6`
- Final pass-log commit: this record's commit; see Git history. No executable model code is changed by this record.

## Objective

Make long-horizon DCM completion auditable pass-by-pass, freeze a ChatGPT-first/Grok-compatible host execution contract, define universal deep research acquisition, and provide a reusable master implementation prompt without falsely claiming the host CLI/provider migration is already implemented.

## Files added or changed

- `AGENTS.md`
- `docs/PROGRAM_STATUS.md`
- `docs/PROGRAM_STATUS.json`
- `docs/CHATGPT_NATIVE_EXECUTION_SPEC.md`
- `docs/UNIVERSAL_RESEARCH_ACQUISITION_SPEC.md`
- `docs/GROK_MASTER_IMPLEMENTATION_PROMPT.md`
- `docs/UNIVERSAL_IMPLEMENTATION_MATRIX_20260831.md`
- `docs/engineering_passes/README.md`
- `docs/generated/README.md`
- `scripts/build_code_inventory.py`
- this immutable pass record

## Modules/functions/classes added or behaviorally changed

No forecasting/model runtime algorithm was changed in this tranche.

New engineering inventory script `scripts/build_code_inventory.py` adds:

- `sha256`
- `workstream`
- `Visitor`
- `Visitor._add`
- `Visitor.visit_ClassDef`
- `Visitor.visit_FunctionDef`
- `Visitor.visit_AsyncFunctionDef`
- `build`
- `render_md`
- `serialize`
- `main`

The script uses Python AST to enumerate DCM Python modules/classes/functions/methods, source hashes and workstream mapping. It is an existence/surface inventory, not a production-completion classifier.

## Contracts/algorithms specified

### ChatGPT-native host contract

Canonical public command family is specified as:

- `dcm-host doctor`
- `dcm-host prepare`
- `dcm-host next-research`
- `dcm-host evidence-import`
- `dcm-host coverage`
- `dcm-host forecast`
- `dcm-host report`
- `dcm-host resume`
- `dcm-host audit`
- `dcm-host settle`
- `dcm-host archive`

Equivalent Python API is specified around `dcm.chat.HostSession`.

The host performs web/tool acquisition. Python remains the only probability/model engine. GitHub repository visibility is explicitly not treated as equivalent to package importability; fresh-host acceptance requires an exact release artifact.

### Universal research acquisition

Universal research is specified around:

Sport → Competition → Event → Affiliation / Counterparty / Environment → Subject → MarketDefinition → Offer.

Paige/Dallas/Connecticut-style depth is generalized into Subject, Affiliation, Counterparty, Event, Environment, MarketDefinition and Offer packets rather than encoded as basketball/player/team core semantics.

Recommended research scheduling objective is specified as:

`fanout × information_importance × freshness_need × expected_uncertainty_reduction / estimated_acquisition_cost`

This formula is a specification in this tranche; it is not yet wired into the runtime scheduler.

### Program completion governance

P0–P14 machine/human status registries and append-only engineering-pass rules are now specified. A subsystem is not 10/10 merely because a file/class exists.

## Validation

GitHub Actions workflow: `DCM v6 branch CI`, run `33410268588`.

Exact tested head: `2a16565ef0cda0c0943eb5b6ada4cb3c138ac8a6`.

Result: **SUCCESS**.

Successful stages:

- package install from repository root
- CLI smoke from clean working directory
- `python -m dcm --help`
- `python -m pillars_dcm --help`
- synthetic end-to-end smoke
- full pytest suite
- engineering benchmark smoke

A previous specification head `c0b844bc7f4db5225353186c3cb2f2727ac82a22` also completed CI successfully.

No host-performance certification is inferred from the engineering benchmark.

## Workstream status

This tranche created the durable P0–P14 progress framework. It did not artificially raise runtime scores merely because specifications were added.

Current registry remains approximately:

- P0 9/10 STRONG PARTIAL
- P1 7/10 PARTIAL
- P2 7/10 PARTIAL
- P3 6/10 PARTIAL
- P4 8/10 STRONG PARTIAL
- P5 7/10 PARTIAL
- P6 6/10 PARTIAL/EXTERNAL VALIDATION
- P7 2/10 EARLY
- P8 4/10 PARTIAL
- P9 8/10 STRONG PARTIAL
- P10 3/10 EARLY
- P11 7/10 PARTIAL
- P12 3/10 EARLY
- P13 5/10 PARTIAL
- P14 4/10 PARTIAL

## Requirements completed in this pass

- PR #12 SportPlugin contract folded into canonical PR #10 integration line before this tranche.
- Persistent human program dashboard created.
- Machine-readable program status registry created.
- Append-only engineering-pass contract created.
- ChatGPT-first/Grok-compatible execution interface frozen as a repository specification.
- Universal deep-research requirements frozen independently of any named sport/player/team.
- GitHub research/archive organization rules specified.
- AST-based function/module/class inventory generator added.
- Reusable master implementation prompt added.
- P7–P14 completion program added to the implementation matrix.

## Requirements still partial or missing

### CODE

- `dcm.chat` / `dcm-host` runtime implementation is not yet built.
- Legacy canonical research/provider semantics still use PLAYER/TEAM in parts of `requests.py`, `provider.py`, `coverage.py` and current packet consumers.
- Universal Subject/Affiliation/Counterparty/Event/Environment packet APIs remain incomplete.
- SourceCatalog/SourceAdapter capability registry is not yet complete.
- Optimized iterative host research scheduler is not yet runtime-integrated.
- Simple host-observation evidence import is not yet implemented.
- FeatureStore and ParameterSnapshot remain partially player/team-shaped.
- EvidenceGraph topology is universal but full Feature→State→ParameterSnapshot→Simulation→Evaluation→Selection→Settlement→Learning lineage remains incomplete.
- SportPlugins remain incomplete; no sport is yet 24/24 universal-production-complete.
- Fresh-host wheel+HAR acceptance is not yet implemented as an end-to-end test.
- Generated `CODE_INVENTORY.json/.md` canonical snapshot still needs to be generated and committed in an execution-capable coding environment, then CI stale-check enabled.

### ENVIRONMENT

- A ChatGPT host needs an explicit way to obtain/mount the exact release wheel. GitHub read/search access alone cannot be treated as a Python import mechanism.
- Grok compatibility depends on Grok having equivalent Python execution, web/tool research and release/HAR access; the CLI/JSON contract itself is host-neutral.

### DATA / EXTERNAL

- Paid/authenticated data providers may improve acquisition but are optional capabilities, not hard-coded requirements. Credentials must remain outside Git.
- Some source material may not be legally appropriate to persist as raw data; content-addressed normalized provenance/indexes must honor licensing/storage policy.

### VALIDATION

- Chronological unseen forecast settlements remain insufficient to justify Learning Revision advancement or a predictive-skill claim.

### GOVERNANCE

- Production root remains closed until independent root/integrity gates are earned.

## Compatibility shims introduced or retired

No new runtime compatibility shim was introduced in this tranche.

The architecture continues to require legacy Player/Team terminology to terminate at sport/source compatibility adapters; canonical provider migration remains a next-pass task.

## Root-of-trust / LR / predictive / performance claims

Unchanged:

- Learning Revision: `LR000000`
- Predictive claim: `NONE`
- Production root: CLOSED / not certified
- Host performance: not certified

## Ordered next pass

1. Generate and commit the canonical AST code-inventory snapshot and wire stale-check CI.
2. Implement `dcm.chat` and `dcm-host` over the existing runner/research/freeze code—no second model engine.
3. Migrate canonical request/provider semantics to SUBJECT/AFFILIATION/COUNTERPARTY/EVENT/ENVIRONMENT while translating PLAYER/TEAM only inside source/sport adapters.
4. Implement universal research packet containers and compatibility projections.
5. Implement SourceCatalog/SourceAdapter capability registry.
6. Implement event-first iterative research batching and simple host-observation evidence import.
7. Move semantic coverage entirely under SportResearchSchema.
8. Universalize FeatureStore and ParameterSnapshot.
9. Populate complete EvidenceGraph runtime lineage.
10. Close all PARTIAL SportPlugin bindings sport-by-sport.
11. Build the exact-wheel fresh-ChatGPT HAR acceptance test.
12. Continue P0–P14 until every code-completable row reaches an evidenced 10/10; leave future predictive promotion fail-closed until chronology earns it.
