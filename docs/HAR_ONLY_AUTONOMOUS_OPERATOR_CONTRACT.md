# HAR-only autonomous DCM contract

The operator input is the supplied HAR set. DCM accepts each file, hashes it,
reads its internal HAR timestamps, runs each capture independently, and creates
a chronological mixed-sport union. A filename timestamp is metadata only; it
cannot override \`log.entries[*].startedDateTime\`.

An Insights record with an exact numeric line and \`HIGHER\` or \`LOWER\` is a
platform-observed \`InsightClaim\` and \`OfferSnapshot\` for research and candidate
generation. It is not silently discarded because the capture has no exact
\`/projections\` rows.

\`boardOfferCount=0\` has one narrow meaning: the parser found no rows from the
exact \`/projections\` board endpoint. It does not mean the HAR was empty or
invalid, and it never causes DCM or ChatGPT to request another board HAR. The
capture authority is operator-controlled: the operator may supply a newer
capture whenever they choose, but freshness is not a hidden input gate.

The durable controller is:

1. account and freeze every HAR;
2. normalize Insights claims and exact board rows separately;
3. resolve identity, event timing, market semantics, and research demand;
4. emit a bounded, sport-neutral research packet;
5. expose \`next_action.json\` with owner \`CHATGPT\` and command
   \`autonomous-resume\`;
6. validate and import ChatGPT's source-backed response;
7. recompute coverage and repeat the packet loop when needed;
8. request authoritative outcomes after final status;
9. settle the whole eligible population with exact identity and rule semantics;
10. run chronological walk-forward and calibration diagnostics;
11. rank/select/freeze only after offer revalidation, coverage, model, and
    production-root gates pass;
12. append postgame learning only from authoritative settled labels.

Every missing external fact is a typed blocker such as
\`OFFER_REVALIDATION_UNAVAILABLE\`, \`EVIDENCE_COVERAGE_INCOMPLETE\`, or
\`AUTHORITATIVE_OUTCOMES_PENDING\`. These blockers do not become operator asks,
invented probabilities, invented outcomes, or a request for another HAR.

\`PLAYABLES=0\` is therefore valid only when the receipt identifies the unmet
production gates and confirms that the research path, model path, and selector
were actually executed or durably handed off. A hard-coded zero, a missing
ChatGPT loop, a mixed-sport routing failure, or an unconditional board-HAR
requirement is a controller defect.
