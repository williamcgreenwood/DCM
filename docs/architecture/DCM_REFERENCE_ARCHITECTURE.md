# DCM reference architecture

This document is the stable architecture index for the v3 CFB gold-standard
reference build. Python is the only forecasting engine. ChatGPT is the priority
execution host; Grok can drive the same host contract.

## Canonical semantic spine

The universal core models:

Sport → Competition → Event → Affiliation / Participant → Subject →
Counterparty → Environment → MarketDefinition → Offer.

Sports own physics through SportPlugin implementations. The CFB plugin owns
opportunity, primitive statistics, conservation identities, EventWorld
construction, MarketDefinitions, and settlement mappings. Universal research
and storage do not hard-code football assumptions.

## Runtime pipeline

HAR captures are reconciled and frozen before research. Research population and
dependency graphs fan reusable requirements into AcquisitionActions. Validated
source records become EvidenceClaims and MaterialFacts; facts become Features,
ParameterSnapshots, shared EventWorlds, primitive ledgers, market-derived
probabilities, uncertainty, grade, rank, and portfolio. The full modeled board
is retained for settlement; Top100 is a frontier view, not a shortcut.

The runtime emits content-addressed artifacts at each semantic boundary.
SQLite and indexes accelerate lookup; they are not sources of truth. Drive is
object storage when configured, GitHub stores code/contracts/manifests, and
the local run store is the legal fallback.

## Feedback and immutability

Before freeze, only lawful material evidence can invalidate affected snapshots,
worlds, probabilities, ranks, and portfolio decisions. Generic evidence does not
increment the frontier pass. After freeze, outcomes can create settlement
records, audits, challenger cells, and future-only proposals only. They cannot
rewrite the forecast, its hash, its root, or its selection.

## CFB declaration

The current branch contains the software reference path for the declared CFB
market population. Current-HAR operational acceptance, prospective calibration,
Drive credentials, and production-root certification remain open gates; this
document does not turn fixtures or CI into those facts.
