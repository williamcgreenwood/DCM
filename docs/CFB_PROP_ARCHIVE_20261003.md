# CFB Player-Prop Evidence Archive: 2026-10-03

## Source boundary

`Photo(5).pdf` is the immutable board source. Screenshot availability is not a current line/price claim. OCR is a searchable evidence index only; no forecast can be released until the player, market, side, line, and current board availability are confirmed.

## Intake artifacts

The Drive packet contains a 73-page PDF, 73 page-level OCR records, a 137-subject player/event manifest, and a content-hash receipt. The artifacts use the run ID `cfb-player-props-2026-10-03-source-intake-v1`.

## Protocol gates

1. Canonicalize and deduplicate by `(sport,event,player,market,direction,line,observation_time)`.
2. Run event/team acquisition before player searches and fan facts out to all dependent offers.
3. Keep a five-minute minimum research/calculation queue. Time passing never turns missing evidence into a playable forecast.
4. Require current starter status, role/opportunity, opponent context, pace/script, weather/venue, current price, and authoritative evidence.
5. Store missing data as `MISSING`; do not infer it favorably.
6. Freeze only evidence-backed current offers and retain lineage to raw source pages.

## Persistence

Drive stores the immutable research objects and receipts. Git stores this contract and the reproducible local archive builder. Raw screenshots, OCR payloads, mutable prices, and bulky research packets are intentionally excluded from Git.
