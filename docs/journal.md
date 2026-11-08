# Journal

Brian's decisions and verdicts, dated, in his words. Newest first. Numbers and run details are in [progress.md](progress.md) and the [experiment files](experiments/README.md).

## 2026-11-08: stop rule for search stage 2

> Stop rule for Stage 2: stop when (a) a trial beats Luwu's EXP-011 3-seed means on saturation, planar tracking and flicker, confirmed with seeds 43/44; or (b) 6 consecutive trials with no improvement beyond seed noise over the current best; or (c) 2 nights of GPU time. Then lock the winner and move to deployment prep (domain randomization, gyro units, joint mapping).

The message came in with stage 2 already running (EXP-021, since 15:39). Claude's readings where the message is silent (on the search page, for Brian to change):
- (a) The bars are EXP-011's unrounded means: saturation 0.950%, planar 0.03104 m/s, flicker 18.52%. So the saturation bar is Luwu's 0.95%, not stage 2's 0.3% limit. A trial that beats all three at seed 42 gets seeds 43/44 straight away; (a) fires if its 42/43/44 means beat all three.
- (b) Only trials newly trained in stage 2 count (not the known points, not confirmation seeds). An improvement is a trial that passes stage 2's limits at seed 42 with flicker more than 0.79 points below the current best. The current best starts at EXP-020 (12.07%). 0.79 points is the pooled flicker SD over the six 3-seed sets so far (EXP-010, 011, 015, 017, 018, 020).
- (c) "2 nights" is 16 h (2 × 8 h) of recorded training time: stage-2 trials plus their confirmation seeds.
- Under (b) or (c) the winner is rank 1 on the search page. When a rule fires the driver exits; locking the winner and the deployment-prep design questions then go through Brian.

## 2026-11-08: owner verify allowed despite the no-identity rule

Claude asked whether to change `CLAUDE.md`'s no-identity rule to allow the owner verify in [roadmap.md](roadmap.md) Phase 1 (VLM verify with multi-reference photos). Brian:

> Yes, allow it

`CLAUDE.md` now lists that as the one exception; the rule against re-adding face/ReID otherwise stands.

## 2026-11-08: EXP-020 added to the seed replicates; stage 2's constraints tightened

