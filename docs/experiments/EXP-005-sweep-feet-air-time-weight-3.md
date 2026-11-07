# EXP-005: sweep: feet_air_time weight 3

**Status:** trained 2026-11-07 (seed 42), verdict pending (Brian) · **Parent:** EXP-004

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) No per-run hypothesis: this is one run of Brian's 1-D sweep, verbatim: "Run a 1-D sweep on feet_air_time's weight: 3.0, 15.0, and 30.0 (7.5 is EXP-004, 1.0 is EXP-003). Same seed 42, everything else identical, one at a time, each as its own experiment, scored the same way." "Objective for ranking: lowest flicker share, with planar tracking error no worse than EXP-002 + 10% and zero falls. Also report swing median and servo saturation for each, so I can spot high-stepping or strain."

## Change (one variable)

vs. EXP-004: **one weight.** `WEIGHTS["feet_air_time"]` 7.5 → **3** (EXP-003: 1.0). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.02924 per step standing still on a zero command; +0.02753 for the EXP-004 policy on the grid (feet_air_time +0.00108, 3.4%), commands +0.0259 to +0.0287. Not flagged.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `3c18e65`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-005`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-005`
- Trained at commit `3c18e65`, 2026-11-07.

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

- **Seed 43**, started 2026-11-07 07:26 at commit `923a51b` (Brian: check the noise, 2026-11-07): `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-005-s43`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-005-s43`. Tests: 88 passed, 1 deselected, 35 warnings in 5.07s. Guard: +0.02924 per step standing, +0.02792 for the EXP-005 seed-42 policy on the grid, commands +0.0252 to +0.0292; not flagged.
- **Seed 44**, started 2026-11-07 08:16 at commit `3b58ca6` (Brian: check the noise, 2026-11-07): `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 44 --agent.run-name EXP-005-s44`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-005-s44`. Tests: 88 passed, 1 deselected, 35 warnings in 5.27s. Guard: +0.02924 per step standing, +0.02792 for the EXP-005 seed-42 policy on the grid, commands +0.0252 to +0.0292; not flagged.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_02-47-40_EXP-005`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.001 | 0.008 | 0.59 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.038 | 0.098 | 3.15 | 1.24 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.064 | 0.116 | 4.08 | 1.41 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.080 | 2.87 | 1.22 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.038 | 0.117 | 2.99 | 1.84 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.046 | 0.093 | 3.17 | 1.84 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.026 | 0.112 | 2.72 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.137 | 2.99 | 3.39 |
| **overall (mean of rows)** | 0.000 | 0.034 | 0.095 | 2.82 | 1.82 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_02-47-40_EXP-005`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.52% | 0.008 | 0.188 | 0.208 | 17.7% | 2.41 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_02-47-40_EXP-005`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00350 | +0.01159 | +0.01704 | +0.01824 |
| track_lin_vel_xy | +0.00509 | +0.01294 | +0.01641 | +0.01674 |
| track_ang_vel_z | +0.00352 | +0.00571 | +0.00642 | +0.00668 |
| torques | -0.00296 | -0.00330 | -0.00312 | -0.00290 |
| action_rate | -0.00233 | -0.00189 | -0.00155 | -0.00139 |
| feet_air_time | -0.00068 | +0.00067 | +0.00075 | +0.00083 |
| lin_vel_z | -0.00434 | -0.00104 | -0.00077 | -0.00069 |
| orientation | -0.00088 | -0.00075 | -0.00050 | -0.00046 |
| ang_vel_xy | -0.00049 | -0.00062 | -0.00048 | -0.00043 |
| joint_acc | -4.9e-05 | -0.00006 | -0.00007 | -0.00007 |
| base_height | -0.00037 | -0.00006 | -0.00006 | -0.00006 |
| undesired_contacts | -8.5e-07 | -2.5e-06 | -1.6e-06 | -1.2e-06 |
| episode length (steps) | 132 | 928 | 952 | 972 |

Episode endings near iteration 1499: fell_over 0.8%, illegal_contact 5.6%, time_out 93.6%.

**2026-11-07, scoreboard v1.** Run `2026-11-07_07-27-13_EXP-005-s43`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.004 | 0.016 | 0.50 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.078 | 2.82 | 1.10 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.069 | 0.097 | 3.30 | 1.20 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.100 | 2.64 | 1.13 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.047 | 0.112 | 2.94 | 1.62 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.050 | 0.116 | 3.02 | 1.70 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.026 | 0.142 | 2.67 | 2.95 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.030 | 0.096 | 2.54 | 3.09 |
| **overall (mean of rows)** | 0.000 | 0.037 | 0.094 | 2.55 | 1.83 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_07-27-13_EXP-005-s43`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.53% | 0.008 | 0.184 | 0.212 | 17.5% | 2.46 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_07-27-13_EXP-005-s43`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00277 | +0.01157 | +0.01704 | +0.01794 |
| track_lin_vel_xy | +0.00545 | +0.01314 | +0.01626 | +0.01667 |
| track_ang_vel_z | +0.00356 | +0.00572 | +0.00649 | +0.00663 |
| torques | -0.00289 | -0.00336 | -0.00303 | -0.00293 |
| action_rate | -0.00234 | -0.00190 | -0.00153 | -0.00145 |
| feet_air_time | -0.00060 | +0.00065 | +0.00078 | +0.00078 |
| lin_vel_z | -0.00429 | -0.00111 | -0.00080 | -0.00071 |
| orientation | -0.00073 | -0.00080 | -0.00052 | -0.00048 |
| ang_vel_xy | -0.00049 | -0.00062 | -0.00046 | -0.00042 |
| base_height | -0.00037 | -0.00007 | -0.00008 | -0.00009 |
| joint_acc | -4.9e-05 | -0.00006 | -0.00006 | -0.00007 |
| undesired_contacts | -1.2e-06 | -2.7e-06 | -1.8e-06 | -1.8e-06 |
| episode length (steps) | 131 | 918 | 952 | 959 |

Episode endings near iteration 1499: fell_over 1.4%, illegal_contact 7.4%, time_out 91.2%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict

(2026-11-07) **Provisional winner** (Brian), pending seeds 43 and 44. "My read: real-world priority is servo strain first (a dead servo makes everything else pointless), then tracking, then flickers. Under that ranking, EXP-005 (weight 3.0) wins: lowest saturation (0.52%), best planar tracking (0.0345), and flickers still down from 24.9% to 17.7%. Weights 15 and 30 cut flickers further but blow up saturation (5.3%, 11.7%) and tracking, so they're out."
