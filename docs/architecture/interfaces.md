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
| `seq` | int | sender's counter **per topic** on that socket, +1 per message, starts at 1 on process start. A subscriber to one topic sees no gap unless a message was dropped; a reset means the sender restarted. |
| `t_ms` | int | sender's monotonic clock in ms. **Intra-host only**: never subtract a Pi `t_ms` from a PC `t_ms` or the reverse (V2 measured 484 ms of skew under NTP). |

Pi-originated messages also carry `tick` (the runtime's 50 Hz tick counter); PC-originated messages have no `tick` field. Expiry and ages on the Pi are expressed in ticks; on the PC in frames or the PC's own seconds.

**Edges and levels.** An event is an edge, sent once. Every event that has a clearing counterpart also has a level in a periodic message from the same owner: `state.active` for the Pi (§4), `owner.state` for the tracker and `goal` for the brain (§12). A subscriber reconciles from the level at startup and after any `seq` gap, so a lost edge is never a lost fact (e.g. a `battery_low` missed in a link blip is still in the next `state.active`).

**Units and frames.** SI unless stated: m, m/s, rad, rad/s, N·m. Angles on the serial link and in `joints_deg` are degrees because that is what the board speaks. Body frame: x forward, y left, z up (the sim's). Yaw rate positive = counter-clockwise from above (matches the board's `turnleft = +yaw`).

**Unknown fields are errors**, not tolerated extras (LESSONS B1). A receiver that gets an unknown field or type logs it, drops the message and raises `event: bad_message` once per sender until the sender's `seq` resets.

**Optional fields** are written as `null`, never omitted, so a missing key is a schema error rather than a silent default (LESSONS C2).

**Topics.** On PUB sockets the first ZMQ frame is the topic (`state`, `health`, `event`, `cmd` on the Pi link; `tracks`, `owner`, `goal`, `say`, `cmd_request`, `event` on the PC bus, §12); the second is the JSON. SUB sockets subscribe by topic. The camera and audio streams are binary, §8.

---

## 2. Socket table

The Pi binds every socket. The PC connects to `PI_HOST` (`raspberrypi.local`, DHCP-reserved fallback `192.168.68.56`). Nothing on the Pi needs the PC's address.

| # | Purpose | Pattern | Pi | PC | Port | Topics / format |
|---|---|---|---|---|---|---|
| S1 | commands PC → Pi | PUB → SUB | SUB **bind** `tcp://*:5556` | PUB connect; **one writer, the `gateway`** (§12) | 5556 | topic `cmd`; types `velocity`, `action`, `mode`, `estop`, `clear_estop`, `noop` |
| S2 | telemetry Pi → PC | PUB → SUB | PUB **bind** `tcp://*:5558` | SUB connect, subscribe `state`, `health`, `event` | 5558 | JSON per topic |
| S3 | handshake | REQ → REP | REP **bind** `tcp://*:5557` | REQ connect | 5557 | `hello` / `hello_reply` |
| S4 | camera Pi → PC | PUSH → PULL | PUSH **bind** `tcp://*:50505`, `SNDHWM=2` | PULL connect, `CONFLATE=1` | 50505 | binary, §8 |
| S5 | lidar Pi → PC (Phase 2) | PUSH → PULL | PUSH **bind** `tcp://*:50507` | PULL connect, `CONFLATE=1` | 50507 | JSON scan, §8 |
| S6 | audio PC → Pi | PUSH → PULL | PULL **bind** `tcp://*:5560` | PUSH connect, `IMMEDIATE=1`, `SNDHWM=AUDIO_SNDHWM`, non-blocking send | 5560 | multipart, §8 |
| I1 | Pi internal: `cam_sender`, `lidar_reader`, `audio_player`, `voice_module_reader` → `runtime` | PUSH → PULL | PULL bind `ipc:///tmp/ironbark/runtime.sock` | — | — | `cam_health`, `lidar_sectors`, `speech`, `keyword` |
| P1–P5 | PC bus: each PC process binds one loopback PUB | PUB → SUB | — | `tcp://127.0.0.1:5570`–`5574` | — | `tracks`, `owner`, `goal`, `say`, `cmd_request`, `event`; §12 |

`LINGER=0` on every socket. S1 is drained to the newest message every tick (as V2 did); S4/S5 use `CONFLATE` so a reconnect never delivers a 3.87 s-old frame (V2 measured that burst). S6 must never queue while the Pi is unreachable, or old speech would play on reconnect (§8). Port 5557 (V1 teleop) and 5560 are unused in V2, so nothing collides; 5556/5558/50505/50507 keep their V2 numbers.

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
6. **S6 live.** The PC sends a 100 ms silent PCM utterance; the Pi's `event: speech_ended` for that `utterance_id` must arrive. This proves the path and that a device opened, not that sound came out: the operator's ears are the check.

**Steps 1–3 block arming.** Steps 4–6 never do: a failure raises a degraded notice (`camera_down`, `lidar_dark`, `audio_down`) on the HUD and blocks only the behaviour that needs that stream (FOLLOW needs the camera; nothing about motion needs audio). The sequence is also the smoke test for a fresh deployment (LESSONS D1).

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
 "active":["battery_low"],
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
| `safety.degraded` | [string] | active degraded notices, e.g. `"lidar_dark"`, `"imu_frozen"`, `"deadman_off"`, `"audio_down"` |
| `active` | [string] | every paired Pi condition that is true right now, by its event name: any of `imu_frozen`, `fell`, `battery_low`, `battery_critical`, `estop`, `cmd_stream_lost`, `camera_stalled`, `lidar_dark`. The level behind the §6 edges |

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
 "voice_module":{"status":"ok","port":"/dev/ttyUSB0","frames":2},
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

Events fire once per crossing. Each has a clearing counterpart where a state can return, and a level in a periodic message (§1, edges and levels). The voice subscribes to these and keeps its own pacing; it never re-derives them (decision 6).

Where each source publishes, always on topic `event`: `pi` on S2; `pc:owner_tracker` on P2 (`:5571`); `pc:brain` on P3 (`:5572`). A subscriber that wants every event connects to all three and merges them; `source` says which owner spoke. PC-origin events carry no `tick`. Which events the voice speaks is the voice's own list (decisions.md D-19), not this table.

| `name` | source | fires when | clears with | `detail` |
|---|---|---|---|---|
| `imu_ready` | pi | first nonzero yaw latched | — | `tick` |
| `imu_frozen` / `imu_ok` | pi | frozen or rejected for ≥ `IMU_STALE_TICKS` / first accepted read after | each other | `frozen_ticks` |
| `fell` / `upright` | pi | `is_fallen` true (Brian's `metrics.py`) / tilt back under `FALL_TILT_DEG` and operator cleared | each other | `tilt_deg`, `mode_before` |
| `battery_low` / `battery_ok` | pi | ≤ `BATTERY_LOW_PCT` (20) / > `BATTERY_REARM_PCT` (30): Brian's T3, "re-arms above 30%" | each other | `pct` |
| `battery_critical` | pi | ≤ `BATTERY_CRITICAL_PCT` | `battery_ok` | `pct` |
| `mode_changed` | pi | every arbiter transition | — | `from`, `to`, `reason`, `degraded: [..]` (LESSONS C3) |
| `estop` / `estop_cleared` | pi | e-stop entered / operator cleared | each other | `reason` |
| `cmd_stream_lost` / `cmd_stream_ok` | pi | no S1 message for `CMD_LOST_TICKS` / first message after | each other | `ticks` |
| `action_result` | pi | an `action` request is accepted, rejected or finished | — | `request_id`, `status` ∈ `accepted, rejected, done`, `reason` |
| `camera_stalled` / `camera_ok` | pi | read-fail streak ≥ `CAM_FAIL_STREAK` / frames flowing again | each other | `streak`, `usb_reset` |
| `lidar_dark` / `lidar_ok` | pi | no valid scan for `LIDAR_DARK_SCANS` / scans again | each other | — |
| `speech_started` / `speech_ended` | pi (audio_player) | first PCM write to the device / `final` chunk received **and** device buffer drained, or a `stop` took effect. A mid-line underrun is not an end | — | both: `utterance_id`, `pc_t_ms` (echo of the first chunk's `t_ms`). started: `device_latency_ms`. ended: `played_bytes`, `interrupted` |
| `bad_message` | pi or pc | unknown type/field/version from a sender | sender `seq` reset | `from`, `type`, `reason` |
| `target_found` / `target_lost` / `target_reacquired` | pc:owner_tracker | first lock / unseen ≥ `TARGET_LOST_FRAMES` / seen again after lost | — | `track_id`, `confidence` |
| `owner_verified` / `owner_rejected` | pc:owner_tracker | VLM verify result | — | `track_id`, `confidence`, `latency_s` |
| `rescan_started` / `rescan_failed` | pc:owner_tracker | sweep begins / `RESCAN_MAX_ATTEMPTS` exhausted | — | `bearing_deg`, `attempt` |
| `owner_verify_needed` | pc:owner_tracker | rescans exhausted → voice fallback ("that you, bro?") | `owner_verified` | — |
| `behavior_changed` | pc:brain | goal changed | — | `from`, `to` |
| `keyword` (Phase 2) | pi (voice_module_reader) | the voice board sends a frame on its serial port | — | `frame` (raw ASCII, e.g. `"$B000#"`), `code` (e.g. `"000"`) |
| `speech_text` (reserved; decisions.md D-22) | pc:voice | free-text STT result | — | `text`, `confidence` (null when the STT gives none). Never written to a committed log |

Measured 2026-11-08 by the voice session with Brian (`docs/voice/s2-voice-module.md`, branch `feature/voice`): saying "Hello Yahboom" made the board (a YB-MVE02-V2.0) send `$B000#` at 115200 baud on `/dev/ttyUSB0` and answer through its own speaker. That `000` is the wake word is inferred from timing; the other codes are unmeasured (M-23). Yahboom's own voice samples drive the dog from spoken commands; nothing in V3 runs them.

---

## 7. PC → Pi: commands (S1, topic `cmd`)

S1 has one writer, the `gateway` (§12). Other PC processes ask for these messages with `cmd_request`; the gateway adds `deadman`, stamps `seq`, and forwards. So `last_cmd_seq` in `state` has exactly one meaning.

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

Multipart, two frames per chunk. Frame 0 (JSON): `{"v":1,"type":"audio","seq":…,"t_ms":…,"utterance_id":"u19","chunk":3,"final":false,"rate_hz":24000,"width_bytes":2,"channels":1}`. Frame 1: raw little-endian 16-bit mono PCM, whole samples only. The last chunk has `final:true` and may carry **zero bytes** of PCM (a TTS stream only knows its last chunk after it ends).

Control, one frame: `{"v":1,"type":"audio_ctl","seq":…,"t_ms":…,"cmd":"stop","utterance_id":"u19"}` (a fall cuts a line; battery lines queue, per Brian).

**Sender (voice).** `IMMEDIATE=1`, so nothing queues while the Pi is unreachable; `SNDHWM = AUDIO_SNDHWM`, bounded but above the longest clip in chunks; sends are non-blocking, and a send that would block drops the whole line. Without these, a link drop would replay up to ~50 s of old speech on reconnect, and the Pi has no way to age audio. This is ZMQ's documented behaviour, not yet tested here (M-22).

**Player (Pi).** PUSH does not pace, so a cached clip arrives in one burst and the player owns the pacing. It receives on a thread separate from playback, so an `audio_ctl stop` is seen while a clip plays; `stop` discards the queued PCM of that utterance and **drops** the device buffer (drop, not drain). Stop-to-silence time is `# MEASURE:` (M-21).

**Events.** `speech_started` at the first PCM write to the device, with `device_latency_ms` (sound leaves the speaker that much after a write). `speech_ended` when the `final` chunk has been received and the device buffer has drained, or when a `stop` took effect (`interrupted: true`), with `played_bytes`. Both echo the first chunk's `t_ms` as `pc_t_ms`. The PC-clock round trip that gives is an **upper bound** on event-to-sound: it includes the Pi → PC leg and the hop through the runtime. If `speech_ended` never arrives, the voice times out from the PCM byte count.

**No device today.** The dog has no speaker the Pi can reach (measured 2026-11-08; decisions.md D-17). Until one exists the voice keeps playing on the PC and S6 is unused.

---

## 9. Policy I/O contract (Pi runtime ↔ ONNX model)

Must match the trained task exactly. Today's deployment target is `IronBark-S2-Walk-Flat-Brian-StaleJoints` (EXP-010 lineage); if the task changes, this section is versioned with it.

**Observation, 35 floats, in this order** (Luwu's actor layout minus `joint_vel`, which Brian dropped because the dog has no velocity readback):

| Slot | Term | Size | Source on the dog | Notes |
|---|---|---|---|---|
| 0–2 | `base_ang_vel` | 3 | IMU gyro, body frame, rad/s, after unit conversion (M-3); held last-good value while frozen/rejected | sim training noise ±1.0. No policy has trained with freezes yet: they are scoring-only in the sim |
| 3–5 | `projected_gravity` | 3 | from filtered roll/pitch: `(sin p, −cos p sin r, −cos p cos r)` (the formula the voice already uses); held while frozen | axes and signs vs the sim are `# MEASURE:` (M-25, gate) |
| 6–8 | `command` | 3 | arbiter's `(vx, vy, wz)` after TTL/clamps | the sim zeroes a command whose norm ≤ 0.1 |
| 9–10 | `phase` | 2 | `sin, cos` of `2π·((tick·0.02 s) mod 0.4 s)/0.4 s` from the tick counter; **both 0 when the command norm < 0.1** | read from `mdp.phase` (luwu_mjlab): the sim's clock is the episode step counter, so the Pi's tick counter is the same thing; the counter restarts at each `adopt` |
| 11–22 | `joint_pos` | 12 | `joints_deg` → sign and zero offset per joint (M-4) → rad − default pose, **sim joint order** `fl, fr, br, bl × (hip, thigh, calf)` via `s2_joint_map.py`; raw held readback, no interpolation | staleness is part of the trained model (EXP-010). xgolib's per-leg suffixes 1/2/3 are calf/thigh/hip, the reverse of the sim's order |
| 23–34 | `actions` | 12 | last policy output, sim order | zeros on the first tick after `adopt` |

**Action, 12 floats, sim order**: joint target (rad) = `default_joint_pos + 0.25 × action`, then → degrees → xgolib order → sign/offset per joint (`# MEASURE:` before deployment) → clamps → nearest byte.

**Checked against an exported model** (joint-control session, 2026-11-08, EXP-025's `policy.onnx`): input [1, 35], output [1, 12], `observation_names` in the order above, `action_scale` 0.25, phase period 0.4 s. **The observation normaliser is inside the ONNX graph**, so the runtime feeds raw values.

**The default pose is still a placeholder.** `default_joint_pos` (hip 0, thigh 1.0, calf 0 rad) is the Mini2S value (`assets/s2.py`, `# MEASURE:`). If M-4 finds the S2 needs a different default, every policy trained so far, the search winner included, has to be retrained. So M-4 is the first hardware session (Brian, 2026-11-08).

**Tick clock.** `phase` assumes one tick is 0.02 s. The loop is paced to 20 ms by a monotonic clock (Brian, 2026-11-08: pacing only); an overrun tick is counted, never caught up.

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
| Pi | `AUDIO_DEVICE` | unset | `# MEASURE:` (M-13). No usable device today: the speaker plugs into the voice board, and the Pi's HifiBerry output was inaudible. The player refuses to start while unset and reports `audio_down` |
| Pi | `VOICE_MODULE_PORT` | `/dev/ttyUSB0` @ 115200 | measured 2026-11-08 (CH340, serial only) |
| PC | `AUDIO_SNDHWM` | 100 chunks | design: above the longest cached clip (~66 chunks of 50 ms) |
| Pi | `REQUIRE_DEADMAN` | `true` | Brian's call per session type |

Thresholds live in `pi/safety_config.py` and `pc/follow_config.py`, each constant with a tag comment: `# measured: <source>`, `# vendor: <doc>`, `# design: <who, date>`, or `# MEASURE: <procedure>`. A `MEASURE` constant is `None` in code; using it raises, and the mode that needs it reports `degraded` at entry instead of running.

---

## 11. Versioning

- `v` is the **major** version of that message type. A receiver accepts `v == its own`. Adding an optional field is a minor change, documented here, and does not bump `v`; a receiver must still reject fields it doesn't know (so both sides deploy together, which is the point).
- The `hello` exchange lists every type's `v` on both sides; the Pi sets `compatible=false` and refuses that type until the versions match. The HUD shows the mismatch; nothing moves.
- Schema changes are recorded in the change log (§13) with date, type, old → new, and the reason.
- The policy I/O contract (§9) carries the task name and the ONNX file's sha256 in `health.versions`; a mismatch between the runtime's expected layout and the model's input size is a startup failure.

---

## 12. PC bus (PC-internal)

Each PC process binds one PUB on loopback and publishes its own topics. Nothing here reaches the Pi except through the gateway. Envelope rules as §1, without `tick`.

| # | Publisher | Bind | Topics | Subscribers |
|---|---|---|---|---|
| P1 | `perception` | `tcp://127.0.0.1:5570` | `tracks` | owner_tracker, hud |
| P2 | `owner_tracker` | `tcp://127.0.0.1:5571` | `owner`, `event` | follow_controller, brain, voice, hud |
| P3 | `brain` | `tcp://127.0.0.1:5572` | `goal`, `event`, `say`, `cmd_request` | follow_controller, voice, hud + gateway |
| P4 | `follow_controller` | `tcp://127.0.0.1:5573` | `cmd_request` | gateway |
| P5 | `hud` | `tcp://127.0.0.1:5574` | `goal` (operator's, wins over the brain's) | follow_controller |

**Gateway: the single S1 writer.** It runs in the HUD process and holds the only socket connected to S1. Armed, it forwards each `cmd_request` as it arrives, adding `deadman` from the key state. Disarmed, it forwards nothing and sends a zero `velocity` with `deadman: false` at 20 Hz, so the link stays LIVE and `last_cmd_seq` keeps advancing. Disarming is therefore one choke point on the PC, in front of the Pi's own checks. `estop` and `clear_estop` come only from the HUD.

### `tracks` (perception, one per camera frame)

```json
{"v":1,"type":"tracks","seq":5121,"t_ms":5123390,"frame_seq":20114,
 "cap_t_us":1731100000123456,"recv_t_ms":5123377,"w":640,"h":480,
 "tracks":[{"id":7,"cls":"person","conf":0.83,"bbox":[212,40,398,470]}]}
```

`cap_t_us` is the Pi's capture stamp, for ordering only; `recv_t_ms` is the PC's receive time, the only time used for ageing. `bbox` is `[x1, y1, x2, y2]` in pixels. The schema says nothing about the host, so the detector can move to the Pi later.

### `owner` (owner_tracker, 20 Hz)

```json
{"v":1,"type":"owner","seq":5121,"t_ms":5123395,"frame_seq":20114,
 "state":"LOCKED","track_id":7,"confidence":0.72,"bbox":[212,40,398,470],
 "offset_x_px":-15,"area_ratio":0.121,"frames_unseen":0,
 "bearing_est_deg":null,"verified_frames_ago":212,"verify_pending":false}
```

`state` ∈ `UNLOCKED, ACQUIRING, LOCKED, LOST, RESCAN, ASKING`: the level behind `target_*`, `rescan_*` and `owner_verify_needed`. `offset_x_px` is bbox centre minus image centre, positive when the target is right of centre (so the controller's `wz` has the opposite sign: positive `wz` turns left). `bearing_est_deg` is the dead-reckoned bearing to the target while unseen, positive to the left, null while seen.

### `goal` (brain: on change and once a second; hud: operator override)

```json
{"v":1,"type":"goal","seq":88,"t_ms":5123000,"behavior":"FOLLOW_OWNER","params":null,"reason":"owner verified"}
```

`behavior` ∈ `FOLLOW_OWNER, STAY, LOOK_AROUND, GO_TO, REST`; `GO_TO` carries `{"bearing_deg":…,"range_m":…}`. The level behind `behavior_changed`. Until a first `goal` arrives the follow controller holds `STAY` (first-message receipt, never a default that looks like data). The HUD's goal lets a supervised FOLLOW session run with no brain.

### `say` (brain → voice)

```json
{"v":1,"type":"say","seq":12,"t_ms":5123100,"utterance_id":"b12","kind":"say","text":"Found you. Let's roll."}
```

`kind` ∈ `say, ask_owner`. Text over `MAX_WORDS_PER_LINE` (12, Brian) is rejected. How the voice paces these is decisions.md D-18.

### `cmd_request` (follow_controller, brain → gateway)

The body of the S1 message being asked for (`velocity`, `action` or `mode`, §7) without `deadman`. The gateway adds `deadman`, stamps its own `seq`, keeps the requester in `src`, and forwards.

---

## 13. Change log

| Date | Type | Change | Why |
|---|---|---|---|
| 2026-11-08 | all | v1 drafted | V3 architecture |
| 2026-11-08 | envelope, `state`, `event`, `audio`, `audio_ctl`, PC bus | `seq` per topic; `state.active`; PC-origin events get sockets (P2, P3); single S1 writer (`gateway`); S6 socket options, zero-length `final` chunk, end-of-utterance definition, `device_latency_ms` / `played_bytes`; `keyword` carries the raw frame; `tracks` / `owner` / `goal` / `say` / `cmd_request` schemas written down; only S1–S3 block arming; T3 re-arm is "above 30" | review by the voice session before merge (decisions.md §1) |
