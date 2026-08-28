# DCM v6 — ChatGPT Master Prompt
## Ask for a 0–100 / 10-per-section implementation blueprint that Grok will build

Copy everything between BEGIN PROMPT and END PROMPT into a new ChatGPT Work project chat.
Attach at minimum:
- DCM v6.0.0 Master Engineering Blueprint
- DCM Computational/Algorithmic Optimization Blueprint v2
- ADR-V6-001
- both algorithm/rules workbooks if available
- this prompt file

If an attachment is missing, mark that section UNVERIFIED and still specify the build.

---

BEGIN PROMPT

You are the lead staff architect and release engineer for Pillars DCM v6.0.

Your only job in this conversation is to produce a **complete, implementable, scored build bible** that another coding agent (Grok, build mode) will execute **start to finish** in a Linux workspace.

Do **not** write the entire production source tree in this reply. Do write everything that agent needs so it does not have to invent architecture: exact files, classes, function signatures, schemas, configs, tests, hashes, fail-closed codes, phase order, and acceptance gates.

If you omit a section, score that section 0. The target is **10/10 on every section**. If you cannot reach 10 because evidence is missing, still specify the artifact and mark the gap UNVERIFIED rather than skipping the section.

════════════════════════════════════
0. NON-NEGOTIABLE LAW
════════════════════════════════════

- Predictive-superiority claim: NONE. LR stays LR000000 until future-only proper scores promote it.
- Software version ≠ Learning Revision.
- Green Goblin: constructor veto. Analytics may score; selection may not.
- Empty card is legal. Six is not a fill target.
- Offered sides only.
- Shared EventWorld → immutable PrimitiveStatLedger → f(ledger, definition_version) for every market.
- Opportunity separate from efficiency.
- Conservation before markets. Illegal worlds never reach projection.
- Settlement is Administrative → Comparison → Economic. max(LB, MG), never sum.
- Tie ≠ DNP ≠ Reboot. Ties stay in eligibility set. DNP/Reboot remove and can same-team-refund.
- Displayed payout hash is the contract. Do not infer multipliers from published 6-pick tables.
- Unknown platform rule → UNRESOLVED, never nearest-match, never WIN.
- Tracking (Statcast, NGS, SportVU, Hawk-Eye) is EvidenceGraph only, not primitives.
- WAR / Strokes Gained / vendor AI are not primitives and not PrizePicks markets.
- Official PrizePicks pages outrank commentary. Current CFB reboot is CFP Playoff only + named list + MORE + 1H leave + no 2H; not bowls; not regular season. NFL reboot is regular+post, not NFLP; defense excluded; K/P only if active with zero kick/punt. MLB batter reboot is MORE + ≤2 PA; pitchers excluded.
- Optimization may not weaken any correctness gate. “Faster” without measurement is not optimized.
- ChatGPT Chat / Work are operators. The production runner is a portable host. The blueprint must support all three, not pretend Chat is the host.
- Lifecycle states only: DESIGNED | AUTHORIZED | IMPLEMENTED_STANDALONE | INTEGRATED | REGRESSION_VERIFIED | RELEASE_ACCEPTED. Ban “done,” “live,” “canonical-adjacent” as status.

Declared hashes (verify bytes if attached; otherwise label DECLARED_UNVERIFIED):
- Canonical v5.4.1 source SHA-256: bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474
- Canonical ledger SHA-256: a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a
- Phase B/C schema SHA-256: 6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22
- PrizePicks snapshot: PRIZEPICKS_PLAYER_PICKS_2026-08-25_V1
- Optimization blueprint original SHA-256: 5316faca8580500d0e23474651905044ac8030c5b5ccd572532b6a1fba18a89d
- WSAB reconstruction schema (NOT the freeze): 08be9307caaa2bff6ca0e705650e47869d52aa79fd47e60aa35a371b4e95b02f

If v5.4.1 bytes are absent in the builder’s workspace, specify a **standalone-safe v6 tree** plus an explicit rebase seam. Do not invent v5 source.

════════════════════════════════════
1. WHAT THE BUILDER WILL ACTUALLY DO WITH YOUR BIBLE
════════════════════════════════════

Grok build mode will:
1. Create the repo layout you specify under a workspace artifacts folder.
2. Implement modules in the phase order you give.
3. Write tests and run them.
4. Produce configs, rule tables, fixtures, a HAR adapter interface, Chat/Work operator files, and host runner stubs.
5. Stop at any UNVERIFIED official-rule or missing-baseline gate rather than guessing.

Your blueprint must be executable by a coding agent that has:
- a Linux sandbox with Python
- optional attached files
- no guarantee that canonical v5.4.1 is mounted
- no guarantee of a multi-hour host
- ability to create .py, .json, .xlsx, .docx, tests

Design the first buildable slice so it runs **without** v5.4.1, and the next slice so it **rebases onto** v5.4.1 when hashes verify.

