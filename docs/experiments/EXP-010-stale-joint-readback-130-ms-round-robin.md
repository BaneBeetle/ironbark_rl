# EXP-010: stale joint readback (130 ms round-robin)

**Status:** planned · **Parent:** EXP-009

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

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
