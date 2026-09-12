# Outlier input contract

This document records the canonical DCM behavior for Outlier captures. It is
an input and research-safety contract, not a claim that an Outlier row is a
winning bet.

## Provider order and accounting

- The HAR adapter tries the strict Outlier shape before the PrizePicks
  JSON:API adapter. PrizePicks payloads still fall through safely because
  they do not contain Outlier `props[].outcome` records.
- Every captured outcome is retained for accounting before any modifier,
  side, target-book, market, or research gate is applied.
- The preferred target book is `PRIZEPICKS` for the existing settlement
  surface, but a normalized Outlier payload may set `targetBook` (or
  `_dcm.targetBook`) to an explicit provider. The parser never silently
  switches providers.

## Exact offer semantics

For each outcome the adapter preserves the source outcome ID, line, event,
player, market/MarketDefinition IDs, period, overtime flag, target-book offer
presence, odds, Outlier ORF/hit-rate fields, source hashes/times, and the
observed modifier.

Higher/More and Lower/Less are emitted only when the capture proves that side.
The outcome `position`/side and a target-book `outcomeAlias` are cross-checked;
conflicts become `UNKNOWN` and are not selectable. A missing target offer,
missing modifier, or malformed side remains accounted but fails closed. The
DCM never manufactures Lower from a Higher line (or the reverse).

The parser emits `allowedWagerTypes` from the observed side for a single
outcome. Same-line deduplication retains modifier, target provider, target
offer presence, period, and MarketDefinition in its key so an unavailable
target row cannot hide a Standard row and a Goblin cannot contaminate it.

## Permanent exclusions and focused research

Green Goblin is terminally excluded after accounting. It must not be modeled,
researched as a candidate, ranked, selected, placed in a card, or used as an
independent learning observation. Demon remains subject to its stricter
policy. These rules are permanent and apply regardless of input format.

For Outlier rows that survive structural gates, the modeled runner applies the
versioned `OUTLIER_PRESELECTION_V1` gate. It computes the directional model
margin in standard deviations from the offered line. A margin inside the
configured uncertainty band (default `0.25 sigma`) is held for targeted
player/matchup research. A wider margin still requires canonical evidence for
role, availability, recent usage, matchup, and the current offer before
directional selection. The gate affects eligibility only; it does not mutate
probabilities or invent research.

The run record exposes `preselection`, `preselectionPolicy`, and
`outlierPreselectionHold` in modeled/top-list rows so ChatGPT Work can request
the smallest useful research batch rather than researching every player at
the same depth.

## Learning boundary

Outlier line, side, modifier, target-book, odds, hit-rate, ORF, decision,
settlement, and slip/leg lineage fields may be appended to future observation
ledgers. Independent-leg summaries exclude correlated slip rows, require
settled outcomes, and remain challenger-only until chronological holdout
evidence promotes them. Historical patterns never override the exact current
offer, Goblin exclusion, cutoff, or research gates.
