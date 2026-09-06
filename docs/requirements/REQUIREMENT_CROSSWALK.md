# Requirement crosswalk (v1)

Generated against `main` @ `c01724382f478ddb4221a098e37e98f55fcd9ffe` (PR #35 `src/dcm` relocate).
Canonical machine ledger: [`REQUIREMENT_LEDGER.v1.json`](./REQUIREMENT_LEDGER.v1.json).

## Policy

- Normalize the handoff seed (`HANDOFF-001`…`042`) into atomic `REQ-*` IDs; parents remain grouping shells.
- Status values: `IMPLEMENTED` / `PARTIAL` / `MISSING` / `EXTERNAL` / `SUPERSEDED` / `N/A`.
- Handoff ZIP is a **read-only quarry** — never execute embedded code; never install ZIP code into `src/dcm`.
- P380X 1500+ pillars = **candidate SignalOperator catalog only**; compile-to-active-DAG rule; do **not** copy 1500 engines.

## Counts

| Scope | Count |
|---|---:|
| Total ledger records | 98 |
| Parent HANDOFF domains | 42 |
| Atomic REQ-* | 56 |
| CFB-critical atomics | 35 |
| CFB-critical open blockers | 10 |

### Atomic by status

| Status | Count |
|---|---:|
| EXTERNAL | 6 |
| IMPLEMENTED | 28 |
| MISSING | 5 |
| N/A | 1 |
| PARTIAL | 15 |
| SUPERSEDED | 1 |

### All records by status (includes parents)

| Status | Count |
|---|---:|
| EXTERNAL | 6 |
| IMPLEMENTED | 28 |
| MISSING | 5 |
| N/A | 1 |
| PARTIAL | 57 |
| SUPERSEDED | 1 |

## Top CFB closure blockers (HAR → evidence → model → card)

These atomic requirements sit on the CFB-critical path and are not yet `IMPLEMENTED`:

| ID | Status | Title | Blocker |
|---|---|---|---|
| `REQ-ID-003.02` | PARTIAL | Namesake and transfer collision handling | Live cross-source official CFB PrizePicks id map / current HAR with both fields still needed for full acceptance |
| `REQ-SIDE-005.01` | PARTIAL | OfferMetadataRecovery for offered sides | Large share of live boards still land UNRESOLVED side rows; web stats must not invent sides |
| `REQ-HOST-009.02` | PARTIAL | Source-aware host action context | Software path merged; current live CFB HAR + host-acquired evidence still required for operational closure |
| `REQ-ADAPT-010.01` | PARTIAL | Source catalog + health + fallbacks | Live adapter fetch beyond fixtures incomplete; licensed providers optional/external |
| `REQ-EVID-011.02` | EXTERNAL | Current-HAR evidence sufficiency for playable card | Current sanitized CFB HAR + host-acquired reusable evidence not supplied in this session |
| `REQ-CFB-MKT-016.01` | PARTIAL | 19 ACTIVE CFB markets + unsupported tasking | Operational acceptance of 19 markets on a current live board still pending |
| `REQ-UNC-019.01` | PARTIAL | Uncertainty decomposition; conformal inactive at LR000000 | Calibration promotion EXTERNAL until prospective settlements exist |
| `REQ-FRZ-023.02` | EXTERNAL | CFB operational freeze on current HAR | Blocked on current HAR + host-acquired evidence (REQ-EVID-011.02) |
| `REQ-LEARN-026.01` | PARTIAL | Full-population chronological settlement consumers | Prospective CFB settlements and chronological unseen evidence EXTERNAL |
| `REQ-FINAL-042.01` | EXTERNAL | Evidence-linked per-scope release receipt | CFB operational acceptance and predictive gates still open |

## Deliberately NOT copied from handoff ZIP

- P380X 1500+ pillar/engine implementations (catalog + compile-to-active-DAG only)
- original_sources/*.docx/*.xlsx/*.zip binary workbooks and donor packages as runtime code
- source_text extractions wholesale into src/dcm
- dcm_v6_workstream_ab / WSAB standalone package onto import path
- Any HAR bytes (none in handoff; never commit)
- Embedded executable code from GROK_EXECUTION_PROMPT or donor ZIPs

## Domain → atomic map (summary)

| Parent | Title | Atomic children |
|---|---|---|
| `HANDOFF-001` | Authority and baseline | `REQ-AUTH-001.01`, `REQ-AUTH-001.02` |
| `HANDOFF-002` | Source integration | `REQ-SRC-002.01`, `REQ-SRC-002.02` |
| `HANDOFF-003` | Identity | `REQ-ID-003.01`, `REQ-ID-003.02` |
| `HANDOFF-004` | Private ingestion | `REQ-HAR-004.01`, `REQ-HAR-004.02` |
| `HANDOFF-005` | Side recovery | `REQ-SIDE-005.01`, `REQ-SIDE-005.02` |
| `HANDOFF-006` | Temporal firewall | `REQ-TIME-006.01`, `REQ-TIME-006.02` |
| `HANDOFF-007` | Shared graph | `REQ-GRAPH-007.01` |
| `HANDOFF-008` | Acquisition planner | `REQ-ACQ-008.01` |
| `HANDOFF-009` | Executing host loop | `REQ-HOST-009.01`, `REQ-HOST-009.02` |
| `HANDOFF-010` | Source adapters | `REQ-ADAPT-010.01` |
| `HANDOFF-011` | Evidence sufficiency | `REQ-EVID-011.01`, `REQ-EVID-011.02` |
| `HANDOFF-012` | Parameter compiler | `REQ-PARAM-012.01` |
| `HANDOFF-013` | CFB opportunities | `REQ-CFB-OPP-013.01` |
| `HANDOFF-014` | CFB efficiency | `REQ-CFB-EFF-014.01` |
| `HANDOFF-015` | CFB conservation | `REQ-CFB-CONS-015.01` |
| `HANDOFF-016` | CFB market coverage | `REQ-CFB-MKT-016.01` |
| `HANDOFF-017` | CFB special teams | `REQ-CFB-ST-017.01` |
| `HANDOFF-018` | Probability | `REQ-PROB-018.01` |
| `HANDOFF-019` | Uncertainty | `REQ-UNC-019.01` |
| `HANDOFF-020` | Full board ranking | `REQ-RANK-020.01` |
| `HANDOFF-021` | Frontier refresh | `REQ-FRNT-021.01` |
| `HANDOFF-022` | Portfolio | `REQ-PORT-022.01` |
| `HANDOFF-023` | Immutable freeze | `REQ-FRZ-023.01`, `REQ-FRZ-023.02` |
| `HANDOFF-024` | Algorithm registry | `REQ-ALG-024.01` |
| `HANDOFF-025` | Measured performance | `REQ-PERF-025.01` |
| `HANDOFF-026` | Learning consumers | `REQ-LEARN-026.01` |
| `HANDOFF-027` | Advanced challengers | `REQ-CHAL-027.01` |
| `HANDOFF-028` | Persistence | `REQ-PERS-028.01` |
| `HANDOFF-029` | Recovery | `REQ-REC-029.01` |
| `HANDOFF-030` | Donor integration | `REQ-P380X-030.01`, `REQ-P380X-030.02` |
| `HANDOFF-031` | Clean wheel | `REQ-WHEEL-031.01` |
| `HANDOFF-032` | Protected promotion | `REQ-PROMO-032.01` |
| `HANDOFF-033` | Tennis | `REQ-SPORT-033.01` |
| `HANDOFF-034` | UFC and boxing | `REQ-SPORT-034.01` |
| `HANDOFF-035` | Soccer leagues | `REQ-SPORT-035.01` |
| `HANDOFF-036` | MLB | `REQ-SPORT-036.01` |
| `HANDOFF-037` | WNBA and NBA | `REQ-SPORT-037.01` |
| `HANDOFF-038` | Hockey | `REQ-SPORT-038.01` |
| `HANDOFF-039` | Remaining declared sports | `REQ-SPORT-039.01` |
| `HANDOFF-040` | Root authenticity | `REQ-ROOT-040.01` |
| `HANDOFF-041` | Predictive promotion | `REQ-PRED-041.01` |
| `HANDOFF-042` | Final acceptance | `REQ-FINAL-042.01` |

## Resume notes for agents

1. Read this crosswalk + `REQUIREMENT_LEDGER.v1.json` before inventing a parallel ontology.
2. Prefer fixing CFB-critical `EXTERNAL`/`PARTIAL` blockers over new sports.
3. Keep `LR000000` / predictive `NONE` / `optimizedDcm60Claim=false` until earned.
4. Optional loader: `dcm.governance.requirement_ledger`.
