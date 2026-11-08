# EXP-018: search 7: feet_air_time 3.38, action_rate 4.00x, torques 0.62x

**Status:** search trial 7 (Optuna); trained 2026-11-08 (seed 42, 1500 iterations, 44 min, no crash), scored with the staleness and delay on; constraints pass; seeds 43/44 trained and scored 2026-11-08 (Brian's pick); verdict pending (Brian) · **Parent:** EXP-010

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

- **Seed 43** (trained and scored 2026-11-08, 44 min, no crash): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-018-s43 --env.rewards.feet_air_time.weight 3.37843 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.0772526`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-018-s43`, console log `~/dev/ironbark_runs/EXP-018-s43.log`.
- **Seed 44** (trained and scored 2026-11-08, 44 min, no crash): `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 44 --agent.run-name EXP-018-s44 --env.rewards.feet_air_time.weight 3.37843 --env.rewards.action_rate.weight -0.32 --env.rewards.torques.weight -0.0772526`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-018-s44`, console log `~/dev/ironbark_runs/EXP-018-s44.log`.

**Seeds 42/43/44, mean ± sample SD [min–max]** (scoreboard v1 overall + gait diagnostics, `model_1499.pt`, staleness and delay on):

| Seed | Falls | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT | Saturation | Flicker | Swing median [s] |
|---|---|---|---|---|---|---|---|---|
| 42 | 0.000 | 0.0319 | 0.0872 | 2.467 | 1.456 | 0.23% | 12.38% | 0.1840 |
| 43 | 0.000 | 0.0316 | 0.0888 | 2.579 | 1.743 | 0.35% | 12.35% | 0.1840 |
| 44 | 0.000 | 0.0308 | 0.0984 | 2.507 | 1.426 | 0.55% | 12.09% | 0.1840 |
| **mean ± SD [min–max]** | 0.000 ± 0.000 [0.000–0.000] | 0.0314 ± 0.0006 [0.0308–0.0319] | 0.0915 ± 0.0060 [0.0872–0.0984] | 2.518 ± 0.057 [2.467–2.579] | 1.541 ± 0.175 [1.426–1.743] | 0.38% ± 0.16% [0.23%–0.55%] | 12.27% ± 0.16% [12.09%–12.38%] | 0.1840 ± 0.0000 [0.1840–0.1840] |

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

**2026-11-08, scoreboard v1.** Run `2026-11-08_11-07-22_EXP-018-s43`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.002 | 0.009 | 0.33 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.089 | 2.88 | 1.31 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.056 | 0.110 | 3.79 | 1.40 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.032 | 0.076 | 2.69 | 1.21 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.035 | 0.111 | 2.94 | 1.62 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.034 | 0.119 | 3.04 | 1.78 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.030 | 0.104 | 2.49 | 3.14 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.093 | 2.46 | nan |
| **overall (mean of rows)** | 0.000 | 0.032 | 0.089 | 2.58 | 1.74 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_11-07-22_EXP-018-s43`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.35% | 0.008 | 0.184 | 0.212 | 12.4% | 2.26 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_11-07-22_EXP-018-s43`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00521 | +0.01279 | +0.01579 | +0.01619 |
| total | -0.00921 | +0.00820 | +0.01478 | +0.01580 |
| track_ang_vel_z | +0.00333 | +0.00478 | +0.00577 | +0.00601 |
| action_rate | -0.00897 | -0.00429 | -0.00352 | -0.00336 |
| torques | -0.00202 | -0.00186 | -0.00175 | -0.00170 |
| feet_air_time | -0.00069 | +0.00063 | +0.00091 | +0.00093 |
| lin_vel_z | -0.00433 | -0.00160 | -0.00093 | -0.00089 |
| orientation | -0.00076 | -0.00123 | -0.00074 | -0.00068 |
| ang_vel_xy | -0.00054 | -0.00082 | -0.00060 | -0.00053 |
| base_height | -0.00038 | -0.00014 | -0.00007 | -0.00010 |
| joint_acc | -0.00005 | -0.00006 | -0.00006 | -0.00006 |
| undesired_contacts | -1.0e-06 | -1.7e-05 | -2.6e-06 | -2.4e-06 |
| episode length (steps) | 132 | 694 | 926 | 928 |

Episode endings near iteration 1499: fell_over 4.0%, illegal_contact 10.7%, time_out 85.3%.

**2026-11-08, scoreboard v1.** Run `2026-11-08_11-52-20_EXP-018-s44`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.005 | 0.32 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.032 | 0.086 | 2.74 | 1.23 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.055 | 0.102 | 3.93 | 1.43 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.035 | 0.083 | 2.66 | 1.15 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.035 | 0.148 | 2.93 | 1.62 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.033 | 0.120 | 2.92 | 1.69 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.025 | 0.122 | 2.14 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.028 | 0.122 | 2.40 | nan |
| **overall (mean of rows)** | 0.000 | 0.031 | 0.098 | 2.51 | 1.43 |

**2026-11-08, gait diagnostics (not scoreboard).** Run `2026-11-08_11-52-20_EXP-018-s44`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.55% | 0.008 | 0.184 | 0.212 | 12.1% | 2.28 |

**2026-11-08, training curves (TensorBoard).** Run `2026-11-08_11-52-20_EXP-018-s44`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00511 | +0.01207 | +0.01558 | +0.01594 |
| total | -0.00910 | +0.00692 | +0.01431 | +0.01523 |
| track_ang_vel_z | +0.00337 | +0.00463 | +0.00570 | +0.00592 |
| action_rate | -0.00886 | -0.00425 | -0.00360 | -0.00355 |
| torques | -0.00199 | -0.00176 | -0.00176 | -0.00171 |
| feet_air_time | -0.00062 | +0.00045 | +0.00092 | +0.00092 |
| lin_vel_z | -0.00430 | -0.00183 | -0.00101 | -0.00088 |
| orientation | -0.00083 | -0.00133 | -0.00078 | -0.00072 |
| ang_vel_xy | -0.00054 | -0.00082 | -0.00061 | -0.00054 |
| base_height | -0.00038 | -0.00018 | -0.00007 | -0.00009 |
| joint_acc | -0.00005 | -0.00005 | -0.00006 | -0.00006 |
| undesired_contacts | -2.7e-06 | -2.5e-05 | -2.8e-06 | -2.4e-06 |
| episode length (steps) | 132 | 676 | 913 | 928 |

Episode endings near iteration 1499: fell_over 3.3%, illegal_contact 11.3%, time_out 85.4%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
