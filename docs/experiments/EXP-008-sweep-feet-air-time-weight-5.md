# EXP-008: sweep: feet_air_time weight 5

**Status:** trained 2026-11-07 (seed 42), verdict pending (Brian) · **Parent:** EXP-004

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) No per-run hypothesis: a new sweep point Brian asked for, verbatim: "A new sweep point: feet_air_time weight 5.0, seed 42, as its own experiment, scored the same way." Ranking objective in force (Brian, 2026-11-07): servo saturation first, then planar tracking error, then flicker share; 0 falls required.

(2026-11-07 11:05; written after training started at ~10:50, before any results) Every metric lands between EXP-005 (3.0) and EXP-004 (7.5): flicker ~16-17%, saturation ~0.5-1.0%, planar error ~0.035-0.036. If saturation stays near EXP-005's while flicker drops toward EXP-004's, 5.0 could be the sweet spot.

## Change (one variable)

vs. EXP-004: **one weight.** `WEIGHTS["feet_air_time"]` 7.5 → **5** (EXP-003: 1.0; EXP-005: 3.0). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.02924 per step standing still on a zero command; +0.02826 for the EXP-004 policy on the grid (feet_air_time +0.00180, 5.6%), commands +0.0267 to +0.0296. Not flagged. Tests 88/88.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `ec13a68`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-008`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-008`
- Trained at commit `ec13a68`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_10-47-06_EXP-008`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.032 | 0.063 | 0.92 | 1.25 |
| (+0.2, +0.0, +0.0) | 0.000 | 0.038 | 0.089 | 3.50 | 1.46 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.071 | 0.113 | 4.56 | 1.52 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.040 | 0.112 | 3.44 | 1.49 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.036 | 0.139 | 3.46 | 2.06 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.041 | 0.141 | 3.43 | 1.87 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.030 | 0.110 | 3.27 | 4.36 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.026 | 0.108 | 3.40 | nan |
| **overall (mean of rows)** | 0.000 | 0.039 | 0.109 | 3.25 | 2.00 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_10-47-06_EXP-008`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.87% | 0.008 | 0.188 | 0.212 | 18.5% | 2.53 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_10-47-06_EXP-008`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00394 | +0.01163 | +0.01714 | +0.01848 |
| track_lin_vel_xy | +0.00509 | +0.01292 | +0.01607 | +0.01668 |
| track_ang_vel_z | +0.00352 | +0.00566 | +0.00640 | +0.00663 |
| torques | -0.00296 | -0.00349 | -0.00320 | -0.00303 |
| feet_air_time | -0.00112 | +0.00136 | +0.00153 | +0.00155 |
| action_rate | -0.00233 | -0.00197 | -0.00164 | -0.00148 |
| lin_vel_z | -0.00435 | -0.00118 | -0.00082 | -0.00075 |
| orientation | -0.00087 | -0.00083 | -0.00054 | -0.00051 |
| ang_vel_xy | -0.00049 | -0.00068 | -0.00050 | -0.00048 |
| joint_acc | -4.9e-05 | -0.00007 | -0.00007 | -0.00007 |
| base_height | -0.00037 | -0.00008 | -0.00008 | -0.00006 |
| undesired_contacts | -7.6e-07 | -3.1e-06 | -1.3e-06 | -1.1e-06 |
| episode length (steps) | 132 | 914 | 957 | 961 |

Episode endings near iteration 1499: fell_over 1.3%, illegal_contact 6.4%, time_out 92.3%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
