# PROGRAM STATUS

- **Constitution:** `DCM-ALGORITHM-CONSTITUTION-v1.0.0-20260903`
- **asOf:** 2026-09-07T12:00:00+00:00
- **canonical main:** `3b80d1c1dfc5f5c1663b67735d5ed0d4a8bb0d39`
- **LR:** `LR000000`
- **predictiveClaim:** `NONE`
- **productionRootCertified:** false
- **hostPerformanceCertified:** false
- **CFB operational:** PARTIAL — `AWAITING_FRONTIER_RESEARCH` on `RUN_d3271703636992cc`
- **recommendationEligible:** false

## Active run
- Run ID: `RUN_d3271703636992cc`
- HAR SHA-256: `72f75ec7ee32035b5e5863e1a61a688350b49ca6c94da091437f5368a41ec5e2`
- Cutoff: `2026-09-06T15:30:00Z`
- Playables: 1
- Coverage: 450/484

## Next
Complete the reviewable NFL league-keyed research-contract increment, including
its generated inventory and all normal checks, before attempting an NFL
current-HAR operation.

```bash
python -m dcm.chat next-research --run <RUN_ROOT>/runs_kickoff/RUN_d3271703636992cc --workspace <WORKSPACE>
```
