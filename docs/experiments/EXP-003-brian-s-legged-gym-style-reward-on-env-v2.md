# EXP-003: Brian's legged_gym-style reward on env v2

**Status:** training · **Parent:** EXP-002

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-06) Similar tracking error, but smoother and gentler: lower action rate, lower servo saturation %, and fewer flicker touchdowns (p10 swing time well above 0.008 s) thanks to the 0.07 s air-time threshold and requested-torque penalty. Risk: slightly worse tracking from the extra regularization.

_Claude's note: servo saturation % and swing-time p10 aren't on the frozen scoreboard; `tools/gait_check.py` reports them next to it as diagnostics. EXP-002 diagnostics: saturation 0.79%, swing p10 0.008 s, flicker touchdowns (< 0.02 s) 22.5%._

## Change (one variable)

vs. EXP-002: **the reward only.** Luwu's terms → Brian's eleven legged_gym-style terms (`ironbark_rl/brian/rewards.py`; weights and parameters in `ironbark_rl/brian/reward_config.py`, approved by Brian 2026-11-06). Task `IronBark-S2-Walk-Flat-Brian` matches the EXP-002 task in terminations, observations, actions, commands, randomization and collisions (config diff checked), and PPO settings differ only in `experiment_name`.

Fall-on-purpose guard before training (`tools/reward_check.py`): mean per-step total +0.0292 standing still on a zero command, and +0.0273 for the EXP-002 policy on the grid, with every command positive.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `455a231`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-003`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-003`
- Trained at commit `455a231`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
