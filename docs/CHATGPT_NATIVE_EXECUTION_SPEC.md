# ChatGPT-native DCM execution specification

## Goal

A fresh ChatGPT or Grok host must be able to execute the complete canonical DCM from an uploaded HAR without understanding internal model modules. Python remains the only forecasting engine. The host performs web/tool research; the engine validates, normalizes, hashes, models and freezes.

Repository visibility is not equivalent to runtime importability. A host-native run requires an exact release artifact (normally a wheel) that is mounted, downloaded through an authorized capability, or otherwise made available to the execution environment.

## Canonical host boundary

```
HAR
→ dcm host prepare
→ board/accounting + universal ResearchPopulation + dependency graph
→ dcm host next-research
→ ChatGPT/Grok web research
→ dcm host evidence-import
→ dcm host coverage
→ repeat research/import until coverage state is explicit
→ dcm host forecast
→ dcm host report
→ freeze
→ later: dcm host settle
→ learning sidecars
```

The Python engine never fabricates web research. The host never computes model probabilities itself.

## Required console entrypoints

The package must expose both:

```bash
dcm-host ...
python -m dcm.chat ...
```

They must be aliases over one implementation.

### 1. Runtime verification

```bash
dcm-host doctor --release-manifest RELEASE_MANIFEST.json
```

Outputs machine-readable runtime identity, package version, git commit, hashes, supported SportPlugins, provider capabilities, cache status and hard blockers.

### 2. Prepare HAR

```bash
dcm-host prepare \
  --har /mnt/data/board.har \
  --cutoff-from-capture \
  --run-root /mnt/data/dcm_runs
```

Required outputs:

- run_manifest.json
- board.json
- accounting.json
- subject_offer_sets.json
- research_population_manifest.json
- research_dependency_graph.json
- sport_plugin_contract_registry.json
- evidence_coverage.json
- host_state.json

Every visible/captured offer is accounted before exclusion. Goblins are then excluded. Offered sides and modifier semantics are frozen.

### 3. Request the next optimized research batch

```bash
dcm-host next-research \
  --run /mnt/data/dcm_runs/<run_id> \
  --max-entities 25 \
  --max-dependent-offers 500
```

Outputs `host_research_batch.json`.

The scheduler must prioritize reusable information by dependency fan-out, information importance, freshness need, sport-plugin requirement, unresolved conflicts and expected acquisition cost. It must research reusable entities once, not one web search per prop.

### 4. Import host research

The host writes simple source observations; it does not construct DCM hashes or internal scopes.

```bash
dcm-host evidence-import \
  --run /mnt/data/dcm_runs/<run_id> \
  --input /mnt/data/host_observations.jsonl
```

Host observation minimum:

```json
{
  "sourceUrl": "https://...",
  "retrievedAt": "ISO-8601",
  "publishedAt": "ISO-8601-or-null",
  "entityRef": {"kind":"SUBJECT","id":"..."},
  "evidenceType": "HISTORICAL_PERFORMANCE",
  "data": {},
  "sourceLabel": "..."
}
```

The engine must resolve canonical entity/scope, normalize sport-specific fields, validate the cutoff, apply source-policy metadata, compute source/content/claim hashes, deduplicate, record conflicts and populate EvidenceGraph lineage.

The host must never be required to invent `source_hash`, `claim_hash`, reliability scores or internal request IDs.

### 5. Coverage gate

```bash
dcm-host coverage --run /mnt/data/dcm_runs/<run_id>
```

Returns:

- complete/partial/blocked entities;
- missing semantic fields by SportResearchSchema;
- stale evidence;
- source conflicts;
- unsupported plugin requirements;
- next recommended research batch;
- whether modeling is permitted;
- whether production selection is permitted.

Coverage means required semantics exist, not merely “a request returned something.”

### 6. Forecast

```bash
dcm-host forecast --run /mnt/data/dcm_runs/<run_id>
```

This is allowed only after explicit coverage evaluation. It executes:

FeatureStore
→ RoleState
→ ParticipationState
→ Opportunity
→ conditional Efficiency
→ Availability mixture
→ ParameterSnapshot
→ EventWorld
→ PrimitiveOutcomeLedger
→ DerivedMarket
→ P(MORE)/P(LESS)/P(PUSH)
→ uncertainty
→ line tolerance
→ grading
→ ranking
→ portfolio
→ final refresh gate
→ freeze

### 7. Report

```bash
dcm-host report \
  --run /mnt/data/dcm_runs/<run_id> \
  --format json
```

Must produce a single `chat_result.json` containing board accounting, research coverage, Top 25 ranked findings, qualified list, 0–6 card, PASS/TRAP directional preferences, probabilities, uncertainty, Reliability/DataQuality/Volatility/Fragility separately, source lineage and blockers.

### 8. Resume

```bash
dcm-host resume --run /mnt/data/dcm_runs/<run_id>
```

