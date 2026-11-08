# IronBark V3 interfaces

Message schemas, transport and versioning. Every component is built against this file; a change here is a versioned change (§11). Companion docs: [architecture.md](architecture.md), [failure-modes.md](failure-modes.md), [decisions.md](decisions.md).

Transport: **ZMQ, JSON payloads** (Brian, 2026-11-08, decision 1). ROS2 appears only inside the Pi for Yahboom's SLAM stack in Phase 2, behind one bridge node that speaks these messages.

---

## 1. Conventions

**Envelope.** Every JSON message is one object with these fields first:

| Field | Type | Meaning |
|---|---|---|
| `v` | int | schema major version of this message type (§11). Currently `1` everywhere. |
| `type` | string | message type, e.g. `"state"`, `"velocity"` |
| `seq` | int | sender's per-socket counter, +1 per message, starts at 1 on process start. A gap means a drop; a reset means a restart. |
| `t_ms` | int | sender's monotonic clock in ms. **Intra-host only**: never subtract a Pi `t_ms` from a PC `t_ms` or the reverse (V2 measured 484 ms of skew under NTP). |

Pi-originated messages also carry `tick` (the runtime's 50 Hz tick counter). Expiry and ages on the Pi are expressed in ticks; on the PC in frames or the PC's own seconds.

**Units and frames.** SI unless stated: m, m/s, rad, rad/s, N·m. Angles on the serial link and in `joints_deg` are degrees because that is what the board speaks. Body frame: x forward, y left, z up (the sim's). Yaw rate positive = counter-clockwise from above (matches the board's `turnleft = +yaw`).

**Unknown fields are errors**, not tolerated extras (LESSONS B1). A receiver that gets an unknown field or type logs it, drops the message and raises `event: bad_message` once per sender until the sender's `seq` resets.

**Optional fields** are written as `null`, never omitted, so a missing key is a schema error rather than a silent default (LESSONS C2).

**Topics.** On PUB sockets the first ZMQ frame is the topic (`state`, `health`, `event`, `cmd`); the second is the JSON. SUB sockets subscribe by topic. The camera and audio streams are binary, §7–§8.

---

## 2. Socket table

The Pi binds every socket. The PC connects to `PI_HOST` (`raspberrypi.local`, DHCP-reserved fallback `192.168.68.56`). Nothing on the Pi needs the PC's address.

| # | Purpose | Pattern | Pi | PC | Port | Topics / format |
|---|---|---|---|---|---|---|
| S1 | commands PC → Pi | PUB → SUB | SUB **bind** `tcp://*:5556` | PUB connect | 5556 | topic `cmd`; types `velocity`, `action`, `mode`, `estop`, `clear_estop`, `noop` |
| S2 | telemetry Pi → PC | PUB → SUB | PUB **bind** `tcp://*:5558` | SUB connect, subscribe `state`, `health`, `event` | 5558 | JSON per topic |
| S3 | handshake | REQ → REP | REP **bind** `tcp://*:5557` | REQ connect | 5557 | `hello` / `hello_reply` |
| S4 | camera Pi → PC | PUSH → PULL | PUSH **bind** `tcp://*:50505`, `SNDHWM=2` | PULL connect, `CONFLATE=1` | 50505 | binary, §7 |
| S5 | lidar Pi → PC (Phase 2) | PUSH → PULL | PUSH **bind** `tcp://*:50507` | PULL connect, `CONFLATE=1` | 50507 | JSON scan, §7 |
| S6 | audio PC → Pi | PUSH → PULL | PULL **bind** `tcp://*:5560` | PUSH connect | 5560 | multipart, §8 |
| I1 | Pi internal: `cam_sender`, `lidar_reader`, `audio_player` → `runtime` | PUSH → PULL | PULL bind `ipc:///tmp/ironbark/runtime.sock` | — | — | `cam_health`, `lidar_sectors`, `speech` |
| P1 | PC internal: `perception` → `owner_tracker` → `follow_controller`, `brain`, `voice`, `hud` | PUB → SUB | — | `tcp://127.0.0.1:5570` (perception), `:5571` (tracker), `:5572` (brain goals) | — | `tracks`, `owner`, `goal` |

`LINGER=0` on every socket. S1 is drained to the newest message every tick (as V2 did); S4/S5 use `CONFLATE` so a reconnect never delivers a 3.87 s-old frame (V2 measured that burst). Port 5557 (V1 teleop) and 5560 are unused in V2, so nothing collides; 5556/5558/50505/50507 keep their V2 numbers.

---

## 3. Handshake and startup self-test

Every socket pair gets a live end-to-end check at startup and the result is shown on the HUD per pair (LESSONS C1). The PC runs the sequence; the Pi just answers.

1. **S3 hello.** PC sends `{"v":1,"type":"hello","seq":1,"t_ms":…,"host":"pc","schema":{"state":1,"velocity":1,…},"git":"<sha>"}`. The Pi replies within 500 ms (PC clock):

```json
{"v":1,"type":"hello_reply","seq":1,"t_ms":…,"tick":1203,"host":"pi",
 "schema":{"state":1,"health":1,"event":1,"velocity":1,"action":1,"mode":1,"audio":1},
 "git":"<sha>","fw":"M-4.0.1-Y","xgolib_sha256":"4371a4…","mode":"BOOT",
 "sockets":[{"id":"S1","bind":"tcp://*:5556"},{"id":"S2","bind":"tcp://*:5558"},…],
 "compatible":true,"reason":null}
```

   `compatible=false` with a `reason` (e.g. `"velocity v2 > pi v1"`) means the Pi will reject commands of that type. Repeated every 5 s as a liveness probe that works even if S2 is broken.
2. **S2 live.** The PC must receive a `state` message within 2 s (PC clock). Link state goes OFFLINE → LIVE only on the first *real* message; nothing is pre-filled.
3. **S1 live.** The PC publishes `{"type":"noop","seq":n}`; within 10 `state` messages `last_cmd_seq` must equal `n`. This proves the command path end to end before anything can move.
4. **S4 live.** First camera frame received, with `health.camera.frame_mean` in a plausible band (a lens cap reads near 0: LESSONS D2).
5. **S5 live** (Phase 2): first scan with ≥ `LIDAR_MIN_POINTS` valid points, else the HUD shows LIDAR DARK and the Pi raises the degraded notice at mode entry.
6. **S6 live.** The PC sends a 100 ms silent PCM utterance; the Pi's `event: speech_ended` for that `utterance_id` must arrive.

Any failed step blocks arming on the HUD. The sequence is also the smoke test for a fresh deployment (LESSONS D1).

---

## 4. Pi → PC: `state` (50 Hz)

```json
{"v":1,"type":"state","seq":48811,"t_ms":976230,"tick":48811,
 "mode":"POLICY","owner":"policy",
 "imu":{"ready":true,"status":"live","frozen_ticks":0,"age_ticks":1,
        "gyro_rps":[0.01,-0.02,0.30],"accel_mps2":[0.1,-0.2,-9.7],"rpy_deg":[0.8,-1.1,214.6]},
 "joints_deg":[12.1,43.7,-0.6, …12 values…],
 "joints_cmd_deg":[12.5,44.0,-0.5, …],
 "joints_changed_tick":[48803,48809,48796, …],
 "cmd":{"vx":0.30,"vy":0.00,"wz":0.15,"ttl_left":11,"src":"pc","deadman":true},
 "last_cmd_seq":9120,
 "action":null,
 "battery_pct":74,
 "lidar":{"front_min_mm":null,"age_scans":null},
 "safety":{"velocity_clamped":false,"joints_clamped":0,"degraded":[]},
 "fw":"M-4.0.1-Y"}
```

| Field | Type / unit | Notes |
|---|---|---|
| `mode` | enum `BOOT, IDLE_HOLD, POLICY, ACTION, REST, ESTOP` | architecture §3.2 |
| `owner` | enum `none, runtime, policy, firmware` | who wrote the last motor command |
| `imu.ready` | bool | the first-nonzero-yaw latch (predicate, never a timer) |
| `imu.status` | enum `live, frozen, rejected, never` | from the sanity filter; `never` until the first accepted read |
| `imu.frozen_ticks` | int | ticks the block has been identical (0 when live) |
| `imu.age_ticks` | int | ticks since the last accepted read |
| `imu.gyro_rps` | [3] rad/s body | **after** unit conversion; the unit is `# MEASURE:` (xgolib implies °/s, V2 wrote rad/s) |
| `imu.accel_mps2` | [3] m/s² body | raw from the board |
| `imu.rpy_deg` | [3] deg | yaw is unwrapped and drifts (0.4 °/s typical on a stand): for display only, never for control |
| `joints_deg` | [12] deg | readback, xgolib id order `11,12,13,21,22,23,31,32,33,41,42,43` = fl calf, fl thigh, fl hip, fr…, br…, bl… (verified map, `s2_joint_map.py`) |
| `joints_cmd_deg` | [12] deg | the angles actually written this tick (after clamps, before byte rounding) |
| `joints_changed_tick` | [12] int | tick each readback value last changed; readback is a ~105–130 ms round-robin |
| `cmd` | object | the velocity the policy saw this tick, after TTL, deadman, clamps and reflex; `src` ∈ `pc, brain, teleop, watchdog, reflex, none` |
| `last_cmd_seq` | int | `seq` of the newest S1 message consumed (the liveness echo) |
| `action` | null or `{"name":"sit","id":…,"ticks_left":…}` | while in `ACTION` |
| `battery_pct` | int 0–100 | integer percent, the only battery readout the SDK has |
| `lidar` | `front_min_mm`, `age_scans` or nulls | Phase 2; `age_scans` counts scans, not seconds |
| `safety.degraded` | [string] | active degraded notices, e.g. `"lidar_dark"`, `"imu_frozen"`, `"deadman_off"` |

---

## 5. Pi → PC: `health` (1 Hz)

```json
{"v":1,"type":"health","seq":976,"t_ms":976000,"tick":48800,
 "loop":{"hz":49.8,"tick_ms_p50":17.9,"tick_ms_p99":19.6,"overruns":0},
 "serial":{"write_ms_p50":9.7,"read_motor_ms_p50":16.1,"read_imu_ms_p50":4.5,"bad_reads":0},
 "imu":{"fresh_value_hz":11.2,"call_hz":25.0,"rejected":3,"freezes":2,"longest_freeze_ticks":51},
 "pi":{"throttled_hex":"0x0","cpu_temp_c":61.5,"wifi_rssi_dbm":-52,"wifi_power_save":false,"uptime_s":8812},
 "camera":{"status":"ok","fps":19.9,"frame_mean":114.2,"frame_std":48.7,"read_fail_streak":0,"usb_resets":0},
 "lidar":{"status":"dark","scan_hz":null,"points_per_scan":null},
 "audio":{"status":"ok","device":"…","utterances":14},
 "cmd":{"rx_hz":19.8,"rejected":0,"rejected_reason":null,"stream_lost_count":0},
 "versions":{"runtime":"<sha>","xgolib":"1.1.10","onnx_model":"EXP-020-s43/model_1499.onnx"}}
```

`imu.fresh_value_hz` is the rate at which the IMU block *changed*, separate from `call_hz` (LESSONS A3, the "343 Hz" mistake). `throttled_hex` is `vcgencmd get_throttled`, logged every second so a Pi hang leaves evidence (`findings/2026-09-30-pi-hang.md`).

---

## 6. Pi → PC and PC → PC: `event`

```json
{"v":1,"type":"event","seq":77,"t_ms":976102,"tick":48805,
 "name":"fell","source":"pi","detail":{"tilt_deg":52.3,"mode_before":"POLICY"}}
```

Events fire once per crossing. Each has a clearing counterpart where a state can return. The voice subscribes to these and keeps its own pacing; it never re-derives them (decision 6).

| `name` | source | fires when | clears with | `detail` |
|---|---|---|---|---|
| `imu_ready` | pi | first nonzero yaw latched | — | `tick` |
| `imu_frozen` / `imu_ok` | pi | frozen or rejected for ≥ `IMU_STALE_TICKS` / first accepted read after | each other | `frozen_ticks` |
| `fell` / `upright` | pi | `is_fallen` true (Brian's `metrics.py`) / tilt back under `FALL_TILT_DEG` and operator cleared | each other | `tilt_deg`, `mode_before` |
| `battery_low` / `battery_ok` | pi | ≤ `BATTERY_LOW_PCT` (20) / ≥ `BATTERY_REARM_PCT` (30) | each other | `pct` |
| `battery_critical` | pi | ≤ `BATTERY_CRITICAL_PCT` | `battery_ok` | `pct` |
| `mode_changed` | pi | every arbiter transition | — | `from`, `to`, `reason`, `degraded: [..]` (LESSONS C3) |
| `estop` / `estop_cleared` | pi | e-stop entered / operator cleared | each other | `reason` |
| `cmd_stream_lost` / `cmd_stream_ok` | pi | no S1 message for `CMD_LOST_TICKS` / first message after | each other | `ticks` |
| `action_result` | pi | an `action` request is accepted, rejected or finished | — | `request_id`, `status` ∈ `accepted, rejected, done`, `reason` |
| `camera_stalled` / `camera_ok` | pi | read-fail streak ≥ `CAM_FAIL_STREAK` / frames flowing again | each other | `streak`, `usb_reset` |
| `lidar_dark` / `lidar_ok` | pi | no valid scan for `LIDAR_DARK_SCANS` / scans again | each other | — |
| `speech_started` / `speech_ended` | pi (audio_player) | first PCM write / buffer drained or stopped | — | `utterance_id`, `pc_t_ms` (echo of the PC's `t_ms`, for a PC-clock round trip), `interrupted` |
| `bad_message` | pi or pc | unknown type/field/version from a sender | sender `seq` reset | `from`, `type`, `reason` |
| `target_found` / `target_lost` / `target_reacquired` | pc:owner_tracker | first lock / unseen ≥ `TARGET_LOST_FRAMES` / seen again after lost | — | `track_id`, `confidence` |
| `owner_verified` / `owner_rejected` | pc:owner_tracker | VLM verify result | — | `track_id`, `confidence`, `latency_s` |
| `rescan_started` / `rescan_failed` | pc:owner_tracker | sweep begins / `RESCAN_MAX_ATTEMPTS` exhausted | — | `bearing_deg`, `attempt` |
| `owner_verify_needed` | pc:owner_tracker | rescans exhausted → voice fallback ("that you, bro?") | `owner_verified` | — |
| `behavior_changed` | pc:brain | goal changed | — | `from`, `to` |
| `keyword` (Phase 2) | pi (voice module) | CSK4002 phrase code received | — | `code`, `phrase` |
| `speech_text` (Phase 2, reserved) | pc | free-text STT result | — | `text`, `confidence` |

---

## 7. PC → Pi: commands (S1, topic `cmd`)

### `velocity` (20 Hz from the follow controller, teleop or the brain)

```json
{"v":1,"type":"velocity","seq":9120,"t_ms":5123400,
 "vx":0.30,"vy":0.00,"wz":0.15,"ttl_ticks":15,"deadman":true,"src":"pc"}
```

| Field | Range | Pi behaviour |
|---|---|---|
| `vx`, `vy`, `wz` | body frame; trained ranges vx −0.5…0.6 m/s, vy ±0.3 m/s, wz ±0.8 rad/s | clamped; `safety.velocity_clamped` set |
| `ttl_ticks` | 1…`VELOCITY_TTL_MAX` | the command is valid for this many Pi ticks, then the arbiter's velocity is zero. Frame count, never seconds. |
| `deadman` | bool | with `REQUIRE_DEADMAN`, false → velocity zero |
| `src` | `pc, teleop, brain` | shown on the HUD; `brain` is capped at `BRAIN_VELOCITY_TTL_MAX` ticks |

Ignored outside `POLICY` (the arbiter answers nothing; the HUD sees `mode`).

### `action`

```json
{"v":1,"type":"action","seq":9121,"t_ms":…,"request_id":"a7f3","name":"sit"}
```

`name` must be in the Pi's allow-list (`pi/actions_allowlist.json`: `name`, xgolib `id`, `budget_ticks`, `requires_mode: IDLE_HOLD`, `min_battery_pct`). The brain only ever sees names. Reply: `event: action_result`. The ids and durations are `# MEASURE:` (read `action()` ids from the xgolib source on the Pi; time each on the stand).

### `mode`

```json
{"v":1,"type":"mode","seq":9122,"t_ms":…,"request":"POLICY","src":"pc"}
```

`request` ∈ `IDLE_HOLD, POLICY, REST`. (`ACTION` is entered through `action`; `ESTOP` through `estop`.) Reply: `event: mode_changed` or `event: action_result` with `status: rejected` and a reason such as `"walking"`, `"imu_not_ready"`, `"battery_critical"`, `"estop"`.

### `estop` / `clear_estop`

```json
{"v":1,"type":"estop","seq":9123,"t_ms":…,"src":"teleop","reason":"operator"}
```

`clear_estop` is honoured only from `src: teleop` (the HUD), never from the brain.

### `noop`

Liveness probe for the self-test and the HUD; the Pi only updates `last_cmd_seq`.

---

## 8. Binary streams

### Camera (S4), unchanged from V2

One ZMQ message per frame: `struct '<qI'` header (int64 capture time in µs on the Pi's clock; uint32 JPEG length) followed by the JPEG bytes. 640×480 MJPG, 20 fps target, quality 75 (measured 7.7 Mbps, 48 kB/frame). The capture stamp orders frames and detects stalls; it is never subtracted from a PC time. Frame statistics go in `health.camera`.

### Lidar (S5), V1 schema

`{"v":1,"type":"scan","seq":…,"t_ms":…,"n":450,"pts":[{"a":0.0,"d":1234,"c":200},…]}` with `a` in degrees (0 = forward, counter-clockwise positive), `d` in mm, `c` the MS200 confidence byte. The Pi-internal `lidar_sectors` message carries only `{"front_min_mm","left_min_mm","right_min_mm","points","scan_seq"}` so the reflex never parses a full scan.

### Audio (S6)

Multipart, two frames. Frame 0 (JSON): `{"v":1,"type":"audio","seq":…,"t_ms":…,"utterance_id":"u19","chunk":3,"final":false,"rate_hz":24000,"width_bytes":2,"channels":1}`. Frame 1: raw little-endian 16-bit mono PCM, whole samples only. A single-frame `{"type":"audio_ctl","cmd":"stop","utterance_id":"u19"}` interrupts (a fall cuts a line; battery lines queue, per Brian). The player answers with `speech_started` / `speech_ended` events carrying the first chunk's `t_ms` as `pc_t_ms`.

---

## 9. Policy I/O contract (Pi runtime ↔ ONNX model)

Must match the trained task exactly. Today's deployment target is `IronBark-S2-Walk-Flat-Brian-StaleJoints` (EXP-010 lineage); if the task changes, this section is versioned with it.

**Observation, 35 floats, in this order** (Luwu's actor layout minus `joint_vel`, which Brian dropped because the dog has no velocity readback):

| Slot | Term | Size | Source on the dog | Notes |
|---|---|---|---|---|
| 0–2 | `base_ang_vel` | 3 | IMU gyro, body frame, rad/s, after unit conversion; held last-good value while frozen/rejected | sim training noise ±1.0 |
| 3–5 | `projected_gravity` | 3 | from filtered roll/pitch: `(sin p, −cos p sin r, −cos p cos r)` (the formula the voice already uses); held while frozen | sign conventions vs the sim `# MEASURE:` |
| 6–8 | `command` | 3 | arbiter's `(vx, vy, wz)` after TTL/clamps | the sim zeroes a command whose norm ≤ 0.1 |
| 9–10 | `phase` | 2 | `sin, cos` of `2π·((tick·0.02 s) mod 0.4 s)/0.4 s` from the tick counter; **both 0 when the command norm < 0.1** | read from `mdp.phase` (luwu_mjlab): the sim's clock is the episode step counter, so the Pi's tick counter is the same thing; the counter restarts at each `adopt` |
| 11–22 | `joint_pos` | 12 | `joints_deg` → rad − default pose, **sim joint order** `fl, fr, br, bl × (hip, thigh, calf)` via `s2_joint_map.py`; raw held readback, no interpolation | staleness is part of the trained model (EXP-010) |
| 23–34 | `actions` | 12 | last policy output, sim order | zeros on the first tick after `adopt` |

**Action, 12 floats, sim order**: joint target (rad) = `default_joint_pos + 0.25 × action`, then → degrees → xgolib order → sign/offset per joint (`# MEASURE:` before deployment) → clamps → nearest byte.

**Parity test** (Phase 2A week 6): a logged real-dog `state` sequence replayed through the Pi obs assembly and through the sim's observation manager must agree to within the sim's noise; the ONNX output on both must agree to 1e-5.

---

## 10. Configuration

Per machine, only what it uses (LESSONS C4):

| Machine | Variable | Default | Note |
|---|---|---|---|
| PC | `PI_HOST` | `raspberrypi.local` | the only address the PC needs |
| PC | `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY` | — | never shipped to the Pi |
| PC | `OWNER_PHOTOS_DIR` | `~/dev/ironbark_private/owner/` | multi-reference photos; outside the repo |
| Pi | `MOTION_PORT` | `/dev/ttyAMA0` | measured |
| Pi | `LIDAR_PORT` | unset | `# MEASURE:` trace the cable; refuses to start the reader while unset |
| Pi | `ONNX_MODEL` | — | path + sha256 pinned in `health.versions` |
| Pi | `REQUIRE_DEADMAN` | `true` | Brian's call per session type |

Thresholds live in `pi/safety_config.py` and `pc/follow_config.py`, each constant with a tag comment: `# measured: <source>`, `# vendor: <doc>`, `# design: <who, date>`, or `# MEASURE: <procedure>`. A `MEASURE` constant is `None` in code; using it raises, and the mode that needs it reports `degraded` at entry instead of running.

---

## 11. Versioning

- `v` is the **major** version of that message type. A receiver accepts `v == its own`. Adding an optional field is a minor change, documented here, and does not bump `v`; a receiver must still reject fields it doesn't know (so both sides deploy together, which is the point).
- The `hello` exchange lists every type's `v` on both sides; the Pi sets `compatible=false` and refuses that type until the versions match. The HUD shows the mismatch; nothing moves.
- Schema changes are recorded in a table at the bottom of this file with date, type, old → new, and the reason.
- The policy I/O contract (§9) carries the task name and the ONNX file's sha256 in `health.versions`; a mismatch between the runtime's expected layout and the model's input size is a startup failure.

| Date | Type | Change | Why |
|---|---|---|---|
| 2026-11-08 | all | v1 drafted | V3 architecture |
