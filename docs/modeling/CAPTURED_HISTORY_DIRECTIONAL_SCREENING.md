# Captured-history directional screening

`dcm.model.captured_history.build_captured_history_decisions` evaluates each
captured player-prop claim before the research Top-100 frontier. It treats the
line and side recorded in the supplied HAR as the chat-ignition offer snapshot.
The snapshot is retained for directional screening even when a later current
offer revalidation is unavailable. Production-card eligibility remains a
separate decision.

The producer uses only dated history outcomes at or before the run cutoff. It
does not turn Outlier's reported hit rate into a forecast. Discrete outcomes
remain exact point masses. For line `L`, it records the empirical frequencies
of `X > L`, `X < L`, and `X = L`. Pushes are shown separately; a directional
screen uses the relevant side's share among decisive (non-push) observations.
It returns Higher or Lower only when the two-sided 95% Wilson lower confidence
bound for that offered side is greater than 0.5. Otherwise it returns Pass.
Sparse rows remain usable and are marked with their sample count and
`lowSampleFlag`; this is an uncalibrated historical screen, not a certified
probability model.

All supplied claims receive a terminal accounting row. Only claims on the
prompt's target local event date enter the run's directional ranking. Other
dated claims are `OUT_OF_RUN_SCOPE`; game-line/non-player claims remain
`UNMODELED` in this player-prop producer. Green Goblins and non-exempt 0.5
lines are `EXCLUDED_BY_POLICY`. Interceptions and NHL plus/minus are explicit
0.5-line exceptions. A missing line, side, cutoff, schedule, or valid history
has its own `UNMODELED` reason.

The model ranking and Top 2000/1000/500/250/100/50/25/12/6 views contain all
modeled rows, including Pass, ordered by supported direction, distance from an
even conditional share, uncertainty bound, and sample count. The separate
recommendation ranking contains only Higher/Lower rows. When fewer rows qualify
than a stage limit, the stage contains every qualifying row. Research priority,
production certification, calibration, joint dependence, and payout EV are
separate outputs; none is inferred from this marginal history screen.
