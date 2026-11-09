# IronBark V3 architecture

Design only: no code lands from this document. Every agent building a V3 component builds to the contracts in [interfaces.md](interfaces.md); the behaviour under faults is in [failure-modes.md](failure-modes.md); the calls Brian made and the ones still open are in [decisions.md](decisions.md).

Status (2026-11-08): Brian accepted all nine recommendations ("Go with all recs"), then approved Claude's defaults C-1 to C-13, set the numbers in `decisions.md` §3 as recommended and answered D-10 to D-16. Still open: the two follow gains (set after M-6) and the `# MEASURE:` register in `decisions.md` §5, whose gate rows block deployment. Every number marked `# MEASURE:` has its procedure there.

Revised the same day after reviews by the voice and joint-control sessions and Brian's six corrections (`decisions.md` §1): the text now says what is measured, what is only scored in sim, and what is unverified. Awaiting Brian: defaults C-14 to C-19 and questions D-18 to D-22 (D-17 is answered: a USB sound card for the dog's mic and speaker).

Sources this design leans on: [`docs/v2-archive/MEASURED_FACTS.md`](../v2-archive/MEASURED_FACTS.md), [`LESSONS.md`](../v2-archive/LESSONS.md), [`findings/`](../v2-archive/findings/), [`docs/phase1-joint-control-results.md`](../phase1-joint-control-results.md), [`docs/deployment-notes.md`](../deployment-notes.md), [`docs/roadmap.md`](../roadmap.md), `docs/voice/decisions.md` (branch `feature/voice`).

---

## 1. Shape

Brian's picture (roadmap): the RL policy is the fast cerebellum, a VLM is the slow brain that sends `(vx, vy, yaw_rate)`. V3 puts one deterministic layer between them, because a ≥1 s brain cannot close a loop on a machine that keeps moving until told otherwise (V2 LESSONS A6, `findings/turn-overcorrection.md`).

```
   slow (0.3–1 Hz)        medium (20 Hz)              fast (50 Hz)                 hardware
 ┌──────────────┐   goals   ┌──────────────────┐  velocity  ┌───────────────────┐  joints  ┌────────┐
 │ Brain (VLM)  │ ────────▶ │ Follow controller │ ────────▶ │ Pi runtime:        │ ───────▶ │ motion │
 │ tools: goal, │           │ + owner tracker   │  (TTL'd)  │ arbiter → safety → │ ◀─────── │ board  │
 │ action, say  │           │ (PC)              │           │ policy → adapter   │ readback │ (ESP32)│
 └──────────────┘           └──────────────────┘           └───────────────────┘          └────────┘
        ▲                           ▲                               │ state, events, health
        └───────────── events ──────┴───────────────────────────────┘
```

Rules every component follows (each one traces to a V2 lesson; the full map is §7):

1. **One motor owner at a time**, chosen by a Pi-side arbiter. The brain and the operator *request*; the arbiter *decides*.
2. **The safety layer never originates motion.** It clamps, zeroes, holds. Nothing in it calls a gait or an action group.
3. **Locomotion runs only in joint mode** (the RL policy). The firmware gait is never used to walk. Firmware action groups run only from a standing stop, through a measured handoff.
4. **Frame counts and state predicates on the Pi; wall clock only on the PC.** Every message that must expire carries a tick count. One exception (Brian, 2026-11-08): a monotonic clock paces the 50 Hz loop on the Pi, and does nothing else; every decision still counts ticks or frames.
5. **No cross-host timestamp arithmetic.** Receivers age data by their own clock or tick.
6. **The owner of a fact publishes it, once.** The Pi says `fell`; the tracker says `target_lost`; voice subscribes and never re-derives either. The event is the edge; the same owner also carries the level in a periodic message, so a lost event is never a lost fact.
7. **The Pi binds every socket; the PC connects to one hostname.** The Pi needs no PC address, and the PC needs no inbound firewall rule.
8. **Every threshold carries a tag** (`measured | vendor | design | MEASURE`). A `MEASURE` threshold blocks the behaviour that depends on it, or at least raises a degraded notice at mode entry.
9. **Every vendor call is unverified until a probe log says otherwise.** The runtime uses the calls a probe has logged; a call with no log is blocked until it has one (§3.4 lists them).
10. **Write V3 from scratch; port facts, not code.** `motor_controller.py` stays in the archive as a reference.

