# IronBark V3 architecture

Design only: no code lands from this document. Every agent building a V3 component builds to the contracts in [interfaces.md](interfaces.md); the behaviour under faults is in [failure-modes.md](failure-modes.md); the calls Brian made and the ones still open are in [decisions.md](decisions.md).

Status: Brian accepted all nine recommendations on 2026-11-08 ("Go with all recs"). Numbers without a measurement tag are Brian's to set and are listed as open in `decisions.md`. Every number marked `# MEASURE:` has a measurement procedure in `decisions.md` §5.

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
4. **Frame counts and state predicates on the Pi; wall clock only on the PC.** Every message that must expire carries a tick count.
5. **No cross-host timestamp arithmetic.** Receivers age data by their own clock or tick.
6. **The owner of a fact publishes it, once.** The Pi says `fell`; the tracker says `target_lost`; voice subscribes and never re-derives either.
7. **The Pi binds every socket; the PC connects to one hostname.** The Pi needs no PC address, and the PC needs no inbound firewall rule.
8. **Every threshold carries a tag** (`measured | vendor | design | MEASURE`). A `MEASURE` threshold blocks the behaviour that depends on it, or at least raises a degraded notice at mode entry.
9. **Every vendor call is unverified until a probe log says otherwise.** The runtime uses the calls Phase 1 measured and nothing else.
10. **Write V3 from scratch; port facts, not code.** `motor_controller.py` stays in the archive as a reference.

---

## 2. What runs where

| Host | Process | Rate | Job |
|---|---|---|---|
| **Pi 5** | `runtime` | 50 Hz tick | Arbiter (modes), safety layer (IMU filter, watchdog, tilt cutoff, joint clamps), lidar reflex (Phase 2), policy inference (ONNX), motion-board adapter (xgolib quirks), telemetry PUB (`state` 50 Hz, `health` 1 Hz, `event`), `hello` REP |
| Pi 5 | `cam_sender` | 20 fps | `/dev/video0` MJPG 640×480 → PUSH to the PC; frame stats + stall detection → runtime over `ipc://` |
| Pi 5 | `lidar_reader` (Phase 2) | scan rate (`# MEASURE:`; vendor nominal ~10 Hz) | MS200 UART → full scans PUSH to the PC; sector minima → runtime over `ipc://` |
| Pi 5 | `audio_player` | on demand | PULL PCM from the PC, play on the S2 speaker (`# MEASURE:` the audio device), report `speech_started/ended` to the runtime |
| **PC (3090)** | `perception` | 20 Hz (camera-bound) | YOLO + tracker on the camera stream → `tracks` |
| PC | `owner_tracker` | 20 Hz | Lock, confidence, dead reckoning, rescan, VLM verify → `owner` + events |
| PC | `follow_controller` | 20 Hz | Deterministic P-control from `owner` → `velocity` with TTL; obeys the brain's goal |
| PC | `brain` | 0.3–1 Hz, event-driven | VLM with tools: goal, direct velocity (short TTL), action group, say, ask owner |
| PC | `voice` | event-driven | Pacing policy (built), cached lines / Haiku → TTS → PCM PUSH to the Pi |
| PC | `hud` | 20 Hz | Operator view, deadman (real key-held), e-stop, link states, `seq` echo, degraded notices |

**Why perception is on the PC** (decision 2): the camera→PC path is measured (20 fps, 10.9 ms one-way), the 3090 is idle at deploy time, and a Pi-side detector needs either the CPU (YOLO11n-class at roughly 5–10 fps, unmeasured) or a Hailo HAT (new hardware). The `tracks` schema is host-agnostic so the detector can move to the Pi later without touching anything downstream. Nothing safety-critical on the Pi depends on perception; the watchdog and the lidar reflex are local.

---

## 3. Pi runtime

### 3.1 Tick schedule

The policy is trained at 50 Hz (20 ms). Measured serial costs (`phase1-joint-control-results.md`): 12-joint `motor()` 9.7 ms of wire time; `read_motor()` 16.2 ms when it waits behind the write; `read_imu()` 4.6 ms; both reads every tick → 21.0 ms/step, 47.6 Hz. So both reads cannot share a 20 ms tick.

Design: alternate the reads. Even ticks write + `read_imu()` (~14 ms); odd ticks write + `read_motor()` (~18 ms). Each tick fits 20 ms. Joint readback lands at 25 Hz, which loses nothing because each joint's value refreshes only every ~105–130 ms in the firmware; the IMU at 25 Hz is finer than its live refresh (4–8 ms) only during live stretches, and it is frozen 42 % of the time anyway.

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

