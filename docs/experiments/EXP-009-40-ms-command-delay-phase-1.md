# EXP-009: 40 ms command delay (Phase 1)

**Status:** planned · **Parent:** EXP-005

## Hypothesis (Brian, before the run)

> Two experiments, both from EXP-005's config (feet_air_time 3.0), seed 42, one at a time:
> - EXP-009: add ~100 ms actuator/command delay (based on Phase 1 data). Nothing else changes.
> - EXP-010: EXP-009 + joint-position observations that refresh round-robin every ~105 ms (stale between refreshes).
>
> Hypothesis: both still walk, but slower and less precisely: higher tracking error, lower step frequency, more falls than EXP-005, with EXP-010 worse than EXP-009. If either can't walk or falls go high, next experiment adds the last ~5 actions to the observation (action history) so the policy knows what's in flight. If that fails too, we go Path B.

Written 2026-11-07, before training. Afterwards (also before training) Brian set the delay to **40 ms**, not ~100 ms: see Change.

## Change (one variable)

vs. EXP-005: the actuator command delay. Luwu's random 1-2 physics steps (4-8 ms) -> **40 ms fixed** (10 physics steps, every env), in training and in scoring.

Brian's choice (2026-11-07 design questions, after the hypothesis): 40 ms, because the earliest of 18 Phase 1 step responses moved 50 ms after the command, and the sine lag (88 ms) minus the mean readback age (~52 ms) is ~36 ms; the rest of the ~100 ms is readback staleness, which EXP-010 adds. Numbers and reasons: `ironbark_rl/brian/latency_config.py`.

Unchanged: reward (EXP-005's, `feet_air_time` 3.0), observations (the actor's joint pos/vel keep their 1-2 policy-step delay), terminations, commands, randomization.

**Scoring (Brian):** the 40 ms delay stays on in the play config (and the joint-observation delay too), so the scoreboard sees it. EXP-005's policy is re-scored under the same conditions as the reference (`--tag cmd_delay`), without retraining.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `8c186ad`
- Task: `IronBark-S2-Walk-Flat-Brian-CmdDelay`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-CmdDelay --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-009`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-CmdDelay --checkpoint <EXP-005>/model_1499.pt`: OK, every mean per-step total >= 0 (standing +0.0291). Tests: 143 passed (+4 sim tests passed: the command reaches `ctrl` exactly 2 policy steps later).
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_cmd_delay/*_EXP-009`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
