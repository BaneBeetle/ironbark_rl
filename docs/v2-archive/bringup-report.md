# IronBark V2 — FOLLOW Bring-Up Report

Implementation session, 2026-08-28. Work items W1–W5 from
`docs/coding-handoff-follow-bringup.md`, built on
`claude/ironbark-v2-oracle-handoff-e29f1a`. No motion command was ever
issued: `/dev/ttyAMA0` was never opened, `motor_controller.py` was never
launched, `run.sh` was never run. The only hardware touched was the USB
camera.

Every claim below is backed by a run recorded under `docs/measurements/`.

---

## 1. What shipped, per work item

### W1 — Target-lock perception ✅

`pc/perception_pipeline.py` rewritten (559 → 479 lines; it absorbs the
latch machinery, so the net shrink understates the removal — 748 lines
went outright with the three deleted files). Deleted:
`pc/perception/face_recognizer.py`, `pc/perception/reid_recognizer.py`,
`pc/enroll_owner.py`, and inside the pipeline `OwnerMatch`, `_fuse_scores`,
`_smooth_face_matches`, `_face_tracks`, gallery loading and the whole
face/owner match plumbing. YOLO11s + ByteTrack are untouched, and the
per-detection list survives verbatim so identity can return later as one
more scorer over it rather than as a parallel pipeline.

The latch is exactly §5's contract:

```
score = area_norm × (1 − TARGET_CENTER_WEIGHT × |cx − W/2| / (W/2))
```

`TARGET_CENTER_WEIGHT = 0.3`, `TARGET_ACQUIRE_FRAMES = 3`,
`TARGET_HOLDOVER_FRAMES = 15`, all in `config.py`. `PerceptionResult`
gains `target` and `target_track_id`. `DEBUG_TARGET_SCORES` prints
per-detection scores plus latch state, in the shape of V1's
`DEBUG_FUSION_SCORES`.

SITUATION VLM is deferred, not deleted: `VLM_SITUATION_ENABLED = False`
builds no reasoner, starts no worker, queues no query, and skips the
runner's Ollama health-check and pre-warm — so Ollama is genuinely not a
runtime dependency while it is off. Mode stays pinned to
`BEHAVIOR_DEFAULT_MODE = "ACTIVE"`, and `_consume_situation` sits dormant
on both sides, so re-enabling is one flag.

Dev mode: `python pc/follower.py --local-cam [INDEX]` swaps the Pi video
stream for the Mac's own camera. Frames are resized to
`CAMERA_RESOLUTION` so pixel thresholds keep their meaning. Nothing else
changes — a PUB with no subscriber is harmless, so a dry run emits real
commands into the void and the HUD shows exactly what the Pi would have
been told.

### W2 — `pi/cam_sender.py` ✅ (measured on the dog)

640×480 JPEG q75 from `/dev/video0`, V1's wire format byte-for-byte, so
`pc_receiver`, `follower_viz.decode_frame` and `bbox_calibrate` consume it
with no edit. MJPG is requested explicitly — at 640×480 it lifts the
sensor cap from YUYV's 30 fps to 120 and moves the USB cost onto the
camera's encoder. `BUFFERSIZE=1` so the driver cannot hand back a backlog
of stale frames. Reopen-with-backoff on camera faults. Added to
`deploy.sh`.

### W3 — `pi/ms200_reader.py` ✅ (parser verified; live pass is yours)

Publishes V1's scan schema byte-for-byte on the same port, so
`pc/lidar_map.py`, the costmap and every clearance decision carry over
unedited. Three modes as specified: `--dump` (record raw bytes, parse
nothing), `--replay`, and live.

The protocol comes from Oradar's own SDK source — `ordlidar_protocol.h`'s
`OradarLidarFrame` plus `ord_lidar_driver.cpp`'s CRC table and angle
interpolation — not from inference or captures. 47-byte packed frame,
`0x54 0x2C` header, 12 points of `{uint16 mm, uint8 confidence}`, angles
in hundredths of a degree, CRC8 over the leading 46 bytes. The vendor's
256-entry table is exactly poly `0x4D` / init `0x00` / non-reflected, so
it is generated and spot-checked against seven vendor entries at import —
a wrong polynomial cannot ship quietly.

