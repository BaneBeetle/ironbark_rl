# EXP-009: 40 ms command delay (Phase 1)

**Status:** trained 2026-11-07 (seed 42, 1500 iterations, 49 min, no crash), scored with the delay on; verdict pending (Brian) · **Parent:** EXP-005

## Hypothesis (Brian, before the run)

> Two experiments, both from EXP-005's config (feet_air_time 3.0), seed 42, one at a time:
> - EXP-009: add ~100 ms actuator/command delay (based on Phase 1 data). Nothing else changes.
> - EXP-010: EXP-009 + joint-position observations that refresh round-robin every ~105 ms (stale between refreshes).
>
> Hypothesis: both still walk, but slower and less precisely: higher tracking error, lower step frequency, more falls than EXP-005, with EXP-010 worse than EXP-009. If either can't walk or falls go high, next experiment adds the last ~5 actions to the observation (action history) so the policy knows what's in flight. If that fails too, we go Path B.

Written 2026-11-07, before training. Afterwards (also before training) Brian set the delay to **40 ms**, not ~100 ms: see Change.

## Change (one variable)

vs. EXP-005: the actuator command delay. Luwu's random 1-2 physics steps (4-8 ms) -> **40 ms fixed** (10 physics steps, every env), in training and in scoring.

Brian's choice (2026-11-07 design questions, after the hypothesis): 40 ms, because the earliest of 18 Phase 1 step responses moved 50 ms after the command, and the sine lag (88 ms) minus the mean readback age (~52 ms) is ~36 ms; the rest of the ~100 ms is readback staleness, which EXP-010 adds. Numbers and reasons: `ironbark_rl/brian/latency_config.py`.

Unchanged: reward (EXP-005's, `feet_air_time` 3.0), observations (the actor's joint pos/vel keep their 1-2 policy-step delay), terminations, commands, randomization.

**Scoring (Brian):** the 40 ms delay stays on in the play config (and the joint-observation delay too), so the scoreboard sees it. EXP-005's policy is re-scored under the same conditions as the reference (`--tag cmd_delay`), without retraining.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `8c186ad`
- Task: `IronBark-S2-Walk-Flat-Brian-CmdDelay`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-CmdDelay --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-009`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-CmdDelay --checkpoint <EXP-005>/model_1499.pt`: OK, every mean per-step total >= 0 (standing +0.0291). Tests: 143 passed (+4 sim tests passed: the command reaches `ctrl` exactly 2 policy steps later).
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_cmd_delay/*_EXP-009`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_19-06-05_EXP-009`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.008 | 0.68 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.036 | 0.090 | 3.06 | 1.15 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.056 | 0.119 | 4.55 | 1.39 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.040 | 0.092 | 2.86 | 1.09 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.035 | 0.131 | 3.30 | 1.77 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.035 | 0.114 | 3.12 | 1.57 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.032 | 0.111 | 2.52 | 2.39 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.035 | 0.109 | 2.51 | 2.71 |
| **overall (mean of rows)** | 0.000 | 0.034 | 0.097 | 2.83 | 1.73 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_19-06-05_EXP-009`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.60% | 0.008 | 0.184 | 0.212 | 13.3% | 2.33 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_19-06-05_EXP-009`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00505 | +0.01100 | +0.01563 | +0.01602 |
| total | -0.00404 | +0.00751 | +0.01397 | +0.01502 |
| track_ang_vel_z | +0.00343 | +0.00471 | +0.00541 | +0.00558 |
| torques | -0.00335 | -0.00361 | -0.00370 | -0.00350 |
| action_rate | -0.00233 | -0.00199 | -0.00175 | -0.00164 |
| lin_vel_z | -0.00437 | -0.00112 | -0.00090 | -0.00085 |
| feet_air_time | -0.00068 | +0.00046 | +0.00073 | +0.00077 |
| orientation | -0.00083 | -0.00106 | -0.00071 | -0.00065 |
| ang_vel_xy | -0.00053 | -0.00073 | -0.00061 | -0.00056 |
| base_height | -0.00038 | -0.00008 | -0.00007 | -0.00008 |
| joint_acc | -0.00005 | -0.00006 | -0.00007 | -0.00007 |
| undesired_contacts | -8.3e-07 | -5.5e-06 | -2.4e-06 | -3.1e-06 |
| episode length (steps) | 132 | 857 | 932 | 926 |

Episode endings near iteration 1499: fell_over 1.8%, illegal_contact 12.9%, time_out 85.3%.

**Reference `cmd_delay`: task `IronBark-S2-Walk-Flat-Brian-CmdDelay`.** **2026-11-07, scoreboard v1.** Run `2026-11-07_02-47-40_EXP-005`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.009 | 0.65 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.044 | 0.139 | 3.45 | 1.46 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.068 | 0.127 | 4.57 | 1.48 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.048 | 0.114 | 3.35 | 1.39 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.043 | 0.123 | 3.71 | 1.90 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.047 | 0.116 | 3.84 | 1.96 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.030 | 0.133 | 2.81 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.027 | 0.132 | 2.93 | nan |
| **overall (mean of rows)** | 0.000 | 0.039 | 0.112 | 3.16 | 1.64 |

**Reference `cmd_delay`: task `IronBark-S2-Walk-Flat-Brian-CmdDelay`.** **2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_02-47-40_EXP-005`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.70% | 0.008 | 0.184 | 0.208 | 12.4% | 2.30 |

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
