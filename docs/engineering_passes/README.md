# Engineering pass log contract

This directory is append-only. Every Grok, ChatGPT, Codex, human, or other coding-agent tranche must add exactly one new pass record before merge.

Filename:

`YYYYMMDDTHHMMSSZ_<agent>_<short-purpose>.md`

A pass record must contain:

- starting branch and exact starting SHA;
- ending branch and exact ending SHA when available;
- objective;
- files changed;
- functions/classes/modules added, removed, renamed or behaviorally changed;
- algorithms/formulas/contracts changed;
- tests added/changed;
- exact validation commands and results;
- benchmark deltas if performance-related;
- workstream scores changed and why;
- requirements completed;
- requirements partially completed;
- requirements attempted but not completed;
- newly discovered requirements;
- unresolved blockers with owner/type: CODE, DATA, EXTERNAL, VALIDATION, GOVERNANCE;
- compatibility shims introduced or retired;
- root-of-trust/LR/predictive/performance claim changes;
- next-pass ordered task list.

Rules:

1. Never edit an old pass record to make history look cleaner. Correct it with a new record.
2. Do not write “complete” when a path is only scaffolded, fixture-backed, shadow-only, or not runtime-integrated.
3. If code changes a status in `PROGRAM_STATUS.json` or the universal implementation matrix, the pass record must name the evidence.
4. If a pass discovers hidden work, add it to the status registry before merge.
5. CI success is evidence of software integrity only; it is not predictive validation.