Open for Brian (decisions.md D-10): whether the sim's readback model should mirror the 40 ms read cadence; the obs-parity test (Phase 2A week 6) tells whether it matters. `# MEASURE:` the actual tick time of this schedule, and whether the firmware accepts 2 Mbaud (xgolib hints "RL programs" use it), which would make the wire time negligible.

### 3.2 Arbiter: modes and the motor owner

| Mode | Motor owner | What the board sees | Entry | Exit |
|---|---|---|---|---|
| `BOOT` | none | nothing | power-on | `imu.ready` latch (first nonzero yaw, a predicate, never a timer) → `IDLE_HOLD` |
| `IDLE_HOLD` | runtime | all 12 joints held at their measured angles (joint mode) | any fault, stream loss timeout, operator | request → `POLICY` or `ACTION` or `REST` |
| `POLICY` | policy | 12 joint targets at 50 Hz; velocity command from the arbiter (PC stream, brain, or zero) | from `IDLE_HOLD` via the adopt ramp | zero-velocity stand → `IDLE_HOLD`; fault → `IDLE_HOLD`/`ESTOP` |
| `ACTION` | firmware | one allow-listed action group, with a tick budget | only from `IDLE_HOLD` after a `release` | budget elapsed → `adopt` → `IDLE_HOLD` |
| `REST` | firmware then none | lie-down action, then `unload_allmotor()` (the thermal lever V2 named, LESSONS A1) | from `IDLE_HOLD` | `load_allmotor()` → `adopt` → `IDLE_HOLD` |
| `ESTOP` | runtime | joints held; after `FALL_UNLOAD_TICKS` when fallen, unloaded | operator e-stop, `fell`, IMU rejected too long | only an operator `clear_estop` |

Priority when requests conflict: `ESTOP` > fault → `IDLE_HOLD` > operator request > brain request. A brain request that arrives while walking is answered with `rejected: walking`; the brain must first set goal `STAY`, the follow controller sends zero velocity, and the arbiter reaches `IDLE_HOLD` on its own. Action groups never preempt walking (decision 4).

**Handoffs** (both `# MEASURE:` on the stand before any deployment; procedures in decisions.md §5):

- **`adopt` (firmware → joint mode):** wait one full readback cycle (≥ 7 ticks) so every joint's reading is fresh; send all 12 *measured* angles first (rounded to the nearest byte, since `conver2u8` truncates); then ramp from the measured pose to the policy's default pose over `ADOPT_RAMP_TICKS`. Reason: the first `motor()` call switches the board to joint mode and drives every unsent joint to its last joint-mode setpoint (~8° jumps seen in Phase 1).
- **`release` (joint mode → firmware):** policy at zero velocity for `STAND_TICKS`, then drive the joints to `firmware_stance` (the pose read at boot while the board still owned the legs), then `stop()`. Reason: `stop()` hands control back and the legs snap to the firmware stance; pre-positioning makes the snap ≈ 0.

### 3.3 Safety layer (runs every tick, between the arbiter and the policy)

