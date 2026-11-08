# EXP-022: search s2-7: feet_air_time 5.38, action_rate 4.40x, torques 1.40x

**Status:** search stage-2 trial 7 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 50 min, no crash), scored with the staleness and delay on; stage-2 constraints fail (planar +6.7% over the limit); verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search stage-2 trial 7: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 5.377; action_rate -0.08 -> -0.3523 (4.40x); torques -0.125 -> -0.1755 (1.40x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `c95294d`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-022 --env.rewards.feet_air_time.weight 5.37698 --env.rewards.action_rate.weight -0.352251 --env.rewards.torques.weight -0.175468`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0291, walking +0.0274 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-022`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_16-38-23_EXP-022`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.009 | 0.35 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.034 | 0.094 | 2.53 | 1.05 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.055 | 0.106 | 3.35 | 1.21 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.083 | 2.48 | 1.09 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.042 | 0.125 | 2.63 | 1.40 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.039 | 0.101 | 2.62 | 1.44 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.028 | 0.087 | 2.08 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.030 | 0.104 | 2.11 | 2.62 |
| **overall (mean of rows)** | 0.000 | 0.033 | 0.089 | 2.27 | 1.47 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_16-38-23_EXP-022`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.09% | 0.008 | 0.188 | 0.208 | 12.1% | 2.27 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_16-38-23_EXP-022`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00504 | +0.01161 | +0.01524 | +0.01564 |
| total | -0.01328 | +0.00567 | +0.01357 | +0.01449 |
| track_ang_vel_z | +0.00343 | +0.00485 | +0.00587 | +0.00605 |
| action_rate | -0.00986 | -0.00402 | -0.00339 | -0.00331 |
| torques | -0.00460 | -0.00344 | -0.00325 | -0.00323 |
| feet_air_time | -0.00113 | +0.00107 | +0.00164 | +0.00167 |
| lin_vel_z | -0.00433 | -0.00194 | -0.00101 | -0.00090 |
| orientation | -0.00087 | -0.00143 | -0.00080 | -0.00074 |
| ang_vel_xy | -0.00053 | -0.00076 | -0.00057 | -0.00053 |
| base_height | -0.00038 | -0.00019 | -0.00009 | -0.00011 |
| joint_acc | -0.00005 | -4.9e-05 | -0.00005 | -0.00005 |
| undesired_contacts | -4.0e-07 | -2.7e-05 | -4.3e-06 | -3.9e-06 |
| episode length (steps) | 132 | 571 | 891 | 911 |

Episode endings near iteration 1499: fell_over 3.6%, illegal_contact 13.5%, time_out 82.9%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
