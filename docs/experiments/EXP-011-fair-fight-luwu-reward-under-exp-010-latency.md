# EXP-011: fair fight: Luwu reward under EXP-010 latency

**Status:** planned · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

## Change (one variable)

vs. EXP-010: the reward. Brian's eleven terms (EXP-005's weights) -> **Luwu's reward** (as in EXP-002). Everything else is EXP-010's: env v2, 40 ms command delay, the actor's joint positions as the 130 ms round-robin readback with no joint velocity, the critic's true joint state, same PPO settings, seed 42, 1500 iterations.

Brian (2026-11-07): "Fair fight: train Luwu's reward with EXP-010's latency conditions (40 ms delay + stale joints, same actor obs as EXP-010) as EXP-011, seed 42, then score it under the same conditions. If it's close to EXP-010, run seeds 43 and 44 for both."

Seen from EXP-002 (Luwu's reward, no latency), this is EXP-009's and EXP-010's two changes together; EXP-002's own policy was already scored under these conditions without retraining (EXP-010 file).

Scored like EXP-010: the delay and the staleness stay on in the play config.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `c093ca8`
- Task: `IronBark-S2-Walk-Flat-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-011`
- Guard: skipped (Luwu's reward; README rule 2). Tests: 171 passed + 5 sim tests (EXP-011's actor and critic inputs match EXP-010's).
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_stale_joints/*_EXP-011`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
