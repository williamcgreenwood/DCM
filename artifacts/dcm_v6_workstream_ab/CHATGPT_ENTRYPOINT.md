# CHATGPT_ENTRYPOINT — DCM v6 operator prefix

WHEN USER SAYS "RUN DCM" / "Final Check DCM" / "Audit DCM":

1. Read `00_READ_ME_FIRST.md` and `CHATGPT_CONTEXT_INDEX.json`.
2. Do not recursively dump the repository.
3. Execute the exact verify command in `COMMANDS.json`.
4. Inspect `CAPABILITY_SUMMARY.json` for each sport/league/market on the board.
5. HAR in `INBOX/current.har` (or attachment). Never paste raw HAR into chat.
6. Extract COMPLETE board before Goblin elimination. Account every row.
7. Research unique event → team → player once; reuse packets.
8. Process every non-Goblin row through DCM. Fail closed only after accounting.
9. Rank complete population. Persist Top100+ and full population.
10. Return compact Top 25 ranked vs Top 25 qualified. Empty card is legal.
11. Do not call Top 25 FINAL unless BOARD/RESEARCH/MODEL/RANK/FREEZE gates are true.

## Hard law

- Green Goblin: extract/analyze/settle; never production-select.
- Offered sides only.
- Red Demon: extra cushion; demotion-only.
- Never force 5/6/12 legs.
- Unknown definition/side/rule → UNRESOLVED / UNSUPPORTED_FAIL_CLOSED.
- Composites from the same PrimitiveStatLedger. Never independently sampled.
- Opportunity ≠ efficiency.
- Displayed payout is the contract. `max(LB, MG)`. LB UNMODELED without group context.
- Do not copy NFL reboot into CFB/CFL/soccer/etc.
- Software version ≠ Learning Revision. LR stays LR000000.
- Predictive superiority: NONE.
- Do not claim optimized DCM 6.0.
- v5.4.1 HAR decoder is NOT_MOUNTED until source bytes hash-verify.

## Chat output only

Run Integrity · CARD or EMPTY · essential blockers · artifact paths/hashes · next deterministic action.

If the window ends: INCOMPLETE_CHECKPOINTED with exact pending IDs. Never approximate remaining rows in prose.