| Guard | Signal | Response |
|---|---|---|
| IMU sanity filter | whole accel or gyro vector exactly 0.0; \|gyro\| > `GYRO_MAX_DPS`; block identical for `IMU_FREEZE_READS` consecutive reads | reading rejected / marked frozen; policy sees the last good value (what the sim's `imu_frozen` term does); `imu.status` and `frozen_ticks` in `state`; frozen or rejected for > `IMU_STALE_TICKS` → velocity zeroed; > `IMU_DEAD_TICKS` → `IDLE_HOLD` |
| Tilt cutoff | `is_fallen` (Brian's `metrics.py`, `FALL_TILT_DEG = 46`) on filtered roll/pitch | `fell` event, `ESTOP` (hold), unload after `FALL_UNLOAD_TICKS` so the servos stop fighting the floor |
| Command watchdog | ticks since the last `velocity` message | TTL expiry → velocity zero (the policy stands); `CMD_LOST_TICKS` → `cmd_stream_lost` event; `CMD_DEAD_TICKS` → `IDLE_HOLD` |
| Deadman | `velocity.deadman` false or absent while `REQUIRE_DEADMAN` | velocity zero |
| Velocity clamp | trained ranges vx −0.5…0.6, vy ±0.3, wz ±0.8 (sim command ranges) | clamp, count in `health` |
| Joint clamp | `MOTOR_LIMIT` minus `JOINT_MARGIN_DEG`; per-tick step ≤ `JOINT_STEP_MAX_DEG` | clamp, count in `health` |
| Lidar reflex (Phase 2) | front-sector minimum range, scan age in scans | vx clamped by a taper; lidar dark → `VX_CAP_LIDAR_DARK` + degraded notice at mode entry; never adds motion (decision 8) |
| Battery | `battery_pct` ≤ `BATTERY_LOW_PCT` (20, Brian) / ≤ `BATTERY_CRITICAL_PCT` | events; critical → velocity zero, then `IDLE_HOLD`; the brain is asked to `REST` before the ≤ 9 % firmware lockout lies the dog down on its own |

All thresholds above are Brian's calls (decisions.md §3) unless tagged measured.

### 3.4 Motion-board adapter

The only module that imports xgolib. It wraps exactly the calls Phase 1 measured and hides the quirks:

- Builds `XGO_DOG(port, 115200, version="xgomini")` directly; never the `XGO()` factory (it calls `reset()`, which moves the dog). Never `calibration()`.
- `write_joints(angles_deg[12])`: xgolib id order `11,12,13,21,…,43`; rounds to the nearest byte; clamps to `MOTOR_LIMIT`; refuses partial writes (all 12 or nothing).
- `read_joints()`: returns angles plus, per joint, the tick its value last changed (readback is a 105–130 ms round-robin sample-and-hold).
- `read_imu()`: raw block → the sanity filter; gyro unit conversion once the unit is measured (xgolib says °/s after `/16.4`; V2 said rad/s: `# MEASURE:`).
- `stop()`, `action(id)` (allow-listed ids only), `unload_allmotor()`/`load_allmotor()`, `attitude('p', deg)` (stationary, firmware mode only).
- Pins the installed `xgolib_dog.py` by hash, as the probe does; refuses to start on a mismatch.

### 3.5 Policy inference

ONNX (exported by the trainer), onnxruntime CPU on the Pi; an MLP forward is well under 1 ms. The observation vector is assembled exactly as the `-StaleJoints` task feeds the actor (interfaces.md §9), including the staleness: raw held readings, no interpolation. Parity is tested before the first tethered step (Phase 2A week 6).

---

## 4. PC side

### 4.1 Perception → tracks

YOLO (11s on the 3090, as V2) + tracker (ByteTrack) on the camera stream, 640×480 at 20 fps. Output: `tracks` per frame, with the frame's PC receive time and the Pi capture stamp (for ordering only). Frame stats (mean, std) travel in the Pi's `health`, so a lens cap or a dead sensor is visible (LESSONS D2).

### 4.2 Owner tracker

States: `UNLOCKED → ACQUIRING → LOCKED ⇄ LOST → RESCAN → (voice fallback) → UNLOCKED`.

- **Lock** by track id, acquisition score = area × centre weight over `ACQUIRE_FRAMES` (V2 §5 shape), then **VLM verify** against the multi-reference owner photos on the PC (the one identity exception, CLAUDE.md). Verify on first lock, after every re-lock, and every `VERIFY_PERIOD_FRAMES` while locked.
- **Confidence** ∈ [0, 1]: verify success → 1.0; decays per frame while unverified, faster while `LOST`; below `RESCAN_CONFIDENCE` → `RESCAN`.
- **Dead reckoning** of the target bearing while unseen: `bearing += K_TURN × wz_cmd × dt`, from the *commanded* yaw rate, never IMU yaw (frozen register, LESSONS A3). `K_TURN` (achieved/commanded) is `# MEASURE:` with an external reference.
- **Rescan**: a yaw sweep *under the policy* (vx = 0, wz = ±`RESCAN_WZ`) toward the dead-reckoned bearing, bounded, with `RESCAN_COOLDOWN_FRAMES` between sweeps. Head pitch is not available in joint mode (`attitude()` is a firmware call); a pitch scan is a stationary `ACTION` and runs only if the yaw sweep failed (decision in decisions.md D-11).
- **Voice fallback** after `RESCAN_MAX_ATTEMPTS`: event `owner_verify_needed` → voice says "that you, bro?" → Phase 2 keyword answer, or a verify on the next lock.

### 4.3 Follow controller (decision 3)

Deterministic, 20 Hz, pixel-domain P-control: `wz = clamp(Kp_yaw × offset_x_norm)`, `vx = clamp(Kp_range × (area_target − area_ratio))`, with deadbands derived from the ladder noise (σ 2.6–3.5 px at 2–3 m, 40 px at 1 m). Area ratio is the range proxy (bbox height saturates under 2 m). Gains and the standoff are Brian's; the dead time they must tolerate is §5.2. The controller obeys the brain's goal (`FOLLOW_OWNER`, `STAY`, `LOOK_AROUND`, `GO_TO(bearing, range)`, `REST`) and emits `velocity` with `deadman` from the HUD. Target lost → zero velocity within `TARGET_LOST_FRAMES` (one constant, shared with the voice's `target_lost` event: LESSONS B4).

### 4.4 Brain

VLM (Claude; model per decisions.md) called on events and on a slow timer with the latest frame, `owner`, `state` summary and `health`. Tools: `set_goal`, `set_velocity` (TTL ≤ `BRAIN_VELOCITY_TTL_S`, clamped), `do_action(name)` (allow-listed names, the "personality menu"), `say(text)`, `ask_owner(text)`. Tool arguments are validated against the schema before anything is sent; a malformed call is dropped and logged. Its latency never sits in a control loop.

### 4.5 Voice

Built on `feature/voice`: pacing policy (4 s / 30 s, urgent events skip, falls interrupt, battery queues), cached lines, Haiku for novel lines, ElevenLabs Flash → 24 kHz PCM. V3 changes two things: it **subscribes to `event`** instead of deriving events from state (decision 6: T1 debounce moves to the tracker, T3/T4 onto the Pi; `is_fallen` stays the single definition), and **audio goes to the Pi** over PUSH/PULL (Brian's option (a)). Phase 2 adds STT: the CSK4002 module is a keyword recogniser over serial, so `keyword` events first; `speech_text` reserved for a raw-mic path (decision 7).

### 4.6 HUD and deadman

Opens DISARMED; a real key-held deadman (W5's design adapted to the PC); SPACE = e-stop; shows three link states per socket pair (OFFLINE / CALIBRATING / LIVE, LESSONS C2), the `last_cmd_seq` echo (LESSONS C1), mode, degraded notices, battery, camera health, IMU status.

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
| PC-internal | perception → tracker → controller → brain/voice | PUB/SUB on `ipc://` or `tcp://127.0.0.1` | — | 20 Hz | `tracks`, `owner`, `goal` |

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

**Policy loop (Pi)**: 20 ms tick; obs are 0–130 ms stale by construction (joints) and up to ~1 s stale during IMU freezes; both are in the sim the policy trained in.

**Comms loss → safe**: TTL expiry ≤ `VELOCITY_TTL_TICKS` × 20 ms after the last message; stand reached one gait cycle later.

**Brain**: 1–3 s per call (`# MEASURE:` per model); never in a loop.

**Voice**: event → first sound, measured 0.19–0.21 s on cached lines (PC speaker); target p50 1.5 s (Brian). With audio on the Pi, the Pi's `speech_started` echo of the PC's `t_ms` gives a round-trip measurement on the PC's clock only (LESSONS C5).

**Lidar reflex (Phase 2)**: worst case one scan period + one tick ≈ 120 ms at the nominal 10 Hz (`# MEASURE:` the scan rate).

### 5.3 Rates the Pi must sustain

| Item | Rate | Headroom |
|---|---|---|
| serial, joint mode | 12 writes + alternating reads per tick | 14/18 ms of 20 ms (measured components; `# MEASURE:` the composed schedule) |
| `state` JSON | 50 Hz × ~600 B ≈ 30 kB/s | trivial |
| camera | 7.7 Mbps at q75 | measured; Wi-Fi dependent |
| ONNX forward | < 1 ms | design |

---

## 6. Phases (roadmap mapping)

| Roadmap item | Component here | Phase |
|---|---|---|
| Deploy the RL policy | Pi runtime §3, parity test, stand-test gate | 1 |
| Domain randomization, gyro units, joint map check, Pi-hang stop test, kill switch | decisions.md §5 measurement register | 1 (gate) |
| VLM brain with owner tracking | §4.2–4.4 | 1 |
| Voice output | §4.5 (built; re-pointed at events + Pi audio) | 1 |
| Personality: action groups as tools | arbiter `ACTION` mode + allow-list | 1 |
| Conversation (STT → Haiku → TTS) | §4.5 Phase 2 path | 2 |
| LiDAR reflex + SLAM | §3.3 reflex; SLAM behind one ROS2 bridge node on the Pi | 2 |
| Gamepad | `velocity` with `src: teleop` | later |

---

## 7. LESSONS.md → design choice

| Lesson | What V3 does | Where |
|---|---|---|
| A1 workarounds for the old platform | No gait-buffer scaffolding; the firmware gait is never used to walk; `REST` uses `unload_allmotor()`; if the runtime grows past ~600 lines, ask what is being ported | §1 rule 3, §3.2 |
| A2 handled boot ruins yaw | `BOOT` waits on the first-nonzero-yaw latch (predicate); an exact-0.0 vector is a rejected read; HUD shows CALIBRATING separately from OFFLINE | §3.2, §3.3, §4.6 |
| A3 frozen IMU misread as fine | Sanity filter with `status`/`frozen_ticks` in `state`; `health` reports fresh-value rate, never call rate; freezes are in the sim's scoring | §3.3, interfaces §4 |
| A4 SDK calls lie | Only Phase-1-measured calls; no `turn_by`, no timed moves; probe verdicts computed from data | §3.4 |
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
