# EXP-005: sweep: feet_air_time weight 3

**Status:** training · **Parent:** EXP-004

## Hypothesis (Brian, before the run)

> What will change on the scoreboard compared to the parent, and why?

(2026-11-07) No per-run hypothesis: this is one run of Brian's 1-D sweep, verbatim: "Run a 1-D sweep on feet_air_time's weight: 3.0, 15.0, and 30.0 (7.5 is EXP-004, 1.0 is EXP-003). Same seed 42, everything else identical, one at a time, each as its own experiment, scored the same way." "Objective for ranking: lowest flicker share, with planar tracking error no worse than EXP-002 + 10% and zero falls. Also report swing median and servo saturation for each, so I can spot high-stepping or strain."

## Change (one variable)

vs. EXP-004: **one weight.** `WEIGHTS["feet_air_time"]` 7.5 → **3** (EXP-003: 1.0). Everything else (task, other weights and parameters, seed 42, 1500 iterations, 4096 envs) is unchanged.

Fall-on-purpose guard before training (`tools/reward_check.py`, new weight): +0.02924 per step standing still on a zero command; +0.02753 for the EXP-004 policy on the grid (feet_air_time +0.00108, 3.4%), commands +0.0259 to +0.0287. Not flagged.

## Setup (auto-filled)

- Date: 2026-11-07
- Commit: `3c18e65`
- Task: `IronBark-S2-Walk-Flat-Brian`
- Seed: 42 · Iterations: 1500 · Envs: 4096
- Train: `python tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-005`
- Run folder: `~/dev/ironbark_runs/logs/rsl_rl/ironbark_s2_walk_brian/*_EXP-005`
- Trained at commit `3c18e65`, 2026-11-07.

## Results (scoreboard: `metrics.py`)

_Pending. Filled by the evaluation harness once training finishes._

## What I saw (Brian: viewer, curves)

## Why / next (Brian)

## Verdict
