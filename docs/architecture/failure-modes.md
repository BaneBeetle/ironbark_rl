# IronBark V3 failure modes

For each failure: how it is detected (signal and predicate), what the Pi runtime does, what the PC does, what the operator sees, how it recovers, what evidence is logged, and how it is tested before it happens for real. Thresholds named in CAPS are Brian's calls, listed in [decisions.md](decisions.md) §3. Message names are from [interfaces.md](interfaces.md).

Standing rule (architecture §1): the safety layer only clamps, zeroes, holds or unloads. It never starts a gait or an action group.

---

## 1. PC → Pi command stream lost

The PC process died, Wi-Fi dropped, or the PC is alive but its loop stalled.

| | |
|---|---|
| Detect (Pi) | ticks since the last S1 message. Three thresholds defined from one another: `VELOCITY_TTL_TICKS` (per message) < `CMD_LOST_TICKS` < `CMD_DEAD_TICKS` |
| Pi does | TTL expiry → the arbiter's velocity is zero; the policy is meant to bring the dog to a stand. **Unverified** (Brian, 2026-11-08): the scoreboard's stand row is a 10 s stand from rest, training has `rel_standing_envs = 0` (zero commands ≈ 0.4 % of draws), and the walk → zero transition is not scored anywhere. At `CMD_LOST_TICKS` → `event: cmd_stream_lost`, `degraded += "cmd_stream"`. At `CMD_DEAD_TICKS` → `IDLE_HOLD` (joints held at measured angles; cheaper than balancing forever) |
| PC does | if alive: HUD link S1 → STALE then OFFLINE from its own clock; disarms; the follow controller keeps publishing (so recovery is automatic when the link returns) |
| Operator sees | HUD: S1 OFFLINE, mode, `last_cmd_seq` frozen |
| Recovery | first S1 message → `cmd_stream_ok`; the arbiter stays in `IDLE_HOLD` until a `mode: POLICY` request arrives (no automatic re-walk) |
| Evidence | `health.cmd.stream_lost_count`, Pi journal line with tick and last `seq` |
| Test | first M-28: an eval of walk → stop transitions in sim (falls, settle time, drift per starting command), then the same on the stand. Then kill the PC process mid-walk on the stand: measure ticks to zero velocity and to `IDLE_HOLD` |

Why zero velocity rather than a freeze: a mid-stride frozen pose may be unstable, and a zero command asks the policy for a stand (decision 5). That choice rests on the policy stopping cleanly from a walk, which nobody has measured. Brian's plan (2026-11-08): the walk → stop eval (M-28) and more stand commands in training. If M-28 shows falls or long drifts, this section is the one to revisit. Freeze applies only when the IMU is also bad (§4).

## 2. Pi hang

The Pi drops off the network mid-session (seen 2026-09-30; cause unknown). Nothing on the Pi can act.