---

## 2. What runs where

| Host | Process | Rate | Job |
|---|---|---|---|
| **Pi 5** | `runtime` | 50 Hz tick | Arbiter (modes), safety layer (IMU filter, watchdog, tilt cutoff, joint clamps), lidar reflex (Phase 2), policy inference (ONNX), motion-board adapter (xgolib quirks), telemetry PUB (`state` 50 Hz, `health` 1 Hz, `event`), `hello` REP |
| Pi 5 | `cam_sender` | 20 fps | `/dev/video0` MJPG 640×480 → PUSH to the PC; frame stats + stall detection → runtime over `ipc://` |
| Pi 5 | `lidar_reader` (Phase 2) | scan rate (`# MEASURE:`; vendor nominal ~10 Hz) | MS200 UART → full scans PUSH to the PC; sector minima → runtime over `ipc://` |
| Pi 5 | `audio_player` | on demand | PULL PCM from the PC, play it on a Pi audio device, report `speech_started/ended` to the runtime. **Device chosen, not installed** (2026-11-08): a USB sound card with its own speakers and a mic (decisions.md D-17). Until it passes M-13 the voice plays on the PC. The Pi's card 2 (`plughw:2,0`) is a silent V1 leftover and is never used |
| Pi 5 | `voice_module_reader` (Phase 2, optional) | per frame | Runs only while the voice board is plugged in (whether it stays is undecided). Owns its serial port (`/dev/ttyUSB0`, 115200); publishes `keyword` through the runtime, as a software wake word could instead |
| **PC (3090)** | `perception` | 20 Hz (camera-bound) | YOLO + tracker on the camera stream → `tracks` |
| PC | `owner_tracker` | 20 Hz | Lock, confidence, dead reckoning, rescan, VLM verify → `owner` + events |
| PC | `follow_controller` | 20 Hz | Deterministic P-control from `owner` → a `velocity` request with TTL; obeys the brain's goal (or the operator's, from the HUD) |
| PC | `brain` | 0.3–1 Hz, event-driven | VLM with tools: goal, direct velocity (short TTL), action group, say, ask owner |
| PC | `voice` | event-driven | Pacing policy (built), cached lines / Haiku → TTS → PCM PUSH to the Pi |
| PC | `hud` + `gateway` | 20 Hz | Operator view, deadman (real key-held), e-stop, link states, `seq` echo, degraded notices. The gateway is the only writer on the command socket: it forwards requests while armed and sends zero velocity while disarmed |

**Why perception is on the PC** (decision 2): the camera→PC path is measured (20 fps, 10.9 ms one-way), the 3090 is idle at deploy time, and a Pi-side detector needs either the CPU (YOLO11n-class at roughly 5–10 fps, unmeasured) or a Hailo HAT (new hardware). The `tracks` schema is host-agnostic so the detector can move to the Pi later without touching anything downstream. Nothing safety-critical on the Pi depends on perception; the watchdog and the lidar reflex are local.

---

## 3. Pi runtime

### 3.1 Tick schedule

The policy is trained at 50 Hz (20 ms). Measured serial costs (`phase1-joint-control-results.md`): 12-joint `motor()` 9.7 ms of wire time (the call returns in 0.13 ms and the bytes drain in the background); `read_motor()` 3.6 ms alone, 16.2–18.0 ms when it waits behind the write; `read_imu()` 4.6 ms; both reads every tick → 21.0 ms/step, 47.6 Hz. So both reads cannot share a 20 ms tick.

Design: alternate the reads.

