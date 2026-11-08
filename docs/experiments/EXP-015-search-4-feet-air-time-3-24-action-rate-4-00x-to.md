# EXP-015: search 4: feet_air_time 3.24, action_rate 4.00x, torques 1.14x

**Status:** search trial 4 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; seeds 43/44 trained and scored 2026-11-08 (Brian's pick); verdict pending (Brian) · **Parent:** EXP-010

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

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

Brian (2026-11-08): "Run seeds 43 and 44 for EXP-017, EXP-018 and EXP-015 (my top 3; I rank by saturation first, then tracking, then flicker)." Same weights, task and scoring as seed 42; one run at a time.

- **Seed 43** (trained and scored 2026-11-08, 44 min, no crash): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-015-s43 --env.rewards.feet_air_time.weight 3.24218 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.142453`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-015-s43`, console log `~/dev/ironbark_runs/EXP-015-s43.log`.
- **Seed 44** (trained and scored 2026-11-08, 44 min, no crash): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 44 --agent.run-name EXP-015-s44 --env.rewards.feet_air_time.weight 3.24218 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.142453`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-015-s44`, console log `~/dev/ironbark_runs/EXP-015-s44.log`.

**Seeds 42/43/44, mean ± sample SD [min–max]** (scoreboard v1 overall + gait diagnostics, `model_1499.pt`, staleness and delay on):

| Seed | Falls | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT | Saturation | Flicker | Swing median [s] |
|---|---|---|---|---|---|---|---|---|
| 42 | 0.000 | 0.0322 | 0.0877 | 2.297 | 1.514 | 0.21% | 12.63% | 0.1840 |
| 43 | 0.000 | 0.0326 | 0.0941 | 2.245 | 1.455 | 0.04% | 13.13% | 0.1800 |
| 44 | 0.000 | 0.0337 | 0.0874 | 2.203 | 1.396 | 0.11% | 12.11% | 0.1840 |
| **mean ± SD [min–max]** | 0.000 ± 0.000 [0.000–0.000] | 0.0329 ± 0.0008 [0.0322–0.0337] | 0.0897 ± 0.0038 [0.0874–0.0941] | 2.248 ± 0.047 [2.203–2.297] | 1.455 ± 0.059 [1.396–1.514] | 0.12% ± 0.09% [0.04%–0.21%] | 12.63% ± 0.51% [12.11%–13.13%] | 0.1827 ± 0.0023 [0.1800–0.1840] |

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

**2026-11-08, scoreboard v1.** Run `2026-11-08_12-37-34_EXP-015-s43`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.008 | 0.39 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.110 | 2.50 | 1.04 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.052 | 0.101 | 3.50 | 1.25 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.074 | 2.40 | 0.95 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.042 | 0.103 | 2.54 | 1.38 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.036 | 0.114 | 2.62 | 1.46 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.029 | 0.124 | 1.94 | 1.89 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.120 | 2.06 | 2.22 |
| **overall (mean of rows)** | 0.000 | 0.033 | 0.094 | 2.24 | 1.46 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_12-37-34_EXP-015-s43`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.04% | 0.008 | 0.180 | 0.212 | 13.1% | 2.29 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_12-37-34_EXP-015-s43`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00527 | +0.01161 | +0.01548 | +0.01591 |
| total | -0.01072 | +0.00522 | +0.01383 | +0.01463 |
| track_ang_vel_z | +0.00334 | +0.00479 | +0.00587 | +0.00604 |
| action_rate | -0.00894 | -0.00379 | -0.00321 | -0.00319 |
| torques | -0.00370 | -0.00275 | -0.00279 | -0.00277 |
| lin_vel_z | -0.00433 | -0.00249 | -0.00095 | -0.00089 |
| feet_air_time | -0.00068 | +0.00040 | +0.00086 | +0.00087 |
| orientation | -0.00072 | -0.00144 | -0.00072 | -0.00070 |
| ang_vel_xy | -0.00053 | -0.00075 | -0.00056 | -0.00051 |
| base_height | -0.00038 | -0.00026 | -0.00007 | -0.00009 |
| joint_acc | -0.00005 | -4.7e-05 | -0.00006 | -0.00006 |
| undesired_contacts | -4.1e-07 | -4.3e-05 | -3.5e-06 | -2.9e-06 |
| episode length (steps) | 132 | 515 | 910 | 922 |

Episode endings near iteration 1499: fell_over 2.8%, illegal_contact 12.6%, time_out 84.6%.

**2026-11-08, scoreboard v1.** Run `2026-11-08_13-22-48_EXP-015-s44`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.007 | 0.43 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.036 | 0.080 | 2.42 | 1.05 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.059 | 0.117 | 3.52 | 1.27 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.032 | 0.073 | 2.32 | 0.95 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.042 | 0.123 | 2.46 | 1.45 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.040 | 0.097 | 2.58 | 1.37 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.027 | 0.099 | 1.91 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.031 | 0.103 | 1.97 | 2.28 |
| **overall (mean of rows)** | 0.000 | 0.034 | 0.087 | 2.20 | 1.40 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_13-22-48_EXP-015-s44`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.11% | 0.008 | 0.184 | 0.208 | 12.1% | 2.27 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_13-22-48_EXP-015-s44`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00518 | +0.01230 | +0.01532 | +0.01585 |
| total | -0.01066 | +0.00572 | +0.01324 | +0.01435 |
| track_ang_vel_z | +0.00338 | +0.00480 | +0.00569 | +0.00594 |
| action_rate | -0.00885 | -0.00394 | -0.00335 | -0.00331 |
| torques | -0.00366 | -0.00292 | -0.00286 | -0.00277 |
| feet_air_time | -0.00063 | +0.00037 | +0.00087 | +0.00090 |
| lin_vel_z | -0.00430 | -0.00239 | -0.00095 | -0.00088 |
| orientation | -0.00081 | -0.00139 | -0.00078 | -0.00071 |
| ang_vel_xy | -0.00054 | -0.00077 | -0.00057 | -0.00052 |
| base_height | -0.00038 | -0.00025 | -0.00007 | -0.00008 |
| joint_acc | -0.00005 | -4.9e-05 | -0.00006 | -0.00006 |
| undesired_contacts | -2.3e-06 | -4.6e-05 | -4.0e-06 | -3.6e-06 |
| episode length (steps) | 132 | 554 | 897 | 909 |

Episode endings near iteration 1499: fell_over 2.4%, illegal_contact 15.4%, time_out 82.3%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
