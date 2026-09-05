# DCM v6 Production Hardening Status — 2026-08-28

Branch: `chatgpt/v6-production-completion-20260828`

This branch completes the code paths that were previously fixture/generic/development-only while preserving LR000000 and predictive claim NONE. It does **not** claim chronological predictive validation or host performance certification.

| Area | Branch state |
|---|---|
| HAR | Snapshot history + as-of cutoff + transition audit; missing offered side fails closed |
| Research | Fixture provider is engineering-only; production FileProvider validates temporal/source/content hashes |
| Evidence | Structured PLAYER/TEAM/EVENT/MARKET claims drive parameter snapshots |
| Opportunity | Explicit evidence-derived distributions with shrinkage for supported families |
| Efficiency | Separate evidence-derived efficiency parameters with shrinkage |
| Event worlds | Evidence-parameterized shared primitive worlds; composites derive from same draw |
| Ranking | Evidence-safe probability + posterior-aware score/top-K stability; calibration remains inactive until earned |
| Portfolio | Unique player, event/team caps, composite overlap, shared dependency and hard failure-path controls |
| Freeze | As-of immutable board/forecast artifacts; production gate requires canonical v5.4.1 + canonical Phase B/C schema |
| Settlement | Postgame immutable forecast settlement/audit sidecar; platform settlement remains separate exact adapter |
| Learning | Append-only settlement/audit/patch proposals; no automatic LR promotion |
| Optimization | Adaptive simulation and stage instrumentation implemented; host certification remains pending measured runs |

## Root-of-trust gates

Production selection requires all of:

1. Exact v5.4.1 source SHA-256 `bd1fb433d5f82d3812e453c30edcbb67db11b20f60e43cf50424c45a7c2ff474`.
2. Exact v5.4.1 ledger SHA-256 `a9956ef1d231eb37ea5898b5145d660b986b68ee4dc6cfbd5c43fed59064c29a`.
3. Exact canonical source bundle reconstruction with every embedded file verified.
4. Exact Phase B/C frozen schema SHA-256 `6e78dacc19843338643bdcabc7477fd3ce2dd065da1e9629646dacc21cdb1f22`.
5. Non-synthetic research evidence complete for the board.
6. Per-player opportunity/efficiency support and verified market definition.
7. Offered side explicitly verified.
8. Market capability production-supported.
9. PLAYABLE analytical gates, including stronger Demon thresholds.
10. Portfolio dependency constraints.

If any gate fails, the run may still be modeled/audited but production selection is prohibited.

## Deliberately not claimed

- LR promotion: **NO — LR000000**
- Predictive superiority: **NONE**
- Chronological calibration active: **NO, until sufficient unseen settled forecasts exist**
- Host performance certified: **NO**
- Frozen Phase B/C reconstruction substituted for canonical bytes: **NO**
