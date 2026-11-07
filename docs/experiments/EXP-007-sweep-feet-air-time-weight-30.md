# EXP-007: sweep: feet_air_time weight 30

**Status:** trained 2026-11-07 (seed 42), verdict pending (Brian) · **Parent:** EXP-004

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) No per-run hypothesis: this is one run of Brian's 1-D sweep, verbatim: "Run a 1-D sweep on feet_air_time's weight: 3.0, 15.0, and 30.0 (7.5 is EXP-004, 1.0 is EXP-003). Same seed 42, everything else identical, one at a time, each as its own experiment, scored the same way." "Objective for ranking: lowest flicker share, with planar tracking error no worse than EXP-002 + 10% and zero falls. Also report swing median and servo saturation for each, so I can spot high-stepping or strain."

## Change (one variable)

vs. EXP-004: **one weight.** `WEIGHTS["feet_air_time"]` 7.5 → **30** (EXP-003: 1.0). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.02924 per step standing still on a zero command; +0.03722 for the EXP-004 policy on the grid (feet_air_time +0.01076, 26.1%), commands +0.0280 to +0.0402. Not flagged.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `9a96180`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-007`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-007`
- Trained at commit `9a96180`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_04-31-49_EXP-007`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.006 | 0.031 | 1.49 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.134 | 0.140 | 8.72 | 5.83 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.186 | 0.169 | 9.12 | 3.48 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.091 | 0.110 | 8.50 | 2.84 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.122 | 0.191 | 8.70 | 4.11 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.111 | 0.216 | 8.22 | 3.50 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.112 | 0.180 | 8.20 | 5.63 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.108 | 0.173 | 8.28 | 6.56 |
| **overall (mean of rows)** | 0.000 | 0.109 | 0.151 | 7.65 | 4.57 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_04-31-49_EXP-007`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 11.72% | 0.144 | 0.228 | 0.348 | 7.4% | 2.15 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_04-31-49_EXP-007`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00874 | +0.01738 | +0.02363 | +0.02147 |
| feet_air_time | -0.00529 | +0.01357 | +0.01787 | +0.01928 |
| track_lin_vel_xy | +0.00493 | +0.01064 | +0.01267 | +0.01192 |
| torques | -0.00304 | -0.00489 | -0.00587 | -0.00676 |
| track_ang_vel_z | +0.00346 | +0.00479 | +0.00591 | +0.00570 |
| action_rate | -0.00237 | -0.00259 | -0.00303 | -0.00417 |
| orientation | -0.00107 | -0.00135 | -0.00135 | -0.00175 |
| lin_vel_z | -0.00440 | -0.00157 | -0.00126 | -0.00133 |
| ang_vel_xy | -0.00053 | -0.00098 | -0.00113 | -0.00124 |
| base_height | -0.00039 | -0.00015 | -0.00009 | -0.00010 |
| joint_acc | -5.0e-05 | -0.00008 | -0.00009 | -0.00009 |
| undesired_contacts | -4.6e-06 | -5.7e-06 | -2.2e-06 | -4.3e-06 |
| episode length (steps) | 130 | 852 | 928 | 863 |

Episode endings near iteration 1499: fell_over 7.0%, illegal_contact 21.0%, time_out 72.0%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict

(2026-11-07) Out (Brian): "Weights 15 and 30 cut flickers further but blow up saturation (5.3%, 11.7%) and tracking, so they're out."