`pi/test_ms200_parser.py`: 41 checks, stdlib only, no hardware.

### W4 — Follower adaptations ✅

`_find_owner` → `_find_target`, which returns the pipeline's latched
target and nothing else. Gone: the recognition ladder, `_investigating`,
the unconfirmed-person counters, the identity bark.
`last_owner_seen` → `last_target_seen`. The 2 s dropout coast survives —
it is orthogonal to the 15-frame holdover (that keeps the ByteTrack ID
alive so the *same* person is re-acquired; the coast keeps the legs moving
while it does).

SEARCH v0 is a slow in-place spin toward the side the target was last seen
on. `EXPLORE_ENABLED = False`; SEARCH expiry lands in IDLE.
`USE_DEPTH_FORWARD_CLEARANCE`, `USE_OAKD_DEPTH` and `USE_OAKD` are all
False. Telemetry consumers moved to the V2 payload. Arrival bark kept but
default-disabled (`V2_ARRIVAL_BARK_ENABLED = False`).

### W5 — Deadman ✅

Both paths start DISARMED and, while disarmed, emit an explicit `stop`
every tick rather than going silent — that halts the dog now instead of
after the Pi's ~1.5 s watchdog, and leaves the watchdog as the backstop
for the case where emission genuinely does stop (this process dying, the
link dropping). All three invariants hold on both paths.

---

## 2. Measured numbers

### Camera stream, Pi → Mac over the LAN (20 s, real scene)

| | |
|---|---|
| Sustained rate | **20.0 fps** (target 20; Pi-side counter agreed) |
| Bitrate | **7.74 Mbps**, 48.3 kB/frame at q75 |
| Inter-frame gap | mean 50.0 ms, median 50.1, max 67.5 |
| One-way latency | **mean 10.9 ms, median 10.4, p95 14.5, max 28.8** |
| Headroom (uncapped) | **46.5 fps** — read 18.8 ms, encode 2.2 ms, send 0.07 ms |

~2.3× headroom over target, so the Pi is not CPU-bound and the
JPEG-pass-through optimisation is not worth its dependency.

**The latency figure is clock-corrected and you should know by how much.**
The Pi's clock runs **+484.4 ± 8 ms ahead of the Mac's**, stable to ~150 µs
across 15 NTP-style samples, even though both hosts report
`System clock synchronized: yes`. Uncorrected, the wire arithmetic reads
about **−474 ms**, i.e. frames appear to arrive before they were captured.
Nothing in the running system depends on this — the Mac only ever compares
its own receive times — but any future "frame age" check that trusts the
Pi's timestamp will be wrong by half a second. Worth fixing at the source
when convenient.

On connect, up to `SNDHWM` (5) queued frames flush at once and can be
seconds old — one arrived 3.87 s stale in the first bench. The Mac's
existing `get_latest_frame()` drain discards them, so this is a note, not
a defect.

### MS200 parser (no lidar hardware)

`pi/test_ms200_parser.py`: **41/41 pass**. `--replay` over a synthetic
5-revolution dump with 9 bytes of injected line noise and one torn frame:
**150 frames parsed, 1 CRC rejection, 29 bytes discarded, 4 clean
revolutions**, no phantom scan from the trailing partial one.

End-to-end into the **unchanged** `pc/lidar_map.py` — the actual point of
W3, so it was tested against the real consumer rather than asserted:

| arc | simulated | measured |
|---|---|---|
| forward (±30°) | 200 cm | 199.0 |
| left | 120 cm | 118.2 |
| right | 150 cm | 148.9 |
| rear | 240 cm | 239.4 |

Costmap builds; `find_best_direction` and `get_direction_to_go` run. (Rear
is 240, not the 3 m rear wall: `get_rear_distance` is a *minimum* over
150–210°, and the 210° edge grazes the 1.2 m left wall at 1200/sin30.)

### FOLLOW dry run (Mac only, no Pi)

`docs/measurements/dryrun_follow_20260828_172654.txt`. Real YOLO11s + real
ByteTrack + the real FSM at 10 Hz, driven by two real person cut-outs
composited onto scripted frames.

