# EXP-006: sweep: feet_air_time weight 15

**Status:** trained 2026-11-07 (seed 42), verdict pending (Brian) · **Parent:** EXP-004

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) No per-run hypothesis: this is one run of Brian's 1-D sweep, verbatim: "Run a 1-D sweep on feet_air_time's weight: 3.0, 15.0, and 30.0 (7.5 is EXP-004, 1.0 is EXP-003). Same seed 42, everything else identical, one at a time, each as its own experiment, scored the same way." "Objective for ranking: lowest flicker share, with planar tracking error no worse than EXP-002 + 10% and zero falls. Also report swing median and servo saturation for each, so I can spot high-stepping or strain."

## Change (one variable)

vs. EXP-004: **one weight.** `WEIGHTS["feet_air_time"]` 7.5 → **15** (EXP-003: 1.0). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.02924 per step standing still on a zero command; +0.03185 for the EXP-004 policy on the grid (feet_air_time +0.00539, 15.0%), commands +0.0280 to +0.0338. Not flagged.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `a58de38`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-006`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-006`
- Trained at commit `a58de38`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_03-41-23_EXP-006`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.005 | 0.020 | 0.96 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.068 | 0.102 | 6.18 | 3.20 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.072 | 0.120 | 7.20 | 2.34 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.074 | 0.096 | 6.10 | 2.81 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.087 | 0.144 | 6.28 | 2.98 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.083 | 0.183 | 6.43 | 3.27 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.073 | 0.181 | 5.85 | 7.11 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.069 | 0.144 | 6.25 | 7.72 |
| **overall (mean of rows)** | 0.000 | 0.066 | 0.124 | 5.66 | 4.20 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_03-41-23_EXP-006`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 5.34% | 0.128 | 0.220 | 0.320 | 9.9% | 2.22 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_03-41-23_EXP-006`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00609 | +0.01398 | +0.01840 | +0.01829 |
| track_lin_vel_xy | +0.00497 | +0.01287 | +0.01523 | +0.01480 |
| feet_air_time | -0.00296 | +0.00529 | +0.00609 | +0.00770 |
| track_ang_vel_z | +0.00350 | +0.00535 | +0.00610 | +0.00608 |
| torques | -0.00299 | -0.00395 | -0.00416 | -0.00469 |
| action_rate | -0.00235 | -0.00224 | -0.00210 | -0.00252 |
| lin_vel_z | -0.00436 | -0.00133 | -0.00104 | -0.00100 |
| orientation | -0.00096 | -0.00103 | -0.00085 | -0.00099 |
| ang_vel_xy | -0.00051 | -0.00078 | -0.00069 | -0.00092 |
| joint_acc | -4.9e-05 | -0.00007 | -0.00008 | -0.00009 |
| base_height | -0.00038 | -0.00012 | -0.00010 | -0.00008 |
| undesired_contacts | -2.9e-06 | -4.8e-06 | -2.3e-06 | -2.6e-06 |
| episode length (steps) | 132 | 874 | 938 | 926 |

Episode endings near iteration 1499: fell_over 1.5%, illegal_contact 12.9%, time_out 85.6%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
