# IronBark V2 — Phase 1 Briefing

Oracle session, 2026-08-28. Everything below is grounded in: V1's complete
memory directory (read in full), the ten SDK course PDFs, live SSH recon of
the Pi, and the V2 repo at Phase 0. Assumptions are flagged as such.

## 1. State of the world

**Repo**: Phase 0 baseline intact (`pc/` carried from v3-checkpoint,
reference PDFs in place). This session adds `pi/test_dogzilla_smoke.py`
(written, compiles, **unrun** — needs the dog), this briefing, and
`docs/migration-notes.md` (measured facts log).

**Pi** (`ssh pi`, alias works): Pi 5 / Debian trixie / Python 3.13. No USB
peripherals, no cameras, no SDK installed. I2C bus 1 has exactly one device,
at 0x3C — the classic SSD1306 OLED address, i.e. the Pi looks already mated
to the DogZilla's carrier board, with the motion link presumably the UART at
`/dev/serial0 → /dev/ttyAMA10` (XGO-lineage protocol; invisible to lsusb).
Flagged as inference until smoke-test stage 0 opens the port.

**Comms**: Tailscale is not on the Pi. LAN-only for now (<PI_LAN_IP>);
fine for bench work. Install-or-not is your call, later. `deploy.sh` is
dangling (ships 9 V1 files that don't exist) — it gets rewritten with the
new controller, after the smoke test.

## 2. The command model changed under us — in our favor

The course PDFs show the S2 is a **velocity-setpoint machine**, not PiDog's
queued-gait-frame machine (details in migration-notes.md):

- `forward/back/left/right/turnleft/turnright(step)` set a gait setpoint
  that runs **until `stop()`** (lesson samples bind them to buttons with an
  explicit Stop; sliders re-issue `move()`/`turn()` on change).
- `turn(step)` is documented as **°/s** (±100), and `read_yaw()` exists —
  so "rotate N degrees" becomes closed-loop and *measured*, not calibrated
  open-loop like V1.
- `pace()` sets step frequency; `imu(1)` is STM32-side self-stabilization
  (mutually exclusive with manual `attitude()` — relevant to camera-aim
  trim while walking).
- `unload_allmotor()` is a native torque-release path — the exact thing
  whose absence killed V1's servos.

Offline introspection of the installed SDK (xgolib 1.1.9 on the Pi, all 27
documented methods present) revealed a third layer the course PDFs never
mention: **closed-loop primitives** — `turn_to(theta, vyaw, emax=4)`,
`turn_by(theta, mintime, k=0.08)` (a P-controller on yaw), displacement
moves `move_x_by/move_y_by(distance, v, k, mintime)`, timed
`turn(step, runtime=…)`, `read_rotate_state()`, `set_yaw_init()`, and
blocking variants (`move_to(..., wait=True)`, `action(id, wait=…)`). If the
S2's 2023-era firmware implements these (smoke-test Q8), EXECUTING for a
turn collapses to **one self-terminating SDK call landing within ±4°** — no
Mac-side completion gate at all. FOLLOW's 10 Hz loop uses the velocity
layer; EXPLORE's perceive-act uses the bounded/closed-loop layer. Clean
split, both native.

Consequences if stage 2 confirms (the buffer-saturation pathology has no
substrate at this API): buffer-depth accounting, `one_shot`, `flush=True`,
leap-prone interpolation, gait segments, and dedup-as-buffer-protection all
die unported. The perceive-act EXECUTING gate changes shape: not "wait for
buffer drain" but "command setpoint → watch yaw-delta/frame-count → stop()".
The new `motor_controller.py` should be a thin setpoint translator — if it
isn't dramatically smaller than 1,172 lines, something is being ported that
shouldn't be.

## 3. The sensor-rig fork (decision needed)

Research pass completed against Yahboom's official docs/GitHub, the shipped
ROS2 workspace mirror, and Luwu's xgolib source (citations in the research
brief within this section's sources; the load-bearing facts):

**What the S2 actually ships** (S2 = S1 + lidar + voice module):

- **Camera: 2MP USB wide-angle** at `/dev/video0` — Yahboom's own code opens
  it with plain `cv.VideoCapture(0)`. Not CSI, no depth. Exact module/FOV
  unpublished.
- **Lidar: Oradar (Orbbec) MS200** — 360°, 4,500 samples/s, 0.03–12 m,
  native **UART @ 230400** (Yahboom wires it to a second Pi UART,
  `ttyAMA1` on their image). Yahboom drives it via a ROS2 package, but the
  MS200 serial protocol is publicly documented (Orbbec manual) and non-ROS
  Python drivers exist to adapt — a standalone reader is a bounded task.
- **Voice module: CSK4002-based**, USB serial, trivial ASCII protocol
  (`$B004#`-style command IDs). Out of mission scope; note it exists for a
  future wake-word/bark phase.
- **Body: 246×145×195 mm, ~972 g, 7.4 V 2,500 mAh** (S2 current gen;
  battery figures vary by generation — 2500/3800/5000 mAh all appear;
  treat runtime as unmeasured until our own sustained-load test). Two
  operational facts that change test protocol vs V1: **plugging the charger
  hard-cuts robot power** (no run-while-charging diagnostics), and **≤9%
  battery → dog lies down and locks out**.

**The fork, quantified:**

**(a) Port the V1 rig** (OAK-D Lite + RPLidar C1): ~200 g of head-high
payload on a **972 g** dog — over 20% of body mass, plus two USB power
draws. That is the exact failure class that defined V1's endgame (tip-overs,
servo thermal death, undervoltage freezes). And the stereo depth we would be
carrying it for is V1's *least*-trusted sensor: memory records it biased
low, 40% invalid, overruled by LiDAR at every clearance decision. No mount
exists on the S2 — it's a fabrication project. **Not recommended.**

