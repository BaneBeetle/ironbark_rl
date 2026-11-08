# EXP-023: search s2-8: feet_air_time 2.07, action_rate 5.56x, torques 1.16x

**Status:** search stage-2 trial 8 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; stage-2 constraints fail (planar +3.3% over the limit); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search stage-2 trial 8: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 2.068; action_rate -0.08 -> -0.4448 (5.56x); torques -0.125 -> -0.1454 (1.16x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `c6b6e82`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-023 --env.rewards.feet_air_time.weight 2.06757 --env.rewards.action_rate.weight -0.444769 --env.rewards.torques.weight -0.145438`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0264 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-023`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_17-29-28_EXP-023`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.006 | 0.34 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.032 | 0.097 | 2.19 | 0.97 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.056 | 0.103 | 3.16 | 1.22 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.067 | 2.23 | 0.89 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.036 | 0.115 | 2.47 | 1.41 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.039 | 0.097 | 2.56 | 1.47 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.025 | 0.107 | 1.82 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.027 | 0.108 | 1.80 | nan |
| **overall (mean of rows)** | 0.000 | 0.032 | 0.087 | 2.07 | 1.19 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_17-29-28_EXP-023`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.06% | 0.008 | 0.180 | 0.208 | 13.8% | 2.31 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_17-29-28_EXP-023`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00506 | +0.01170 | +0.01563 | +0.01621 |
| total | -0.01422 | +0.00505 | +0.01368 | +0.01523 |
| track_ang_vel_z | +0.00342 | +0.00486 | +0.00608 | +0.00633 |
| action_rate | -0.01231 | -0.00429 | -0.00360 | -0.00331 |
| torques | -0.00379 | -0.00261 | -0.00265 | -0.00247 |
| lin_vel_z | -0.00433 | -0.00253 | -0.00096 | -0.00087 |
| orientation | -0.00087 | -0.00123 | -0.00069 | -0.00061 |
| feet_air_time | -0.00044 | +0.00016 | +0.00052 | +0.00056 |
| ang_vel_xy | -0.00053 | -0.00067 | -0.00052 | -0.00045 |
| base_height | -0.00038 | -0.00026 | -0.00008 | -0.00011 |
| joint_acc | -0.00005 | -4.4e-05 | -0.00005 | -0.00005 |
| undesired_contacts | -1.8e-07 | -4.0e-05 | -3.4e-06 | -2.3e-06 |
| episode length (steps) | 132 | 567 | 903 | 932 |

Episode endings near iteration 1499: fell_over 2.4%, illegal_contact 11.7%, time_out 86.0%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