════════════════════════════════════
2. REQUIRED OUTPUT SHAPE — 20 SECTIONS, EACH SCORED 0–10
════════════════════════════════════

Write every section below, in order. At the end of each section include:

```
SECTION SCORE: n/10
MISSING FOR 10: <one line or NONE>
GROK BUILD ORDER IN THIS SECTION: <exact files to create, in order>
```

At the end of the whole document include a score table summing /200 and a “Grok Sprint 0–8” checklist.

### S00 — Executive build contract
One page. What gets built in Sprint 0 vs later. What is FAIL CLOSED. What ChatGPT Project will contain. What the host owns. The single user story to satisfy first:

“Source lives in a project folder. User drops current.har. Runner produces RUNS/<id>/{board,card_or_empty,blockers,hashes,checkpoint}. Chat prints only Run Integrity + CARD/EMPTY + paths.”

State honestly whether that user story is Sprint 0 (only if HAR ingest exists) or Sprint 3+.

### S01 — Repository layout
Full tree, every directory, every file name. Include:

```
DCM_v6/
  INSTRUCTIONS_CHAT.md
  INSTRUCTIONS_WORK.md
  INSTRUCTIONS_HOST.md
  SOURCE/
  RULES/prizepicks/<snapshot>/
  INBOX/current.har
  RUNS/
  STATE/
  CACHE/
  FIXTURES/
  PERFORMANCE/
  RELEASE/
```

Mark each file: SPRINT 0 | SPRINT 1 | LATER | HOST-ONLY.

### S02 — Frozen contracts and schemas
Exact dataclasses / JSON schemas for:
EventWorldSet, EventWorld, PrimitiveStatLedger, ConservationRule, MarketDefinition, WorldProjectionResult, EntryContract, EntryPickContract, ParticipationFacts, WorldLineupOutcome, LineupSettlement, EvidenceClaim, NodeKey, NodeState, RunCheckpoint, BlockPlan (research-only).

Field lists, types, which fields enter content_hash (exclude wall-clock created_at), fail-closed enums.

If Phase B/C original JSON is not attached, specify a reconstruction inventory that adds **zero new common types**, and a verify_schema_hash() that fails closed if bytes ≠ 6e78dacc….

### S03 — Content-addressed DAG
Node types, key formula, state machine, descendant invalidation table (line-only / status / weather / rule-version / unchanged). Checkpoint schema matching Optimization Blueprint §18. Atomic write: temp + validate + rename.

### S04 — Sport plugin envelope
How a sport registers without minting common-schema classes. Appearance atom payload inside OpportunityState. Required plugin functions:

```
appearance_process_for(...)
build_world(...)
materialize_ledger(...)
evaluate_conservation(...)
project_market(...)
participation_facts_adapter(...)
```

### S05 — Basketball plugin (LIVE doctrine, fixture-safe)
Primitive list, identities (2PA=FGA−3PA, FGM=2PM+3PM, REB=OREB+DREB, PTS=2·2PM+3·3PM+FTM, PRA derived), reboot/DNP row for NBA and WNBA, tests. Do not rewrite a missing live v5 basketball registry; provide a minimal fixture module plus an integration seam.

### S06 — Football plugin NFL + CFB (IMPLEMENT NOW)
Primitives, identities, non-identities (Σ snaps ≠ plays), opportunity vs efficiency, appearance atoms (play, snap, target, carry, dropback, K/P attempt).

Official platform map, exact predicates:
- board_id
- game_phase ∈ {REGULAR, POSTSEASON, CFP_PLAYOFF, BOWL, PRESEASON, UNKNOWN}
- left_first_half, no_second_half_return, achieved_before_exit
- CFB hashed official qualifying list + retrieval URL + as-of stamp (include the 44 names from prizepicks.com/reboots retrieved 2026-08-27 if that list is in context; do not use WSAB fixture IDs as production)
- NFL defense excluded; K/P active + zero attempt path before stat allowlist
- NFLP / partial boards never reboot
- combo-square OR
- LESS never reboots

List every function and every test file.

### S07 — MLB plate-appearance design (code later, specify now)
State S, PA identity, H/TB identities, path-heavy vs aggregable markets, official batter ≤2 PA reboot, pitcher exclusion, two-way split, spring/ASG fail-closed. Exact modules to create **after** football official predicates are green. No new common-schema class named PlateAppearance unless you prove the frozen schema cannot hold the payload.

### S08 — All-other-sports horizon
One table: soccer, tennis, golf, cricket, UFC, NHL, CFL, AFL, LAX, handball, esports, OTD.
Columns: appearance atom, identities, PP reboot (YES official / NO PAGE → FAIL CLOSED), DNP note, DCM class, first file to create when authorized.
Do not emit production registries for these in Sprint 0–3.

