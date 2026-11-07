# EXP-002: baseline on env v2: 50 deg tilt, 1.4 N contact, all collisions

**Status:** training · **Parent:** EXP-000

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

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
