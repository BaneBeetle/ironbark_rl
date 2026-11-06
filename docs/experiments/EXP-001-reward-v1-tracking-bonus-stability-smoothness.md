# EXP-001: reward v1: tracking bonus, stability, smoothness

**Status:** superseded 2026-11-06, never trained · **Parent:** EXP-000

## Hypothesis (Brian, before the run)

Brian, 2026-10-30, verbatim:

> Id say maybe our fall rate would be higher purely because we are having a cold start rn.
>
> Id say everyting would proabbly be worse but future iterations we can make it better

Brian's clarification, 2026-10-30, still before the run, verbatim:

> When I mean cold start, I mean this is our first run without any adaptations. We probably didnt account for power consumption, and potential consequences of our naive reward policies for now. Like originally, u saw I had a loophole, there may be other loop holes who knows?

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

_Commit is filled at launch (it must include Brian's implementation)._

- Date: 2026-10-30
- Commit: _at launch_
- Task: `IronBark-S2-Walk-Flat-BrianReward` (EXP-000's task with only the reward swapped; glue in `ironbark_rl/tasks/s2_walk_brian/`)
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-BrianReward --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-001`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_reward/*_EXP-001`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

- 2026-11-06: not run. Brian replaced reward v1 with his own legged_gym-style term set (Rudin et al. 2021), which becomes a new experiment under task `IronBark-S2-Walk-Flat-Brian`. See [progress.md](../progress.md), 2026-11-06.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