Must be deterministic and semantically equivalent to uninterrupted execution.

### 9. Audit

```bash
dcm-host audit --run /mnt/data/dcm_runs/<run_id>
```

Validates hashes, release identity, evidence temporal integrity, model path, selection gates and frozen forecast.

### 10. Settlement

```bash
dcm-host settle \
  --run /mnt/data/dcm_runs/<run_id> \
  --outcomes outcomes.json
```

Settlement is append-only and cannot rewrite forecast artifacts.

## Optional single-command shell

For environments with an orchestration callback/tool interface:

```bash
dcm-host run --har board.har --host-protocol jsonrpc
```

The executable may emit `RESEARCH_REQUIRED` with a batch, accept observations, and continue. It must not directly browse unless a declared host adapter supplies that capability.

## Python API

```python
from dcm.chat import HostSession

session = HostSession.prepare(...)
batch = session.next_research_batch(...)
session.import_evidence(...)
coverage = session.coverage()
forecast = session.forecast()
report = session.report()
```

The API and CLI must use identical contracts.

## Universal research depth

The Paige/Dallas/Connecticut example is a depth benchmark, not a basketball schema.

For every modeled offer the research system must be able to produce, when relevant to that sport:

### Subject
- identity and current affiliation;
- status/availability and expected participation;
- current role and role epoch;
- role-comparable historical performances;
- season, recent and context-specific performance;
- opportunity drivers;
- conditional efficiency drivers;
- workload/rest/travel/recovery context;
- teammate/lineup/depth dependencies;
- opponent/counterparty splits where statistically defensible;
- advanced metrics defined by the SportResearchSchema;
- current news/context with factual claims separated from sentiment.

### Affiliation
- roster/depth/lineup/rotation;
- injuries/availability;
- team style and opportunity environment;
- offensive/defensive or analogous efficiency;
- pace/tempo/plays/possessions/attempt environment when applicable;
- position/role matchup tendencies;
- recent and season form with schedule-strength context;
- rest/travel/schedule;
- relevant coaching/tactical changes.

### Counterparty
- same level of relevant team/participant research as Affiliation;
- defensive/offensive/interaction tendencies against the subject’s role/market;
- matchup-specific allowed/suppressed opportunity and efficiency;
- personnel expected to directly interact with the subject.

### Event
- exact event identity/start/status;
- venue/course/track/map/surface/park/rink/court;
- expected lineup/starters/participants;
- event format and segment rules;
- rest/travel/time zone;
- officials/referee/umpire when material and supportable.

### Environment
- weather/wind/temperature/humidity/roof;
- park/course/track/rink/court effects;
- altitude/surface;
- other sport-specific environmental inputs.

### MarketDefinition and Offer
- exact stat definition;
- period/segment;
- overtime/inning/set/map/round semantics;
- offered sides;
- modifier;
- reboot/DNP/push rules;
- line history and final refresh.

Not every field applies to every sport. Each SportPlugin declares applicability and requiredness. No basketball-specific term is allowed as a universal-core requirement.

## Source acquisition architecture

Create a versioned `source_catalog.json`/registry with source adapters declaring:

- sports/competitions/entities/fields covered;
- source tier and authority;
- public vs authenticated;
- structured API vs table/page/news;
- historical depth;
- advanced-metric coverage;
- expected update latency;
- rate/cost constraints;
- terms/licensing/storage restrictions;
- identifier mapping;
- parser/adapter version;
- fallback sources.

Preferred acquisition order:

1. official league/event/stat sources;
2. licensed structured provider/API when configured;
3. high-quality statistical databases;
4. authoritative team/player status sources;
5. reputable news;
6. search discovery/fallback.

No single website is a universal dependency.

## GitHub organization

Do not commit raw private HARs, cookies, tokens, API keys or large copyrighted source dumps.

GitHub should store:

- code and schemas;
- source catalog and adapter definitions;
- release manifests and hashes;
- compact normalized EvidenceClaims when licensing permits;
- content hashes/provenance even when raw content cannot be stored;
- research indexes;
- immutable run/audit manifests;
- engineering pass logs.

Use content-addressed paths for reusable research, for example:

`research_store/<sport>/<entity_kind>/<entity_id>/<asof_date>/<content_hash>.json`

Maintain indexes by entity, event, source, as-of time, schema version and content hash. Large/high-churn data belongs in an artifact/object/database layer referenced by hashes rather than Git history.

## Fresh ChatGPT acceptance gate

Production host-native operability requires a test starting with only:

1. exact DCM release wheel;
2. release manifest/hashes;
3. host contract;
4. uploaded HAR.

No source checkout, prior chat memory, fixture evidence, manually supplied player logs or hidden PYTHONPATH is permitted.

The test must prove install → prepare → host research loop → evidence import → coverage → forecast → report → freeze.

GitHub read access alone does not satisfy this gate.