- Frames 1–2: IDLE while acquiring; latch at **frame 3**, on the *nearer,
  off-centre* person (score 0.1417) over the *centred, far* one (0.0436) —
  area-primary behaving as designed. IDLE → FOLLOW.
- The clearance-dark warning fires once.
- Frames 9–18: 10-frame occlusion held (`HOLD`), commands coast.
- Frame 19: same ByteTrack ID recovered.
- Right→left walk: `turn_right` → `forward` (off_x +54) → `turn_left`.
- Frame 64: released on the **16th** missing frame.
- Frame 67: FOLLOW → SEARCH, spinning **left** — the side it was lost on.
- Frame 95: SEARCH → IDLE (EXPLORE gated off).

### Deadman

`docs/measurements/deadman_20260828_175134.txt`: **18/18 pass**, asserted
against recorded wire traffic on both paths.

---

## 3. Two bugs the dry runs caught

**Boot-time SEARCH would have spun the dog on startup.** `last_target_seen`
is initialised to `time.time()`, so a freshly launched follower fell
straight into the SEARCH branch for its first 5 seconds. V1 could afford
that because SEARCH was a head sweep; V2's SEARCH is a *body spin*, so the
dog would have turned in place the moment the controller came up, before
it had ever seen a person. SEARCH entry is now gated to FOLLOW/SEARCH —
it means "I lost someone I was following", never "I have not seen anyone
yet".

**The clearance-dark warning was reachable but not guaranteed.** Written
first inside `_effective_forward_cm`, it never fired in the dry run: on a
LiDAR-less FOLLOW the depth veto only calls that function when the
*pre-hysteresis* action is already `forward`, and the cornered/imminent
block is gated on `has_lidar`. A safety-degradation notice that depends on
which branch happened to run is not a notice, so it is now raised from
FOLLOW entry.

---

## 4. Things you need to fix before a dog session

### `.env` holds Tailscale IPs and the Pi is not on Tailscale — **blocking**

`PC_IP=<MAC_TAILSCALE_IP>` and `PI_IP=<PI_TAILSCALE_IP>` are Tailscale addresses.
Tailscale is not installed on the Pi (migration-notes says so, and the Pi
confirms it: `<MAC_TAILSCALE_IP> unreachable`, `<MAC_LAN_IP> REACHABLE`). As
it stands the Pi cannot reach the Mac and the Mac cannot reach the Pi;
the handoff's note that `.env` has "working LAN IPs" is not the case.

Two ways out, per briefing §6.4 — your call:

```bash
printf 'PC_IP=<MAC_LAN_IP>\nPI_IP=<PI_LAN_IP>\n' && echo "edit .env to these"
```

or install Tailscale on the Pi and keep the portable addresses. Everything
measured in this report used the LAN addresses explicitly.

### `deploy.sh` ships `.env` — including `ANTHROPIC_API_KEY`

Inherited V1 behaviour, left alone as out of scope. The Pi has no `.env`
today and never calls Anthropic; the key only needs to exist on the Mac.
Worth trimming what gets copied, or splitting the key into a Mac-only
file.

### Teleop and the follower share `CMD_PORT`

V2's `motor_controller` has one command socket, so `remote_control.py` and
`follower.py` both bind `PC_IP:5556` and cannot run at the same time. Not
a defect, but it will look like one the first time you try.

---

## 5. Every `# MEASURE:` placeholder still open

| Constant | Value | How it gets measured |
|---|---|---|
| `V2_LIDAR_PORT` | `/dev/ttyAMA2` | Trace the MS200's cable, add the matching overlay to `/boot/firmware/config.txt`, reboot, then confirm with `--dump`. Only `ttyAMA0` (motion MCU) and `ttyAMA10` (debug connector) exist today. Yahboom's factory image exposes it as `ttyAMA1`, so `ttyAMA1`/`ttyAMA2` are the leading candidates. |
| `V2_TURN_BANDS` | 220/160/100/60 px at area 0.08/0.15/0.30 | `pc/bbox_calibrate.py` against the dog's own camera; walk 1–4 m and read `area_ratio` + `off_x` per band. OAK-D-derived, unverified on the wide-angle lens. |
| `V2_ARRIVAL_AREA_RATIO` | 0.55 | Same tool: the ratio observed at your intended stopping distance. This is now the **only** arrival signal — there is no depth sensor. |
| `V2_ARRIVAL_RECENTER_PX` | 80 | Same tool: the offset you are willing to tolerate before the arrival re-centre turn fires. |
| `V2_TURN_RATE_DPS` | 40 (measured 39.2°/s) | Calibrated on hardware; flagged here only because SEARCH v0 now depends on it — see the tuning item below. |

