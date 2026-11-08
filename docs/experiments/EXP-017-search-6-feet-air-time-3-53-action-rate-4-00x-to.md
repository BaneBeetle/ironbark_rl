# EXP-017: search 6: feet_air_time 3.53, action_rate 4.00x, torques 2.00x

**Status:** search trial 6 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 6: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 3.529; action_rate -0.08 -> -0.32 (4.00x); torques -0.125 -> -0.25 (2.00x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `dec02d9`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-017 --env.rewards.feet_air_time.weight 3.52921 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.25`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0290, walking +0.0264 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-017`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_06-32-37_EXP-017`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.005 | 0.32 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.088 | 2.28 | 0.91 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.054 | 0.097 | 3.17 | 1.11 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.036 | 0.074 | 2.35 | 0.96 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.042 | 0.113 | 2.45 | 1.27 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.037 | 0.103 | 2.39 | 1.25 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.028 | 0.106 | 1.78 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.032 | 0.114 | 1.88 | 1.81 |
| **overall (mean of rows)** | 0.000 | 0.033 | 0.088 | 2.08 | 1.22 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_06-32-37_EXP-017`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.03% | 0.008 | 0.180 | 0.208 | 12.9% | 2.29 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_06-32-37_EXP-017`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00506 | +0.01089 | +0.01503 | +0.01541 |
| total | -0.01389 | +0.00389 | +0.01219 | +0.01274 |
| track_ang_vel_z | +0.00343 | +0.00495 | +0.00586 | +0.00598 |
| torques | -0.00653 | -0.00398 | -0.00426 | -0.00427 |
| action_rate | -0.00897 | -0.00332 | -0.00302 | -0.00308 |
| feet_air_time | -0.00076 | +0.00034 | +0.00092 | +0.00096 |
| lin_vel_z | -0.00433 | -0.00268 | -0.00094 | -0.00087 |
| orientation | -0.00085 | -0.00132 | -0.00075 | -0.00072 |
| ang_vel_xy | -0.00052 | -0.00062 | -0.00052 | -0.00049 |
| base_height | -0.00038 | -0.00029 | -0.00008 | -0.00013 |
| joint_acc | -0.00005 | -4.0e-05 | -4.9e-05 | -5.0e-05 |
| undesired_contacts | -2.5e-07 | -4.7e-05 | -4.6e-06 | -3.0e-06 |
| episode length (steps) | 132 | 495 | 896 | 919 |

Episode endings near iteration 1499: fell_over 3.8%, illegal_contact 13.3%, time_out 82.8%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
