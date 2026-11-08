# EXP-014: search 3: feet_air_time 1.12, action_rate 3.03x, torques 1.15x

**Status:** search trial 3 (Optuna), training · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 3: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 1.124; action_rate -0.08 -> -0.2423 (3.03x); torques -0.125 -> -0.1438 (1.15x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `4f2467e`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-014 --env.rewards.feet_air_time.weight 1.12416 --env.rewards.action_rate.weight -0.242267 --env.rewards.torques.weight -0.143809`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0263 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-014`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