- **Odd ticks**, write + `read_motor()`: **18.0 ms, measured** (p99 18.3).
- **Even ticks**, write + `read_imu()`: **17–19 ms, inferred, not measured.** A read behind a write is not a plain sum: `read_motor()` costs 3.0–4.7 ms more than write plus read alone, and the same penalty on `read_imu()` gives 17–19 ms (the joint-control session's review; the first draft's 14 ms was a plain sum).
- That leaves **≤ 2 ms per tick** for the observation, the ONNX forward, the safety layer and the JSON. The composed schedule has never run; it is M-2, a gate, and needs a new probe mode.
- **Battery reads get their own tick** (Brian, 2026-11-08): once every `BATTERY_EVERY_TICKS`, a tick does write + `read_battery()` and no other read. On an IMU tick it would add ~3.2 ms and overrun.
- **Pacing** (Brian, 2026-11-08): "a monotonic clock is allowed on the Pi for loop pacing ONLY; decisions still use tick/frame counts." The schedule does not pace itself (the Phase 1 loop ran at whatever the serial link took), and the policy's phase observation assumes tick × 0.02 s. So the loop sleeps to the next 20 ms boundary on the monotonic clock. A tick that overruns is counted in `health.loop.overruns` and never caught up. Nothing else on the Pi reads a clock.
- **What the cadence costs.** Joint readback at 25 Hz loses little: each joint's value refreshes only every ~105–130 ms in the firmware. The IMU at 25 Hz is **coarser** than its live refresh (4–8 ms), so every IMU value is held one extra tick, on top of a register that is frozen 42 % of the time. Neither 40 ms hold is in the sim.

```
tick t (even)                          tick t+1 (odd)
├ read command queue (drain to newest) ├ same
├ arbiter: mode, velocity, TTLs        ├ same
├ safety: IMU filter, tilt, watchdog   ├ same
├ obs = f(held joints, held IMU, cmd, tick phase, last action)
├ policy forward (ONNX, <1 ms)         ├ same
├ joint clamps → motor(12 angles)      ├ same
├ read_imu() → IMU filter              ├ read_motor() → joint hold buffer
└ telemetry: state (every tick), health (every 50), events
```

Work placed between the write and the read may cost nothing, since the bytes drain in the background; untested (M-2).

Brian (D-10, 2026-11-08): whether the sim should mirror the 40 ms read cadence is decided after the obs-parity test (Phase 2A week 6), which tells whether it matters. The review adds the IMU hold to that question; D-10 was asked about joints only.

A faster serial link is not a way out today: xgolib has no call that changes the firmware's baud (`__change_baud` only reopens the host side), so 2 Mbaud helps only if the board is found to support it some other way (M-11).

### 3.2 Arbiter: modes and the motor owner

| Mode | Motor owner | What the board sees | Entry | Exit |
|---|---|---|---|---|
| `BOOT` | none | nothing | power-on | `imu.ready` latch (first nonzero yaw, a predicate, never a timer) → `adopt` → `IDLE_HOLD`. This is the session's first `motor()` call, so it is an `adopt` like any other |
| `IDLE_HOLD` | runtime | all 12 joints held at their measured angles (joint mode) | any fault, stream loss timeout, operator | request → `POLICY` or `ACTION` or `REST` |
| `POLICY` | policy | 12 joint targets at 50 Hz; velocity command from the arbiter (PC stream, brain, or zero) | from `IDLE_HOLD` via the adopt ramp | zero-velocity stand → `IDLE_HOLD`; fault → `IDLE_HOLD`/`ESTOP` |
| `ACTION` | firmware | one allow-listed action group, with a tick budget | only from `IDLE_HOLD` after a `release` | budget elapsed → `adopt` → `IDLE_HOLD` |
| `REST` | firmware then none | lie-down action, then `unload_allmotor()` (the thermal lever V2 named, LESSONS A1) | from `IDLE_HOLD` | `load_allmotor()` → `adopt` → `IDLE_HOLD`. Loading moves the joints before `adopt` can run (one leg measured: two joints went back to their pre-unload angles, the third was still moving when the window ended): M-24 |
| `ESTOP` | runtime | joints held; after `FALL_UNLOAD_TICKS` when fallen, unloaded (hold only until M-24 has logged `unload_allmotor()`) | operator e-stop, `fell`, IMU rejected too long | only an operator `clear_estop` |

Priority when requests conflict: `ESTOP` > fault → `IDLE_HOLD` > operator request > brain request. A brain request that arrives while walking is answered with `rejected: walking`; the brain must first set goal `STAY`, the follow controller sends zero velocity, and the arbiter reaches `IDLE_HOLD` on its own. Action groups never preempt walking (decision 4).

**Handoffs** (both are gate items, `# MEASURE:` on the stand before any deployment: M-8 in decisions.md §5):

