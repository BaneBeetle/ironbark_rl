# EXP-016: search 5: feet_air_time 4.39, action_rate 4.00x, torques 1.00x

**Status:** search trial 5 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 5: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 4.393; action_rate -0.08 -> -0.32 (4.00x); torques -0.125 -> -0.1247 (1.00x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `49b5d8b`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-016 --env.rewards.feet_air_time.weight 4.39307 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.124666`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0274 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-016`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_05-46-46_EXP-016`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.006 | 0.41 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.105 | 2.80 | 1.26 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.052 | 0.105 | 3.76 | 1.38 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.034 | 0.079 | 2.58 | 1.06 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.038 | 0.120 | 2.87 | 1.61 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.042 | 0.095 | 2.78 | 1.55 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.032 | 0.106 | 2.14 | 2.76 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.028 | 0.115 | 2.29 | 3.03 |
| **overall (mean of rows)** | 0.000 | 0.033 | 0.091 | 2.45 | 1.81 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_05-46-46_EXP-016`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.28% | 0.008 | 0.188 | 0.208 | 13.3% | 2.27 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_05-46-46_EXP-016`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00508 | +0.01173 | +0.01544 | +0.01592 |
| total | -0.01084 | +0.00717 | +0.01409 | +0.01538 |
| track_ang_vel_z | +0.00343 | +0.00479 | +0.00579 | +0.00607 |
| action_rate | -0.00897 | -0.00401 | -0.00342 | -0.00316 |
| torques | -0.00327 | -0.00254 | -0.00259 | -0.00251 |
| feet_air_time | -0.00095 | +0.00086 | +0.00131 | +0.00132 |
| lin_vel_z | -0.00433 | -0.00151 | -0.00096 | -0.00090 |
| orientation | -0.00086 | -0.00124 | -0.00077 | -0.00071 |
| ang_vel_xy | -0.00053 | -0.00071 | -0.00058 | -0.00052 |
| base_height | -0.00038 | -0.00014 | -0.00007 | -0.00007 |
| joint_acc | -0.00005 | -4.9e-05 | -0.00006 | -0.00006 |
| undesired_contacts | -2.4e-07 | -1.8e-05 | -3.0e-06 | -3.5e-06 |
| episode length (steps) | 132 | 669 | 914 | 915 |

Episode endings near iteration 1499: fell_over 2.5%, illegal_contact 13.1%, time_out 84.4%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
