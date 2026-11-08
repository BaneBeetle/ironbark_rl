# EXP-012: search 1: feet_air_time 2.13, action_rate 3.61x, torques 1.38x

**Status:** search trial 1 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 1: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 2.127; action_rate -0.08 -> -0.2888 (3.61x); torques -0.125 -> -0.1724 (1.38x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `716e79d`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-012 --env.rewards.feet_air_time.weight 2.12689 --env.rewards.action_rate.weight -0.288829 --env.rewards.torques.weight -0.172419`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0291, walking +0.0264 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-012`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_02-43-09_EXP-012`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.005 | 0.37 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.088 | 2.36 | 0.98 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.057 | 0.100 | 3.47 | 1.23 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.036 | 0.090 | 2.39 | 0.94 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.037 | 0.125 | 2.69 | 1.37 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.037 | 0.119 | 2.46 | 1.31 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.026 | 0.120 | 1.81 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.027 | 0.114 | 1.86 | nan |
| **overall (mean of rows)** | 0.000 | 0.032 | 0.095 | 2.17 | 1.17 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_02-43-09_EXP-012`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.19% | 0.008 | 0.180 | 0.208 | 14.9% | 2.34 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_02-43-09_EXP-012`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00504 | +0.01163 | +0.01517 | +0.01567 |
| total | -0.01078 | +0.00540 | +0.01252 | +0.01311 |
| track_ang_vel_z | +0.00344 | +0.00477 | +0.00575 | +0.00584 |
| torques | -0.00451 | -0.00340 | -0.00340 | -0.00343 |
| action_rate | -0.00810 | -0.00353 | -0.00310 | -0.00314 |
| lin_vel_z | -0.00434 | -0.00212 | -0.00095 | -0.00089 |
| orientation | -0.00088 | -0.00121 | -0.00077 | -0.00078 |
| ang_vel_xy | -0.00053 | -0.00069 | -0.00058 | -0.00052 |
| feet_air_time | -0.00046 | +0.00024 | +0.00053 | +0.00051 |
| base_height | -0.00038 | -0.00021 | -0.00008 | -0.00009 |
| joint_acc | -0.00005 | -4.6e-05 | -0.00005 | -0.00005 |
| undesired_contacts | -6.6e-07 | -3.1e-05 | -3.0e-06 | -3.8e-06 |
| episode length (steps) | 132 | 605 | 905 | 909 |

Episode endings near iteration 1499: fell_over 4.4%, illegal_contact 14.3%, time_out 81.3%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