- **`adopt` (firmware → joint mode):** wait one full readback cycle (≥ 8 ticks: the 12-joint cycle measured 126–144 ms) so every joint's reading is fresh; send all 12 *measured* angles first (rounded to the nearest byte, since `conver2u8` truncates); then ramp from the measured pose to the policy's default pose over `ADOPT_RAMP_TICKS`. Reason: the first `motor()` call switches the board to joint mode and drives every unsent joint to its last joint-mode setpoint (~8° jumps seen in Phase 1). It is not atomic: the 12 packets take 9.7 ms on the wire. Logged so far only from the boot pose (final change ≤ 0.8°); an adopt from the firmware's stance after `stop()` or an action group is unlogged.
- **`release` (joint mode → firmware):** policy at zero velocity for `STAND_TICKS`, then drive the joints to the pose `stop()` will return them to, then `stop()`, so the snap is small. **That pose is unmeasured** (Brian, 2026-11-08). The first draft read it at boot, and the logs contradict that: the boot pose and the pose after `stop()` differ by 7–8° at the calves and 4–5° at the thighs, and that `stop()` followed a `reset()`, which V3 never calls. Where `stop()` lands with no `reset()` that boot has never been logged. M-8 must cover that case. Until it does, `release` is blocked, and `ACTION` and `REST` with it.

### 3.3 Safety layer (runs every tick, between the arbiter and the policy)

