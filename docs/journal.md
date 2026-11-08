# Journal

Brian's decisions and verdicts, dated, in his words. Newest first. Numbers and run details are in [progress.md](progress.md) and the [experiment files](experiments/README.md).

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
