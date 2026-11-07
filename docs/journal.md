# Journal

Brian's decisions and verdicts, dated, in his words. Newest first. Numbers and run details are in [progress.md](progress.md) and the [experiment files](experiments/README.md).

## 2026-11-07: EXP-005 wins; `feet_air_time` weight 3.0 is the current best

> My read: EXP-005 (weight 3.0) is the winner.
> - vs EXP-004: saturation is a real win (ranges don't overlap: 0.39–0.53 vs 0.75–1.15); tracking is a tie (ranges overlap).
> - vs Luwu baseline EXP-002: saturation is a tie but EXP-005 is more consistent (±0.08 vs ±0.20); tracking is a tie (overlap, EXP-005's mean slightly better); flicker is a real win, 23.6% → 17.2% (~27% fewer), no overlap.
> Headline: my reward matches the baseline on servo strain and tracking while cutting flickers ~27% across 3 seeds.

Decision: set the config to EXP-005's weight (3.0) as the current best (commit `e520970`). Evidence: seeds 42–44 of EXP-002 (Luwu baseline), EXP-004 (7.5) and EXP-005 (3.0); ranking objective: servo saturation, then planar tracking, then flicker, 0 falls.
