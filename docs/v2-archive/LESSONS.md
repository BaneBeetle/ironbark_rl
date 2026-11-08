# V2 lessons: what made it finicky

Drawn from the V2 commit history, the archived docs, and the V1-era failure
notes kept in `reference/config.py`'s comments. Every lesson names its
evidence. Paths are relative to this folder; `commit <sha>` refers to
`ironbark-v2`.

## The short version for V3

1. **Measure the update rate, not the call rate.** V2 believed its yaw ran
   at 343 Hz; at rest it never updated at all.
2. **No threshold crosses a hardware change unmeasured.** The arrival
   ratio that worked on the OAK-D can't be reached on the S2's lens, and
   that one number broke FOLLOW.
3. **Command-until-countermanded motion has dead time.** The yaw turn
   doesn't show up until 0.78 s after the command. Design control around
   it rather than stacking more hysteresis on top.
4. **Every socket pair gets a live end-to-end check.** ZMQ never complains
   about the wrong direction, the wrong port or a missing peer — V2
   teleop silently did nothing.
5. **Liveness comes from first-message receipt, never from a default value
   that looks like data.**
6. **No cross-host timestamp arithmetic.** The Pi's clock was half a
   second off the Mac's while both claimed NTP sync.
7. **Write from scratch rather than porting.** Most of V2's surprises came
   from V1 code that rode along: dead fields, inherited entry conditions,
   inherited thresholds.
8. **Keep the smoke-test gate.** It was the best decision in V2.

---

## A. The platform

### A1. V1's mechanical limits produced most of V1's code

**What happened:** On the PiDog, V1 grew buffer accounting, `one_shot`,
`flush`, action dedup, leap-prone interpolation and a synthesized 360° turn.
All of it was scaffolding around a queued-gait-frame SDK and arc turns.
In the perceive-act loop the servos held full torque through every
PERCEIVING phase, because the SDK had no release path. V1 ended in
undervoltage freezes on the shared battery rail, servo thermal death, and
tip-overs when backing up slowly.

**Evidence:** `phase1-briefing.md` §2–3; V1 failure notes in
`reference/config.py` (`CMD_INTERVAL`, `STRATEGIC_TURN_STEP_COUNT`,
`STRATEGIC_GAIT_SPEED`, `MIN_PERCEIVE_S`).

**What changed in V2:** The S2 is a velocity-setpoint machine. It turns in
place, strafes natively, reads yaw natively and can release torque
(`unload_allmotor`), so the whole category of buffer workarounds had
nothing left to work around (smoke Q1). V2's controller is ~250 lines
against V1's 1,172.

**For V3:** Before writing any workaround, ask whether the platform needs
it or whether you're carrying an old platform's habit. Put
`unload_allmotor()` rest states to use. They're the thermal lever V1 never
had.

### A2. Handling the dog during boot silently ruined yaw for the session

**What happened:** The first bench pass measured −9.89 °/s of yaw drift
with 0.029° residuals, a perfect ramp. The cause: the firmware samples gyro
bias at power-on, and the dog was in someone's hands at the time. During
that window yaw reads exactly 0.0. A clean, hands-off boot fixed it.

**Evidence:** `migration-notes.md` "First hardware contact" and "Q2
RESOLVED"; `measurements/smoke_20260828_234946.jsonl`,
`smoke_20260828_235710.jsonl`.

**For V3:** Power on with the dog on the ground and nobody touching it.
Gate all motion on the "first nonzero yaw" latch, as a state predicate,
never a timer. Treat an exact 0.0 from any `read_*` call as possibly a
sentinel rather than a value.

### A3. The IMU register freezes, and V2 misread it as fine

**What happened:** In the clean-boot smoke run the yaw register didn't
change once in 30 s (`update_rate_hz: 0.0`). That same run is the source
of V2's headline "343 Hz read_yaw" (the call rate) and of its "−0.009 °/s
drift" (a slope measured on a frozen value). The notes did mention the
register "holds near-frozen values … when still", but filed it as a
curiosity. V3 has since measured roughly 1 s freezes across the whole IMU
block.

**Evidence:** `measurements/smoke_20260829_000317.jsonl` stage 1;
`migration-notes.md` smoke-test table; `../phase1-joint-control-results.md`.

**For V3:** Any sensor metric must state whether it's a call rate or a
fresh-value rate. An IMU sanity filter (freeze detection, zeroed vectors,
impossible values) is a prerequisite for control, not a nice-to-have.

