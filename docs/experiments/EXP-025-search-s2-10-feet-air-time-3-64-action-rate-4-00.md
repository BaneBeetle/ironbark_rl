# EXP-025: search s2-10: feet_air_time 3.64, action_rate 4.00x, torques 0.71x

**Status:** search stage-2 trial 10 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 75 min, no crash), scored with the staleness and delay on; stage-2 constraints fail (saturation +21.2%, planar +3.1% over the limit); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search stage-2 trial 10: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 3.64; action_rate -0.08 -> -0.32 (4.00x); torques -0.125 -> -0.08888 (0.71x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `b2a9269`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-025 --env.rewards.feet_air_time.weight 3.64034 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.0888754`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0274 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-025`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_19-01-39_EXP-025`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.006 | 0.42 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.089 | 2.65 | 1.12 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.058 | 0.102 | 3.63 | 1.35 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.032 | 0.083 | 2.52 | 1.13 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.037 | 0.139 | 2.88 | 1.74 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.035 | 0.105 | 2.85 | 1.68 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.029 | 0.126 | 2.11 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.028 | 0.118 | 2.14 | 2.71 |
| **overall (mean of rows)** | 0.000 | 0.032 | 0.096 | 2.40 | 1.62 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_19-01-39_EXP-025`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.36% | 0.008 | 0.184 | 0.208 | 13.2% | 2.30 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_19-01-39_EXP-025`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00506 | +0.01237 | +0.01560 | +0.01592 |
| total | -0.00979 | +0.00750 | +0.01449 | +0.01524 |
| track_ang_vel_z | +0.00343 | +0.00470 | +0.00576 | +0.00595 |
| action_rate | -0.00899 | -0.00417 | -0.00342 | -0.00341 |
| torques | -0.00234 | -0.00200 | -0.00196 | -0.00192 |
| feet_air_time | -0.00078 | +0.00065 | +0.00104 | +0.00099 |
| lin_vel_z | -0.00433 | -0.00178 | -0.00103 | -0.00091 |
| orientation | -0.00087 | -0.00128 | -0.00075 | -0.00067 |
| ang_vel_xy | -0.00053 | -0.00076 | -0.00060 | -0.00053 |
| base_height | -0.00038 | -0.00016 | -0.00008 | -0.00010 |
| joint_acc | -0.00005 | -0.00005 | -0.00006 | -0.00006 |
| undesired_contacts | -1.2e-07 | -2.3e-05 | -3.8e-06 | -4.9e-06 |
| episode length (steps) | 132 | 648 | 913 | 921 |

Episode endings near iteration 1499: fell_over 1.0%, illegal_contact 14.8%, time_out 84.2%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
