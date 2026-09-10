# DCM research funnel v1

Status: implementation cut; research-only.  This is not a probability model,
an outcome-trained learner, or a production-card certification.

## Boundary

The HAR is a price-board catalogue.  It identifies offers and their observed
side metadata; it does not say that a player will play, how many opportunities
they will receive, or what the settled result will be.  The funnel therefore
allocates research attention without assigning a hit probability:

```text
raw board
  -> structural gates
  -> same-line merge and primary-line selection
  -> deterministic quota shortlist (at most 24)
  -> game packets for external research
  -> typed evidence import and field coverage
```

`dcm.chat research-funnel --run <RUN_ROOT>` writes four local receipts:
`gates.json`, `leftover.json`, `shortlist.json`, and `research_funnel.json`.
Only sanitized metadata, counts, hashes, and row identities belong in a
remote receipt.  Raw HAR bytes, headers, cookies, response bodies, and tokens
remain local quarantine.

## Gate law

The default gate accepts only `pre_game`, `STANDARD`, full-game, non-combo,
single-stat rows with a resolved projection/player/event/league, a numeric
line, and a populated `allowedWagerTypes`.  Live or suspended rows, duration
boards, goblins, demons, fantasy/TD/longest markets, malformed rows, and
unknown sides receive a typed exclusion.  A populated allowed-wager field is
authoritative; contradictory convenience booleans never create a side.

Lower is legal only for NFL and MLB in this cut.  CFB and other leagues can
produce `OVER_ONLY`, never an invented Lower.  Every input row is accounted for
as a legal primary, alternate-line duplicate, same-line merge, or gate
exclusion.

## Attention allocation

The shortlist is a deterministic greedy sampler, not a ranker.  It reserves
the SF@LAR target, protects must-include rows supplied by an independent injury
or consensus screen, repairs two-way/game/league floors, then fills by a
structural key (game time, legal side class, volume-stat family, league,
identity).  Hard caps are visible in the receipt: at most 24 distinct players,
2 players per game, 14 NFL rows, 8 over-only rows, and the configured minimum
diversity floors.  Every legal row not selected is retained in `leftover.json`
with its first blocking reason; it is never silently dropped.

The implementation records `ALG-GROUP-001`, `ALG-INDEX-001`, `ALG-SORT-001`,
and `ALG-SCHED-003` as the applicable constitution paths.  DuckDB, ANN search,
and machine learning are intentionally absent from this boundary.  They may
be benchmarked later over sanitized snapshots only after a real evidence packet
has imported successfully.

## Research boundary

The shortlist is clustered by event and handed to an external source-acquisition
tool as bounded packets: event context, two teams, and surviving listed players.
The packet must return typed values or `UNCERTAIN`, with source URL, retrieved
time, valid time where applicable, and field-level provenance.  Missing
starters/inactives remain `UNCERTAIN`; venue or schedule facts may still import.
An uncertain role or opportunity blocks a production card but does not turn an
empty source response into success.

`predictiveClaim` remains `NONE`, `productionSelectionPermitted` remains false,
and outcomes are not read by the funnel.  Official post-game outcomes belong
to a separate after-the-fact settlement/audit stage.