### A4. SDK convenience functions don't do what their names say

**What happened:** `turn_by(45°)` looked like a closed-loop P-controller
on yaw. It turned 73.8°: it's a timed turn whose duration
(`mintime + θ·k` = 4.1 s) matched the blocking time exactly.
`read_rotate_state()` returns opaque integers. The smoke tool's own
`turn_by_result` record still printed "closed-loop works", because that
verdict string was hardcoded.

**Evidence:** `measurements/smoke_20260829_000317.jsonl` stage 6;
`migration-notes.md` Q8.

**For V3:** Treat every vendor call as unverified until a trace confirms
it. Close loops yourself on measured signals. Measurement tools should
compute their verdicts from the data, never print canned conclusions.

### A5. Power shapes how you can test

**What happened:** The battery fell from 99% to 79% in about 3 minutes of
intermittent motion. At ≤9% the dog lies down and locks out. Plugging in
the charger hard-cuts power, so tethered runs are impossible. Nobody ever
measured runtime under sustained load.

**Evidence:** `measurements/smoke_20260829_000317.jsonl` stage 5;
`phase1-briefing.md` §3; `migration-notes.md` battery flag.

**For V3:** Log `battery_pct` in every run. At the observed rate (about
20 points in 3 minutes), a full charge reaches the 9% lockout in roughly
13 minutes of intermittent motion; plan sessions around that. Don't
promise a demo length until a sustained-load test exists.

### A6. Continuous motion plus perception latency means dead time

**What happened:** On the S2 a turn keeps going until something
countermands it. In the stage 3 trace yaw doesn't move until **0.78 s**
after `turnleft(40)`, then wobbles: 32 of 141 samples step backward during
a counter-clockwise turn. FOLLOW stacks a 100 ms command cadence and
3-frame commit hysteresis on top of perception latency.
`ACTION_COMMIT_FRAMES` was a V1 fix for flapping between buffered gait
bursts, and on a continuous machine it only adds delay. The commit that
recorded the first on-dog calibration describes centering as "chaotic" at
close range.

**Evidence:** stage 3 `yaw_sample` series; `reference/config.py`
(`ACTION_COMMIT_FRAMES`, `CMD_INTERVAL`); commit `7f44ec8`.

**For V3:** Measure the command-to-motion latency per action before
designing control. Prefer proportional commands (the S2's `turn(±v)`
takes a rate) over bang-bang turns with deadbands. Treat yaw during gait
as noisy.

## B. What came along from V1

### B1. Porting V1 wholesale imported dead machinery

**What happened:** Phase 0 copied V1's `pc/` stack whole. V2 then had to
delete or switch off the identity stack, the head-servo concepts
(`head_mode`, `owner_bbox`), bark plumbing, the OAK-D depth paths and the
SITUATION VLM. EXPLORE had to be gated off entirely, because its
completion gate waited on a gait `buffer_depth` the S2 has no notion of.
The wire protocol still carries nine fields the controller tolerates and
ignores.

**Evidence:** commit `7b80565`; `bringup-report.md` W1/W4;
`reference/motor_controller.py` header (tolerated fields);
`reference/config.py` (`EXPLORE_ENABLED` comment).

**For V3:** Starting from scratch is the right call. Port facts
(`MEASURED_FACTS.md`), not code.

### B2. Thresholds crossed the sensor change unmeasured

**What happened:** `V2_ARRIVAL_AREA_RATIO = 0.55` came from the OAK-D. On
the S2's wide lens a person at 1 m fills only 0.159 of the frame, so FOLLOW
never declared arrival, drove into the zone under 1 m (σ 40 px, 90%
clipping) and made centering chaotic. The turn bands and every `LIDAR_*`
threshold (tuned for a 13 cm PiDog; the S2 is 14.5 cm wide) carried over
the same way. Marking them `# MEASURE:` was right, but they were live in
code before anyone measured them.

**Evidence:** `measurements/ladder_20260904_204929.json`; commit `7f44ec8`;
`reference/config.py`.

**For V3:** A new sensor or body means every threshold that depends on it
is unknown, not "probably close". Run the calibration ladder before the
first motion session, not after.

### B3. A behaviour changed meaning but kept its entry condition

**What happened:** In V1, SEARCH was a head sweep and was entered whenever
no owner had been seen for under 5 s, including right after boot. In V2,
SEARCH became a body spin and kept that entry condition. A freshly started
follower would have spun in place for 5 s before ever seeing anyone. The
dry run caught it.