**(b) Use the S2 built-ins — RECOMMENDED:**
- The MS200 is spec-equivalent to the RPLidar C1 for our use (C1: ~5,000
  samples/s, 12 m). Deliverable: `pi/ms200_reader.py` emitting the same
  ZMQ scan schema as V1's `lidar_reader.py` → **`lidar_map`, costmap,
  cornered/imminent, and all clearance logic carry over unchanged**. V1's
  most-trusted layer survives intact.
- Camera sender becomes a trivial USB-cam JPEG publisher (V1's
  `pi_sender.py` pattern). The small camera is *why* identity was deferred
  — this choice and the mission simplification are the same decision.
- What we lose: stereo depth. Per V1's own memory, the depth-veto it fed
  was firing wrongly anyway, and FOLLOW arrival already keys on bbox-area
  ratio, not depth. The forward nose-cone veto reassigns to the MS200's
  forward arc. Known residual gap: obstacles below the lidar plane
  (~18 cm) are invisible — but the V1 rig had the same class of gap.
- Zero added payload: the thermal/stability envelope we measure is the
  dog's own.

**(c) Hybrid** (built-in camera + strap the RPLidar C1 back on): fallback
only, if MS200 bring-up fails hard. The C1 and OAK-D go in a drawer, not
in the trash — identity's future phase may want a better camera anyway.

**Two verification gates before (b) is committed in code** (both cheap,
both in the first hardware session): (1) MS200 bring-up on vanilla trixie —
enable its UART, read one full revolution with a standalone reader;
(2) USB-cam → Mac stream → YOLO detection sanity at 3–6 m.

**Folded-in stack decision (recommend deciding together):** stay on the
Pi's current **vanilla Debian trixie + standalone Python SDK + our ZMQ**
rather than flashing Yahboom's factory image (ROS2-Humble-in-Docker, their
systemd services — including an OLED service that polls battery over the
motion serial port every 3 s, a documented contention source). Our
architecture is ZMQ-native and needs none of their stack. Cost of vanilla:
we enable the UARTs ourselves — **`dtparam=uart0=on`** in
`/boot/firmware/config.txt` + reboot creates `/dev/ttyAMA0` for the motion
MCU (currently absent; only the debug UART exists), and the lidar UART
overlay gets identified at bring-up. One command, yours to run:

    ssh pi "echo 'dtparam=uart0=on' | sudo tee -a /boot/firmware/config.txt && sudo reboot"

## 4. Smoke-test plan (the gate on all motor code)

`pi/test_dogzilla_smoke.py` — six stages, seven questions, JSONL trace,
stdlib-only, SDK-agnostic import (tries `DOGZILLA`, falls back to `xgolib`).
Motion stages are operator-gated (Enter to proceed, `s` to skip); Ctrl-C
always sends `stop()`.

| Stage | Motion | Answers |
|---|---|---|
| 0 probe | none | Q5 (standalone import), Q6 (battery value/type + voltage-method hunt), read-call latencies (bounds telemetry rate) |
| 1 yaw-static | none | Q2a: update rate, 30s drift (V1 pass bar <5°), noise, zero-sentinel frequency |
| 2 blocking | walk ≤8s | Q1 (return latency + self-stop watch + operator verdict), Q3 (watchdog-guarded first in-motion read) |
| 3 yaw-turn | spin ~380° | Q2b: ±180 wrap shape, measured °/s vs commanded step |
| 4 compose | walk + pitch | Q7 (attitude mid-gait; forces `imu(0)` first per course 05) |
| 5 teardown | reset only | Q4 (close → reopen → re-read) |

Stage 6 (added after SDK introspection) probes Q8: does `turn_by(45°)`
block-until-converged and land within its ±4° tolerance on this firmware?

