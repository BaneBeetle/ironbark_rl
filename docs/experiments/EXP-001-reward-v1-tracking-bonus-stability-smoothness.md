# EXP-001: reward v1: tracking bonus, stability, smoothness

**Status:** planned · **Parent:** EXP-000

## Hypothesis (Brian, before the run)

Brian, 2026-10-30, verbatim:

> Id say maybe our fall rate would be higher purely because we are having a cold start rn.
>
> Id say everyting would proabbly be worse but future iterations we can make it better

## Change (one variable)

vs. EXP-000: **the reward.** Luwu's reward is replaced by Brian's reward v1 (`ironbark_rl/brian/rewards.py`). Everything else (robot, observations, actions, commands, randomization, PPO settings) stays EXP-000's.

Brian's reward v1 (2026-10-30, designed on paper before reading Luwu's reward):

| # | Term | Type | Priority |
|---|---|---|---|
| 1 | Velocity tracking: highest at zero error, always ≥ 0 | bonus | largest |
| 2 | Stability: body tilt + wobble (body rotation speed) | penalty | medium |
| 3 | Smoothness: joint-target change rate | penalty | small |
| 4 | Falling: ends the episode; no extra penalty (the lost future bonus is the cost) | termination | n/a |

Design reasoning (Brian):
- The dog should be paid for doing what it's told ("reaching the goal" = matching the commanded velocity, which also covers "how fast"), and for getting there smoothly.
- Bad habits: falling and being unstable. Speed vs. stability trade-off: prioritize stability to keep the fall rate down.
- Per-step reward must stay above 0 while the dog is up, so a fall forfeits future reward. If penalties made steps negative, falling early would *raise* the score.
- The tracking bonus peaks at the command, so standing idle loses when ordered to walk and wins when ordered to stand: no standing-still loophole.

## Setup

_Refreshed when training starts: the task will be an S2 task using `rewards.py` (not `IronBark-S2-Walk-Flat`, which uses Luwu's reward), and the commit will include Brian's implementation._

- Date: 2026-10-30
- Commit: _at launch_
- Task: _S2 task with Brian's reward (to be wired)_
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: _at launch_ (tagged `--agent.run-name EXP-001`)
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/<experiment>/*_EXP-001`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
