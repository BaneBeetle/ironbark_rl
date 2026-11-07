# EXP-003: Brian's legged_gym-style reward on env v2

**Status:** trained 2026-11-07 (seed 42), verdict pending (Brian) · **Parent:** EXP-002

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-06) Similar tracking error, but smoother and gentler: lower action rate, lower servo saturation %, and fewer flicker touchdowns (p10 swing time well above 0.008 s) thanks to the 0.07 s air-time threshold and requested-torque penalty. Risk: slightly worse tracking from the extra regularization.

_Claude's note: servo saturation % and swing-time p10 aren't on the frozen scoreboard; `tools/gait_check.py` reports them next to it as diagnostics. EXP-002 diagnostics: saturation 0.79%, swing p10 0.008 s, flicker touchdowns (< 0.02 s) 22.5%._

## Change (one variable)

vs. EXP-002: **the reward only.** Luwu's terms → Brian's eleven legged_gym-style terms (`ironbark_rl/brian/rewards.py`; weights and parameters in `ironbark_rl/brian/reward_config.py`, approved by Brian 2026-11-06). Task `IronBark-S2-Walk-Flat-Brian` matches the EXP-002 task in terminations, observations, actions, commands, randomization and collisions (config diff checked), and PPO settings differ only in `experiment_name`.

Fall-on-purpose guard before training (`tools/reward_check.py`): mean per-step total +0.0292 standing still on a zero command, and +0.0273 for the EXP-002 policy on the grid, with every command positive.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `455a231`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-003`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-003`
- Trained at commit `455a231`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

**2026-11-07, scoreboard v1.** Run `2026-11-07_00-08-25_EXP-003`, checkpoint `model_1499.pt` (iteration 1499), 32 dogs × 10 s per command, seed 0, mass 0.972 kg. Smoothness and CoT use only episodes that never fell; CoT is NaN by design where there's no ground speed (standing, turning in place).

| Command (vx, vy, wz) | Fall rate | Planar err [m/s] | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT |
|---|---|---|---|---|---|
| (+0.0, +0.0, +0.0) | 0.000 | 0.009 | 0.032 | 0.71 | nan |
| (+0.2, +0.0, +0.0) | 0.000 | 0.046 | 0.072 | 2.87 | 1.04 |
| (+0.4, +0.0, +0.0) | 0.000 | 0.070 | 0.104 | 3.97 | 1.37 |
| (-0.2, +0.0, +0.0) | 0.000 | 0.048 | 0.074 | 2.40 | 1.00 |
| (+0.0, +0.2, +0.0) | 0.000 | 0.045 | 0.099 | 2.99 | 1.60 |
| (+0.0, -0.2, +0.0) | 0.000 | 0.040 | 0.088 | 2.97 | 1.57 |
| (+0.0, +0.0, +0.5) | 0.000 | 0.024 | 0.096 | 2.10 | nan |
| (+0.0, +0.0, -0.5) | 0.000 | 0.029 | 0.110 | 2.19 | 2.21 |
| **overall (mean of rows)** | 0.000 | 0.039 | 0.084 | 2.53 | 1.47 |

**2026-11-07, gait diagnostics (not scoreboard).** Run `2026-11-07_00-08-25_EXP-003`, checkpoint `model_1499.pt`, 32 dogs × 10 s per command (first 1 s skipped), seed 0. Saturation: requested torque above the 0.43 N·m cap.

| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< 0.02 s) | Touchdowns / foot / s |
|---|---|---|---|---|---|
| 1.04% | 0.008 | 0.168 | 0.208 | 24.8% | 2.65 |

**2026-11-07, Claude: `undesired_contacts` check.** TensorBoard's `Episode_Metrics/reward/undesired_contacts` isn't 0: 1492 of 1500 points are nonzero, mean −2.0e-6 per step. (Claude's results table had rounded it to −0.00000 and called it 0.) Reproduction, EXP-003 policy under training conditions, 1024 dogs × 20 s: the penalty fired on 16 of 16 contact-termination steps (1.06 parts on average) and on 0 other steps (no light brushes between 0.1 and 1.43 N). Sensor slots and the reward-before-reset order are correct. A contact over 1.43 N ends the episode in the same step, so the term pays once per contact ending, −0.25 × ~1 part × 0.02 s ≈ −0.005, and averages to ~1e-7 to 1e-6 per step. Pinned by `tests/test_brian_task_sim.py` (`pytest -m sim`).

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

(2026-11-07) Q1: feet_air_time contributes ~1.2% of tracking (0.0002 vs 0.0167), too small to shape anything, which explains why flickers didn't drop. Only torques (~18%) and action_rate (~9%) were big enough to steer the policy. Future fix: raise feet_air_time's weight ~7.5x so it lands around action_rate's size.

(2026-11-07) Q2: Likely a bug. 6.8% of episodes end on non-foot contact (>1.43 N), which is also above undesired_contacts' 0.1 N floor, so the penalty should fire at least on those steps, yet it reads exactly 0 all run. Investigate before any new training. → Claude's check (Results above): not a bug; it fires on those steps, and "exactly 0" was Claude's rounding.

Hold off on extra seeds until the bug's sorted.

(2026-11-07) undesired_contacts: the termination already costs ~300 steps × 0.017 ≈ 5 per contact fall, so the −0.005 penalty adds ~0.1% on top. The only range where it could teach anything (0.1–1.43 N light brushes) never occurs (0 in ~1M steps). Verdict: undesired_contacts is dormant on flat ground. Keep it unchanged (harmless, may matter on rough terrain or if the contact termination threshold changes).

## Verdict
