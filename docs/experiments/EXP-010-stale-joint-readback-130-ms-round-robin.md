# EXP-010: stale joint readback (130 ms round-robin)

**Status:** trained 2026-11-07 (seed 42, 1500 iterations, 65 min incl. a slow start from GPU sharing, no crash), scored with the staleness and delay on; verdict pending (Brian) · **Parent:** EXP-009

## Hypothesis (Brian, before the run)

> Two experiments, both from EXP-005's config (feet_air_time 3.0), seed 42, one at a time:
> - EXP-009: add ~100 ms actuator/command delay (based on Phase 1 data). Nothing else changes.
> - EXP-010: EXP-009 + joint-position observations that refresh round-robin every ~105 ms (stale between refreshes).
>
> Hypothesis: both still walk, but slower and less precisely: higher tracking error, lower step frequency, more falls than EXP-005, with EXP-010 worse than EXP-009. If either can't walk or falls go high, next experiment adds the last ~5 actions to the observation (action history) so the policy knows what's in flight. If that fails too, we go Path B.

Written 2026-11-07, before EXP-009 trained. Afterwards (before either trained) Brian set the delay to 40 ms and the refresh cycle to 130 ms: see Change.

## Change (one variable)

vs. EXP-009: the actor's joint feedback becomes what the real dog can see.
- **Joint positions:** the round-robin sample-and-hold of `read_motor()` (`ironbark_rl/brian/obs.py`): a 130 ms cycle of 15 slots polled in xgolib ID order (11, 12, 13, 21, ..., 43, then 3 empty arm slots), a random phase per env at reset, each poll's value interpolated within the policy step it lands in. It replaces the actor's 1-2 policy-step (20-40 ms) joint-position delay (Brian agreed, 2026-11-07).
- **Joint velocities:** dropped from the actor (the dog has no velocity readback). Actor input 12 smaller.
- The critic keeps the true joint positions and velocities (with their usual 1-2 step delay); it never runs on the dog.

Brian's choices (2026-11-07 design questions): 130 ms, measured with all 12 joints commanded at 55 Hz like a policy (coarse: 126-144 ms; 105 ms with single-joint commands); drop the actor's joint velocity. The polling order uses the joint map Brian verified on the dog (`ironbark_rl/assets/s2_joint_map.py`).

Unchanged from EXP-009: 40 ms command delay, reward (EXP-005's), terminations, commands, randomization, observation noise.

**Scoring (Brian):** the staleness and the delay stay on in the play config. EXP-005's policy is re-scored under the same conditions as the reference: it needs a joint-velocity input, so it gets the change of the stale reading per step (task `IronBark-S2-Walk-Flat-Brian-StaleJoints-VelRef`, `--tag stale_joints`).

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `8db9835`
- Task: `IronBark-S2-Walk-Flat-Brian-StaleJoints`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian-StaleJoints --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-010`
- Guard: `tools/reward_check.py IronBark-S2-Walk-Flat-Brian-StaleJoints` (standing only: no earlier checkpoint has this actor input): OK, standing +0.0292. Tests: 163 passed + 3 sim tests (stale readings refresh ~once per cycle and lag; actor input 12 smaller).
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian_stale_joints/*_EXP-010`

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_20-02-00_EXP-010`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.007 | 0.70 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.046 | 0.133 | 3.30 | 1.17 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.062 | 0.150 | 4.86 | 1.44 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.043 | 0.090 | 3.23 | 1.22 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.048 | 0.166 | 3.45 | 1.82 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.042 | 0.167 | 3.53 | 1.87 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.030 | 0.137 | 2.41 | 2.33 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.033 | 0.133 | 2.53 | 2.47 |
| **overall (mean of rows)** | 0.000 | 0.038 | 0.123 | 3.00 | 1.76 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_20-02-00_EXP-010`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.80% | 0.008 | 0.184 | 0.208 | 15.1% | 2.34 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_20-02-00_EXP-010`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| track_lin_vel_xy | +0.00505 | +0.00936 | +0.01490 | +0.01556 |
| total | -0.00401 | +0.00594 | +0.01269 | +0.01388 |
| track_ang_vel_z | +0.00344 | +0.00452 | +0.00520 | +0.00536 |
| torques | -0.00335 | -0.00329 | -0.00367 | -0.00358 |
| action_rate | -0.00234 | -0.00197 | -0.00181 | -0.00174 |
| lin_vel_z | -0.00433 | -0.00098 | -0.00099 | -0.00088 |
| orientation | -0.00087 | -0.00113 | -0.00086 | -0.00079 |
| feet_air_time | -0.00065 | +0.00028 | +0.00072 | +0.00070 |
| ang_vel_xy | -0.00052 | -0.00071 | -0.00065 | -0.00060 |
| base_height | -0.00038 | -0.00008 | -0.00007 | -0.00007 |
| joint_acc | -0.00005 | -0.00005 | -0.00007 | -0.00007 |
| undesired_contacts | -4.3e-07 | -6.4e-06 | -3.4e-06 | -2.0e-06 |
| episode length (steps) | 132 | 829 | 896 | 921 |

Episode endings near iteration 1499: fell_over 3.8%, illegal_contact 12.0%, time_out 84.2%.

**Reference `stale_joints`: task `IronBark-S2-Walk-Flat-Brian-StaleJoints-VelRef`.** **2026-11-07, scoreboard v1.** Run `2026-11-07_02-47-40_EXP-005`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.003 | 0.011 | 1.14 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.084 | 0.206 | 7.59 | 1.91 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.133 | 0.300 | 10.60 | 1.84 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.064 | 0.175 | 6.84 | 1.71 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.071 | 0.229 | 6.65 | 2.20 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.075 | 0.205 | 7.42 | 2.53 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.043 | 0.165 | 5.28 | 4.13 |
| (+0.0, +0.0, -0.5) | 0.000 | 0.033 | 0.164 | 5.51 | nan |
| **overall (mean of rows)** | 0.000 | 0.064 | 0.182 | 6.38 | 2.39 |

**Reference `stale_joints`: task `IronBark-S2-Walk-Flat-Brian-StaleJoints-VelRef`.** **2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_02-47-40_EXP-005`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 2.38% | 0.008 | 0.176 | 0.216 | 19.9% | 2.57 |

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
