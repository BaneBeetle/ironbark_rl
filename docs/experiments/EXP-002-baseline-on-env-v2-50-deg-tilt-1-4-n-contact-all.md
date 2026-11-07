# EXP-002: baseline on env v2: 50 deg tilt, 1.4 N contact, all collisions

**Status:** trained 2026-11-07 (seed 42), verdict pending (Brian) · **Parent:** EXP-000

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-06) With all collisions on and stricter terminations (50° tilt, 1.43 N contact), the baseline still learns to walk. Tracking error similar to EXP-000, possibly slower early learning since the trunk can no longer sink through the floor. Measured with metrics.py on the command grid.

## Change (one variable)

vs. EXP-000: the environment's fall handling (env v2), reward unchanged (Luwu's). Brian's decisions, 2026-11-06. These are bundled as one re-baseline, not an ablation, so this run becomes the baseline the legged_gym-style reward is compared against.

1. Tilt termination 70° → **50°** (`FALL_TILT_TERMINATION_DEG`). The scoreboard's fall line stays `metrics.FALL_TILT_DEG = 46`, where passive sim recovery fails.
2. Non-foot contact termination 10 N → **15% of body weight, 1.43 N** (`NONFOOT_CONTACT_LIMIT_N`). 10 N exceeded the S2's whole weight (9.54 N).
3. **All collision meshes touch the ground** (trunk, hips, thighs, calves; no self-collision; `S2_WALK_COLLISION`). Before, only the 4 calves collided, so the contact termination could never fire and a fallen trunk sank through the floor. Random actions, 4096 dogs × 5 s: contact terminations 0 → 2888, lowest base z −0.018 → +0.060 m. Same env step time standing (58.3 → 57.7 ms), and no contact-buffer warnings.

The scoreboard runs with terminations off, so changes 1–2 only affect training. Change 3 also changes physics during evaluation.

## Setup (auto-filled)

- Date: 2026-11-06
- Commit: `347a788`
- Task: `IronBark-S2-Walk-Flat`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-002`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk/*_EXP-002`
- Trained at commit `ef8fde1` (the baseline env is unchanged since `347a788`), 2026-11-06.

### Seed replicates (same setup, different seed: measures the noise floor, rule 4)

- **Seed 43**, started 2026-11-07 09:04 at commit `15c2f9d` (Brian: check the noise, 2026-11-07): `python tools/run.py train IronBark-S2-Walk-Flat --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 43 --agent.run-name EXP-002-s43`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk/*_EXP-002-s43`. Tests: 88 passed, 1 deselected, 35 warnings in 5.49s. Guard skipped: this is Luwu's reward (the guard is for Brian's terms, and would list Luwu's).

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-06_22-53-42_EXP-002`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.001 | 0.003 | 0.33 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.041 | 0.070 | 2.36 | 1.04 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.088 | 0.141 | 3.35 | 1.42 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.033 | 0.079 | 2.11 | 0.92 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.039 | 0.127 | 2.76 | 1.80 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.039 | 0.106 | 2.62 | 1.60 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.021 | 0.116 | 1.77 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.023 | 0.096 | 1.86 | nan |
| **overall (mean of rows)** | 0.000 | 0.036 | 0.092 | 2.14 | 1.36 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-06_22-53-42_EXP-002`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.79% | 0.008 | 0.144 | 0.196 | 22.5% | 2.62 |

**2026-11-07, scoreboard v1.** Run `2026-11-07_09-04-47_EXP-002-s43`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.001 | 0.003 | 0.33 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.050 | 0.103 | 2.38 | 1.06 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.071 | 0.132 | 3.24 | 1.29 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.037 | 0.065 | 2.08 | 0.90 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.045 | 0.135 | 2.57 | 1.61 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.038 | 0.128 | 2.63 | 1.63 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.019 | 0.118 | 1.84 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.022 | 0.113 | 1.88 | nan |
| **overall (mean of rows)** | 0.000 | 0.035 | 0.100 | 2.12 | 1.30 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_09-04-47_EXP-002-s43`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 0.40% | 0.008 | 0.132 | 0.192 | 25.0% | 2.74 |

**2026-11-07, training curves (TensorBoard).** Run `2026-11-07_09-04-47_EXP-002-s43`. Reward rows: each term's per-step contribution (weight × value × dt), mean over ±10 iterations.

| | iter 0 | iter 100 | iter 400 | iter 1499 |
|---|---|---|---|---|
| episode length (steps) | 132 | 975 | 958 | 973 |

Episode endings near iteration 1499: fell_over 1.5%, illegal_contact 3.8%, time_out 94.8%.

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

(2026-11-07) EXP-002 early learning: at iter 100 its error (0.569) beat EXP-000 (0.618), so my "slower early learning" prediction was wrong (one seed).

## Verdict
