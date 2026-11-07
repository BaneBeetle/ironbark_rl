# EXP-004: feet_air_time weight 7.5x

**Status:** training · **Parent:** EXP-003

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) Flicker touchdowns drop well below EXP-003's 24.8% and feet_air_time rises to ~0.0015/step, with tracking roughly unchanged. Risk: exaggerated high-stepping.

_Claude's note: the flicker share (swings < 0.02 s) and swing times come from `tools/gait_check.py`, not the frozen scoreboard; feet_air_time's per-step contribution from TensorBoard (`Episode_Metrics/reward/feet_air_time`, EXP-003: +0.0002 at the end of training)._

## Change (one variable)

vs. EXP-003: **one weight.** `WEIGHTS["feet_air_time"]` 1.0 → **7.5** in `ironbark_rl/brian/reward_config.py` (Brian, 2026-11-07). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Why (Brian): in EXP-003 the term contributed ~1.2% of the tracking bonus (+0.0002 vs +0.0167 per step), too small to shape anything, so flickers didn't drop. 7.5× lands it near `action_rate`'s size (−0.0015).

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.0292 per step standing still on a zero command, and +0.0290 for the EXP-003 policy on the grid (feet_air_time +0.0021, 6.4%), with every command positive (+0.0261 to +0.0305). All 88 tests pass, including the 3 scenario rules.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `9b33231`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-004`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-004`
- Trained at commit `9b33231`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
