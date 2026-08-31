# Universal Research Acquisition Specification

## Objective

P1 must gather enough current and historical evidence to model every eligible offer while minimizing duplicated host work. Named player/team examples define desired depth only; they never define universal vocabulary.

The host (ChatGPT/Grok) performs web/tool acquisition. The DCM determines what must be researched, validates/normalizes observations, measures semantic coverage, and reuses evidence across every dependent offer.

## Three-layer research model

### Layer A — universal entity core

Every run can reason about:

Sport, Competition, Event, Affiliation, Subject, Counterparty, Environment, MarketDefinition, Offer.

The universal core may not require basketball/football/baseball-specific nouns or metrics.

### Layer B — SportResearchSchema

Each SportPlugin declares, for each entity kind:

- required fields;
- optional/high-value fields;
- freshness class;
- preferred source capabilities;
- canonical units/definitions;
- role-comparability keys;
- opportunity fields;
- efficiency fields;
- environment fields;
- matchup fields;
- market-triggered expansions;
- minimum semantic coverage for MODEL, QUALIFIED and PLAYABLE states.

### Layer C — market-triggered expansion

Do not fetch every imaginable stat for every subject on every run. Gather a deep reusable subject/affiliation/event core, then expand only the stat families that can affect offered markets.

Broad historical/advanced data may be cached for future reuse, but current-run hydration must be relevance-driven.

## Required research packets

### SubjectResearchPacket

When applicable:

- canonical identity, aliases and current affiliation;
- current status and availability probabilities/state;
- expected participation/workload;
- current role and role epoch;
- role-comparable historical event logs;
- season, recent and context-specific windows;
- opportunity inputs;
- efficiency conditional on opportunity;
- advanced metrics relevant to offered markets;
- direct/role-similar counterparty history when statistically defensible;
- workload/rest/travel/recovery;
- lineup/depth/teammate dependencies;
- coaching/tactical role changes;
- factual current news and separately labeled sentiment/context;
- source lineage and as-of timestamps.

### AffiliationResearchPacket

When applicable:

- roster/depth/rotation/lineup;
- injuries/suspensions/availability;
- expected starters/participants;
- offensive/defensive or analogous team efficiency;
- pace/tempo/play/possession/attempt environment;
- opportunity allocation by role;
- matchup tendencies;
- recent/season form with strength-of-schedule context;
- rest/travel/time zone;
- tactical/coaching changes;
- market-relevant team advanced metrics.

### CounterpartyResearchPacket

Counterparty receives the same depth appropriate to its type, plus:

- suppression/allowance of the subject’s relevant opportunities;
- suppression/allowance of conditional efficiency;
- likely direct matchup personnel or interaction;
- scheme/style interaction;
- handedness/surface/line/map/role or analogous sport-specific interaction;
- vulnerabilities/strengths tied to offered market definitions.

### EventResearchPacket

- exact event identity;
- competition;
- scheduled start and current status;
- format/segment structure;
- venue/course/track/map/surface;
- expected participant/lineup state;
- rest/travel/time-zone context;
- officials/referee/umpire when material;
- event-level pace/scoring/possession/resource context.

### EnvironmentResearchPacket

- weather;
- wind;
- temperature/humidity;
- roof;
- altitude;
- park/course/track/rink/court/surface effects;
- other SportPlugin-declared environmental variables.

### MarketDefinitionResearchPacket

- exact physical/statistical definition;
- platform semantics;
- period/segment;
- overtime/extras;
- DNP/reboot/push;
- combination/composite derivation;
- units and rounding;
- valid primitive derivation.

### OfferResearchPacket

- line;
- offered sides;
- modifier;
- line history;
- capture times;
- final pre-freeze refresh.

## Acquisition scheduling

The canonical scheduler is dependency/fan-out driven.

Recommended score:

`fanout × information_importance × freshness_need × uncertainty_reduction / estimated_acquisition_cost`

Batch primarily by Event, then Affiliation/Counterparty, then Subject. A single event batch should research shared event/environment/team context once and then all unresolved subjects in that event.

The scheduler must support:

- high-priority refresh of status/lineup/weather near cutoff;
- conflict-resolution batches;
- missing-field batches;
- market-triggered expansion;
- cache reuse when still cutoff-safe and fresh;
- bounded parallel host searches;
- explicit budget/token estimates;
- stop when additional research cannot change production eligibility or material uncertainty enough to justify cost.

## Source catalog

Implement a versioned SourceAdapterRegistry/SourceCatalog. Every entry declares:

- source ID/domain;
- source tier/authority;
- sports and competitions;
- entity kinds and fields;
- public/authenticated/licensed;
- HTML/table/API/feed;
- historical depth;
- advanced-metric coverage;
- freshness/update latency;
- rate/cost constraints;
- identifier strategy;
- parser version;
- terms/licensing/storage policy;
- fallback chain;
- known failure modes.

Priority is generally official structured source → configured licensed structured provider → high-quality statistical database → official team/participant source → reputable news → search discovery/fallback.

Authenticated sources are optional capabilities. Production architecture must not silently assume ChatGPT can log into a site.

## Evidence import

Host observations are intentionally simpler than EvidenceClaims. ChatGPT/Grok supplies source, retrieval/publication time, entity reference, evidence type and extracted data. DCM code owns:

- canonical scope/entity resolution;
- units/stat normalization;
- SportResearchSchema validation;
- temporal firewall;
- source policy;
- reliability/freshness computation;
- semantic/source/claim hashing;
- dedupe/conflict ledger;
- EvidenceGraph population;
- cache identity and invalidation.

## Storage and reuse

Research should be content-addressed and immutable by as-of state.

GitHub is suitable for compact indexes, manifests, normalized claims/provenance and small reusable snapshots when licensing permits. Do not use normal Git history as a giant raw scraped-data warehouse.

Required indexes:

- by Subject/Affiliation/Counterparty/Event;
- by sport/competition;
- by source;
- by as-of time/freshness;
- by schema/parser version;
- by content hash;
- latest-safe pointer per entity/field.

High-volume historical tables should live in a queryable artifact/database/object store with GitHub manifests and hashes if/when scale justifies it.

## Completion test for P1

P1 reaches 10/10 only when a fresh HAR can produce a complete universal research population, generate optimized batches, accept real host observations, close semantic coverage for every supported SportPlugin, resolve conflicts, refresh volatile fields, populate EvidenceGraph and hand complete packets to P2 without canonical PLAYER/TEAM request semantics outside adapters.