Also unverified but not `MEASURE`-marked, because they are dormant rather
than wrong: the per-mode `arrival_ratio` / `arrival_cm` values in
`BEHAVIOR_MODES` are OAK-D numbers and will need re-deriving if
`VLM_SITUATION_ENABLED` is ever flipped back on.

---

## 6. Deviations from the spec, with reasons

**W2 transport is PUSH, not PUB.** The item said "ZMQ PUB on port 50505"
but also said to match the wire format the pc-side receiver already
expects and not to invent a new one. The receiver has always been a PULL
bind, and a PUB would never have connected to it. Matching the receiver
won; the sender PUSHes and connects out.

**The follower's arming is a toggle, not hold-to-arm.** In a FOLLOW
session the operator *is* the person being followed and cannot keep a key
down. The spec anticipated this and named the compensations, which are all
present: starts disarmed, a full-width HUD banner, and any key other than
`a` is an instant panic stop. Teleop, where the operator is at the
keyboard by definition, gets the closer approximation — tap `F` to arm,
any recognised key refreshes the arm, letting go lapses it after 1.0 s.
True key-held is not implementable in curses: it delivers key-down only,
with no keyup event and no way to hold two keys at once.

**Arrival no longer commands `BARK_HEAD_PITCH`.** It asked for 35°, which
`motor_controller` clamps to the S2's ±15° attitude limit, so arrival
would have tipped the body back 15° for a greeting that is disabled. The
S2 has no head servos; `attitude('p')` is a camera-aim trim, not a
look-up-and-greet gesture. Arrival now uses the default pitch.

**Beyond the five items**, three things were fixed because the work items
could not be honestly completed around them, each in its own commit:
`remote_control.py`'s transport (it published the wrong direction to a
port V2 never listens on — teleop, the *first* dog session, did nothing at
all); `bbox_calibrate.py` (it read `result.face_matches` and two
`ARRIVAL_*` constants V2's config no longer defines, and it is the tool
that measures W4's placeholders); and `requirements-pi.txt` (V1's, pinning
depthai/rplidarc1/pidog against Python 3.11).

`pi/motor_controller.py` was **not modified**. No telemetry field was
added — nothing needed one.

---

## 7. What is NOT verified, and what would verify it

**The live webcam acceptance run for W1 did not happen.** macOS denies
camera access to this session's host process
(`OpenCV: not authorized to capture video`), and granting it is a
Privacy & Security setting I cannot change. The `--local-cam` path is
written and the pipeline, FSM and HUD are verified end-to-end with real
YOLO and real ByteTrack through the composited-frame harness — but nobody
has yet pointed the Mac's own camera at two actual people.

To close it: **System Settings → Privacy & Security → Camera → enable
Claude**, then

```bash
python pc/follower.py --local-cam
```

Stand with a second person in frame, one nearer than the other. Expect:
the latch acquires the nearer person after 3 frames, the HUD shows
`Target #N LOCKED`, it survives a brief walk-behind, and it releases after
sustained absence. Set `DEBUG_TARGET_SCORES = True` in `config.py` to see
the scores driving it.

**Nothing has moved.** Every motion path in this report is verified only
as far as the JSON on the wire. The dog has not executed a single command
from this code.

---

## 8. Commands for your next sessions, in order

### Session 0 — bench, no motion (~10 min)

Fix `.env` first (§4), then:

```bash
./deploy.sh
```

Camera end-to-end, nothing that moves:

```bash
ssh pi 'cd ~/ironbark && .venv/bin/python -u cam_sender.py'
```

and on the Mac, in another terminal:

```bash
python pc/pc_receiver.py
```