**Already staged on the Pi this session**: `~/ironbark/` exists with the
script, a `logs/` dir, and a `--system-site-packages` venv with xgolib
1.1.9 + pyserial installed. The one remaining prerequisite is yours: the
`uart0` config.txt line + reboot from §3. Then, from the Mac (interactive
`-t` because the script prompts):

    ssh -t pi 'cd ~/ironbark && .venv/bin/python -u test_dogzilla_smoke.py --no-motion'
    ssh -t pi 'cd ~/ironbark && .venv/bin/python -u test_dogzilla_smoke.py'

Each run writes `smoke_<ts>.jsonl` next to the script; pull it back with
`scp pi:~/ironbark/smoke_*.jsonl logs/` and we read it together.

## 5. FOLLOW target-lock design sketch (Phase 2, after smoke test)

Replaces the identity stack with ByteTrack ID latching. This is V1's
"owner holdover" machinery minus the recognition gate — the code shape
already exists in `perception_pipeline.py:451-488`.

**Pipeline** (`perception_pipeline.py`, shrinks by roughly the 450 dormant
identity lines): keep YOLO11s + ByteTrack; delete FaceRecognizer,
ReIDRecognizer, `_fuse_scores`, `_smooth_face_matches`, galleries,
`enroll_owner.py` (unported). The per-detection list structure stays —
identity slots back in later as an additional scorer, per the handoff's
re-addition requirement.

**Acquisition** (entering FOLLOW, no latched target): score every person

    score = area_norm × (1 − CENTER_WEIGHT × |cx − W/2| / (W/2))

with `CENTER_WEIGHT ≈ 0.3`, and latch the argmax's ByteTrack ID once that
same track has been the argmax for `TARGET_ACQUIRE_FRAMES = 3` consecutive
frames. Why area-primary rather than most-centered: bbox area is a proximity
proxy — the person who walked up to the dog is the person to follow, which
is the natural "any human" interaction. Most-centered is an artifact of
wherever the dog happened to be aimed at FOLLOW entry (post-SEARCH sweep =
arbitrary). The centering term only breaks ties toward whom the dog already
faces; the 3-frame persistence filters a passerby crossing the frame edge.
Single scalar, loggable per-frame under a `DEBUG_TARGET_SCORES` flag
(V1 `DEBUG_FUSION_SCORES` pattern).

**Hold** (in FOLLOW): the detection matching the latched ID is the target.
ID absent → holdover counter, `TARGET_HOLDOVER_FRAMES = 15` (carried from
V1's `_owner_holdover`, ByteTrack re-association usually recovers within
it). Expiry → release latch → existing SEARCH → EXPLORE ladder unchanged.
The 2-second FOLLOW dropout-coast in `follower.py:434` survives — it smooths
detector dropouts, orthogonal to identity.

**Dies with identity**: identity bark, `_investigating`, unconfirmed-person
counters, the Priority-1/2 recognition ladder in `_find_owner` (becomes
`_find_target`, ~15 lines). Arrival bark is identity-free (greeting on
arrival) — kept off by default, your call whether it stays at all.

## 6. Flags for your decision (ranked)

1. **Sensor rig** — §3. Gates the perception input side, depth-veto layer,
   costmap source, and the Pi requirements file.
2. **SITUATION VLM: recommend deferring.** Behavior modes existed to
   modulate courtship of a *known owner* (GENTLE near sitting owner, etc.).
   With any-human following, mode discrimination has nothing to key off;
   llava's 5.5GB RAM + 9s pre-warm buys nothing. Run `BEHAVIOR_DEFAULT_MODE
   = "ACTIVE"` as the single mode; the `_consume_situation` plumbing stays
   in place dormant, so re-enabling later is a config flip. (V1 memory
   confirms SITUATION worked as image classification — this is a
   value-for-cost deferral, not a capability retreat.)
3. **Strategic prompt "Motion (your hardware)" block must be rewritten**
   before first V2 EXPLORE run — it currently teaches Haiku that turns are
   arc turns (PiDog fact, now false: S2 spins in place, and strafes exist as
   a new vocabulary candidate). Per curl-test discipline: A/B against
   `vlm_sample_20260425_151829.jpg` scenarios from V1 before deploying.
4. **Tailscale on the Pi or LAN-only** — one command either way, your call.
5. **`requirements-pi.txt` is V1's** (pidog/robot_hat/depthai/numpy<2 pins,
   Python 3.11 assumptions). Rewrite lands with the rig decision; trixie's
   Python 3.13 + system numpy 2.2.4 change the pin story (venv with
   `--system-site-packages` recommended).

## 7. Sequencing from here

1. You: sensor-rig call (§3) + confirm smoke-test session timing.
2. SDK install on the Pi (per §3 research), bench pass (`--no-motion`),
   then the motion stages with you present.
3. Smoke-test results → migration-notes + memory; THEN `motor_controller.py`
   skeleton (ZMQ + JSON schema carried, everything else fresh).
4. Perception simplification (§5) can proceed in parallel on the Mac — it
   has no hardware dependency (webcam or logged frames for bring-up).
