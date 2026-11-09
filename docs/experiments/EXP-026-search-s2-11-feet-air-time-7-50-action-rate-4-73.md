# EXP-026: search s2-11: feet_air_time 7.50, action_rate 4.73x, torques 1.89x

**Status:** search stage-2 trial 11 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 102 min, no crash), scored with the staleness and delay on; stage-2 constraints fail (planar +8.1% over the limit); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search stage-2 trial 11: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 7.5; action_rate -0.08 -> -0.3786 (4.73x); torques -0.125 -> -0.2363 (1.89x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `cefc595`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-026 --env.rewards.feet_air_time.weight 7.5 --env.rewards.action_rate.weight -0.378628 --env.rewards.torques.weight -0.236256`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0290, walking +0.0277 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-026`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_20-19-25_EXP-026`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.010 | 0.34 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.082 | 2.49 | 1.21 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.062 | 0.098 | 3.26 | 1.29 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.087 | 2.47 | 1.13 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.041 | 0.111 | 2.54 | 1.50 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.039 | 0.097 | 2.49 | 1.51 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.028 | 0.088 | 2.10 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.103 | 2.18 | nan |
| **overall (mean of rows)** | 0.000 | 0.033 | 0.085 | 2.23 | 1.33 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_20-19-25_EXP-026`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.01% | 0.112 | 0.188 | 0.212 | 9.6% | 2.21 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_20-19-25_EXP-026`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00505 | +0.01206 | +0.01517 | +0.01552 |
| total | -0.01603 | +0.00516 | +0.01396 | +0.01447 |
| track_ang_vel_z | +0.00342 | +0.00491 | +0.00603 | +0.00611 |
| torques | -0.00618 | -0.00412 | -0.00398 | -0.00400 |
| action_rate | -0.01059 | -0.00400 | -0.00325 | -0.00335 |
| feet_air_time | -0.00159 | +0.00165 | +0.00228 | +0.00244 |
| lin_vel_z | -0.00433 | -0.00288 | -0.00096 | -0.00090 |
| orientation | -0.00086 | -0.00133 | -0.00070 | -0.00071 |
| ang_vel_xy | -0.00053 | -0.00074 | -0.00051 | -0.00053 |
| base_height | -0.00038 | -0.00029 | -0.00007 | -0.00006 |
| joint_acc | -0.00005 | -4.7e-05 | -0.00005 | -0.00005 |
| undesired_contacts | -2.5e-07 | -4.8e-05 | -3.0e-06 | -2.6e-06 |
| episode length (steps) | 132 | 542 | 919 | 921 |

Episode endings near iteration 1499: fell_over 3.9%, illegal_contact 12.0%, time_out 84.1%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
