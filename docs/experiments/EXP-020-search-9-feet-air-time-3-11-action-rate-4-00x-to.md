# EXP-020: search 9: feet_air_time 3.11, action_rate 4.00x, torques 0.75x

**Status:** search trial 9 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 45 min, no crash), scored with the staleness and delay on; constraints pass; verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 9: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 3.106; action_rate -0.08 -> -0.32 (4.00x); torques -0.125 -> -0.09338 (0.75x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `880da1f`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-020 --env.rewards.feet_air_time.weight 3.10615 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.093384`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0292, walking +0.0272 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-020`

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

Brian (2026-11-08): "Add EXP-020 to the seed replicates (seeds 43 and 44)." Same weights, task and scoring as seed 42; one run at a time.

- **Seed 43** (training 2026-11-08): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-020-s43 --env.rewards.feet_air_time.weight 3.10615 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.093384`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-020-s43`, console log `~/dev/ironbark_runs/EXP-020-s43.log`.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_08-49-59_EXP-020`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.011 | 0.44 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.030 | 0.085 | 2.71 | 1.21 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.052 | 0.089 | 3.68 | 1.35 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.087 | 2.53 | 1.09 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.033 | 0.110 | 2.85 | 1.68 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.036 | 0.128 | 2.83 | 1.53 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.023 | 0.096 | 2.21 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.025 | 0.111 | 2.15 | nan |
| **overall (mean of rows)** | 0.000 | 0.030 | 0.090 | 2.42 | 1.37 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_08-49-59_EXP-020`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.23% | 0.008 | 0.184 | 0.208 | 12.1% | 2.29 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_08-49-59_EXP-020`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00506 | +0.01218 | +0.01554 | +0.01611 |
| total | -0.00973 | +0.00801 | +0.01432 | +0.01556 |
| track_ang_vel_z | +0.00343 | +0.00474 | +0.00578 | +0.00595 |
| action_rate | -0.00897 | -0.00400 | -0.00335 | -0.00328 |
| torques | -0.00245 | -0.00205 | -0.00201 | -0.00196 |
| feet_air_time | -0.00067 | +0.00053 | +0.00082 | +0.00083 |
| lin_vel_z | -0.00433 | -0.00134 | -0.00098 | -0.00081 |
| orientation | -0.00086 | -0.00112 | -0.00075 | -0.00063 |
| ang_vel_xy | -0.00053 | -0.00075 | -0.00059 | -0.00052 |
| base_height | -0.00038 | -0.00011 | -0.00007 | -0.00007 |
| joint_acc | -0.00005 | -0.00005 | -0.00006 | -0.00006 |
| undesired_contacts | -1.2e-07 | -1.1e-05 | -4.0e-06 | -1.8e-06 |
| episode length (steps) | 132 | 776 | 915 | 947 |

Episode endings near iteration 1499: fell_over 1.8%, illegal_contact 9.2%, time_out 89.0%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
