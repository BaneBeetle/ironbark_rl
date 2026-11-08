# EXP-014: search 3: feet_air_time 1.12, action_rate 3.03x, torques 1.15x

**Status:** search trial 3 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints fail (planar +2.1% over the limit); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 3: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 1.124; action_rate -0.08 -> -0.2423 (3.03x); torques -0.125 -> -0.1438 (1.15x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `4f2467e`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-014 --env.rewards.feet_air_time.weight 1.12416 --env.rewards.action_rate.weight -0.242267 --env.rewards.torques.weight -0.143809`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0263 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-014`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_04-14-51_EXP-014`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.005 | 0.37 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.040 | 0.097 | 2.56 | 0.94 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.062 | 0.101 | 3.74 | 1.21 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.044 | 0.084 | 2.30 | 0.88 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.043 | 0.150 | 2.77 | 1.51 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.034 | 0.145 | 2.87 | 1.49 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.031 | 0.119 | 2.07 | 1.61 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.144 | 1.87 | nan |
| **overall (mean of rows)** | 0.000 | 0.036 | 0.105 | 2.32 | 1.27 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_04-14-51_EXP-014`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.18% | 0.008 | 0.176 | 0.208 | 15.8% | 2.40 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_04-14-51_EXP-014`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00507 | +0.00921 | +0.01485 | +0.01576 |
| total | -0.00854 | +0.00563 | +0.01208 | +0.01361 |
| track_ang_vel_z | +0.00344 | +0.00476 | +0.00548 | +0.00575 |
| torques | -0.00378 | -0.00262 | -0.00311 | -0.00300 |
| action_rate | -0.00686 | -0.00321 | -0.00292 | -0.00287 |
| lin_vel_z | -0.00433 | -0.00086 | -0.00095 | -0.00087 |
| orientation | -0.00088 | -0.00098 | -0.00076 | -0.00072 |
| ang_vel_xy | -0.00052 | -0.00058 | -0.00059 | -0.00052 |
| feet_air_time | -0.00025 | +1.9e-05 | +0.00021 | +0.00023 |
| base_height | -0.00038 | -0.00007 | -0.00007 | -0.00010 |
| joint_acc | -0.00005 | -4.1e-05 | -0.00005 | -0.00006 |
| undesired_contacts | -1.1e-07 | -4.8e-06 | -3.3e-06 | -2.9e-06 |
| episode length (steps) | 132 | 862 | 925 | 923 |

Episode endings near iteration 1499: fell_over 3.7%, illegal_contact 11.2%, time_out 85.1%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
