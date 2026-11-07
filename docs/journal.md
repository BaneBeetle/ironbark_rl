# Journal

Brian's decisions and verdicts, dated, in his words. Newest first. Numbers and run details are in [progress.md](progress.md) and the [experiment files](experiments/README.md).

## 2026-11-07: Phase 1 gate: Path A conditionally alive; test delay and stale readback in sim first

> My Phase 1 read: Path A is conditionally alive. Command rate (102 Hz) is fine, but servos lag ~100 ms (tracking falls off above ~2 Hz) and joint readback refreshes only every ~105 ms round-robin, while the sim models 4–8 ms of delay. Servo spec is 0.1 s/60° (a 10° move ≈ 17 ms unloaded) and 4.5 kg·cm ≈ 0.44 N·m (matches our 0.43 cap), so the motors are fast: the lag is mostly the motion board firmware and bus polling. Model it as command-pipeline delay + readback staleness, not slow motors.

> Two experiments, both from EXP-005's config (feet_air_time 3.0), seed 42, one at a time:
> - EXP-009: add ~100 ms actuator/command delay (based on Phase 1 data). Nothing else changes.
> - EXP-010: EXP-009 + joint-position observations that refresh round-robin every ~105 ms (stale between refreshes).
>
> Hypothesis: both still walk, but slower and less precisely: higher tracking error, lower step frequency, more falls than EXP-005, with EXP-010 worse than EXP-009. If either can't walk or falls go high, next experiment adds the last ~5 actions to the observation (action history) so the policy knows what's in flight. If that fails too, we go Path B.

Evidence: [phase1-joint-control-results.md](phase1-joint-control-results.md). Path A goes ahead only if EXP-009/010 (or the action-history follow-up) still walk; otherwise Path B.

## 2026-11-07: EXP-005 wins; `feet_air_time` weight 3.0 is the current best

> My read: EXP-005 (weight 3.0) is the winner.
> - vs EXP-004: saturation is a real win (ranges don't overlap: 0.39–0.53 vs 0.75–1.15); tracking is a tie (ranges overlap).
> - vs Luwu baseline EXP-002: saturation is a tie but EXP-005 is more consistent (±0.08 vs ±0.20); tracking is a tie (overlap, EXP-005's mean slightly better); flicker is a real win, 23.6% → 17.2% (~27% fewer), no overlap.
> Headline: my reward matches the baseline on servo strain and tracking while cutting flickers ~27% across 3 seeds.

Decision: set the config to EXP-005's weight (3.0) as the current best (commit `e520970`). Evidence: seeds 42–44 of EXP-002 (Luwu baseline), EXP-004 (7.5) and EXP-005 (3.0); ranking objective: servo saturation, then planar tracking, then flicker, 0 falls.
