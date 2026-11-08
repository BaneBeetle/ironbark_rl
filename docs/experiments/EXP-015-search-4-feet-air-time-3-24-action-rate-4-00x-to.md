# EXP-015: search 4: feet_air_time 3.24, action_rate 4.00x, torques 1.14x

**Status:** search trial 4 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 4: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 3.242; action_rate -0.08 -> -0.32 (4.00x); torques -0.125 -> -0.1425 (1.14x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `9c80f71`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-015 --env.rewards.feet_air_time.weight 3.24218 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.142453`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0269 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-015`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_05-00-55_EXP-015`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.005 | 0.32 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.032 | 0.082 | 2.62 | 1.10 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.054 | 0.082 | 3.55 | 1.29 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.085 | 2.45 | 1.04 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.037 | 0.118 | 2.74 | 1.54 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.041 | 0.126 | 2.56 | 1.38 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.025 | 0.101 | 2.01 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.102 | 2.12 | 2.73 |
| **overall (mean of rows)** | 0.000 | 0.032 | 0.088 | 2.30 | 1.51 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_05-00-55_EXP-015`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.21% | 0.008 | 0.184 | 0.208 | 12.6% | 2.26 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_05-00-55_EXP-015`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00505 | +0.01112 | +0.01548 | +0.01595 |
| total | -0.01107 | +0.00542 | +0.01366 | +0.01468 |
| track_ang_vel_z | +0.00343 | +0.00474 | +0.00584 | +0.00602 |
| action_rate | -0.00897 | -0.00379 | -0.00331 | -0.00321 |
| torques | -0.00373 | -0.00274 | -0.00284 | -0.00276 |
| lin_vel_z | -0.00433 | -0.00203 | -0.00099 | -0.00089 |
| feet_air_time | -0.00070 | +0.00038 | +0.00086 | +0.00086 |
| orientation | -0.00086 | -0.00128 | -0.00069 | -0.00066 |
| ang_vel_xy | -0.00053 | -0.00070 | -0.00056 | -0.00051 |
| base_height | -0.00038 | -0.00021 | -0.00007 | -0.00007 |
| joint_acc | -0.00005 | -4.6e-05 | -0.00006 | -0.00006 |
| undesired_contacts | -1.9e-07 | -3.0e-05 | -3.0e-06 | -2.4e-06 |
| episode length (steps) | 132 | 578 | 910 | 929 |

Episode endings near iteration 1499: fell_over 3.6%, illegal_contact 12.5%, time_out 83.9%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
