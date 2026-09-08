# PROGRAM STATUS

- **Constitution:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`
- **asOf:** 2026-09-08T08:19:14+00:00
- **canonical main:** `8044c459de29fe9c92db79906682fffd8dce6435`
- **LR:** `LR000000`
- **predictiveClaim:** `NONE`
- **productionRootCertified:** false
- **hostPerformanceCertified:** false
- **CFB operational:** PARTIAL — last recorded run is `AWAITING_FRONTIER_RESEARCH` on `RUN_d3271703636992cc`; no operational completion is claimed by this status readback
- **recommendationEligible:** false

## Last recorded operational run

The run record below is retained as the latest redacted operational evidence. It was
not reopened from this clean documentation worktree, so it is not a proof of current
live-board freshness or completion.

- Run ID: `RUN_d3271703636992cc`
- HAR SHA-256: `72f75ec7ee32035b5e5863e1a61a688350b49ca6c94da091437f5368a41ec5e2`
- Cutoff: `2026-09-06T15:30:00Z`
- Playables: 1
- Coverage: 450/484

## Verified repository readback

- `main` was read back at `8044c459de29fe9c92db79906682fffd8dce6435`.
- The NFL league-keyed research-contract increment is already merged in PR #57 and
  recorded as `DCM61-08: VERIFIED`; it must not be duplicated.
- PRs #60, #61, #62, and #63 are also in the current first-parent history.
- `main` is protected and requires the `python-dcm` check; this pass found no open PR
  before its own implementation branch was created.
- The local startup gate passed `doctor`, `compileall`, generated-inventory check,
  policy validation, and whitespace validation. The configured runtime did not provide
  `pytest`, so the full pytest suite remains a separately recorded tool-availability
  limitation.

## Next

Use a verified current run/checkpoint and permitted current evidence for the remaining
external CFB/NFL gates. Do not restart the private HAR from this checkout, fabricate
operational evidence, or publish a final forecast, Top100/Top25, freeze, settlement,
predictive claim, production-root certification, or host-performance certification
without the corresponding receipts.

```bash
python -m dcm.chat next-research --run <RUN_ROOT>/runs_kickoff/RUN_d3271703636992cc --workspace <WORKSPACE>
```
