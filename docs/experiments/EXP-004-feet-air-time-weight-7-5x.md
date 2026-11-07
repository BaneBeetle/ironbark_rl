# EXP-004: feet_air_time weight 7.5x

**Status:** trained 2026-11-07 (seed 42), verdict pending (Brian) · **Parent:** EXP-003

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) Flicker touchdowns drop well below EXP-003's 24.8% and feet_air_time rises to ~0.0015/step, with tracking roughly unchanged. Risk: exaggerated high-stepping.

_Claude's note: the flicker share (swings < 0.02 s) and swing times come from `tools/gait_check.py`, not the frozen scoreboard; feet_air_time's per-step contribution from TensorBoard (`Episode_Metrics/reward/feet_air_time`, EXP-003: +0.0002 at the end of training)._

## Change (one variable)

vs. EXP-003: **one weight.** `WEIGHTS["feet_air_time"]` 1.0 → **7.5** in `ironbark_rl/brian/reward_config.py` (Brian, 2026-11-07). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Why (Brian): in EXP-003 the term contributed ~1.2% of the tracking bonus (+0.0002 vs +0.0167 per step), too small to shape anything, so flickers didn't drop. 7.5× lands it near `action_rate`'s size (−0.0015).

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.0292 per step standing still on a zero command, and +0.0290 for the EXP-003 policy on the grid (feet_air_time +0.0021, 6.4%), with every command positive (+0.0261 to +0.0305). All 88 tests pass, including the 3 scenario rules.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `9b33231`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-004`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-004`
- Trained at commit `9b33231`, 2026-11-07.

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