### S09 — Higher/Lower law
The single derivation algorithm in 8 numbered steps. Grade vocabulary PLAYABLE / LEAN / PASS / TRAP. Reliability, fragility, OOD, false-sign, Demon cushion as separate numbers. Forbidden substitutes.

### S10 — PrizePicks rule tables (compiled)
Compiled lookup key:
Platform + EntryType + League + Market + RuleVersion + Situation
JSON table files for DNP, Reboot, Tie, same-team refund, 2-pick refund, MG fixture companion (labeled FIXTURE not live display), Leaderboard weights, stack 0.95 override, max(LB,MG).
Unknown key → UNRESOLVED.
How EntryContract captures payout_display_hash.

### S11 — HAR ingest and the Project user story
Specify the adapter:
HAR bytes → bounded decode → normalized board rows → MarketDefinition join → offered sides → INBOX/current.har contract.

If v5 HAR decoder source is not attached:
- specify the interface and a **synthetic HAR fixture format** Grok can implement now
- specify the rebase points onto v5 decoder when bytes verify
- specify size gates: tiny / small / typical / too-large-for-chat → host handoff command

Never require pasting HAR into chat.

### S12 — Runtime pipeline
Exact call graph from inbox HAR (or synthetic board) to RUNS/<id>/ outputs.
Five compute tiers. Online stats vs retain-all-worlds. Common random numbers for line surfaces. Adaptive stop rules. Sparse dependence edges only.
Planner and Governor: interfaces + decision tables now; host implementations marked HOST-ONLY.

### S13 — Chat / Work / Host split
Three instruction files, full text.
Chat: thin operator, output budget, token-pressure procedure.
Work: project cockpit, Performance_Demo.json allowed, Performance_Final.json forbidden.
Host: DAG, RSS, process pools, 2× board, interruption suite.
Trust boundary for hashes (VERIFIED vs DECLARED_UNVERIFIED).

### S14 — Optimization Blueprint v2 mapping
Table: v2 §§1–24 and original A–N → module → sprint → proof artifact.
List every §22 filename. State which Grok can create as STUB vs DEMO vs FORBIDDEN-WITHOUT-HOST.

### S15 — Storage
sqlite portable runtime store schema (tables, keys, indexes). XLSX is audit export only. Reconciliation hash. No required external DB.

### S16 — Tests
Complete test matrix. Minimum:
- conservation identities + corruption
- Goblin veto
- offered-sides
- empty card
- NFL reboot matrix (LESS, 1H, 2H return, defense, K/P zero, NFLP, partial board, already-cleared MORE)
- CFB matrix (regular / bowl / CFP / unlisted player / listed player)
- MLB design tests as skip/xfail until coded
- settlement accounting identities
- max(LB,MG)
- payout>0 ≠ net>0
- hash stability (no created_at in content hash)
- DAG invalidation
- checkpoint resume on a tiny fixture
- synthetic HAR → board row count identity
Mark each test file path.

### S17 — Sprint plan Grok will execute
Sprint 0: repo + contracts + hashes + fail-closed enums + operator md files.
Sprint 1: football physics + conservation + tests.
Sprint 2: compiled rule tables + settlement E2E + official CFB/NFL predicates.
Sprint 3: synthetic HAR adapter + RUNS/ writer + Chat output contract.
Sprint 4: DAG + checkpoints + descendant invalidation on fixtures.
Sprint 5: basketball fixture path through same pipeline.
Sprint 6: sqlite store + claim store + token/run integrity writer.
Sprint 7: MLB PA modules as DESIGNED stubs + tests that xfail until authorized.
Sprint 8: host harness stubs + Performance_Demo on fixtures only.

For each sprint: files created, tests run, exit criteria, forbidden work.

### S18 — ChatGPT Project pack
Exact files the user copies into a ChatGPT Project today, and the one user message they send after dropping a HAR.
Include the refusal when SOURCE lacks a real HAR runner.

### S19 — Risks, anti-patterns, document-drift control
Lifecycle metadata JSON. How a future chat is forbidden from promoting IMPLEMENTED_STANDALONE to RELEASE_ACCEPTED.

### S20 — Acceptance scorecard
Copy Part I gates from the dual-build review: path + hash + metric or it is not PASS.
Add a column “Grok can prove in sandbox? YES/NO/PARTIAL.”

════════════════════════════════════
3. STYLE
════════════════════════════════════

- Prefer tables, signatures, JSON examples, file paths.
- Every function named with args and return type.
- Every fail-closed code named.
- No motivational filler.
- No “world-class” / “10/10 predictive” language. 10/10 means section completeness of the bible, not model skill.
- If you start running out of space, finish the current section’s SCORE + GROK BUILD ORDER, then continue from the next section on the following message without rewriting earlier sections.
- After all 20 sections, print:

```
BIBLE SCORE TOTAL: /200
SECTIONS BELOW 10: ...
FIRST GROK COMMAND: ...
```

Begin with S00.

END PROMPT
