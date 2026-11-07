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

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict

(2026-11-07) Finalist against EXP-005 (Brian); seeds 43 and 44 will check whether the saturation gap (0.97% vs 0.52%) is noise.
