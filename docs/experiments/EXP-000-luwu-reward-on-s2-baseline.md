# EXP-000: Luwu reward on S2 (baseline)

**Status:** running · **Parent:** none

## Hypothesis (Brian, before the run)

> Written by Claude from the plan stated when the run started (it began before this log existed). Brian: amend or replace before results land.
>
> The S2 model (30% heavier than the Mini2S, same simulated servos) can learn Luwu's walking task with Luwu's reward and settings unchanged: no falls, and velocity tracking in the same range as Luwu's Mini2S policy (0.044 m/s error in our headless check). If it can't, the gap points at mass/servo strength, not the reward.

## Change (one variable)

None. This is the baseline: Luwu's Mini2S walking task (reward, observations, commands, randomization) with the S2 robot swapped in.

## Setup

Filled by hand: this run started before experiment tagging, so it has no `_EXP-000` suffix.

- Date: 2026-10-30, started 18:26
- Commit: `5b275e8` (code at launch; later commits don't touch training)
- Task: `IronBark-S2-Walk-Flat`
- Seed: 42 (default) · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat --env.scene.num-envs 4096`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk/2026-10-30_18-26-15`
- Console log: `~/dev/ironbark_runs/baseline_s2_luwu_reward.log`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
