# First autonomous FOLLOW run (2026-08-30)

The first time V2 followed a person on its own. Written from session notes
after the fact: **no trace from this run was committed**, so everything
here is an observation, not a measurement.

## Setup

| | |
|---|---|
| Pi | `motor_controller.py` (launched through `run.sh`), `cam_sender.py` |
| Mac | `pc/follower.py`: YOLO11s + ByteTrack target latch, the W4 FOLLOW state machine |
| Clearance | **dark.** No lidar (the MS200's UART was never traced), no depth. The obstacle veto and the cornered/imminent checks were all off, and the follower printed its one-time warning to say so |
| Safety | deadman armed by hand (toggle + panic key, see `../bringup-report.md` W5); an operator stood next to the dog; open floor |
| Code | the W1–W5 bring-up plus the post-review fixes (`FOLLOW_COAST_S = 1.5`, deploy ships network variables only) |

## What worked

- **Latch and pursue.** The pipeline latched a ByteTrack ID and FOLLOW
  walked toward the person.
- **Re-latch.** After the target was lost and reappeared, the latch
  re-acquired.
- **SEARCH.** On losing the target the dog spun in place **toward the side
  the target was last seen on**. This was the first physical check of the
  SEARCH v0 design and of the boot-time-SEARCH fix (no spin at startup).
- **Panic disarm** stopped the dog cleanly.

That's the W1–W5 chain working end to end on hardware for the first time:
camera stream → perception → latch → FSM → command PUB → Pi SUB → S2
setpoints.

## What didn't

1. **Turn overcorrection.** While centring on the target, the dog swung
   past centre and oscillated. Diagnosis and tuning ladder:
   [`turn-overcorrection.md`](turn-overcorrection.md). No tuning was
   applied in V2.
2. **HUD liveness defect.** With no controller running, the HUD showed
   "IMU CALIBRATING – motion refused" indefinitely, because the telemetry
   receiver's default dict pre-filled `action: "stop"` and passed the
   liveness check. This surfaced in the first sessions with an operator
   and was fixed in commit `b5f4720` (now three states: TELEMETRY OFFLINE /
   IMU CALIBRATING / nothing). See `../LESSONS.md` C2.
3. **Exit segfault.** The Mac process exited with code 139 (SIGSEGV) during
   OpenCV/macOS window teardown after a disarm. It was cosmetic: the stop
   had already gone out, so the dog wasn't affected. It was never fixed.
   Likely the OpenCV HighGUI window being destroyed during interpreter
   shutdown; unconfirmed.

## What was learned afterwards

The 2026-09-04 static ladder (`../measurements/ladder_20260904_204929.json`,
commit `7f44ec8`) explained much of this run's erratic close-range
behaviour:

- `V2_ARRIVAL_AREA_RATIO = 0.55` can't be reached on the S2's wide lens
  (area is 0.159 at 1 m). FOLLOW therefore never declared arrival and kept
  closing in to under 1 m.
- At 1 m the person is clipped by the frame in 90% of frames and the
  target's x-offset jitters by σ ≈ 40 px (closer was not measured). Centring there is noisy whatever
  the turn controller does.

## Gaps for anyone repeating it

- **No trace was committed.** A follower drive log did exist around this
  time (its median frame-to-frame target jump of 45 px is quoted in
  [`turn-overcorrection.md`](turn-overcorrection.md)), but it never reached
  the repo. A committed log with per-frame target offset, commanded action
  and telemetry yaw would have answered most of the open turn questions.
- The arrival threshold was never re-derived, so arrival was never
  exercised.
- Clearance-dark only. FOLLOW never ran with the MS200 live.
