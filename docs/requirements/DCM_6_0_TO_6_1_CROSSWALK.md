# DCM 6.0 to 6.1 release crosswalk

The v1 requirement ledger remains the source of detailed historical
requirements. DCM 6.1 does not rewrite its status. This release control layer
groups the active CFB/NFL finish path so the work is deliverable in coherent
PRs rather than treated as a single undefined rebuild.

| 6.1 control | Existing requirements / evidence | 6.1 boundary |
|---|---|---|
| `DCM61-04` native runtime | `REQ-WHEEL-031.01`, `REQ-ROOT-040.01` | Canonical native 6.1 runtime; legacy replay stays separate. |
| `DCM61-05`–`07` runner/accounting/authority | `REQ-HAR-004.*`, `REQ-SIDE-005.*`, `REQ-HOST-009.*` | Typed receipts and true platform ownership. |
| `DCM61-08`–`10` research/reuse | `REQ-ADAPT-010.01`, `REQ-EVID-011.*`, `REQ-PERS-028.01`, `REQ-REC-029.01` | CFB/NFL routing, source health, resumability. |
| `DCM61-11` CFB acceptance | `REQ-CFB-OPP-013.01` through `REQ-FRZ-023.02` | Current-HAR acceptance, not a synthetic claim. |
| `DCM61-12` NFL acceptance | Universal path plus league-keyed NFL contract | Same receipt/gates as CFB. |
| `DCM61-13`–`16` model/freeze/learning | `REQ-PROB-018.01`, `REQ-UNC-019.01`, `REQ-RANK-020.01`, `REQ-FRZ-023.*`, `REQ-LEARN-026.01` | No predictive promotion before prospective proof. |
| `DCM61-18`–`20` release | `REQ-PROMO-032.01`, `REQ-FINAL-042.01` | CI, protected promotion, explicit release state. |

P380X remains a candidate SignalOperator catalog compiled to an active DAG; it
is not a reason to copy donor engines or create a second runtime.
