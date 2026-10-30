# EXP-000: Luwu reward on S2 (baseline)

**Status:** trained (awaiting scoreboard v1) · **Parent:** none

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

_Scoreboard (`metrics.py` v1) results pending: the scoreboard isn't frozen yet._

**2026-10-30, interim sanity check, NOT the scoreboard.** Checkpoint `model_1499.pt`. Headless play config: 256 envs × 500 steps (10 s sim each), random commands in the play ranges (vx −0.35…0.45 m/s, vy ±0.25 m/s, yaw rate 0), no pushes or observation noise. "Falls" = the env's own terminations.

| | Luwu Mini2S policy on Mini2S (same check) | EXP-000 on S2 |
|---|---|---|
| Falls / early terminations | 0 | 0 |
| Mean planar speed error | 0.044 m/s | 0.052 m/s |
| Mean \|vx\| achieved / commanded | 0.202 / 0.203 m/s | 0.202 / 0.210 m/s |

End of training (iteration 1499, training conditions with pushes and noise): mean reward 83.58 (reward-scale specific; don't compare across rewards), mean episode length 965.5 / 1000, training-time planar error 0.204 m/s, yaw-rate error 0.496 rad/s. Wall time 1 h 12 min, slowed by a viewer open alongside; ~2.1 s/iteration without it.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