You should see the dog's-eye view at ~20 fps. `q` quits.

### Session 1 — teleop, dog on the floor, YOU present

Power the dog on **on the ground, hands off**, and wait for the IMU banner
to clear — the firmware is sampling its gyro bias and `motor_controller`
refuses every motion command until it does. Handling the dog through that
window is what produced the −9.9°/s drift in the first smoke session.

```bash
./run.sh
```

Then, in another terminal:

```bash
python pc/remote_control.py
```

The TUI opens **DISARMED**. Tap `F` to arm. `W`/`S` forward/back,
`A`/`D` turn, `Q`/`E` strafe, `SPACE` panic-stop, `ESC` quit. Let go of
the keyboard for a second and it disarms itself.

First thing to check: that the dog stops when you take your hands off.
Then that `A`/`D` spin at a rate you would be happy having sweep past you
during SEARCH — if `V2_TURN_RATE_DPS = 40` feels too fast to scan with,
that is the tuning item, not a mechanism to add.

### Session 2 — lidar bring-up, no motion

Trace the MS200's cable to a Pi UART, add the overlay, reboot. Then
**capture before trusting anything**:

```bash
ssh pi 'cd ~/ironbark && .venv/bin/python -u ms200_reader.py --port /dev/ttyAMAn --dump /tmp/ms200_raw.bin --dump-bytes 200000'
```

Pull it back and parse it offline, where a bad guess costs nothing:

```bash
scp pi:/tmp/ms200_raw.bin logs/ && python pi/ms200_reader.py --replay logs/ms200_raw.bin --no-publish --verbose
```

What good output looks like: `crc_fail` near zero, `frames_ok` in the
thousands, scans of roughly 200–450 points spanning ~0–359°, and ~10 rev/s.
A high `crc_fail` with a low `frames_ok` means the wrong port or the wrong
baud. Then set `V2_LIDAR_PORT` in `config.py` and run it live.

### Session 3 — supervised FOLLOW, YOU present

Only after sessions 1 and 2. Three terminals:

```bash
./run.sh
```

```bash
ssh pi 'cd ~/ironbark && .venv/bin/python -u cam_sender.py'
```

```bash
python pc/follower.py 2>&1 | tee logs/follow_$(date +%Y%m%d_%H%M%S).log
```

The HUD opens **DISARMED** with a red band. Click the window, press `a` to
arm; any other key is a panic stop. Watch for the IMU banner to clear
before arming.

Expect: IDLE until a person is latched, FOLLOW with the target boxed
green, SEARCH spinning toward where they went, then IDLE. If
`pi/ms200_reader.py` is not running you will get the clearance-dark
warning once at FOLLOW entry — that is correct, and it means the obstacle
veto, cornered and imminent checks are all off. Do not run that session
near stairs.

---

## 9. Open questions for the oracle

1. **SEARCH spin rate.** `V2_TURN_RATE_DPS = 40` is a FOLLOW-centring
   rate. At 40°/s a full sweep takes 9 s, and the 3-frame acquire needs
   the target to stay argmax for ~300 ms — comfortable, but a person
   crossing the frame edge during a spin may not land three frames. If
   session 1 says it is too fast to scan with, the choice is tuning the
   shared constant versus giving SEARCH its own rate; the handoff asked
   for the former, so nothing was added.

2. **Arrival with no depth sensor.** `V2_ARRIVAL_AREA_RATIO` is now the
   sole arrival signal and is an unverified OAK-D number on a wide-angle
   lens. Worth deciding whether the MS200's forward arc should also gate
   arrival once it is live, rather than leaving bbox area alone on it.

3. **Pi clock offset (+484 ms).** Harmless today, wrong for any future
   frame-age check. Fix at the source or drop Pi timestamps from the wire?

4. **Holdover vs coast.** The pipeline's 15-frame holdover (~1.5 s at
   10 Hz) and the follower's 2 s coast now overlap: the coast outlives the
   latch by ~0.5 s, so there is a window where the dog is replaying its
   last action with no latch behind it (visible at frames 64–66 of the dry
   run). It behaved sanely, but the two timers were tuned independently
   and should probably be related on purpose.
