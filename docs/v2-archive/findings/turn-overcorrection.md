# Turn overcorrection, and why the frozen yaw register matters

Seen in the first autonomous FOLLOW run
([`2026-08-30-first-autonomous-follow.md`](2026-08-30-first-autonomous-follow.md)).
V2 diagnosed it but **never applied a fix and never traced it**. The
latency figures below are estimates unless marked measured.

## Symptom

While centring on the target, the dog turned past it, reversed, and
oscillated instead of settling.

## Diagnosis: dead time on a machine that doesn't stop by itself

On the S2 a turn keeps going until something countermands it (smoke Q1:
movement continues until `stop()`). FOLLOW's countermand reaches the motors
only after a stack of delays:

| Stage | Delay | Basis |
|---|---|---|
| Camera to Mac | ~10 ms | measured one-way, `../migration-notes.md` camera section |
| YOLO + ByteTrack + FSM | ~100–200 ms | estimate; perception runs ~10 Hz |
| Command cadence (`CMD_INTERVAL`) | 0–100 ms | config |
| `ACTION_COMMIT_FRAMES = 3` hysteresis | ~300 ms at 10 Hz | config |
| S2 stop latency after `stop()` | **unmeasured** | — |

That adds up to roughly 0.3–0.6 s before the turn is told to stop. At the
measured 39.2 °/s, that's about **12–24° of overshoot**, before counting
whatever the gait adds after the stop arrives. Yahboom doesn't publish the
lens FOV, so the size of that overshoot in pixels is unmeasured. For any
90–120° horizontal FOV at 640 px it comes to roughly 65–170 px. The
close-range turn bands are 60–160 px (`V2_TURN_BANDS`), so one overshoot
can carry the target across the whole deadband to the far side, which
starts the opposite turn.

### Why V1 never showed it

On the PiDog a turn was a queued burst of gait frames that ended by itself.
`ACTION_COMMIT_FRAMES` was added there to stop the follower flapping
between bursts: "every flap sends a STOP that flushes the Pi's gait buffer,
so flap = zero net rotation" (`../reference/config.py`). On a machine that
turns continuously, the same hysteresis just delays the stop. The
stabiliser V1 needed became a source of overshoot on V2.

### What the 2026-09-04 ladder added

`../measurements/ladder_20260904_204929.json`:

- **Sensor noise is not the cause at follow range.** The target's x-offset
  noise with the operator standing still was σ 2.6 px at 2 m and 3.5 px at
  3 m, against bands of 160–220 px.
- **Most of the jitter comes from motion.** A drive log from that period
  (never committed) showed a median frame-to-frame target jump of about
  45 px while moving. That's blur, changing pose and the dog's own
  rotation, so widening the deadband treats the wrong cause.
- **Some "turning for no reason" wasn't overcorrection at all.** FOLLOW
  never declared arrival (0.55 can't be reached; area is 0.159 at 1 m), so
  it closed to 1 m and nearer. There σ ≈ 40 px, and 3σ (119 px) exceeds the
  100 px band, so noise alone triggered turns.

## The frozen yaw register

V2's FOLLOW centred on pixel offset alone and never read yaw, so the
register didn't cause the oscillation. It does undermine the obvious
fixes, and V2's own estimate of the turn's dead time.

**What's known about the register:**

1. **At rest it doesn't update.** In the clean-boot smoke run, stage 1
   logged `call_rate_hz: 342.9` but `update_rate_hz: 0.0`: no change in
   30 s (`../measurements/smoke_20260829_000317.jsonl`). V3 has since
   measured the whole IMU block holding an identical value for ~1 s at a
   time (`../../phase1-joint-control-results.md`).
2. **The 0.78 s "turn onset" is confounded.** In stage 3, yaw sat at 35.77°
   for 0.779 s after `turnleft(40)`, then started moving. That fits a gait
   start-up delay, a register still inside a frozen stretch (V3's last up
   to ~1 s), or both. The trace has no independent motion reference, so
   V2 cannot separate the turn's real dead time from IMU staleness.
3. **During motion it updates but wobbles.** 130 of 141 stage-3 samples
   changed (about 70 ms apart), but 32 of them stepped *backward* during a
   counter-clockwise turn. A yaw rate taken from differences is noisy at
   gait frequency.
4. **Telemetry adds staleness.** `motor_controller` reads yaw every 50 Hz
   tick but publishes it at 10 Hz (`V2_TELEM_EVERY_TICKS = 5`).

**What that does to the fixes:**

- **Closing turn loops on yaw**, V2's stated replacement for the
  dead-reckoned SDK `turn_by` (`../migration-notes.md` Q8), can start from
  up to ~1 s of stale yaw and stop late. That's the overshoot it was meant
  to remove.
- **Yaw can't be the brake** for FOLLOW centring (yaw-rate damping). The
  pixel error is the fresher signal: about 10 ms of transport plus
  inference.
- **Turn and stop latency must be measured against something outside the
  IMU**: video of the dog against a floor mark, or optical flow from its
  own camera.

## Tuning ladder (proposed in V2, never applied)

One variable at a time, in this order:

1. **Halve the turn rate for FOLLOW** (`V2_TURN_RATE_DPS` 40 → ~20). This
   halves the overshoot for the same delay. If SEARCH still needs the
   faster rate, give it its own constant rather than tuning the shared
   one.
2. **Re-derive the turn deadband for the wide lens** from ladder data
   (`pc/bbox_calibrate.py --ladder`).
3. **Asymmetric hysteresis**: start a turn at a large offset, stop it at a
   small one. Alternatively drop `ACTION_COMMIT_FRAMES` for turns.
4. **Proportional turning**: rate = k × offset, clamped. The S2's
   `turn(±v)` accepts a rate, which the PiDog's step-quantised turns never
   could. It needs a rate field on the wire, an additive change to
   `motor_controller`, which only sends a fixed `V2_TURN_RATE_DPS` today.

Also on the list, both aimed at motion-induced jitter rather than noise:

- An A/B test of `imu(1)` self-stabilisation. It's mutually exclusive with
  `attitude()` trim.
- ByteTrack low-confidence association.

## For V3

- Measure command-to-motion and stop latency **per action**, with an
  external reference, before designing turn control.
- Treat IMU values as stale until proven fresh: run the sanity filter
  (freeze detection) before any control use. If yaw has to be a control
  input, a dedicated I2C IMU is already logged as a fallback
  (`../../deployment-notes.md`).
- If a learned policy observes yaw, put freeze behaviour in its training
  data or randomisation. Otherwise the policy will treat a frozen yaw
  value as a stationary dog.
