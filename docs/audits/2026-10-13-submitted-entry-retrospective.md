# 2026-10-13 submitted-entry retrospective

**Classification:** Post-event audit only; not a DCM-issued forecast or backtest.
**Source:** user-provided `101326audit.pdf`, SHA-256 `38da1fcabc9849b750f3cfeee43b4490e0885fca0a8f97b94010bb92a6a68c01` (kept outside Git).
**Evidence cutoff:** the screenshot capture/cutoff could not be independently established from the PDF alone. No postgame information is admissible to a pregame replay.

## What the saved screenshots support

The screenshots show historical trends and an entry interface; they do not establish a calibrated DCM probability, a validated pick, or the counterfactual result for the opposite side.

| Saved entry (as supplied in the audit request) | Result | What the existing elements could have done before the game | What the misses do not justify |
|---|---|---|---|
| Anthony Carrie MORE 12.5 rushing attempts | 10, loss | A trend-disagreement gate could have compared the exact 12.5 line with the screenshot's away-only claim that Carrie stayed below 11.5 in 6 of 7 road games, average 10.1 (PDF page 5). It could have raised a conflict/fragility blocker pending role, event, and cutoff validation. | It could not certify LESS from this one small and possibly non-comparable trend. The later 10 attempts do not make LESS a valid pregame inverse. |
| Caden Creel LESS 29 pass attempts | 22, win | The packet contains unrelated Creel passing-yard, completion, and fantasy-score trends (PDF pages 9 and 11); those are not interchangeable with attempts. Exact-market history and the cutoff-safe distribution were needed. | This win does not validate a LESS model or authorize borrowing another market's trend. |
| Deondre Johnson MORE 11 fantasy score | 19.3, win | Exact fantasy scoring version, role/opportunity history, and calibrated joint probability would be required. The screenshot's receiving-yard claim is not a fantasy-score forecast. | A winning realization does not validate the pick's probability. |
| James Resar MORE 2.5 receptions | 5, win | Exact target/route role and opponent-adjusted reception history, plus calibrated probability, were needed. | A win does not prove that the model had evidence or that the selection was sound. |
| JJ Kohl MORE 0.5 interceptions | 0, loss | The screenshot shows passing-touchdown, completion, and attempt trend cards (PDF pages 7, 9, and 11), not a verified interception distribution. A supported interception model could have abstained for missing market-specific labels. | The result alone cannot support LESS; the exact opposite side's offer and a calibrated interception forecast are not established. |
| Maguire Anderson LESS 14.5 fantasy score | 33.8, loss | PDF page 55 shows the exact 14.5 fantasy-score line and five displayed scores: 16.7, 27.7, 21.9, 14.8, and 2.9 (mean 16.8). Four of five exceed the line. A contradiction/unsupported-inverse gate could have blocked LESS absent independent cutoff-safe role/regime evidence. | Five observations do not prove MORE, and the screenshot does not establish the scoring definition, offer capture time, exact selection state, or a calibrated probability. The 33.8 result cannot be used to tune the archived forecast. |

The request records a 3–3 result. The ticket was user-submitted; DCM did not freeze it. A complete six-leg payout EV cannot be reconstructed without the exact entry contract, payout table, settlement/reversion treatment, calibrated joint outcomes, and contemporaneous offer snapshot.

## Retrospective conclusion

The missing safeguards could have flagged at least two risky cases for review: Carrie MORE conflicted with the more specific road-only trend in the screenshots, while Anderson LESS conflicted with four of five displayed scores at the exact line. This supports *abstain/block pending evidence*, not “the model would have caught the loss” and not an automatic inverse. For Kohl and the other rows, the supplied trend cards do not provide exact-market calibrated probabilities. No capability can reliably remove every losing prop; calibration, opportunity/role state, exact market definitions, dependence, and payout rules determine whether the engine can make a defensible selection at all.

## Reproducible test-run status

The repository's advanced execution test suite was run with synthetic software fixtures and verifies the seven capability receipts and explicit missing-input blockers. It is not a replay of this ticket. The screenshot PDF itself was not ingested into the production ResearchStore, so no production run receipt is claimed. The 2026-10-14 mixed-props PDF is 211,036,978 bytes; Drive metadata is readable, but raw transfer failed in this session. Its offers, pages, and candidate claims therefore remain unverified test inputs.
