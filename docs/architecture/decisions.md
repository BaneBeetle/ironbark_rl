# IronBark V3 architecture: decisions

Brian owns every decision here. Claude recommends and records. Newest decisions go at the bottom of each section with date and Brian's words.

Sections: §1 decided; §2 Claude's defaults (plumbing choices taken while writing, each one a veto away); §3 open: Brian's numbers; §4 open: design questions still waiting; §5 the `# MEASURE:` register (what must be measured, how, and which decision it unblocks).

---

## 1. Decided

### 2026-11-08: the nine architecture questions (Brian)

Claude sent nine questions with a recommendation each; Brian: **"Go with all recs."** The recommendations, now decisions:

| # | Question | Decision | Why |
|---|---|---|---|
| D-1 | Transport | **ZMQ + JSON** for everything PC ↔ Pi: one socket table, a `hello` handshake and a startup self-test per pair, `last_cmd_seq` echoed in `state`. ROS2 only inside the Pi for Yahboom's SLAM in Phase 2, behind one bridge node | V2's failures were discipline, not transport; DDS over Wi-Fi adds discovery and clock problems that would need measuring |
| D-2 | Perception placement | **PC (3090)**, with a host-agnostic `tracks` schema so the detector can move to the Pi later. Nothing safety-critical on the Pi depends on perception | The camera → PC path is measured (20 fps, 10.9 ms one-way); a Pi detector needs the CPU (~5–10 fps, unmeasured) or new hardware |
| D-3 | Who closes the follow loop | **A deterministic PC follow controller** (proportional on pixel offset, 20 Hz) emits velocity; the VLM sets goals at ~1 Hz and gets direct velocity only as a short-TTL tool | A ≥ 1 s VLM on a continuous-motion machine is V2's overcorrection (LESSONS A6) tripled |
| D-4 | Mode arbitration | **Pi-side arbiter** owns the motors: `ESTOP > fault → IDLE_HOLD > operator > brain`. Action groups **never preempt walking**: request → zero velocity → stand → handoff; action groups only from `IDLE_HOLD` | One owner at a time; handoffs are measured, not improvised |
| D-5 | Comms loss / Pi hang | On losing the PC stream: **zero-velocity command, the policy keeps standing**; freeze (stop writing) only if the IMU is also rejected. Firmware gait is never used for locomotion, so a Pi hang leaves a held pose, not a walking dog (stand test confirms). **Kill switch = power button** | A frozen mid-stride pose may be unstable; standing is the trained behaviour |
| D-6 | Who publishes events | **The owner of a fact publishes it once**: Pi → `fell`, `battery_low`, `imu_frozen`, `mode_changed`, `estop`; owner tracker → `target_found/lost/reacquired`, `verify_result`; voice subscribes and keeps its pacing policy. T1 debounce moves into the tracker, T3/T4 onto the Pi; `is_fallen` stays the single fall definition | Two fall definitions can drift |
| D-7 | STT path | The CSK4002 is a keyword recogniser over serial. **Schema for keyword events now; `speech_text` reserved** for a raw-mic → PC STT path | Mic availability is unknown |
| D-8 | Velocity semantics | Body frame, m/s / m/s / rad/s; each command carries `ttl_ticks` and expires to zero; the Pi clamps to the trained ranges (vx −0.5…0.6, vy ±0.3, wz ±0.8). **The lidar reflex blocks only** (clamps vx), never steers | The safety layer never originates motion |
| D-9 | Versioning | `v` int per message type; `hello` compares versions and lists socket pairs; the Pi refuses mismatched types and says so in `health`. JSON until a measured need for msgpack | Fail loudly at startup, before anything is armed |

Carried in from earlier calls (deployment-notes.md, journal.md), unchanged: policy loop on the Pi; IMU sanity filter; round-to-nearest bytes; all-12-first on `adopt`; `XGO_DOG` direct (no `reset()`); never `calibration()`; no wall-clock on the Pi; dead reckoning from commanded turns, not IMU yaw; hostnames not IPs; receiver-clock ageing only; persistent journal + `get_throttled` logging; kill switch within reach; stand test of Pi-silence in both modes before deployment; voice pacing (4 s / 30 s / falls interrupt / battery queues), `FALL_TILT_DEG = 46`, `BATTERY_LOW_PCT = 20` re-arm 30.

---

## 2. Claude's defaults (veto any)

Plumbing choices made while writing the docs. None is a `brian/` design decision, but each changes how things are built, so they are listed for a veto.

