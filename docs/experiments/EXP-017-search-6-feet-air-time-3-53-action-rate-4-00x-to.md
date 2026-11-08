# EXP-017: search 6: feet_air_time 3.53, action_rate 4.00x, torques 2.00x

**Status:** search trial 6 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; seeds 43/44 trained and scored 2026-11-08 (Brian's pick); verdict pending (Brian) · **Parent:** EXP-010

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

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

Brian (2026-11-08): "Run seeds 43 and 44 for EXP-017, EXP-018 and EXP-015 (my top 3; I rank by saturation first, then tracking, then flicker)." Same weights, task and scoring as seed 42; one run at a time.

- **Seed 43** (trained and scored 2026-11-08, 44 min, no crash): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-017-s43 --env.rewards.feet_air_time.weight 3.52921 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.25`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-017-s43`, console log `~/dev/ironbark_runs/EXP-017-s43.log`.
- **Seed 44** (trained and scored 2026-11-08, 45 min, no crash): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 44 --agent.run-name EXP-017-s44 --env.rewards.feet_air_time.weight 3.52921 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.25`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-017-s44`, console log `~/dev/ironbark_runs/EXP-017-s44.log`.

**Seeds 42/43/44, mean ± sample SD [min–max]** (scoreboard v1 overall + gait diagnostics, `model_1499.pt`, staleness and delay on):

| Seed | Falls | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT | Saturation | Flicker | Swing median [s] |
|---|---|---|---|---|---|---|---|---|
| 42 | 0.000 | 0.0335 | 0.0876 | 2.078 | 1.219 | 0.03% | 12.94% | 0.1800 |
| 43 | 0.000 | 0.0338 | 0.0976 | 2.009 | 1.274 | 0.04% | 11.00% | 0.1840 |
| 44 | 0.000 | 0.0341 | 0.0975 | 2.041 | 1.153 | 0.02% | 13.03% | 0.1800 |
| **mean ± SD [min–max]** | 0.000 ± 0.000 [0.000–0.000] | 0.0338 ± 0.0003 [0.0335–0.0341] | 0.0942 ± 0.0058 [0.0876–0.0976] | 2.042 ± 0.035 [2.009–2.078] | 1.215 ± 0.061 [1.153–1.274] | 0.03% ± 0.01% [0.02%–0.04%] | 12.32% ± 1.15% [11.00%–13.03%] | 0.1813 ± 0.0023 [0.1800–0.1840] |

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

**2026-11-08, scoreboard v1.** Run `2026-11-08_09-36-25_EXP-017-s43`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.005 | 0.43 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.109 | 2.21 | 0.91 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.059 | 0.101 | 2.99 | 1.09 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.096 | 2.11 | 0.87 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.041 | 0.118 | 2.35 | 1.25 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.042 | 0.101 | 2.39 | 1.24 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.029 | 0.118 | 1.74 | 1.78 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.132 | 1.84 | 1.78 |
| **overall (mean of rows)** | 0.000 | 0.034 | 0.098 | 2.01 | 1.27 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_09-36-25_EXP-017-s43`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.04% | 0.008 | 0.184 | 0.208 | 11.0% | 2.23 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_09-36-25_EXP-017-s43`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00528 | +0.01062 | +0.01504 | +0.01538 |
| total | -0.01352 | +0.00396 | +0.01249 | +0.01253 |
| track_ang_vel_z | +0.00333 | +0.00496 | +0.00594 | +0.00596 |
| torques | -0.00646 | -0.00391 | -0.00428 | -0.00433 |
| action_rate | -0.00893 | -0.00322 | -0.00294 | -0.00307 |
| feet_air_time | -0.00075 | +0.00039 | +0.00099 | +0.00096 |
| lin_vel_z | -0.00433 | -0.00268 | -0.00090 | -0.00090 |
| orientation | -0.00071 | -0.00116 | -0.00070 | -0.00080 |
| ang_vel_xy | -0.00053 | -0.00063 | -0.00053 | -0.00049 |
| base_height | -0.00038 | -0.00031 | -0.00008 | -0.00011 |
| joint_acc | -0.00005 | -4.1e-05 | -0.00005 | -0.00005 |
| undesired_contacts | -3.9e-07 | -4.9e-05 | -3.2e-06 | -3.8e-06 |
| episode length (steps) | 132 | 510 | 911 | 899 |

Episode endings near iteration 1499: fell_over 3.6%, illegal_contact 15.6%, time_out 80.8%.

**2026-11-08, scoreboard v1.** Run `2026-11-08_10-21-36_EXP-017-s44`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.012 | 0.47 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.108 | 2.25 | 0.89 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.062 | 0.117 | 3.09 | 1.08 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.036 | 0.079 | 2.19 | 0.84 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.039 | 0.134 | 2.31 | 1.16 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.042 | 0.115 | 2.39 | 1.15 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.027 | 0.109 | 1.82 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.106 | 1.81 | 1.79 |
| **overall (mean of rows)** | 0.000 | 0.034 | 0.097 | 2.04 | 1.15 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_10-21-36_EXP-017-s44`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.02% | 0.008 | 0.180 | 0.208 | 13.0% | 2.31 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_10-21-36_EXP-017-s44`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00521 | +0.01146 | +0.01507 | +0.01535 |
| total | -0.01338 | +0.00509 | +0.01216 | +0.01263 |
| track_ang_vel_z | +0.00338 | +0.00495 | +0.00591 | +0.00595 |
| torques | -0.00639 | -0.00408 | -0.00433 | -0.00423 |
| action_rate | -0.00883 | -0.00341 | -0.00307 | -0.00309 |
| feet_air_time | -0.00069 | +0.00050 | +0.00096 | +0.00089 |
| lin_vel_z | -0.00430 | -0.00210 | -0.00096 | -0.00086 |
| orientation | -0.00079 | -0.00127 | -0.00076 | -0.00074 |
| ang_vel_xy | -0.00053 | -0.00065 | -0.00052 | -0.00049 |
| base_height | -0.00038 | -0.00024 | -0.00008 | -0.00009 |
| joint_acc | -0.00005 | -4.3e-05 | -0.00005 | -4.9e-05 |
| undesired_contacts | -2.2e-06 | -3.5e-05 | -5.3e-06 | -3.3e-06 |
| episode length (steps) | 132 | 562 | 873 | 912 |

Episode endings near iteration 1499: fell_over 4.7%, illegal_contact 13.5%, time_out 81.8%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
