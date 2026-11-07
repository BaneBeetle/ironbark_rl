# EXP-008: sweep: feet_air_time weight 5

**Status:** training · **Parent:** EXP-004

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) No per-run hypothesis: a new sweep point Brian asked for, verbatim: "A new sweep point: feet_air_time weight 5.0, seed 42, as its own experiment, scored the same way." Ranking objective in force (Brian, 2026-11-07): servo saturation first, then planar tracking error, then flicker share; 0 falls required.

(2026-11-07 11:05; written after training started at ~10:50, before any results) Every metric lands between EXP-005 (3.0) and EXP-004 (7.5): flicker ~16-17%, saturation ~0.5-1.0%, planar error ~0.035-0.036. If saturation stays near EXP-005's while flicker drops toward EXP-004's, 5.0 could be the sweet spot.

## Change (one variable)

vs. EXP-004: **one weight.** `WEIGHTS["feet_air_time"]` 7.5 → **5** (EXP-003: 1.0; EXP-005: 3.0). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.02924 per step standing still on a zero command; +0.02826 for the EXP-004 policy on the grid (feet_air_time +0.00180, 5.6%), commands +0.0267 to +0.0296. Not flagged. Tests 88/88.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `ec13a68`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-008`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-008`
- Trained at commit `ec13a68`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