| | |
|---|---|
| Detect (PC) | S2 silent for `TELEM_STALE_S` (PC clock) **and** S3 `hello` unanswered. Either alone is a link fault; both together is "the Pi is gone" |
| Pi does | nothing: that is the failure |
| Board does | **joint mode: expected to hold the last joint setpoints** (a standing or mid-stride pose). **Gait mode: keeps walking** (V2 smoke Q1, 8 s window). V3 walks only in joint mode, so a hang should leave a held pose, not a walking dog. `# MEASURE:` Brian's stand test, both modes, before any deployment (deployment-notes.md requirement 1). Whether the board has any timeout of its own: unknown, same test |
| PC does | HUD alarm "PI UNREACHABLE: use the kill switch"; voice says nothing (it would need the Pi's speaker) |
| Operator | **kill switch = power button** within reach every motion session (Brian). Cutting power drops torque; the dog collapses from standing height |
| Recovery | power cycle on the ground, hands off through the IMU bias window (`BOOT` → `imu_ready`), then the startup self-test |
| Evidence | Pi: persistent journal (`/var/log/journal`) so `journalctl -b -1` survives; `health` logged every second on the PC with `throttled_hex`, Wi-Fi RSSI and power-save state, CPU temperature, so the last seconds before the hang are on the PC's disk |
| Test | the stand test above; plus a "pull the Ethernet/Wi-Fi" drill with the dog on the stand to confirm the HUD alarm path |

## 3. Pi → PC telemetry lost, commands still flowing

Rare (one PUB socket) but it is exactly the case V2's HUD got wrong.

| | |
|---|---|
| Detect (PC) | S2 silent for `TELEM_STALE_S` while S3 `hello` still answers |
| Pi does | nothing changes; it keeps walking under live commands. The Pi's `hello_reply` carries `mode` and `tick`, so the PC can still see it is alive |
| PC does | HUD S2 → OFFLINE (distinct from CALIBRATING and LIVE: LESSONS C2); the follow controller stops publishing nonzero velocity after `TELEM_STALE_S` because the PC can no longer see the dog's state; the Pi's TTL then stands the dog |
| Operator sees | "TELEMETRY OFFLINE, commands halted" |
| Recovery | automatic when `state` resumes |
| Test | block port 5558 on the PC firewall mid-walk on the stand |

## 4. IMU frozen, rejected, or never ready

Measured: the whole IMU block holds for ~1 s at a time (41.8 % of the time), occasional exact-zero vectors, gyro outliers > 1500 °/s. Yaw reads exactly 0.0 until the boot bias sampling ends.

| | |
|---|---|
| Detect (Pi) | sanity filter every read: zero vector → `rejected`; \|gyro\| > `GYRO_MAX_DPS` → `rejected`; identical block for `IMU_FREEZE_READS` → `frozen`; no nonzero yaw yet → `ready=false` |
| Pi does | `BOOT` refuses every motion until `ready` (predicate, never a timer; LESSONS A2). While `frozen`/`rejected`: the policy sees the last accepted value (the same hold as the sim's `imu_frozen` term). That term is scoring-only: no policy has trained with freezes, and scoring EXP-010's policy under them raised flicker 15.1 % → 25.4 % with 0 falls. At `IMU_STALE_TICKS` → velocity zero, `event: imu_frozen`, `degraded += "imu"`. At `IMU_DEAD_TICKS` → `IDLE_HOLD`. Tilt cutoff keeps using the last accepted roll/pitch |
| PC does | HUD shows `imu.status` and `frozen_ticks`; the brain is told in its state summary |
| Operator sees | CALIBRATING (before ready) / IMU FROZEN n ticks |
| Recovery | first accepted read → `imu_ok`; `IDLE_HOLD` stays until requested out |
| Evidence | `health.imu` fresh-value rate, freeze count, longest freeze; `state.imu.status` at 50 Hz in the PC log |
| Test | replay the measured freeze logs (`joint_control_imu*_20261108-*.jsonl`) through the filter: no false `rejected` on live reads, every measured freeze detected within `IMU_FREEZE_READS`; sim scoring with `-ImuFreeze` already exists for the policy side; training with freezes is planned for the domain-randomization phase (Brian, 2026-11-08) |
| Fallback (logged option, not decided) | a separate I2C IMU wired to the Pi (Brian, 2026-11-07) |

`IMU_STALE_TICKS` must exceed the longest measured freeze (1004 ms = 50 ticks) or the dog would stop on every normal freeze; `IMU_DEAD_TICKS` sits above that. If a future experiment adds an "IMU age" observation, the filter already has `age_ticks` for it.

## 5. Stale or dead perception

Frames stop, the detector hangs, or the tracker outputs an old frame's result.

| | |
|---|---|
| Detect (PC) | camera: PC frame age in frames of expected period (PC clock) ≥ `FRAME_STALE_FRAMES`; detector: `tracks.frame_id` not advancing; tracker: target unseen ≥ `TARGET_LOST_FRAMES` |
| PC does | follow controller → zero velocity within `TARGET_LOST_FRAMES` (one constant shared with the voice's `target_lost`, LESSONS B4); owner tracker → `LOST` → confidence decays → `RESCAN` only if it was locked (never from boot: LESSONS B3); frames stale → controller zero, HUD CAMERA STALE |
| Pi does | nothing special: a zero-velocity stream is normal. If the PC pipeline dies entirely, §1 applies |
| Operator sees | HUD target state, frame age, detector fps |
| Recovery | automatic on new frames/tracks; re-lock → VLM verify → `target_reacquired` |
| Test | pause the camera stream on the stand; assert zero velocity within `TARGET_LOST_FRAMES` and no rescan before the lock existed |

## 6. Camera stall after a dog power cycle

Measured: `/dev/video0` opens but `select()` times out until a USB unbind/rebind (`findings/usb-camera-stall.md`).

| | |
|---|---|
| Detect (Pi, `cam_sender`) | read failures counted, not timed: `OPENCV_VIDEOIO_V4L_SELECT_TIMEOUT=1` so each failure costs ≤ 1 s; streak ≥ `CAM_FAIL_STREAK` → stalled |
| Pi does | `cam_health.status = stalled` → runtime `event: camera_stalled`; reopen once; if still failing after `CAM_REOPEN_LIMIT`, look up the USB port path at runtime (`readlink /sys/class/video4linux/video0/device/..`), unbind/rebind, reopen; `usb_resets` counted |
| PC does | §5 (stale perception) |
| Operator sees | HUD CAMERA RECOVERING with the reset count; `health.camera.frame_mean` ≈ 0 flags a lens cap separately |
| Recovery | automatic; `camera_ok` |
| Evidence | `health.camera.read_fail_streak`, `usb_resets`; journal |
| Test | power-cycle the dog with the Pi on: time to `camera_ok` ≤ a few seconds, not V2's ~5 minutes |

## 7. Low battery

Measured drain 99 → 79 % in ~3 min of intermittent motion; the firmware lies the dog down and locks out at ≤ 9 %; charging cuts power.

| | |
|---|---|
| Detect (Pi) | `battery_pct` (read every `BATTERY_EVERY_TICKS`) ≤ 20 → low (Brian); ≤ `BATTERY_CRITICAL_PCT` → critical; re-arm above 30 (Brian's T3). The battery read has its own tick |
| Pi does | low: `event: battery_low`. Critical: velocity zero, `event: battery_critical`, `degraded += "battery"`, `IDLE_HOLD` after `STAND_TICKS`; `action`/`mode: POLICY` requests rejected with `"battery_critical"` |
| PC does | voice says the cached `battery_low` line (queued behind a playing line, per Brian); whether `battery_critical` is spoken at all is decisions.md D-19 (it has no cached line today); the brain is expected to request `REST` (lie down, unload) so the dog rests under control before the firmware does it mid-stride at 9 % |
| Operator sees | percent and the event on the HUD |
| Recovery | charging (power off) |
| Evidence | `battery_pct` in every `state` → the session log doubles as a drain measurement (`# MEASURE:` sustained-load runtime, never measured) |

## 8. Lidar dark (Phase 2)

| | |
|---|---|
| Detect (Pi) | no valid scan for `LIDAR_DARK_SCANS`, or the reader isn't running (port unset) |
| Pi does | reflex treats the front as unknown: vx capped at `VX_CAP_LIDAR_DARK`; `degraded += "lidar_dark"` raised at **mode entry**, not inside a helper (LESSONS C3); `event: lidar_dark` |
| PC does | HUD LIDAR DARK; the brain's state summary says so |
| Recovery | scans resume → `lidar_ok`, cap lifted |
| Test | unplug the lidar on the stand; assert the cap and the notice at the next `POLICY` entry |

## 9. Brain (VLM) timeout or malformed output

| | |
|---|---|
| Detect (PC) | API timeout, schema validation failure of a tool call, an out-of-range argument |
| PC does | keep the last goal (the follow controller does not depend on the brain for safety); drop the malformed call, log it, `event: bad_message` with `from: brain`; a `set_velocity` tool call is clamped and capped to `BRAIN_VELOCITY_TTL_MAX` ticks so a dead brain's last command expires on the Pi anyway |
| Pi does | nothing special |
| Operator sees | brain latency and last error on the HUD |
| Test | inject a tool call with `vx: 9.0` and a 30 s API stall; assert clamping and that walking continues under the follow controller |

## 10. Voice path failure (API, network, Pi speaker)

No effect on motion by construction: the voice only subscribes to events and pushes audio, and an S6 failure never blocks arming (it raises `audio_down`).

- **API failure.** Cached events never call an API. A Haiku or TTS failure on any other line is logged and the line is dropped; there is no fallback line (the voice's built behaviour).
- **Link drop mid-line.** The sender does not queue while the Pi is unreachable (`IMMEDIATE=1`, bounded high-water mark), so no old speech plays after a reconnect; the line is dropped (M-22).
- **`speech_ended` never arrives.** The voice times out from the PCM byte count.
- **A fall during a line.** `audio_ctl stop` is read by the player's receive thread while the clip plays; it discards the queued PCM and drops the device buffer (M-21).
- **Device failure** on the Pi: `health.audio.status`, `audio_down`.
- **Device busy at boot.** The first open after power-on failed with "Device or resource busy" (2026-11-08, uptime 0) and worked seconds later: the player retries a counted number of times, then reports `audio_down`.
- **A device that opens but makes no sound.** Seen for real: `aplay` to the Pi's card 2 exits 0 and nothing is heard, because the overlay registers a card with no DAC behind it. No software check catches this; the session-start test line and the operator's ears do (interfaces §3, step 6).
- **The default route goes to the dead card.** This Pi's `/etc/asound.conf` (V1's) sends `default` to card 2. The player names its device by card name and never uses `default`.
- **The speaker browns out the Pi.** The USB sound card (decisions.md D-17) shares the Pi's USB current budget with the camera. A brownout is not a voice failure: it is a Pi hang (§2). The draw at speech volume is `# MEASURE:` (M-30) before the dog walks with voice on it; if it is too high, lower the gain or use one speaker of the pair.
- **The voice board talks into the new mic.** While the board stays cabled with its speaker, its own wake reply plays beside the mic, and nothing tells the Pi when it speaks. The mic gate (D-20) opens a counted number of ticks after a `keyword` whose `source` is the voice board (the reply's length is `# MEASURE:`, M-14), or the board's speaker is unplugged.
- **Today** the dog's audio device is chosen but not installed (decisions.md D-17), so the voice plays on the PC and none of the above is live yet.

## 11. Version or schema mismatch

| | |
|---|---|
| Detect | `hello` compares every type's `v`; receivers reject unknown fields |
| Pi does | refuses the mismatched type (`health.cmd.rejected_reason`), stays in `IDLE_HOLD`/`BOOT` |
| PC does | HUD blocks arming with the reason |
| Test | bump `velocity.v` on one side; nothing moves, the HUD says why |

## 12. Policy misbehaves (sim-to-real surprise)

| | |
|---|---|
| Detect (Pi) | tilt ≥ `FALL_TILT_DEG` (46, Brian); joint clamps hitting (`safety.joints_clamped`); per-tick step > `JOINT_STEP_MAX_DEG`; operator judgement |
| Pi does | clamps every tick; `fell` → `ESTOP` (hold), unload after `FALL_UNLOAD_TICKS`; operator SPACE → `ESTOP` |
| PC does | HUD; voice "fell" line (interrupts, per Brian) |
| Recovery | operator `clear_estop` only, after setting the dog upright; `load_allmotor()` if it was unloaded, then `adopt` → `IDLE_HOLD`. Loading moves the joints before `adopt` can run, and `unload_allmotor` / `load_allmotor` have never been logged (M-24) |
| Evidence | 50 Hz `state` log: the whole episode is replayable through the parity test |
| Test | first steps tethered on the stand with velocity zero, then slow commands, deadman held (Phase 2A week 6) |

## 13. Clock skew and config drift

Not failures that can happen at runtime by construction: no component subtracts timestamps across hosts, and the PC's only address is a hostname validated by connecting at startup. A stale hostname shows up as every link OFFLINE at the self-test, before anything is armed.

## 14. A once-only event is lost

An event is sent once. A link blip, a slow joiner or a restarted subscriber can miss it, and a `battery_low` that is missed would not fire again until the dog was recharged (Brian: `battery_low` is "never dropped").

| | |
|---|---|
| Detect (subscriber) | a gap in `seq` for the `event` topic (counted per topic), or its own startup |
| Subscriber does | reconciles from the level: `state.active` for the Pi's conditions, `owner.state` for the target, `goal` for the behaviour. A condition that is active and was never announced is treated as if its event had just arrived |
| Publisher does | nothing extra: the level rides in a periodic message it already sends |
| Test | start the voice after the battery crossed 20 %; drop S2 for a second across a `fell`. Both must still be spoken |

## 15. A handoff that cannot be trusted yet

`release` (joint mode → firmware) needs the pose `stop()` returns the legs to, and that pose is unmeasured without a prior `reset()` (Brian, 2026-11-08; M-8). `load_allmotor()` moves the joints before `adopt` can run (M-24). Until those rows are measured the arbiter refuses `ACTION` and `REST` with `rejected: handoff_unmeasured`, and `ESTOP` after a fall holds the joints without unloading (`unload_allmotor()` is itself unlogged): the operator recovers the dog by hand with the power button.

---

## Summary: who stops the dog, by failure

| Failure | Stopper | How fast |
|---|---|---|
| PC dies | Pi TTL → zero velocity → stand → hold | zero velocity ≤ `VELOCITY_TTL_TICKS` × 20 ms; the stand itself is unmeasured (M-28) |
| Pi dies, joint mode | nobody; the board holds the pose (to confirm on the stand) | — |
| Pi dies, firmware mode | nobody; the board keeps going → **why V3 never walks in firmware mode** | — |
| IMU bad | Pi safety layer | `IMU_STALE_TICKS` |
| Fall | Pi tilt cutoff | 1 tick after the filtered reading crosses |
| Target lost | PC controller → zero velocity | `TARGET_LOST_FRAMES` |
| Operator | HUD SPACE → `estop`; power button | one message; immediate |
