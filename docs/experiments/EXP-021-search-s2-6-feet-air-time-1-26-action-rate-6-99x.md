# EXP-021: search s2-6: feet_air_time 1.26, action_rate 6.99x, torques 0.60x

**Status:** search stage-2 trial 6 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 57 min, no crash), scored with the staleness and delay on; stage-2 constraints fail (planar +6.0% over the limit); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search stage-2 trial 6: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 1.261; action_rate -0.08 -> -0.5591 (6.99x); torques -0.125 -> -0.0752 (0.60x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `d7faa11`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-021 --env.rewards.feet_air_time.weight 1.2609 --env.rewards.action_rate.weight -0.559142 --env.rewards.torques.weight -0.0751951`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0293, walking +0.0264 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-021`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_15-39-22_EXP-021`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.007 | 0.37 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.093 | 2.33 | 1.07 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.055 | 0.090 | 3.21 | 1.26 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.076 | 2.17 | 0.93 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.040 | 0.125 | 2.51 | 1.49 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.038 | 0.105 | 2.59 | 1.45 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.026 | 0.118 | 1.95 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.030 | 0.114 | 1.83 | nan |
| **overall (mean of rows)** | 0.000 | 0.033 | 0.091 | 2.12 | 1.24 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_15-39-22_EXP-021`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.24% | 0.008 | 0.180 | 0.208 | 15.0% | 2.35 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_15-39-22_EXP-021`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00505 | +0.01191 | +0.01585 | +0.01624 |
| total | -0.01527 | +0.00542 | +0.01434 | +0.01501 |
| track_ang_vel_z | +0.00343 | +0.00471 | +0.00602 | +0.00623 |
| action_rate | -0.01535 | -0.00486 | -0.00404 | -0.00412 |
| torques | -0.00195 | -0.00143 | -0.00148 | -0.00142 |
| lin_vel_z | -0.00433 | -0.00267 | -0.00095 | -0.00090 |
| orientation | -0.00087 | -0.00118 | -0.00068 | -0.00067 |
| ang_vel_xy | -0.00053 | -0.00075 | -0.00056 | -0.00050 |
| feet_air_time | -0.00027 | +4.2e-05 | +0.00031 | +0.00029 |
| base_height | -0.00038 | -0.00027 | -0.00007 | -0.00009 |
| joint_acc | -0.00005 | -4.4e-05 | -0.00006 | -0.00005 |
| undesired_contacts | -1.1e-07 | -4.3e-05 | -3.2e-06 | -3.0e-06 |
| episode length (steps) | 132 | 576 | 916 | 920 |

Episode endings near iteration 1499: fell_over 2.1%, illegal_contact 14.2%, time_out 83.7%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
