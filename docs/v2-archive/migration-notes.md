# IronBark V2 — Migration Notes

Working log of measured facts and standing decisions for the PiDog → DogZilla
S2 port. Append, don't rewrite; every entry is dated. Assumption-flagged items
get promoted to facts only by hardware measurement.

## 2026-08-28 — Phase 1 prep (oracle session)

### Pi recon (measured over `ssh pi`)

- Pi 5 Model B, Debian 13 trixie, Python 3.13.5, aarch64. User `lolly`,
  passwordless sudo, all hardware groups present.
- `lsusb`: **root hubs only** — no OAK-D, no RPLidar, no USB link to the dog.
- `rpicam-hello --list-cameras`: none.
- `/dev/serial0 → /dev/ttyAMA10` exists, `root:dialout`, lolly has access.
- `i2c-tools` installed this session (lives in `/usr/sbin` — non-login SSH
  shells need the full path). **Bus 1 scan: one device at `0x3C`** — the
  canonical SSD1306 OLED address. Buses 13/14 answer every address (Pi 5 RP1
  internal buses, ignore).
- Reading of the evidence: the Pi appears to be mated to a carrier board that
  has an OLED (consistent with the DogZilla's display), and the motion
  controller link is most plausibly the **UART at `/dev/ttyAMA10`** (XGO
  lineage protocol), which `lsusb` can't see. Smoke-test stage 0 confirms or
  refutes; until then this is flagged as inference, not fact.
- No `DOGZILLA` or `xgolib` module importable — SDK not installed yet.
- V1 leftovers in `~`: `robot-hat/`, `vilib/` (SunFounder). Ignore; don't
  reorganize.

### SDK facts extracted from the course PDFs (`reference/dogzilla_pdfs/`)

Beyond the API table in the README/handoff, the lessons add:

1. **The command model is velocity-setpoint, not queued gait frames.**
   Lesson 1 binds `forward(25)` to a button and requires an explicit Stop
   button; lesson 2's sliders call `move('x', step)` / `turn(v)` on slider
   change and the dog keeps walking at that setpoint. PiDog's
   `legs_action_buffer` concept has **no analogue at this API surface**.
   (Still hypothesis until stage 2 of the smoke test — but it is the
   documented usage pattern, not a guess.)
2. **`move(direction, step)` takes signed steps** ('x': ±25, 'y': ±18) —
   forward/back/strafe are one signed axis each, joystick-shaped.
3. **`turn(step)` is documented as rotation speed in °/s** (±100). Paired
   with `read_yaw()`, "turn N degrees" becomes a *closed-loop measured*
   primitive — V1's open-loop turn calibration problem dies here. Stage 3
   of the smoke test measures commanded-vs-actual °/s.
4. **`pace('slow'|'normal'|'high')`** sets step frequency; speed = frequency
   × step width. This is the S2's version of V1's `speed` param.
5. **`imu(mode)` self-stabilization** (course 05): STM32 auto-levels the back
   using a **9-axis IMU** (magnetometer present — yaw may be compass-fused;
   drift test will tell). **Manual `attitude()` is disallowed while
   stabilization is on** — the two are mutually exclusive. Any camera-aim
   trim via `attitude('p', …)` therefore requires `imu(0)`.
6. **`unload_allmotor()` / `load_allmotor()`** — a native torque-release
   path. V1's servo thermal death traced precisely to the *absence* of this
   (PiDog servos held full torque forever). A "lie down + unload" rest state
   is now a real thermal-management lever.
7. **`read_*` failure semantics are ambiguous sentinels**: `read_yaw()`
   returns `0` on failure (indistinguishable from true 0°), `read_battery()`
   returns 0 on failure, `read_motor()` returns `[]`. Telemetry design must
   treat exact-zero streaks as suspect.
8. **`read_battery()` ambiguity**: English text says integer 1–100 (percent);
   the Chinese UI label says 读取电压 ("read voltage"). Smoke-test stage 0
   records the value and type, and inventories any voltage-ish methods.
9. Neutral pose from the servo lesson: shoulder 0 / thigh 48 / calf 14;
   default body height z = 105 mm (range 75–115). Servo IDs `[11,12,13,
   21,22,23, 31,32,33, 41,42,43]`, legs 1 LF / 2 RF / 3 RR / 4 LR.
10. Preset action IDs confirmed against the handoff table (1 lie … 19
    handshake, 255 stop+reset); `perform(1|0)` cycles all actions.

### What this kills from V1's Pi-side code (pending stage-2 confirmation)

Buffer-depth accounting, `one_shot` semantics, `flush=True` machinery,
leap-prone interpolation, gait-segment tracking, action dedup as a
*buffer-protection* mechanism (it may survive in miniature as plain
don't-resend-identical-setpoint hygiene), Direction 1's synthesized 360.
The EXECUTING→DONE gate changes shape entirely: there is no buffer to
drain — completion becomes *measured* (yaw delta reached, frame count
elapsed, or distance proxy) followed by `stop()`.

### Mac↔Pi comms note

Tailscale is NOT installed on the Pi; config.py/README still assume it.
LAN-only (<PI_LAN_IP>) works for bench development. Decide later whether
to install Tailscale on the Pi (one command, user's call) or keep LAN.

### deploy.sh status

Dangling: it scp's 9 V1 `pi/` files, none of which exist in V2. Rewrite
comes with the new Pi-side controller, after the smoke test. The smoke test
was deployed manually this session (see below).

### S2 platform research (web pass, citations in the session's research brief)

- **S2 = S1 + Oradar MS200 lidar + CSK4002 voice module.** Camera on both:
  2MP USB wide-angle, `/dev/video0`, opened with `cv.VideoCapture(0)` in
  Yahboom's own code. MS200: 360°, 4,500 samples/s, 0.03–12 m, UART
  @230400 (`ttyAMA1` on Yahboom's image), documented serial protocol
  (Orbbec manual), driven by ROS2 only in *their* stack — standalone reader
  feasible. Voice: USB serial, ASCII `$Bxxx#` command protocol.
- **SDK provenance settled**: `DOGZILLA` is NOT on PyPI; Yahboom ships
  `DOGZILLALib.py` (v3.1.9, 2023) preinstalled on their image, and it is a
  **renamed fork of Luwu's `xgolib`** — identical register map (VX 0x30,
  VY 0x31, VYAW 0x32, ATTITUDE 0x36…), identical limits ([0,25]/[0,18]/
  [0,100] = xgolib's `xgomini` param set), verbatim docstrings. `xgolib`
  IS on PyPI and actively maintained (1.1.10 released 2026-08-26).
- **Motion MCU**: ESP32 co-processor (current gen), on the Pi's
  **`/dev/ttyAMA0` @ 115200**. On this vanilla-trixie Pi, `ttyAMA0` does
  not exist yet — `dtparam=uart0=on` + reboot creates it (`ttyAMA10` is
  the Pi 5 debug connector, not the header UART). Lidar UART overlay TBD
  at bring-up.
- **Yahboom factory image** (not what we run): ROS2-Humble-in-Docker on
  Pi 5, systemd services incl. `yahboom_oled.service` polling battery over
  the motion serial port every 3 s — Yahboom's own docs flag it as a serial
  contention source. Vanilla trixie has none of this; one less tenant on
  the bus.
- **Body/battery (S2 current gen)**: 246.2 × 144.6 × 195.3 mm, ~972 g,
  7.4 V 2,500 mAh, claimed ~1 h runtime (generation-dependent figures
  exist; measure ourselves). **Charger plug = hard power cut** (no
  run-while-charging tests); **≤9% battery = lie-down lockout**. Body
  width 144.6 mm is the input for re-deriving `LIDAR_SIDE_FIT`-class
  thresholds (V1: 25 cm for a ~13 cm body).

### Offline SDK introspection (measured on the Pi, no hardware link)

`pip install xgolib` → 1.1.9 in `~/ironbark/.venv`. `xgolib.XGO(...)` is a
factory *function* (auto-scans `SCAN_PORTS`, firmware-detects model,
returns `XGO_DOG`). `XGO_DOG` carries all 27 course-documented methods
**plus closed-loop primitives the PDFs never mention**:

    turn_to(theta, vyaw=60, emax=4)          # absolute yaw, ±4° tolerance
    turn_by(theta, mintime, vyaw=16, k=0.08) # relative, P-controller
    move_by / move_x_by / move_y_by(distance, v, k, mintime)
    turn(step, runtime=0)                    # timed velocity turn
    move_to(data, wait=True, overtime=15.0)  # explicit blocking variant
    read_rotate_state(), set_yaw_init(), read_firmware(), read_lib_version()

Whether the S2's 2023-era firmware implements the closed-loop registers is
smoke-test Q8 (stage 6). If yes: FOLLOW uses the velocity layer at 10 Hz;
perceive-act EXECUTING becomes a single self-terminating call.

### First hardware contact — bench pass results (2026-08-28 evening)

User enabled `uart0` + rebooted, then ran stages 0–1 (`--no-motion`).
Raw JSONL: `docs/measurements/smoke_20260828_234946.jsonl`.

**Answered:**
- **Q5 — standalone SDK: YES.** xgolib on vanilla trixie opened
  `/dev/ttyAMA0`, firmware identified as **`M-4.0.1-Y`** (xgomini
  protocol, Yahboom build, 4.x — recent; good sign for Q8's closed-loop
  registers). Auto-detect resolved model XGOMINI.
- **Q6 — battery: int percent** (read 99). No voltage-ish methods on the
  SDK surface; percent is what we get (matches course docs; the Chinese
  "voltage" label was about the OLED's own display).
- **Read latencies: 3.0–4.2 ms mean, ~5 ms max** across read_firmware /
  battery / motor / roll / pitch / yaw → serial round-trips support
  100 Hz+ polling; a 10 Hz telemetry loop with a multi-sensor sweep is
  trivial. read_motor returns sane 12-angle lists; roll/pitch level and
  clean (0.0 / −0.4°).

**Q2 stationary yaw — FAILED the <5°/30 s bar, with a clean diagnosis:**
- Stage 1: −266.6° drift over 30 s (−8.9°/s), and `noise_std` 78.8 ≈
  span/√12 (77.0) — the signature of a **pure linear ramp**.
- Follow-up 12 s probe (least-squares): slope **−9.892°/s, residual std
  0.029°** — pristine signal, one constant error term. Bias moved
  −8.9 → −9.9°/s across ~40 min powered (temperature).
- `read_imu()` decode (9-vector): `[ax, ay, az(=−9.83 ✔ gravity), gx, gy,
  gz, roll(rad), pitch(rad), yaw(rad)]` — imu-block yaw −1035.11 rad ×
  57.296 ≈ read_yaw's −59,307°. **Yaw = raw gyro-Z integrated
  continuously (unwrapped, no ±180 wrap at the register), no magnetometer
  fusion, no bias correction.** Stationary gz ≈ 0.18 rad/s ≈ 10°/s = the
  drift rate. Roll/pitch are accel-referenced, hence clean.
- Working hypothesis: firmware boot-time gyro-bias sampling either doesn't
  exist or was corrupted by handling the dog at power-on (V1 precedent:
  PiDog required ~10 s stillness after boot for bias cal).
  **Discriminating test: power-cycle untouched on the floor, 15 s hands
  off, rerun stage 1.** Stage 1 now logs `bias_slope_deg_per_s` +
  `resid_std_deg` directly.
- Fallback if firmware never calibrates: estimate bias during stationary
  windows and subtract. Perceive-act PERCEIVING phases are free
  stationary windows every cycle; FOLLOW consumes no yaw at all. Cheap
  either way. Firmware-side `turn_to`/`turn_by` (Q8) inherit whatever
  bias exists — interpret stage 6 only after the power-cycle result.

**Q2 RESOLVED (power-cycle experiment, 2026-08-28 ~23:57 + follow-up probes):**

- Rerun of stage 1 immediately after an untouched power cycle returned
  **1,764/1,764 reads of exactly 0.0** at 48.5 Hz
  (`docs/measurements/smoke_20260828_235710.jsonl`) — not a pass, and not
  a failure either: **the firmware serves 0.0 on the yaw register during
  a boot-time gyro-bias calibration window** (non-IMU registers healthy
  throughout; firmware detect fine). Minutes later the IMU was live with
  yaw at 38.8°.
- 15 s least-squares probe post-clean-boot: **slope +0.43°/s, residual
  std 1.81°** — vs −9.89°/s / 0.029° on the handled boot. The raw
  `read_imu()` gz register still shows ~10–14°/s: **firmware subtracts a
  boot-sampled bias before integrating; the raw register is unsubtracted
  and single-sample noisy (never use raw gyro for control — consume
  integrated yaw only).**
- **Verdict: boot-time calibration EXISTS; handling the dog during boot
  corrupts it** (session 1's −9.9°/s was a powered-on-in-hand boot).
  Residual 0.43°/s exceeds the literal V1 bar (12.9°/30 s) but passes
  functionally for V2's consumption: FOLLOW uses no yaw; perceive-act
  windows of 2–6 s see 0.9–2.6° error against ±45° decisions; each
  PERCEIVING re-snapshots the reference so nothing accumulates;
  `turn_to`'s ±4° tolerance absorbs ~1°. Optional refinement if traces
  ever demand it: per-cycle stationary bias estimate during PERCEIVING.
- **Operational rule (memory-worthy): power the dog on ON THE GROUND and
  hands-off until yaw goes nonzero (~30–60 s).** The all-zeros window is
  detectable, so "IMU ready" is a state predicate (first nonzero yaw,
  latched), NOT a timer — motor_controller must gate yaw-telemetry
  validity on it. Stage 1 of the smoke test now auto-waits on this
  predicate (90 s cap).

**Safety note from SDK source:** `calibration(state)` writes the servo
CALIBRATION register — source docstring says "use with caution!!!". It is
NOT an IMU fix and can corrupt servo zeros if invoked outside the
assembly-calibration procedure. Never call it casually. `set_yaw_init()`
only latches a client-side reference zero (does not touch drift rate).

### SMOKE TEST COMPLETE — full motion pass (2026-08-29 00:03, `docs/measurements/smoke_20260829_000317.jsonl`)

**The empirical gate is lifted. All eight questions answered on hardware:**

| Q | Answer |
|---|---|
| Q1 | `forward()` returns in **0.1 ms** (non-blocking) and runs **continuously until `stop()`** (8 s window, never self-stopped, operator confirmed). Velocity-setpoint model confirmed — the gait-buffer pathology has no substrate. |
| Q2 | Register is **unwrapped continuous degrees** (spun 385.6°, yaw 35.8 → 421.8, zero ±180 jumps). **Sign: turnleft = +yaw (CCW-positive).** Clean-boot stationary drift this run: **−0.009°/s, resid 0.051°** — fully green. |
| Q3 | **Concurrent reads work during motion** (battery read mid-walk, 3.2 ms). |
| Q4 | **No teardown protocol** — no close() method exists; drop the object, reopen, reads fine. Crashed controllers just restart. |
| Q5 | Standalone xgolib on vanilla trixie (established bench pass). |
| Q6 | Battery = int percent (established bench pass). |
| Q7 | **`attitude('p', 8)` mid-walk composes**: pitch read back 7.3°, gait smooth (operator "c"), non-blocking call. Requires `imu(0)`. |
| Q8 | **`turn_by` is NOT closed-loop.** Commanded 45° → measured **73.8°**; runtime = `mintime + θ·k` = 0.5 + 45×0.08 = **4.1 s, exactly matching** the observed blocking return. It's a dead-reckoned timed turn. `read_rotate_state` returns opaque ints (101/234/180/219 — not a usable turning flag). `turn_to` (has `emax` feedback param) untested. **Design call: don't use SDK convenience turns — close the loop ourselves** with `turnleft/turnright(°/s)` + 343 Hz `read_yaw`, which are individually verified (rate calibrated within 2%). |

**Also measured:** `turnleft(40)` → 39.2°/s actual (≈1:1 °/s calibration).
Stationary yaw register appears to hold near-frozen values (quantized/
deadbanded) when still — updates continuously during motion.

**Battery flag:** 99% → 79% across a ~3-minute intermittent-motion session.
Either real steep drain or load-sag-biased percent (likely some of both).
**No demo-duration promises until the V1-style sustained-load test** (hold
forward N minutes, log percent + behavior; remember charger-plug = power
cut, so no tethered testing).

### motor_controller.py v0 (written post-gate, same session)

~250 lines vs V1's 1,172. Consumes V1's command JSON unchanged (Mac side
runs as-is), maps to S2 setpoint calls, publishes telemetry at 10 Hz
(`action/yaw/roll/pitch/battery_pct/imu_ready/seq/fw` — no distance_cm,
no battery_v, **no buffer_depth**: Mac's v3 EXECUTING gate must move to
yaw/frame predicates in Phase 3 before EXPLORE runs). Key behaviors:
- **Refuses motion until imu_ready latches** (first nonzero yaw) — protects
  the boot gyro calibration from being corrupted by early commands.
- Watchdog: `V2_CMD_WATCHDOG_TICKS` loop ticks (count predicate) of Mac
  silence → stop().
- `head_pitch` → `attitude('p')` trim (Q7); head_yaw/head_mode ignored
  (no head servos); bark/one_shot/flush/step_count tolerated-ignored.
- `imu(0)` + `pace('normal')` at startup; no sudo (dialout group).
- New V2_* constants in config.py, all measurement-annotated.
- deploy.sh/run.sh un-dangled (V2 file list; venv python, no sudo).
- **Unrun** — first live run is FOLLOW bring-up with the user present.

### Pi state changes made this session

- `i2c-tools` installed (apt).
- `~/ironbark/` created: `test_dogzilla_smoke.py`, `logs/`, `.venv`
  (`--system-site-packages`, xgolib 1.1.9, pyserial 3.5).
- Nothing else touched; no motion commands issued; config.txt unmodified
  (the `uart0` line is the user's call).

## 2026-08-28 — FOLLOW bring-up (implementation session)

Work items W1–W5 from the coding handoff. Full account in
`docs/bringup-report.md`; only the newly *measured* facts are logged here.
No motion: `/dev/ttyAMA0` never opened, `motor_controller.py` never
launched. Camera only.

### Camera (measured, Pi → Mac over LAN, real scene)

- `/dev/video0` advertises **MJPG 640×480 @ 120 fps** (also 1280×720@60,
  1920×1080@30) and **YUYV 640×480 @ 30 fps**. MJPG is the right pick:
  it lifts the 640×480 cap from 30 to 120 and moves the USB cost onto the
  camera's encoder.
- `pi/cam_sender.py` at the 20 fps target: **20.0 fps sustained,
  7.74 Mbps, 48.3 kB/frame at q75**, inter-frame gap mean 50.0 ms /
  max 67.5 ms.
- **One-way latency mean 10.9 ms, median 10.4, p95 14.5, max 28.8.**
- Uncapped headroom: **46.5 fps** — read 18.8 ms, encode 2.2 ms, send
  0.07 ms. ~2.3× the target, so the Pi is not CPU-bound and the
  JPEG-pass-through optimisation is not worth its dependency.
- As-shipped auto-exposure exposes correctly at 120 fps with gain 0
  (frame mean 114/255). A probe across gain / manual-exposure / YUYV
  combinations overexposed in every case, so **no camera control is
  touched**. (An early all-black capture was the lens cap, not the
  120 fps mode starving exposure — hypothesis raised and refuted.)
- On connect, up to `SNDHWM` (5) queued frames flush at once and can be
  seconds old (3.87 s observed). The Mac's existing `get_latest_frame()`
  drain discards them.

### Clock skew — NEW, and it bites any future frame-age check

**The Pi's clock runs +484.4 ± 8 ms ahead of the Mac's**, stable to
~150 µs across 15 NTP-style samples, despite both hosts reporting
`System clock synchronized: yes`. Uncorrected, `mac_recv − pi_frame_ts`
reads **≈ −474 ms** — frames appear to arrive before capture. Nothing
running depends on it (the Mac only compares its own receive times), but
every latency figure above is clock-corrected, and any future staleness
check that trusts a Pi timestamp will be wrong by half a second.

### Network — `.env` does not work as shipped

`PC_IP`/`PI_IP` in `.env` are **Tailscale** addresses (<MAC_TAILSCALE_IP> /
<PI_TAILSCALE_IP>) and Tailscale is still not on the Pi. Measured from the
Pi: `<MAC_TAILSCALE_IP> unreachable`, `<MAC_LAN_IP> REACHABLE`. So the Pi
cannot reach the Mac and the Mac cannot reach the Pi with the current
file. LAN addresses are Mac `<MAC_LAN_IP>`, Pi `<PI_LAN_IP>`;
everything measured this session used them explicitly. Briefing §6.4's
Tailscale-or-LAN decision is now blocking, not optional.

### MS200 protocol — settled from vendor source, not inferred

Frame layout and checksum taken from Oradar's own SDK
(`ordlidar_protocol.h` → `OradarLidarFrame`; `ord_lidar_driver.cpp` →
CRC table + angle interpolation), shipped with the MS200 ROS driver:

- **47-byte packed frame**, little-endian: `0x54` header, `0x2C` ver_len
  (version 1 | 12 points), `uint16` speed in deg/s (rev/s = /360),
  `uint16` start angle in hundredths of a degree, 12 × `{uint16
  distance_mm, uint8 confidence}`, `uint16` end angle, `uint16` device
  timestamp, `uint8` CRC8 over the leading 46 bytes.
- **CRC8 is poly 0x4D, init 0x00, non-reflected, no final XOR** — the
  vendor's 256-entry literal reproduces exactly.
- Angle interpolation: `diff = (end + 36000 − start) % 36000`,
  `step = diff / 11 / 100`, fold at 360.
- **230400 8N1.** The MS200 free-runs on power; the vendor sample only
  opens the port and reads, so a reader need write nothing to the device.
- Still unknown: **which UART it is on.** Only `ttyAMA0` (motion MCU) and
  `ttyAMA10` (debug connector) exist on this Pi. Yahboom's factory image
  exposes it as `ttyAMA1`. `config.V2_LIDAR_PORT` defaults to `ttyAMA2`,
  MEASURE-marked, pending the cable trace.

### Mac-side behaviour verified without hardware

- Target latch: acquires on exactly the 3rd argmax frame, holds 15
  missing frames and releases on the 16th, re-acquires — confirmed both
  synthetically and through real YOLO11s + ByteTrack.
- Full FOLLOW cycle IDLE → FOLLOW → SEARCH → IDLE at 10 Hz
  (`docs/measurements/dryrun_follow_20260828_172654.txt`).
- MS200 parser 41/41, and a replayed scan drives the **unchanged**
  `pc/lidar_map.py` to the right geometry (forward 199 cm of a 200 cm
  wall, left 118/120, right 149/150, rear 239/240).
- Deadman 18/18 against recorded wire traffic on both command paths.

### Two defects found by the dry runs (both fixed)

1. **Boot-time SEARCH would have spun the dog on startup.**
   `last_target_seen` starts at `time.time()`, so a fresh follower fell
   into SEARCH for its first 5 s. Harmless in V1 (head sweep); in V2
   SEARCH is a *body spin*, so the dog would have turned in place before
   ever seeing a person. SEARCH entry is now gated to FOLLOW/SEARCH.
2. **`remote_control.py` could not reach the V2 controller at all** — it
   published to `PI_IP:5557` while `motor_controller` subscribes to
   `PC_IP:5556`, i.e. wrong direction, wrong port. Teleop, the *first*
   dog session, would have done nothing. Mac now binds PUB on `CMD_PORT`;
   teleop and the follower therefore cannot run simultaneously.

### Still unverified

The live-webcam acceptance run for the target latch. macOS denies camera
access to this session's host process and the grant is a Privacy &
Security setting. Everything else about that path is verified through
composited frames with real YOLO and real ByteTrack.