**Evidence:** `bringup-report.md` §3; `measurements/dryrun_follow_20260828_172654.txt`.

**For V3:** When an action's physical meaning changes, re-derive the
states that lead into it.

### B4. Two related timers were tuned separately

**What happened:** FOLLOW kept coasting (repeating its last action) for
2.0 s after the target vanished, but the target latch released at 15 frames
(~1.5 s). That left a 0.5 s blind window where the dog kept moving with no
target behind it. It was fixed by deriving one from the other.

**Evidence:** commit `aba0477`; `bringup-report.md` §9 Q4.

**For V3:** When two constants describe the same physical window, define
one in terms of the other, with the constraint written at the definition.

## C. Plumbing

### C1. ZMQ fails silently

**What happened:** Teleop published to the Pi's IP on 5557. The V2
controller subscribes on the Mac's IP on 5556, so every keystroke went
nowhere, with no error. The camera work item said "PUB" while the receiver
was a PULL bind, and those never connect. V3's own `CLAUDE.md` still says
"PUB" for the camera and lidar streams.

**Evidence:** commit `579c662`; `bringup-report.md` §6.

**For V3:** One table of socket pairs (who binds, who connects, which
pattern, which port). A startup self-test that confirms each pair has a
live peer. Telemetry the operator can see that proves commands are
arriving (echo `seq`).

### C2. A default value that looked like data defeated the liveness check

**What happened:** The HUD showed "IMU CALIBRATING – motion refused"
indefinitely even with no controller running. The telemetry receiver's
default dict pre-filled `action: "stop"`, which satisfied the check meant
to detect live telemetry.

**Evidence:** commit `b5f4720`.

**For V3:** Track "first real message received" explicitly. Show offline,
calibrating and live as three distinct states.

### C3. A safety warning that depended on which branch ran

**What happened:** The "no clearance data" warning sat inside
`_effective_forward_cm`, which the LiDAR-less FOLLOW path only reached for
some actions. In the dry run it never fired.

**Evidence:** `bringup-report.md` §3.

**For V3:** Raise degraded-safety notices at mode entry, not deep inside
a helper.

### C4. Config doesn't follow the code

**What happened:**
- `.env` is gitignored, so it doesn't travel with the code.
- The copy used for V2 bring-up held Tailscale IPs, while the Pi wasn't on
  Tailscale, so neither machine could reach the other.
- `deploy.sh` copied the whole `.env`, Anthropic API key included, to a
  Pi that never calls Anthropic. It was changed to ship only `PC_IP` and
  `PI_IP`.

**Evidence:** `bringup-report.md` §4; `migration-notes.md` network
section; commit `8f64c15`.

**For V3:** Use hostnames (mDNS) or DHCP reservations instead of literal
IPs. Validate config at startup by actually connecting. Ship machines only
the variables they use.

### C5. Cross-host clocks can't be trusted

**What happened:** The Pi ran 484 ms ahead of the Mac, stable to the
millisecond, with both claiming NTP sync. Naive latency came out
negative.

**Evidence:** `migration-notes.md` clock skew.

**For V3:** Age data by the receiver's own clock only. If cross-host
timing is ever needed, measure the offset explicitly, as V2 did with
round-trip samples.

## D. Process

### D1. The smoke-test gate paid for itself

No controller code was written until eight hardware questions had answers
from a trace. That one session ruled out the whole gait-buffer design,
uncovered the `turn_by` lie, the boot-calibration window and the
battery-percent API, and showed `attitude()` composes with walking.
(`migration-notes.md` "SMOKE TEST COMPLETE".) **Keep this pattern for
V3's joint-control gate.**

### D2. Check the physical world first

An all-black camera frame looked like 120 fps mode starving exposure. It
was the lens cap. (`migration-notes.md` camera section.) **Have senders
log simple image statistics (mean, standard deviation) so dead input is
obvious.**

### D3. Development-machine friction blocked an acceptance test

macOS camera permissions denied the agent's process, so W1's live-webcam
acceptance test never ran. (`bringup-report.md` §7.) **On the PC, check
camera, serial and network permissions in Phase 0, before the work that
needs them.**

### D4. Write down what was never measured

The `# MEASURE:` convention and per-file measurement tags made the
unknowns visible. They only failed where code used the values anyway
(B2). **V3: an unmeasured threshold should block the behaviour that
depends on it, or at least shout when used.**
