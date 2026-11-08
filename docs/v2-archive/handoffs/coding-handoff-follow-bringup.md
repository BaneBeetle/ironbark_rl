# IronBark V2 — Coding Handoff: FOLLOW Bring-Up (Steps 1–5)

You are the implementation instance for IronBark V2's FOLLOW bring-up. An
oracle session designed this work from hardware measurements; your job is to
build it. This document plus the repo files it names are your world. The
human (the creator) runs all sessions involving the physical dog — you never
actuate motors.

## Read first, in this order

1. `docs/phase1-briefing.md` — especially §5 (target-lock design, your W1 spec)
2. `docs/migration-notes.md` — every measured fact; treat as ground truth
3. `pi/motor_controller.py` — header + code; this is what your Mac-side code talks to
4. `docs/measurements/*.jsonl` — the smoke-test data behind every claim
5. Project memory auto-loads (`MEMORY.md`); read both indexed entries

Work on top of branch `claude/ironbark-v2-oracle-handoff-e29f1a`.
V1 stays frozen at `~/Projects/ironbark` — reference only, for the sender/
reader wire formats (`pi/pi_oakd_sender.py`, `pi/lidar_reader.py` there).

## Hard rules (non-negotiable, from the project's operating discipline)

- **Never run anything that moves the dog.** No motion SDK calls, no
  motor_controller launches, no `run.sh`. Deploying files to the Pi and
  bench-testing the camera over SSH is fine. Never open `/dev/ttyAMA0`.
- **Single-variable commits.** One work item = at least one commit; never
  bundle two work items in one commit. Match the existing message style.
- **No wall-clock logic in Pi-side code.** Frame counts and state
  predicates only. Mac-side timers are fine.
- **Name thresholds by semantic role**, and mark every value you could not
  measure with a `# MEASURE:` comment explaining how it will be measured.
- **Do not modify `pi/motor_controller.py` semantics** — it is
  measurement-derived. Additive telemetry fields are acceptable if a work
  item genuinely needs one; say so in the report.
- **Do not re-add identity** (no face/ReID paths), **do not build EXPLORE
  work** (Phase 3), do not port `enroll_owner.py`.

## Environment facts

- `ssh pi` works (user lolly, passwordless sudo, key auth). Pi paths:
  `~/ironbark/` with `.venv` (xgolib 1.1.9, pyzmq, pyserial). PATH gotcha:
  non-login shells miss `/usr/sbin` and `~/.local/bin`.
- USB camera present at `/dev/video0` (ARC International 2MP wide-angle).
- MS200 lidar UART is **not enabled yet** — port unknown until the human
  traces the cable and adds the overlay. Code against a configurable port;
  live lidar testing is deferred, not yours.
- `.env` exists (gitignored) with working LAN IPs; TCP 5556 Pi→Mac verified
  open. `config.py` loads it.
- Wire protocol Mac↔Pi: commands JSON on PUB `PC_IP:5556` (Pi subscribes),
  telemetry JSON strings PUB'd by Pi on `:5558`. Telemetry fields:
  `action, yaw, roll, pitch, battery_pct, imu_ready, seq, fw`. There is
  deliberately no `buffer_depth` and no `battery_v`.
- Motion vocabulary motor_controller accepts: `stop | forward | backward |
  turn_left | turn_right | strafe_left | strafe_right` (+ `head_pitch` →
  attitude trim). `turn_*` runs at fixed `V2_TURN_RATE_DPS` (°/s, measured
  calibrated within 2%).

## Work items

### W1 — Perception simplification: target-lock (the big one)

Implement `docs/phase1-briefing.md` §5 exactly. Summary of the contract:

- `perception_pipeline.py` keeps YOLO11s + ByteTrack; **delete** the
  FaceRecognizer/ReIDRecognizer usage, `_fuse_scores`,
  `_smooth_face_matches`, `_face_tracks`, gallery loading, and the
  face/owner match plumbing. Delete `pc/perception/face_recognizer.py`,
  `pc/perception/reid_recognizer.py`, and `pc/enroll_owner.py`. Keep the
  per-detection list structure (identity returns later as one more scorer).
- Target latch (mirrors the removed `_owner_track_id` machinery, minus
  recognition): when unlatched, score each person
  `area_norm × (1 − CENTER_WEIGHT × |cx − W/2| / (W/2))`, CENTER_WEIGHT
  0.3 in config; latch a ByteTrack ID after it is argmax for
  `TARGET_ACQUIRE_FRAMES = 3` consecutive frames. While latched: the
  matching track is the target; if absent, hold `TARGET_HOLDOVER_FRAMES =
  15` frames, then release. `PerceptionResult` gains `target` and
  `target_track_id`.
- `DEBUG_TARGET_SCORES` flag prints per-detection scores + latch state
  (same pattern as the old `DEBUG_FUSION_SCORES`).
- SITUATION VLM: **deferred, not deleted.** Add `VLM_SITUATION_ENABLED =
  False`; when False, never start the worker or queue queries; behavior
  mode is pinned `BEHAVIOR_DEFAULT_MODE = "ACTIVE"`. Ollama must not be a
  runtime requirement when disabled.