- **Seed 43**, started 2026-11-07 05:48 at commit `a32447b` (Brian: check the noise, 2026-11-07): `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-004-s43`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-004-s43`. Tests: 88 passed, 1 deselected, 35 warnings in 5.26s. Guard: +0.02924 per step standing, +0.02915 for the EXP-004 seed-42 policy on the grid, commands +0.0277 to +0.0307; not flagged.
- **Seed 44**, started 2026-11-07 06:38 at commit `2294fb4` (Brian: check the noise, 2026-11-07): `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 44 --agent.run-name EXP-004-s44`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-004-s44`. Tests: 88 passed, 1 deselected, 35 warnings in 5.21s. Guard: +0.02924 per step standing, +0.02915 for the EXP-004 seed-42 policy on the grid, commands +0.0277 to +0.0307; not flagged.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_01-42-51_EXP-004`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.006 | 0.017 | 0.46 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.038 | 0.095 | 4.00 | 1.68 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.053 | 0.111 | 4.81 | 1.55 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.040 | 0.088 | 3.73 | 1.67 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.054 | 0.135 | 4.03 | 2.20 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.046 | 0.095 | 3.68 | 2.09 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.027 | 0.100 | 3.31 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.028 | 0.125 | 3.53 | 5.17 |
| **overall (mean of rows)** | 0.000 | 0.036 | 0.096 | 3.44 | 2.39 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_01-42-51_EXP-004`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.97% | 0.008 | 0.192 | 0.216 | 15.7% | 2.38 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_01-42-51_EXP-004`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00448 | +0.01307 | +0.01776 | +0.01910 |
| track_lin_vel_xy | +0.00509 | +0.01385 | +0.01605 | +0.01655 |
| track_ang_vel_z | +0.00352 | +0.00563 | +0.00635 | +0.00661 |
| torques | -0.00297 | -0.00379 | -0.00324 | -0.00319 |
| feet_air_time | -0.00160 | +0.00233 | +0.00234 | +0.00257 |
| action_rate | -0.00233 | -0.00206 | -0.00166 | -0.00151 |
| lin_vel_z | -0.00436 | -0.00125 | -0.00084 | -0.00079 |
| ang_vel_xy | -0.00050 | -0.00071 | -0.00052 | -0.00051 |
| orientation | -0.00091 | -0.00078 | -0.00056 | -0.00050 |
| joint_acc | -4.9e-05 | -0.00007 | -0.00007 | -0.00007 |
| base_height | -0.00038 | -0.00008 | -0.00008 | -0.00006 |
| undesired_contacts | -1.7e-06 | -3.2e-06 | -1.9e-06 | -1.1e-06 |
| episode length (steps) | 132 | 902 | 951 | 971 |

Episode endings near iteration 1499: fell_over 0.7%, illegal_contact 5.3%, time_out 94.0%.

**2026-11-07, scoreboard v1.** Run `2026-11-07_05-49-09_EXP-004-s43`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.013 | 0.042 | 0.85 | 2.13 |
| (+0.2, +0.0, +0.0) | 0.000 | 0.041 | 0.127 | 3.98 | 1.63 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.059 | 0.177 | 4.98 | 1.62 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.093 | 3.89 | 1.53 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.044 | 0.143 | 4.05 | 2.19 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.041 | 0.108 | 3.75 | 2.19 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.033 | 0.129 | 3.66 | 5.84 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.032 | 0.166 | 3.69 | 4.30 |
| **overall (mean of rows)** | 0.000 | 0.037 | 0.123 | 3.60 | 2.68 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_05-49-09_EXP-004-s43`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 1.15% | 0.008 | 0.192 | 0.216 | 15.7% | 2.44 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_05-49-09_EXP-004-s43`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00370 | +0.01248 | +0.01756 | +0.01921 |
| track_lin_vel_xy | +0.00544 | +0.01351 | +0.01605 | +0.01662 |
| track_ang_vel_z | +0.00355 | +0.00564 | +0.00635 | +0.00662 |
| torques | -0.00290 | -0.00372 | -0.00333 | -0.00311 |
| feet_air_time | -0.00137 | +0.00226 | +0.00231 | +0.00253 |
| action_rate | -0.00234 | -0.00206 | -0.00168 | -0.00149 |
| lin_vel_z | -0.00431 | -0.00134 | -0.00087 | -0.00079 |
| ang_vel_xy | -0.00050 | -0.00071 | -0.00053 | -0.00053 |
| orientation | -0.00082 | -0.00094 | -0.00057 | -0.00050 |
| joint_acc | -4.9e-05 | -0.00007 | -0.00007 | -0.00007 |
| base_height | -0.00038 | -0.00010 | -0.00010 | -0.00007 |
| undesired_contacts | -2.8e-06 | -4.1e-06 | -1.8e-06 | -1.2e-06 |
| episode length (steps) | 131 | 875 | 946 | 968 |

Episode endings near iteration 1499: fell_over 0.5%, illegal_contact 5.6%, time_out 93.9%.

**2026-11-07, scoreboard v1.** Run `2026-11-07_06-38-18_EXP-004-s44`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.012 | 0.046 | 0.61 | 0.66 |
| (+0.2, +0.0, +0.0) | 0.000 | 0.040 | 0.087 | 3.91 | 1.64 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.053 | 0.146 | 4.52 | 1.55 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.048 | 0.121 | 3.88 | 1.68 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.047 | 0.128 | 3.87 | 2.17 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.043 | 0.112 | 4.15 | 2.35 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.028 | 0.109 | 3.52 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.034 | 0.131 | 3.59 | 4.39 |
| **overall (mean of rows)** | 0.000 | 0.038 | 0.110 | 3.51 | 2.06 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_06-38-18_EXP-004-s44`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.75% | 0.008 | 0.192 | 0.216 | 15.6% | 2.38 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_06-38-18_EXP-004-s44`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00416 | +0.01253 | +0.01788 | +0.01901 |
| track_lin_vel_xy | +0.00525 | +0.01320 | +0.01606 | +0.01648 |
| track_ang_vel_z | +0.00353 | +0.00566 | +0.00643 | +0.00660 |
| torques | -0.00294 | -0.00357 | -0.00324 | -0.00319 |
| feet_air_time | -0.00155 | +0.00222 | +0.00235 | +0.00265 |
| action_rate | -0.00233 | -0.00201 | -0.00166 | -0.00151 |
| lin_vel_z | -0.00436 | -0.00126 | -0.00083 | -0.00081 |
| orientation | -0.00082 | -0.00088 | -0.00056 | -0.00056 |
| ang_vel_xy | -0.00051 | -0.00069 | -0.00051 | -0.00052 |
| joint_acc | -4.9e-05 | -0.00007 | -0.00007 | -0.00007 |
| base_height | -0.00038 | -0.00008 | -0.00009 | -0.00006 |
| undesired_contacts | -1.7e-06 | -4.0e-06 | -1.7e-06 | -1.4e-06 |
| episode length (steps) | 132 | 901 | 959 | 972 |

Episode endings near iteration 1499: fell_over 1.3%, illegal_contact 4.9%, time_out 93.9%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict

(2026-11-07) Finalist against EXP-005 (Brian); seeds 43 and 44 will check whether the saturation gap (0.97% vs 0.52%) is noise.