| Guard | Signal | Response |
|---|---|---|
| IMU sanity filter | whole accel or gyro vector exactly 0.0; \|gyro\| > `GYRO_MAX_DPS`; block identical for `IMU_FREEZE_READS` consecutive reads | reading rejected / marked frozen; policy sees the last good value (the same hold as the sim's `imu_frozen` term, which is scoring-only: see below); `imu.status` and `frozen_ticks` in `state`; frozen or rejected for > `IMU_STALE_TICKS` → velocity zeroed; > `IMU_DEAD_TICKS` → `IDLE_HOLD` |
| Tilt cutoff | `is_fallen` (Brian's `metrics.py`, `FALL_TILT_DEG = 46`) on filtered roll/pitch | `fell` event, `ESTOP` (hold), unload after `FALL_UNLOAD_TICKS` so the servos stop fighting the floor |
| Command watchdog | ticks since the last `velocity` message | TTL expiry → velocity zero (the policy should then stand: unverified, see below); `CMD_LOST_TICKS` → `cmd_stream_lost` event; `CMD_DEAD_TICKS` → `IDLE_HOLD` |
| Deadman | `velocity.deadman` false or absent while `REQUIRE_DEADMAN` | velocity zero |
| Velocity clamp | trained ranges vx −0.5…0.6, vy ±0.3, wz ±0.8 (sim command ranges) | clamp, count in `health` |
| Joint clamp | `MOTOR_LIMIT` minus `JOINT_MARGIN_DEG`; per-tick step ≤ `JOINT_STEP_MAX_DEG` | clamp, count in `health` |
| Lidar reflex (Phase 2) | front-sector minimum range, scan age in scans | vx clamped by a taper; lidar dark → `VX_CAP_LIDAR_DARK` + degraded notice at mode entry; never adds motion (decision 8) |
| Battery | `battery_pct` ≤ `BATTERY_LOW_PCT` (20, Brian) / ≤ `BATTERY_CRITICAL_PCT` | events; critical → velocity zero, then `IDLE_HOLD`; the brain is asked to `REST` before the ≤ 9 % firmware lockout lies the dog down on its own |

All thresholds above are Brian's calls, set 2026-11-08 (decisions.md §3).

**Two things this layer leans on that no trained policy has shown yet** (Brian, 2026-11-08, after the joint-control session's review):

- **IMU freezes are scoring-only in the sim today.** Every policy so far trained with a fresh IMU each step. Scoring EXP-010's policy under the measured freezes raised flicker from 15.1 % to 25.4 %, with 0 falls. Plan: train with them in the domain-randomization phase (Phase 2A week 5).
- **"The policy stands" on a zero command is unverified.** Training has `rel_standing_envs = 0`, so zero commands are about 0.4 % of draws, and the scoreboard's stand row is a 10 s stand from rest. The walk → zero transition, which TTL expiry, the deadman and `release` all depend on, is not scored anywhere and is rarely trained. Plan: an eval of walk → stop transitions (M-28: sim first, then the stand) and more stand commands in training.

### 3.4 Motion-board adapter

The only module that imports xgolib. It wraps the calls a probe has logged, hides their quirks, and blocks the rest until they have a log:

- Builds `XGO_DOG(port, 115200, version="xgomini")` directly; never the `XGO()` factory (it calls `reset()`, which moves the dog). Never `calibration()`.
- `write_joints(angles_deg[12])`: xgolib id order `11,12,13,21,…,43`; rounds to the nearest byte; clamps to `MOTOR_LIMIT`; refuses partial writes (all 12 or nothing).
- `read_joints()`: returns angles plus, per joint, the tick its value last changed (readback is a 105–130 ms round-robin sample-and-hold).
- `read_imu()`: raw block → the sanity filter; gyro unit conversion once the unit is measured (xgolib says °/s after `/16.4`; V2 said rad/s: `# MEASURE:`).
- Sets `motor_speed` explicitly at every `adopt`: every Phase 1 joint test set it first (255 unless the test varied it), and the boot default is unknown.
- `stop()`: logged; it hands control back to the firmware.
- **Not logged by any probe yet, so blocked until they are:** `action(id)` for allow-listed ids (only `reset()` = action 255 has ever run: M-10); `unload_allmotor()` / `load_allmotor()` (only the per-leg `unload_motor` / `load_motor` have run: M-24); `attitude('p', deg)` standing still (V2 logged it mid-walk in gait mode only).
- Pins the installed `xgolib_dog.py` by hash, as the probe does; refuses to start on a mismatch.

### 3.5 Policy inference

ONNX (exported by the trainer), onnxruntime CPU on the Pi; an MLP forward is well under 1 ms. The observation vector is assembled exactly as the `-StaleJoints` task feeds the actor (interfaces.md §9), including the staleness: raw held readings, no interpolation. The observation normaliser is inside the ONNX graph, so the runtime feeds raw values (checked by the joint-control session on EXP-025's `policy.onnx`: input [1, 35], output [1, 12]). Parity is tested before the first tethered step (Phase 2A week 6).

---

## 4. PC side

### 4.1 Perception → tracks

YOLO (11s on the 3090, as V2) + tracker (ByteTrack) on the camera stream, 640×480 at 20 fps. Output: `tracks` per frame, with the frame's PC receive time and the Pi capture stamp (for ordering only). Frame stats (mean, std) travel in the Pi's `health`, so a lens cap or a dead sensor is visible (LESSONS D2).

### 4.2 Owner tracker

States: `UNLOCKED → ACQUIRING → LOCKED ⇄ LOST → RESCAN → (voice fallback) → UNLOCKED`.

- **Lock** by track id, acquisition score = area × centre weight over `ACQUIRE_FRAMES` (V2 §5 shape), then **VLM verify** against the multi-reference owner photos on the PC (the one identity exception, CLAUDE.md). Verify on first lock, after every re-lock, and every `VERIFY_PERIOD_FRAMES` while locked.
- **Confidence** ∈ [0, 1]: verify success → 1.0; decays per frame while unverified, faster while `LOST`; below `RESCAN_CONFIDENCE` while `LOST` → `RESCAN`. A verify reject drops confidence to `RESCAN_CONFIDENCE`; two consecutive rejects unlock (Brian, D-13).
- **Dead reckoning** of the target bearing while unseen: `bearing += K_TURN × wz_cmd × dt`, from the *commanded* yaw rate, never IMU yaw (frozen register, LESSONS A3). `K_TURN` (achieved/commanded) is `# MEASURE:` with an external reference.
- **Rescan**: a yaw sweep *under the policy* (vx = 0, wz = ±`RESCAN_WZ`) toward the dead-reckoned bearing, bounded, with `RESCAN_COOLDOWN_FRAMES` between sweeps. Head pitch is not available in joint mode (`attitude()` is a firmware call); a pitch scan is a stationary `ACTION` and runs only if the yaw sweep failed (Brian, D-11).
- **Voice fallback** after `RESCAN_MAX_ATTEMPTS`: event `owner_verify_needed` → voice says "that you, bro?" → Phase 2 keyword answer, or a verify on the next lock.

### 4.3 Follow controller (decision 3)

Deterministic, 20 Hz, pixel-domain P-control: `wz = clamp(Kp_yaw × offset_x_norm)`, `vx = clamp(Kp_range × (area_target − area_ratio))`, with deadbands derived from the ladder noise (σ 2.6–3.5 px at 2–3 m, 40 px at 1 m). Area ratio is the range proxy (bbox height saturates under 2 m). The standoff is 1.5 m (`STANDOFF_AREA_RATIO = 0.118`, Brian); the gains are set from a step test after M-6, against the dead time in §5.2. The controller obeys the brain's goal (`FOLLOW_OWNER`, `STAY`, `LOOK_AROUND`, `GO_TO(bearing, range)`, `REST`) and emits `velocity` with `deadman` from the HUD. Target lost → zero velocity within `TARGET_LOST_FRAMES` (one constant, shared with the voice's `target_lost` event: LESSONS B4).

### 4.4 Brain

VLM (Claude; model per decisions.md) called on events and on a slow timer with the latest frame, `owner`, `state` summary and `health`. Tools: `set_goal`, `set_velocity` (TTL ≤ `BRAIN_VELOCITY_TTL_S`, clamped), `do_action(name)` (allow-listed names, the "personality menu"), `say(text)`, `ask_owner(text)`. Tool arguments are validated against the schema before anything is sent; a malformed call is dropped and logged. Its latency never sits in a control loop.

### 4.5 Voice

Built on `feature/voice`: pacing policy (4 s / 30 s, urgent events skip, falls interrupt, battery queues), cached lines, Haiku for novel lines, ElevenLabs Flash → 24 kHz PCM. V3 changes two things: it **subscribes to `event`** instead of deriving events from state (decision 6: T1 debounce moves to the tracker, T3/T4 onto the Pi; `is_fallen` stays the single definition), and **audio goes to the Pi** over PUSH/PULL (Brian's option (a)) once the Pi has a playback path that makes sound. Brian has picked one: a USB sound card with its own speaker pair and an onboard mic (D-17), not on the dog yet. Until it passes M-13 (sound) and M-30 (USB current), the voice plays on the PC. The Pi's existing card 2 (`plughw:2,0`) is V1's Robot HAT audio setup still on this OS install: eight silent plays, nothing behind it on the S2, and the default ALSA route still points at it (decisions.md §1; LESSONS B1 once more). So the player names its device and never uses the default.

Listening is already built PC-side on `feature/voice`: PC mic → ElevenLabs Scribe → Haiku → TTS, half-duplex, unit-tested, not yet run live. It needs no cross-component message. The dog's voice board is a wake-word and command recogniser, not a microphone the Pi can read: "Hello Yahboom" produced `$B000#` on its serial port, and `arecord -l` lists no capture device with or without the board cabled. So `keyword` events come first (decision 7). Today they come from a `voice_module_reader` on the Pi; whether the board stays is undecided, so `keyword` names what was heard and a software wake word can publish it instead (C-18, M-32). The USB card gives the dog a mic (D-17) but documents no echo cancellation, so listening stays half-duplex. The mic stream to the PC waits on D-20; what heard speech may cause waits on D-21 and D-22.

### 4.6 HUD and deadman

Opens DISARMED; a real key-held deadman (W5's design adapted to the PC); SPACE = e-stop; shows three link states per socket pair (OFFLINE / CALIBRATING / LIVE, LESSONS C2), the `last_cmd_seq` echo (LESSONS C1), mode, degraded notices, battery, camera health, IMU status.

The HUD process also hosts the **gateway**, the only writer on the command socket. Armed, it forwards the follow controller's and the brain's requests with the deadman flag; disarmed, it forwards nothing and sends zero velocity, so the link stays live and disarming is one choke point on the PC (interfaces.md §12). The HUD can also set the goal itself, so a supervised FOLLOW session runs with no brain.

---

## 5. Data flow, rates, latency budgets

### 5.1 Streams

| Stream | From → to | Pattern | Port | Rate | Payload |
|---|---|---|---|---|---|
| `state` | Pi → PC | PUB (Pi binds) → SUB | 5558 | 50 Hz | robot state, ~600 B |
| `health` | Pi → PC | same socket, topic `health` | 5558 | 1 Hz | throttling, Wi-Fi, camera, loop timing |
| `event` | Pi → PC | same socket, topic `event` | 5558 | on change | named events |
| `velocity` / `action` / `mode` / `estop` | PC → Pi | PUB (PC connects) → SUB (Pi binds) | 5556 | velocity 20 Hz; others on change | commands |
| `hello` | PC ⇄ Pi | REQ → REP (Pi binds) | 5557 | startup + every 5 s | versions, socket table, liveness |
| camera | Pi → PC | PUSH (Pi binds) → PULL (PC connects, CONFLATE) | 50505 | 20 fps | `<qI` header + JPEG (V2 format) |
| lidar (Phase 2) | Pi → PC | PUSH (Pi binds) → PULL | 50507 | scan rate | V1 scan JSON |
| audio | PC → Pi | PUSH (PC connects) → PULL (Pi binds) | 5560 | on demand | header + PCM, multipart |
| PC bus | each PC process's own loopback PUB | PUB → SUB | 5570–5574 on `127.0.0.1` | 20 Hz | `tracks`, `owner`, `goal`, `say`, `cmd_request`, `event` (interfaces.md §12) |

Full schemas: [interfaces.md](interfaces.md).

### 5.2 Latency budgets per path

Measured values are tagged; the rest are estimates to be replaced (`# MEASURE:`).

**Perception → motion (the follow loop)**

| Stage | Budget | Basis |
|---|---|---|
| camera frame period | 50 ms (worst 67.5) | measured, 20 fps |
| capture → PC | 10.9 ms mean, 28.8 max | measured one-way |
| YOLO11s + tracker on the 3090 | ~15 ms | `# MEASURE:` |
| follow controller tick | ≤ 50 ms (20 Hz) | design |
| `velocity` PC → Pi over Wi-Fi | ~5 ms | `# MEASURE:` |
| arbiter picks it up | ≤ 20 ms (next tick) | design |
| command delay (board + servo) | 40 ms | Brian's model from Phase 1 (EXP-009) |
| **total dead time** | **≈ 150–250 ms** | vs V2's 300–600 ms plus hysteresis |

At the trained maximum of 0.8 rad/s (46 °/s), 0.25 s of dead time is ≈ 11° of yaw before a correction starts: the P-gain and deadband must be chosen against that number, measured, not assumed.

**Policy loop (Pi)**: 20 ms tick, paced by the monotonic clock. Joint observations are 0–130 ms stale by construction, plus up to 40 ms from the read cadence; the policy trained with the 130 ms staleness (EXP-010) but not with the cadence. IMU observations are up to ~1 s stale during freezes, which no policy has trained with yet (§3.3).

**Comms loss → safe**: TTL expiry ≤ `VELOCITY_TTL_TICKS` × 20 ms after the last message. How long the walk → stand transition then takes, and whether it is always clean, is unmeasured (M-28).

**Brain**: 1–3 s per call (`# MEASURE:` per model); never in a loop.

**Voice**: event → first sound, measured 0.19–0.21 s on cached lines (PC speaker); target p50 1.5 s (Brian). With audio on the Pi, the Pi's `speech_started` echo of the PC's `t_ms` gives a round trip on the PC's clock only (LESSONS C5). It is an upper bound: it includes the Pi → PC leg.

**Lidar reflex (Phase 2)**: worst case one scan period + one tick ≈ 120 ms at the nominal 10 Hz (`# MEASURE:` the scan rate).

### 5.3 Rates the Pi must sustain

| Item | Rate | Headroom |
|---|---|---|
| serial, joint mode | 12 writes + alternating reads per tick | 17–19 ms (inferred) / 18.0 ms (measured) of 20 ms, so ≤ 2 ms is left for everything else. `# MEASURE:` the composed schedule (M-2, gate) |
| `state` JSON | 50 Hz × ~600 B ≈ 30 kB/s | trivial |
| camera | 7.7 Mbps at q75 | measured; Wi-Fi dependent |
| ONNX forward | < 1 ms | design |

---

## 6. Phases (roadmap mapping)

| Roadmap item | Component here | Phase |
|---|---|---|
| Deploy the RL policy | Pi runtime §3, parity test, stand-test gate | 1 |
| Domain randomization (now also the measured IMU freezes and more stand commands), gyro units, joint map check, Pi-hang stop test, kill switch | decisions.md §5 measurement register. M-4 (joint sign and zero offset) is the first hardware session: a new default pose means retraining every policy | 1 (gate) |
| VLM brain with owner tracking | §4.2–4.4 | 1 |
| Voice output | §4.5 (built; re-pointed at events + Pi audio) | 1 |
| Personality: action groups as tools | arbiter `ACTION` mode + allow-list | 1 |
| Conversation (STT → Haiku → TTS) | §4.5: the PC-side loop is built; the dog's speaker and mic are a USB sound card (D-17), waiting on its arrival, M-13, M-30 and D-20 | 2 |
| LiDAR reflex + SLAM | §3.3 reflex; SLAM behind one ROS2 bridge node on the Pi | 2 |
| Gamepad | `velocity` with `src: teleop` | later |

---

## 7. LESSONS.md → design choice

| Lesson | What V3 does | Where |
|---|---|---|
| A1 workarounds for the old platform | No gait-buffer scaffolding; the firmware gait is never used to walk; `REST` uses `unload_allmotor()`; if the runtime grows past ~600 lines, ask what is being ported | §1 rule 3, §3.2 |
| A2 handled boot ruins yaw | `BOOT` waits on the first-nonzero-yaw latch (predicate); an exact-0.0 vector is a rejected read; HUD shows CALIBRATING separately from OFFLINE | §3.2, §3.3, §4.6 |
| A3 frozen IMU misread as fine | Sanity filter with `status`/`frozen_ticks` in `state`; `health` reports fresh-value rate, never call rate; freezes are in the sim's scoring | §3.3, interfaces §4 |
| A4 SDK calls lie | Only calls a probe has logged; the unlogged ones are blocked until they are; no `turn_by`, no timed moves; probe verdicts computed from data | §3.4 |
| A5 power shapes testing | `battery_pct` in every `state`; `battery_low`/`critical` events; `REST` before the 9 % lockout; sustained-load runtime `# MEASURE:` | §3.3 |
| A6 dead time on a continuous machine | TTL'd velocity; proportional 20 Hz controller on the PC, not the VLM; no commit-frame hysteresis; dead time measured externally | §4.3, §5.2 |
| A7 watchdog on the machine that hung | Walk only in joint mode (a hang holds a pose, it doesn't walk: stand test confirms); kill switch = power button in reach; board-timeout test; persistent journal + `get_throttled` + Wi-Fi in `health` | §3.2, failure-modes §2 |
| B1 ported dead machinery | Runtime from scratch; unknown command fields are rejected with an event, not tolerated | interfaces §1 |
| B2 thresholds crossed a sensor change | Every threshold tagged; `MEASURE` blocks or shouts at mode entry | §1 rule 8, decisions §3 |
| B3 behaviour kept an old entry condition | `RESCAN` entry = lost ≥ N frames **and** was locked; never from boot; every mode's entry row is explicit | §3.2, §4.2 |
| B4 two timers tuned apart | `TARGET_LOST_FRAMES` is one constant for controller and voice; TTL, lost and dead ticks defined from one another with the constraint written | §4.3, decisions §3 |
| C1 ZMQ fails silently | One socket table; `hello` handshake and startup self-test per pair; `last_cmd_seq` echoed in `state`, shown on the HUD | §5.1, interfaces §3 |
| C2 default looked like data | Receivers track first-message receipt; OFFLINE / CALIBRATING / LIVE; no pre-filled state dicts | §4.6 |
| C3 warning depended on a branch | Degraded notices are raised at mode entry and carried in `mode_changed.degraded` | §3.3, interfaces §6 |
| C4 config doesn't follow the code | The Pi binds everything; the PC knows one hostname; per-machine env ships only its variables; startup validates by connecting | §1 rule 7, interfaces §10 |
| C5 cross-host clocks | Ages in receiver ticks/frames; `t_ms` is intra-host only; capture stamps order frames, never age them | §1 rule 5 |
| C6 camera stall | `cam_sender` fails fast (count-based), escalates to a USB rebind, reports camera health | failure-modes §6 |
| D1 smoke-test gate paid off | The stand-test gate (decisions §5) must be green before the first tethered step | decisions §5 |
| D2 check the physical world | Frame mean/std in `health`; IMU plausibility; joint readback vs command in `state` | interfaces §4 |
| D3 dev-machine friction | Phase 0 checks on the PC; no inbound firewall rule needed because the Pi binds | §1 rule 7 |
| D4 write down what was never measured | `# MEASURE:` register with procedures and the decision each unblocks | decisions §5 |