- Add a local-webcam dev mode (e.g. `--local-cam` on the runner or a small
  harness) so the pipeline + viz run against the Mac's own camera with no
  Pi. Keep it small; it is a dev tool, not a product path.

Acceptance: on the Mac webcam with two people in frame, the HUD shows the
latch acquiring the higher-scoring person after 3 frames, holding through
brief occlusion (≤15 frames), and releasing after sustained absence.
Capture the console log of one such run for the report.

### W2 — Camera sender: `pi/cam_sender.py`

`/dev/video0` → 640×480 JPEG (quality ~75) → ZMQ PUB on port 50505,
**matching the wire format the pc-side frame receiver already expects** —
read the V2 pc receiver code and V1's `pi/pi_oakd_sender.py` (reference
repo) for the contract; do not invent a new format. Target ~15–20 fps;
print achieved fps once per second. No depth stream exists — make sure the
pc side tolerates the depth port being silent (see W4).

Acceptance: frames from the dog's camera render in the Mac viz over the
LAN; measured fps + one-way latency (frame timestamp vs receive) recorded
in the report. Bench-safe: camera only, no motion. Add the file to
`deploy.sh`.

### W3 — Lidar reader: `pi/ms200_reader.py`

Oradar/Orbbec MS200 (dToF, UART 230400 8N1) → the same ZMQ scan schema
V1's `lidar_reader.py` published on port 50507, so `pc/lidar_map.py` and
the costmap consume it unchanged — derive the schema contract from
`pc/lidar_map.py`'s ingestion plus V1's reader. Implement the MS200 frame
protocol from its public documentation; structure the code as
parser-over-byte-stream with three modes:

- `--dump FILE`: record raw serial bytes (first live bench session
  captures data before anything else — instrument first)
- `--replay FILE`: parse a recorded dump and publish/print (offline
  verification)
- live mode: serial port from `V2_LIDAR_PORT` config placeholder
  (default `/dev/ttyAMA2`, marked `# MEASURE: set after cable trace`)

Acceptance: parser unit-tested against a synthetic frame (build one from
the protocol spec's checksum rules) and structured to run `--replay`
cleanly. Live full-revolution verification is deferred to the human's
bench session — leave exact instructions for it in the report.

### W4 — Follower adaptations (`pc/follower.py` + config)

- `_find_owner` → `_find_target`: return the pipeline's latched target;
  delete the recognition ladder, `_investigating`, unconfirmed-person
  counters, and the identity bark (`_should_bark` machinery). Arrival-bark
  plumbing may stay but default-disabled.
- FOLLOW entry: latched target present (the pipeline's 3-frame acquire is
  the gate). `last_owner_seen` semantics → `last_target_seen`.
- SEARCH v0: replace the head-servo sweep with a **slow in-place spin
  toward the last-seen side** (body `turn_left`/`turn_right`; the S2 spins
  natively and rotation-only is safe without clearance). Keep it gentle —
  if the fixed `V2_TURN_RATE_DPS` proves too fast for search scanning,
  note it as a tuning item rather than adding new mechanisms.
- EXPLORE: `EXPLORE_ENABLED = False` config gate for bring-up — SEARCH
  timeout falls back to IDLE instead of EXPLORE. Do not touch EXPLORE
  internals otherwise.
- Depth: `USE_DEPTH_FORWARD_CLEARANCE = False`; every `_effective_forward_cm`
  style fusion must degrade cleanly to LiDAR-only, and to "no clearance
  data" (bring-up before W3 is live) — in that last case FOLLOW forward
  motion still works but log a once-per-session warning that the clearance
  layer is dark.
- Telemetry consumers: `battery_v` → `battery_pct` in HUD; surface
  `imu_ready` (banner while False); tolerate absent fields.
- Pixel thresholds (`BODY_TURN_THRESHOLD`, arrival area ratios) were tuned
  for the OAK-D's FOV: introduce V2 values as config entries carrying
  `# MEASURE:` notes (initial values may copy V1's, explicitly marked
  unverified for the new wide-angle camera).

Acceptance: full-stack dry run on the Mac webcam with **no Pi connected**
(ZMQ PUB with no subscriber is harmless): states transition IDLE → FOLLOW
on person-enter, FOLLOW → SEARCH → IDLE on person-leave, and the HUD's
command banner shows sane forward/turn decisions. Log one full cycle for
the report.

### W5 — Deadman (hold-to-arm) for supervised sessions

Add an arming gate to command emission in `pc/remote_control.py` and the
follower session path: default **disarmed** (only `stop` flows); a single
obvious control arms it; disarming (or losing the input context) stops
emission immediately — the Pi's count-based watchdog then halts the dog
within ~1.5 s. True key-held semantics are preferred; if macOS keyup
detection forces a pragmatic alternative (e.g. OpenCV-window focus +
toggle with giant HUD state banner + any-key instant stop), choose one,
justify it in the report, and keep the three invariants: starts disarmed,
instant stop always available, disarm ⇒ emission stops.

## Report back

Write `docs/bringup-report.md`: what shipped per work item, measured
numbers (fps, latency, dry-run behavior), every `# MEASURE:` placeholder
awaiting hardware, deviations from this spec with reasons, and the exact
commands for the human's next dog sessions (teleop first, then supervised
FOLLOW). The oracle reviews that report before any motion session.
