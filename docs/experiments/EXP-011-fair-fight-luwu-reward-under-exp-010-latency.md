# EXP-011: fair fight: Luwu reward under EXP-010 latency

**Status:** trained 2026-11-07 (seed 42, 1500 iterations, 69 min, no crash), scored with the staleness and delay on; seeds 43/44 queued for EXP-010 and EXP-011 (seed rule); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Hypothesis: same pattern as without latency. EXP-010 and EXP-011 tie on servo strain and tracking, and EXP-010 wins on flicker, since the 0.07 s air-time threshold works the same with or without latency.

Written 2026-11-07, before training.

**Seed rule (Brian, verbatim):**

> "Close" = any metric within seed noise (~5% tracking, ~9% smoothness/saturation, from EXP-000). If close, run seeds 43 and 44 for both.

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
- Note: at ~21:31 a ~20 s GPU render from another Claude session (the IronBark website) overlapped EXP-011's first iterations (reported by that session). It affects timing only.
- Guard: skipped (Luwu's reward; README rule 2). Tests: 171 passed + 5 sim tests (EXP-011's actor and critic inputs match EXP-010's).
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_stale_joints/*_EXP-011`

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

Brian's seed rule (EXP-011 file): EXP-011 seed 42 came out within 5% of EXP-010 on yaw error, so both get seeds 43 and 44. Run one at a time, in the order EXP-010-s43, EXP-011-s43, EXP-010-s44, EXP-011-s44; each scored under the same conditions as seed 42.

- **Seed 43** (queued 2026-11-07): `python tools/run.py train IronBark-S2-Walk-Flat-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-011-s43`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_stale_joints/*_EXP-011-s43`, console log `~/dev/ironbark_runs/EXP-011-s43.log`.
- **Seed 44** (queued 2026-11-07): `python tools/run.py train IronBark-S2-Walk-Flat-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 44 --agent.run-name EXP-011-s44`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_stale_joints/*_EXP-011-s44`, console log `~/dev/ironbark_runs/EXP-011-s44.log`.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_21-32-37_EXP-011`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.005 | 0.28 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.107 | 2.88 | 1.27 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.049 | 0.131 | 4.08 | 1.49 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.036 | 0.102 | 2.36 | 1.02 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.037 | 0.156 | 2.98 | 1.82 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.037 | 0.137 | 3.07 | 1.79 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.024 | 0.171 | 1.99 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.024 | 0.190 | 1.92 | nan |
| **overall (mean of rows)** | 0.000 | 0.031 | 0.125 | 2.45 | 1.48 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_21-32-37_EXP-011`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 1.07% | 0.008 | 0.152 | 0.200 | 18.8% | 2.53 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_21-32-37_EXP-011`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| episode length (steps) | 132 | 957 | 938 | 946 |

Episode endings near iteration 1499: fell_over 3.2%, illegal_contact 7.6%, time_out 89.2%.

**2026-11-07, seed-rule check (Brian's rule, mechanical).** EXP-011 vs EXP-010, seed 42, unrounded overall values, relative change vs EXP-010. Bands: 5% tracking, 9% smoothness/saturation.

| Metric | EXP-010 | EXP-011 | Change | Band | Within |
|---|---|---|---|---|---|
| Planar err [m/s] | 0.0383 | 0.0305 | -20.3% | 5% | no |
| Yaw err [rad/s] | 0.1228 | 0.1251 | +1.8% | 5% | **yes** |
| Joint-target rate [rad/s] | 3.001 | 2.445 | -18.5% | 9% | no |
| Servo saturation | 0.805% | 1.074% | +33.4% | 9% | no |

One metric within its band, so "close": seeds 43 and 44 run for both. (Not in the rule, for reference: CoT 1.759 vs 1.478, -16.0%; flicker 15.1% vs 18.8%, +25.1%.)

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