| # | Default | Why | Where |
|---|---|---|---|
| C-1 | **The Pi binds every socket; the PC connects to `PI_HOST`.** PUB/SUB roles are unchanged (the PC's command PUB *connects* to the Pi's SUB bind) | The Pi needs no PC address (fixes LESSONS C4 and the 2026-09-30 address-drift step); no inbound Windows firewall rule; one config value on the PC | interfaces §2 |
| C-2 | **Alternate `read_imu()` and `read_motor()` on even/odd ticks** so each 20 ms tick fits (14 / 18 ms measured components, vs 21 ms with both) | A 47.6 Hz loop is a 5 % rate error against the 50 Hz training; joint readback at 25 Hz loses nothing (105–130 ms refresh) | architecture §3.1; see D-10 |
| C-3 | **`CONFLATE=1` on the PC's camera and lidar PULL sockets** | V2 saw a 3.87 s-stale frame burst on connect | interfaces §2 |
| C-4 | **Camera, lidar and audio are separate Pi processes**, reporting to the runtime over `ipc://`; the runtime publishes one consolidated `health` | Keeps JPEG encoding and serial parsing out of the 50 Hz process; one place for the operator to look | architecture §2 |
| C-5 | **`firmware_stance` is read at boot** (the board owns the legs after power-on) and the `release` handoff pre-positions the joints there before `stop()` | Makes the snap on `stop()` ≈ 0 instead of the ~8° jumps Phase 1 saw | architecture §3.2 |
| C-6 | **Action groups are an allow-list file** (`name`, xgolib `id`, `budget_ticks`, `min_battery_pct`); the brain sees names only | The ids are vendor numbers nobody has verified; a budget in ticks bounds every firmware action | interfaces §7 |
| C-7 | **`ESTOP` holds, then unloads after `FALL_UNLOAD_TICKS` when fallen**; never unloads while upright | Unloading upright drops the dog; servos fighting the floor after a fall overheat (V1's death) | architecture §3.2 |
| C-8 | **`REST` = lie-down action group then `unload_allmotor()`**, requested by the brain or operator, never automatic | It is a firmware motion, so it goes through the arbiter like any action | architecture §3.2 |
| C-9 | **Rescan is a yaw sweep under the policy**; a pitch scan is a stationary `ACTION` used only when the yaw sweep failed | `attitude()` is a firmware call; no handoff is needed for the common case | architecture §4.2; see D-11 |
| C-10 | **`speech_started` echoes the PC's `t_ms`** so the voice latency is measured as a round trip on the PC clock | No cross-host arithmetic | interfaces §6 |
| C-11 | **Camera message format kept from V2** (`<qI` + JPEG) | It is measured and works; the stats move to `health` | interfaces §8 |
| C-12 | **Owner photos live outside the repo** (`OWNER_PHOTOS_DIR`) | Privacy; they are not code | interfaces §10 |
| C-13 | **Unknown fields are rejected, not tolerated** | LESSONS B1: V2 carried nine dead fields | interfaces §1 |

---

## 3. Open: Brian's numbers

Each constant: what it controls, the measured context, Claude's recommendation with a one-line reason, blank for Brian's call. Constraints between constants are written where they bind (LESSONS B4).

### 3.1 Pi safety layer

| Constant | Controls | Context | Rec | Brian |
|---|---|---|---|---|
| `VELOCITY_TTL_TICKS` (default sent by the PC) | how long one velocity command stays valid | commands at 20 Hz = 2.5 ticks apart | 15 (300 ms; tolerates 5 missed messages) | |
| `CMD_LOST_TICKS` | when `cmd_stream_lost` fires | must be > TTL | 50 (1 s) | |
| `CMD_DEAD_TICKS` | when the arbiter drops to `IDLE_HOLD` | must be > `CMD_LOST_TICKS` | 250 (5 s) | |
| `REQUIRE_DEADMAN` | whether nonzero velocity needs `deadman=true` | supervised sessions first | `true` until the first unsupervised session is a deliberate decision | |
| `IMU_FREEZE_READS` | identical blocks before `frozen` | live refresh 4–8 ms; reads 40 ms apart under C-2 | 3 (120 ms; unambiguous) | |
| `GYRO_MAX_DPS` | reject threshold | outliers measured 1514–1623 °/s; real gait rates `# MEASURE:` (M-5) | 1000 | |
| `IMU_STALE_TICKS` | frozen/rejected → velocity zero | longest measured freeze 1004 ms = 50 ticks; must exceed it | 75 (1.5 s) | |
| `IMU_DEAD_TICKS` | → `IDLE_HOLD` | > `IMU_STALE_TICKS` | 150 (3 s) | |
| `FALL_UNLOAD_TICKS` | hold → unload after a fall | servo heat vs a chance to recover | 100 (2 s) | |
| `JOINT_MARGIN_DEG` | inside `MOTOR_LIMIT` | the probe used 3° | 3 | |
| `JOINT_STEP_MAX_DEG` | max target change per tick | servo spec 0.1 s/60° → 12°/20 ms | 12 | |
| `ADOPT_RAMP_TICKS` | measured pose → policy default pose | | 50 (1 s) | |
| `STAND_TICKS` | zero-velocity settle before `release` or `IDLE_HOLD` | one gait cycle ≈ 0.4 s | 25 (0.5 s) | |
| `BATTERY_CRITICAL_PCT` | velocity zero, rest requested | firmware lockout at 9 %; load sag suspected | 12 | |
| `BATTERY_EVERY_TICKS` | battery read cadence | V2 used 250 (5 s); a read costs ~3 ms in a tick | 250, on an `imu` tick | |

### 3.2 PC follow controller and owner tracker

| Constant | Controls | Context | Rec | Brian |
|---|---|---|---|---|
| `TARGET_LOST_FRAMES` | zero velocity and `target_lost`, one constant for both | voice placeholder was 3 at 5 Hz; tracker runs at 20 fps | 10 (0.5 s) | |
| `STANDOFF_AREA_RATIO` | the range the dog holds | ladder: 0.159 at 1 m, 0.118 at 1.5 m, 0.099 at 2 m; 1 m is noisy (σ 40 px, clipped) | 0.118 (1.5 m); re-run the 1.5 m station first (its hit-rate dip is one sample) | |
| `OFFSET_DEADBAND_PX` | no yaw correction inside | static noise σ 2.6–3.5 px at 2–3 m, 40 px at 1 m; motion jitter ~45 px median (uncommitted V2 log) | 30 at ≥ 1.5 m | |
| `KP_YAW`, `KP_RANGE` | proportional gains | dead time ≈ 150–250 ms (architecture §5.2); the real number is M-6 | set from a step test after M-6; start at half the gain that gives one overshoot | |
| `ACQUIRE_FRAMES` | consecutive argmax frames before lock | V2 §5: 3 | 3 | |
| `CONFIDENCE_DECAY_LOCKED` | per-frame multiplier while locked and unverified | | 0.999 (half-life ~35 s at 20 fps) | |
| `CONFIDENCE_DECAY_LOST` | per-frame multiplier while lost | | 0.97 (half-life ~1 s) | |
| `RESCAN_CONFIDENCE` | below this → rescan | | 0.3 | |
| `VERIFY_PERIOD_FRAMES` | periodic VLM verify while locked | VLM cost/latency | 600 (30 s) | |
| `RESCAN_WZ` | sweep yaw rate | trained max 0.8 rad/s | 0.5 rad/s | |
| `RESCAN_MAX_ANGLE_DEG` | sweep bound each side of the dead-reckoned bearing | | 90 | |
| `RESCAN_COOLDOWN_FRAMES` | between sweeps | | 100 (5 s) | |
| `RESCAN_MAX_ATTEMPTS` | before the voice fallback | | 2 | |
| `BRAIN_VELOCITY_TTL_MAX` | cap on a brain `set_velocity` | | 100 ticks (2 s) | |
| `TELEM_STALE_S`, `FRAME_STALE_FRAMES` | PC-side link/age thresholds (PC clock allowed) | | 1.0 s; 5 frames | |

### 3.3 Lidar reflex (Phase 2)

| Constant | Controls | Context | Rec | Brian |
|---|---|---|---|---|
| `FRONT_SECTOR_DEG` | half-width of the forward sector | body 14.5 cm wide; lidar offset from the nose `# MEASURE:` (M-9) | ±30° | |
| `STOP_DISTANCE_M` | vx → 0 at or under | | 0.25 | |
| `TAPER_DISTANCE_M` | full vx allowed at or beyond | | 0.60 | |
| `VX_CAP_LIDAR_DARK` | forward cap with no scan | | 0.2 m/s | |
| `LIDAR_DARK_SCANS` | scans missing before dark | | 3 | |

---

## 4. Open: design questions still waiting

| # | Question | Options | Rec | Brian |
|---|---|---|---|---|
| D-10 | Should the sim's joint-readback model mirror the 40 ms read cadence of C-2? | (a) leave `JOINT_REFRESH_PERIOD_S = 0.130` as is; (b) add the 2-tick read cadence to `stale_joint_pos`; (c) decide after the parity test | (c): the parity test (week 6) shows whether the extra ≤ 40 ms of staleness moves the policy; retrain only if it does | |
| D-11 | Pitch scan during rescan | (a) never (yaw sweep only); (b) stationary `ACTION` with `attitude('p')` after the yaw sweep fails (C-9); (c) add body pitch to the policy's command and retrain | (b) | |
| D-12 | VLM model for owner verify | Haiku 5.5 (fast, cheap) vs a larger model | Haiku 5.5 first; promote only if M-12's held-out accuracy says so | |
| D-13 | Verify failure policy | reject → unlock immediately, or reject → keep following at low confidence until the next verify | unlock after 2 consecutive rejects; one reject lowers confidence to `RESCAN_CONFIDENCE` | |
| D-14 | Unsupervised sessions | when `REQUIRE_DEADMAN` may be false | after the stand-test gate and ≥ 3 supervised sessions with zero `ESTOP`s from the safety layer | |
| D-15 | Session logging | what the PC records every session | all of `state`, `health`, `event`, `tracks`, `owner`, `velocity` to JSONL + the camera stream to MJPEG, by session id; it is the dataset for Path B-style learning later and the evidence after any hang | |
| D-16 | Gamepad (roadmap, later) | `velocity` with `src: teleop` through the same arbiter | yes, nothing new on the Pi | |

---

## 5. `# MEASURE:` register

Every unmeasured number the architecture depends on, with the procedure and the decision it unblocks. This list is the **stand-test gate** (LESSONS D1): nothing deploys until the rows marked **gate** are green. Brian runs everything that moves the dog.

| # | Measure | How | Unblocks | Gate |
|---|---|---|---|---|
| M-1 | Board behaviour when the Pi stops sending mid-motion, joint mode and gait mode | dog on the stand; probe commands a motion then `kill -STOP`s itself; video the legs; log whether the pose holds, the gait continues, and any board-side timeout | D-5, failure-modes §2 | **gate** |
| M-2 | Composed tick time of the C-2 schedule | probe `imu-loop` variant alternating reads; p50/p99 per tick over 1500 ticks | C-2, D-10 | **gate** |
| M-3 | Gyro unit and bias | rotate the dog by a known angle on the stand, integrate `read_imu()` gyro z; compare °/s vs rad/s; bias at rest over 60 s | obs slot 0–2 | **gate** |
| M-4 | Joint sign and zero offset per joint vs the sim | probe `map` with foot directions answered; command 0° per joint vs the MJCF default pose | action mapping, obs slots 11–22 | **gate** |
| M-5 | Real gyro and accel ranges during walking | first tethered steps, `state` log | `GYRO_MAX_DPS`, accel band | before unsupervised |
| M-6 | Command-to-motion and stop latency, external reference | high-speed video of the dog against floor marks for step velocity commands; compare against the 40 ms model | `KP_YAW`, `KP_RANGE`, §5.2 budget | before FOLLOW |
| M-7 | `K_TURN` (achieved / commanded yaw rate) | video of in-place turns at 0.2/0.4/0.8 rad/s | dead reckoning | before FOLLOW |
| M-8 | `adopt` and `release` handoffs | stand: readback before/after; max joint jump; ramp smoothness | D-4 | **gate** |
| M-9 | Lidar UART port, scan rate, points per scan, lidar-to-nose offset | trace the cable; `ms200_reader --dump`; tape measure | §3.3 reflex | Phase 2 |
| M-10 | xgolib `action()` ids, each group's duration and whether it ends standing | read `xgolib_dog.py` on the Pi; time each allow-listed group on the stand | C-6 allow-list | before personality |
| M-11 | Whether the firmware accepts 2 Mbaud and how it is switched | xgolib `__init__` hints; try `XGO_DOG(port, 2000000)` read-only | C-2 headroom | optional |
| M-12 | Owner verify accuracy | held-out photo set: owner vs others, same room, same lighting; accuracy and latency per model | D-12, D-13 | before FOLLOW |
| M-13 | Pi-side audio device and playback latency | `aplay -l`; round-trip via `speech_started` | voice on the Pi | before voice on dog |
| M-14 | CSK4002 wiring and whether raw audio is exposed | trace the module's connector; Yahboom tutorial | D-7 | Phase 2 |
| M-15 | Pi-side detector rate (for a later move) | `yolo benchmark` NCNN export on the Pi 5 | D-2 revisit | optional |
| M-16 | Sustained-load battery runtime | one full session with `battery_pct` logged, policy standing and walking | session planning | before demos |
| M-17 | Wi-Fi one-way `velocity` latency | `noop` → `last_cmd_seq` round trip on the PC clock, halved | §5.2 budget | before FOLLOW |
| M-18 | YOLO + tracker time on the 3090 | PC-side timing log | §5.2 budget | before FOLLOW |
| M-19 | Camera stall recovery time | power-cycle the dog with the Pi up; time to `camera_ok` | failure-modes §6 | before FOLLOW |
| M-20 | ~~`mdp.phase` standing gate~~ resolved from source 2026-11-08: both phase values are 0 when the command norm < 0.1; otherwise sin/cos of the episode-step clock over a 0.4 s period | — | obs slots 9–10 | done |
