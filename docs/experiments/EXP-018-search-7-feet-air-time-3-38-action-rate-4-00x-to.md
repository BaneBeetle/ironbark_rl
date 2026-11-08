# EXP-018: search 7: feet_air_time 3.38, action_rate 4.00x, torques 0.62x

**Status:** search trial 7 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; verdict pending (Brian) · **Parent:** EXP-010

## Hypothesis (Brian, before the run)

> Search trial 7: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on [SEARCH-exp010-reward-weights.md](SEARCH-exp010-reward-weights.md).

## Change (one variable)

vs. EXP-010: three reward weights, picked by the search (Brian's search varies them together): feet_air_time 3 -> 3.378; action_rate -0.08 -> -0.32 (4.00x); torques -0.125 -> -0.07725 (0.62x). Everything else is EXP-010's: task `IronBark-S2-Walk-Flat-Brian-StaleJoints` (40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, seed 42, 1500 iterations. Scored like EXP-010: the delay and the staleness stay on.

## Setup (auto-filled)

- Date: 2026-11-08
- Commit: `e2588aa`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-018 --env.rewards.feet_air_time.weight 3.37843 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.0772526`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints --checkpoint <EXP-010 run>/model_1499.pt` with this trial's three weights (standing still; EXP-010's policy on the command grid): standing +0.0293, walking +0.0273 per step. OK
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-018`

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

Brian (2026-11-08): "Run seeds 43 and 44 for EXP-017, EXP-018 and EXP-015 (my top 3; I rank by saturation first, then tracking, then flicker)." Same weights, task and scoring as seed 42; one run at a time.

- **Seed 43** (training 2026-11-08): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-018-s43 --env.rewards.feet_air_time.weight 3.37843 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.0772526`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-018-s43`, console log `~/dev/ironbark_runs/EXP-018-s43.log`.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-08, scoreboard v1.** Run `2026-11-08_07-18-24_EXP-018`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.007 | 0.37 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.032 | 0.084 | 2.82 | 1.33 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.052 | 0.095 | 3.69 | 1.44 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.078 | 2.72 | 1.20 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.039 | 0.124 | 2.84 | 1.67 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.037 | 0.107 | 2.85 | 1.64 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.031 | 0.096 | 2.30 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.026 | 0.107 | 2.14 | nan |
| **overall (mean of rows)** | 0.000 | 0.032 | 0.087 | 2.47 | 1.46 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_07-18-24_EXP-018`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.23% | 0.008 | 0.184 | 0.208 | 12.4% | 2.26 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_07-18-24_EXP-018`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| total | -0.00937 | +0.00790 | +0.01490 | +0.01639 |
| track_lin_vel_xy | +0.00505 | +0.01188 | +0.01565 | +0.01628 |
| track_ang_vel_z | +0.00343 | +0.00477 | +0.00579 | +0.00613 |
| action_rate | -0.00897 | -0.00414 | -0.00339 | -0.00321 |
| torques | -0.00203 | -0.00163 | -0.00170 | -0.00164 |
| feet_air_time | -0.00071 | +0.00053 | +0.00098 | +0.00092 |
| lin_vel_z | -0.00433 | -0.00143 | -0.00098 | -0.00084 |
| orientation | -0.00086 | -0.00119 | -0.00073 | -0.00061 |
| ang_vel_xy | -0.00053 | -0.00071 | -0.00059 | -0.00050 |
| base_height | -0.00038 | -0.00011 | -0.00007 | -0.00007 |
| joint_acc | -0.00005 | -4.9e-05 | -0.00006 | -0.00006 |
| undesired_contacts | -1.4e-07 | -1.3e-05 | -3.7e-06 | -1.8e-06 |
| episode length (steps) | 132 | 717 | 917 | 950 |

Episode endings near iteration 1499: fell_over 1.7%, illegal_contact 7.6%, time_out 90.7%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
