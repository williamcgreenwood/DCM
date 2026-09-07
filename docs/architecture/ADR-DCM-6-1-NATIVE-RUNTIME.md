# ADR-DCM-6-1 — Native runtime boundary for CFB/NFL

- **Status:** Accepted for implementation
- **Date:** 2026-09-07
- **Constitution:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`

## Context

The historic DCM 6.0 lineage contains an exact-v5.4.1 mount/checker used for
legacy replay. Treating unavailable historical mounted bytes as a requirement
for every new CFB/NFL run makes a new release appear blocked even when its
native canonical source is healthy. Conversely, silently substituting a new
runtime for a requested historical replay would make lineage claims false.

## Decision

1. DCM 6.1 CFB/NFL runs use the canonical, self-contained runtime installed
   from this repository's `src/dcm` package and a typed `dcm-host` interface.
2. Installation is side-effect free: no tracked virtual environment, mounted
   dependency, private run store, or machine-specific absolute path is a
   runtime prerequisite. A clean temporary environment must pass the release
   smoke test.
3. The exact v5.4.1 checker remains available solely for an explicitly
   requested legacy replay. If its required historical bytes are unavailable,
   that replay returns a typed fail-closed `LEGACY_RUNTIME_UNAVAILABLE` state.
4. A 6.1 receipt declares `runtime_family = native_6_1` or
   `runtime_family = legacy_replay`; it never relabels one as the other.
5. Raw HARs and private evidence remain outside Git. Native runtime receipts
   may publish only redacted, typed, hash-addressed summaries.

## Consequences

The 6.1 program can close software and current-HAR operational gates on its
own canonical source. It does not retroactively certify old replay output,
prediction, calibration, or production root. `LR000000` and `NONE` remain in
force. This ADR supersedes no legacy provenance rule.
