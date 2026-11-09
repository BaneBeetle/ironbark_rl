# EXP-024: search s2-9: feet_air_time 2.65, action_rate 4.00x, torques 0.70x

**Status:** search stage-2 trial 9 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; stage-2 constraints fail (saturation +56.7%, planar +6.0% over the limit); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search stage-2 trial 9: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 2.645; action_rate -0.08 -> -0.32 (4.00x); torques -0.125 -> -0.08761 (0.70x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `718c0c1`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-024 --env.rewards.feet_air_time.weight 2.64527 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.0876075`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0270 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-024`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_18-15-17_EXP-024`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.006 | 0.37 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.096 | 2.56 | 1.14 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.062 | 0.124 | 3.69 | 1.31 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.036 | 0.091 | 2.61 | 1.15 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.037 | 0.117 | 2.93 | 1.71 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.040 | 0.137 | 2.84 | 1.55 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.024 | 0.100 | 2.21 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.026 | 0.115 | 2.19 | nan |
| **overall (mean of rows)** | 0.000 | 0.033 | 0.098 | 2.42 | 1.37 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_18-15-17_EXP-024`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.47% | 0.008 | 0.184 | 0.208 | 12.6% | 2.30 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_18-15-17_EXP-024`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00507 | +0.01203 | +0.01570 | +0.01601 |
| total | -0.00952 | +0.00751 | +0.01454 | +0.01507 |
| track_ang_vel_z | +0.00343 | +0.00473 | +0.00578 | +0.00595 |
| action_rate | -0.00898 | -0.00409 | -0.00339 | -0.00338 |
| torques | -0.00230 | -0.00196 | -0.00190 | -0.00190 |
| lin_vel_z | -0.00433 | -0.00150 | -0.00094 | -0.00091 |
| orientation | -0.00088 | -0.00120 | -0.00067 | -0.00068 |
| feet_air_time | -0.00057 | +0.00044 | +0.00066 | +0.00067 |
| ang_vel_xy | -0.00053 | -0.00075 | -0.00057 | -0.00053 |
| base_height | -0.00038 | -0.00013 | -0.00007 | -0.00011 |
| joint_acc | -0.00005 | -0.00005 | -0.00006 | -0.00006 |
| undesired_contacts | -2.0e-07 | -1.6e-05 | -2.7e-06 | -3.4e-06 |
| episode length (steps) | 132 | 694 | 927 | 922 |

Episode endings near iteration 1499: fell_over 1.8%, illegal_contact 12.7%, time_out 85.5%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