> Add EXP-020 to the seed replicates (seeds 43 and 44). For stage 2, keep the flicker objective but tighten the constraints to: saturation ≤ 0.3% and planar ≤ 0.031 m/s (Luwu's 3-seed mean). Goal: beat the vendor on strain, tracking and flicker at once. Everything else approved.

The message came in at ~10:40, with EXP-017-s44 training. Claude's calls where the message is silent (on the search page, for Brian to change):
- EXP-020 goes after EXP-015, seed 43 then 44, like the other three. The replicate run stops after EXP-017-s44 (`optuna/STOP`) and restarts with EXP-020 added; seeds already scored are skipped. Stage 2 starts after EXP-020's two seeds.
- The planar limit is Brian's 0.031 m/s; Luwu's unrounded 3-seed mean is 0.03104 m/s (EXP-011).
- The stage-2 study's known points (EXP-015 to EXP-020) get their constraint values under the new limits.
- The search page ranks every trial, both stages, under the newest limits (stage 2's), with each trial's stage-1 verdict in its own column. "Miss" stays each overshoot as a fraction of its limit, summed.

## 2026-11-08: top 3 search trials picked for seeds 43/44; search stage 2 (action_rate 4x–10x)

> Pause the search after EXP-019. Run seeds 43 and 44 for EXP-017, EXP-018 and EXP-015 (my top 3; I rank by saturation first, then tracking, then flicker). Then resume with action_rate's range extended to 4x–10x, since all the top trials hit the 4x ceiling.

The message came in at ~09:10, after EXP-019 had been scored (08:49) and EXP-020 (stage-1 trial 9) had started, so EXP-020 runs to the end (~09:35) and the search stops after it.

Claude's calls where the message is silent (on the search page, for Brian to change):
- Seed runs in Brian's order, each seed 43 then 44: EXP-017, EXP-018, EXP-015. Same weights, task and scoring as seed 42 (`tools/reward_search.py replicate`); results in each entry, the index and the search page. They stay out of the study (seed 42 only).
- Stage 2 is a new Optuna study (one study's ranges can't change): action_rate 4x–10x (−0.32 to −0.8), the other two ranges, the constraints, the objective, the ranking and the guard unchanged. The stage-1 trials at the 4x ceiling go in as known points, not retrained (EXP-015 to EXP-020); then 3 random trials in the new range, then the GP. Sampler seed 43 (42 would repeat stage 1's random draws of feet_air_time and torques). One ranked table covers both stages.

## 2026-11-08: Optuna search over three of Brian's reward weights (EXP-010's latency)

> After the 4 seed runs finish and are scored, start an Optuna search (Bayesian optimization) on MY reward under EXP-010's latency conditions:
> - Tune 3 weights: feet_air_time (1.0–7.5), action_rate (0.5x–4x current), torques (0.5x–2x current). Everything else fixed.
> - Objective: servo saturation ≤ 0.9% AND planar tracking ≤ 0.035 m/s, then minimize flicker. Trials failing a constraint rank below all that pass.
> - Seed 42, one trial at a time, each a numbered experiment with its weights recorded. Keep going until I stop you.
> - Leave the GPU free when the website session asks.
> - Morning summary: ranked table of trials. Don't interpret. I'll pick the top 2–3 to re-run with seeds 43/44.

Claude's defaults where the spec is silent (listed on the search page for Brian to change): Optuna GPSampler (Gaussian-process BO, constraint-aware), sampler seed 42; first 4 trials random, EXP-010 (seed 42, start weights) counted as one known point; log scale on all three ranges; failing trials ordered by flicker below the passing ones; reward guard skipped, as in the feet_air_time sweep. Driver: `tools/reward_search.py`; page: [SEARCH-exp010-reward-weights.md](experiments/SEARCH-exp010-reward-weights.md).

Brian's changes before the start (2026-11-08): "Two changes before ~03:20: (1) run the reward guard for every trial (penalty weights go up to 4x, so the fall-on-purpose trap is possible), and flag but don't skip any trial whose standing or walking total goes negative; (2) rank failing trials by how far they miss the constraints, not by flicker. Everything else approved."

How they're built: the guard runs before each trial trains, with the trial's weights, standing still and on EXP-010's policy over the command grid ("walking"). "How far they miss" is read as each constraint's overshoot as a fraction of its limit, summed (e.g. saturation 0.99% and planar 0.0385 m/s = 10% + 10% = 20%); flicker breaks a tie.

## 2026-11-07: EXP-011, the fair fight (Luwu's reward under EXP-010's latency)

> Fair fight: train Luwu's reward with EXP-010's latency conditions (40 ms delay + stale joints, same actor obs as EXP-010) as EXP-011, seed 42, then score it under the same conditions. If it's close to EXP-010, run seeds 43 and 44 for both.

> "Close" = any metric within seed noise (~5% tracking, ~9% smoothness/saturation, from EXP-000). If close, run seeds 43 and 44 for both.

Hypothesis is in [EXP-011](experiments/EXP-011-fair-fight-luwu-reward-under-exp-010-latency.md).

## 2026-11-07: Pi-hang safety requirements before any policy deployment

> Add to the V3 safety plan (from docs/v2-archive/findings/2026-09-30-pi-hang.md): if the Pi hangs, the motion board keeps executing the last command, and the Pi-side watchdog can't stop it. Before any policy deployment: (1) test what the board does if the Pi stops sending mid-motion in joint mode vs gait mode, dog on the stand; (2) every motion session needs a physical kill switch within reach (power switch or battery disconnect); (3) log enough before each session that a hang leaves evidence. Add this to docs/deployment-notes.md.

Logged in [deployment-notes.md](deployment-notes.md), "Safety: if the Pi hangs".

## 2026-11-07: IMU freezes: no new hardware yet; read-only tests, then model them in sim if they persist

> I don't want new hardware yet. Run the read-only tests (read 0x61, read_imu_int16 alongside read_imu, slow-read at ~100 ms). Only if 0x61 shows stabilization on, send imu(0) and rerun the still test. If freezes persist, the plan is to model them in sim: IMU sample-and-hold freezes matching our logs plus an "IMU age/fresh" observation for the actor, as a future experiment after EXP-010.

Context: no public firmware update for `M-4.0.1-Y`, xgolib 1.1.10 is the newest, and `0x61` (self-stabilization) is the only IMU setting ([phase1-xgolib-api.md](phase1-xgolib-api.md)).

## 2026-11-07: IMU reruns, and an IMU sanity filter for deployment

> Agreed, I'll run both: dog still first, then the policy-like loop. Add a note for deployment: the runtime needs an IMU sanity filter (reject zeroed/impossible vectors, detect freezes). If the onboard IMU proves unusable, the fallback is a separate I2C IMU wired directly to the Pi; log that as an option.

Context: the first `imu` run (dog handled, then set on the floor) showed ~1 s freezes of the whole IMU block and a few zeroed or impossible vectors. Logged in [deployment-notes.md](deployment-notes.md).

## 2026-11-07: joint map verified on the dog

> 11 was fl calf, 12 is fl thigh, 13 is fl hip, 21 is fr calf, 22 is fr thigh, 23 is fr hip, 31 is br calf, 32 is br  thigh, 33 is br hip, 41 is bl calf, 42 is bl thigh, 43 is bl hip

From the probe's `map` run (`joint_control_map_20261108-001412.jsonl`; Brian skipped the prompts and gave the answers in chat). Locked in `ironbark_rl/assets/s2_joint_map.py` (tested). It matches the order EXP-009/010 assumed, so neither changes. Still `# MEASURE:` before deployment: each joint's sign and zero offset.

## 2026-11-07: Phase 1 gate: Path A conditionally alive; test delay and stale readback in sim first

> My Phase 1 read: Path A is conditionally alive. Command rate (102 Hz) is fine, but servos lag ~100 ms (tracking falls off above ~2 Hz) and joint readback refreshes only every ~105 ms round-robin, while the sim models 4–8 ms of delay. Servo spec is 0.1 s/60° (a 10° move ≈ 17 ms unloaded) and 4.5 kg·cm ≈ 0.44 N·m (matches our 0.43 cap), so the motors are fast: the lag is mostly the motion board firmware and bus polling. Model it as command-pipeline delay + readback staleness, not slow motors.

> Two experiments, both from EXP-005's config (feet_air_time 3.0), seed 42, one at a time:
> - EXP-009: add ~100 ms actuator/command delay (based on Phase 1 data). Nothing else changes.
> - EXP-010: EXP-009 + joint-position observations that refresh round-robin every ~105 ms (stale between refreshes).
>
> Hypothesis: both still walk, but slower and less precisely: higher tracking error, lower step frequency, more falls than EXP-005, with EXP-010 worse than EXP-009. If either can't walk or falls go high, next experiment adds the last ~5 actions to the observation (action history) so the policy knows what's in flight. If that fails too, we go Path B.

Design answers (2026-11-07, Brian chose each recommended option; reasons as they were put to him):
- **Command delay 40 ms**, fixed, replacing the sim's 4-8 ms (not ~100 ms): the earliest of 18 step responses moved 50 ms after the command, and sine lag minus mean readback age is ~36 ms; the rest of the ~100 ms is readback staleness, which EXP-010 adds.
- **Joint readback cycle 130 ms** (measured with all 12 joints commanded at 55 Hz, like a policy; 105 ms with single-joint commands), polled in ID order with ~3 empty arm slots, random phase per env.
- **Actor joint velocity dropped** in EXP-010 (the dog has no velocity readback); the critic keeps the true joint state.
- **Scoring with the delays on**, plus EXP-005's policy re-scored under the same conditions as the reference.

Brian agreed (2026-11-07) with Claude's two smaller calls: EXP-009 keeps the existing 20-40 ms joint-observation delay; in EXP-010 the 130 ms sample-and-hold replaces it for the actor's joint positions.

Brian (2026-11-07): "Before any policy deployment (not now), add a mapping-verification step to the probe: wiggle each xgolib joint ID one at a time so I can confirm which physical leg/joint moves, then lock the mapping in a tested config. Until then it stays # MEASURE:."

Evidence: [phase1-joint-control-results.md](phase1-joint-control-results.md). Path A goes ahead only if EXP-009/010 (or the action-history follow-up) still walk; otherwise Path B.

## 2026-11-07: EXP-005 wins; `feet_air_time` weight 3.0 is the current best

> My read: EXP-005 (weight 3.0) is the winner.
> - vs EXP-004: saturation is a real win (ranges don't overlap: 0.39–0.53 vs 0.75–1.15); tracking is a tie (ranges overlap).
> - vs Luwu baseline EXP-002: saturation is a tie but EXP-005 is more consistent (±0.08 vs ±0.20); tracking is a tie (overlap, EXP-005's mean slightly better); flicker is a real win, 23.6% → 17.2% (~27% fewer), no overlap.
> Headline: my reward matches the baseline on servo strain and tracking while cutting flickers ~27% across 3 seeds.

Decision: set the config to EXP-005's weight (3.0) as the current best (commit `e520970`). Evidence: seeds 42–44 of EXP-002 (Luwu baseline), EXP-004 (7.5) and EXP-005 (3.0); ranking objective: servo saturation, then planar tracking, then flicker, 0 falls.
