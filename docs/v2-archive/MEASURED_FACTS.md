# V2 measured facts

Every measured constant and protocol fact from IronBark V2, in one place.
Paths are relative to this folder. `commit <sha>` means a commit message
in the V2 repo (`ironbark-v2`, branch `claude/ironbark-v2-oracle-handoff-e29f1a`).

Each fact carries one of these tags:

- **[measured]**: read off the hardware, with a trace or a logged number
- **[code]**: true by construction of the V2 code (wire format, ports)
- **[vendor]**: from Yahboom's or Oradar's own docs or source
- **[unverified]**: a configured value nobody measured on the S2

Hardware: Yahboom DOGZILLA S2, motion MCU firmware `M-4.0.1-Y`, xgolib
1.1.9 (`read_lib_version()` returns `'1.4.1'`), Raspberry Pi 5, Debian 13
trixie, Python 3.13.5.

---

## Motion command model

| Fact | Value | Tag | Source |
|---|---|---|---|
| `forward()` blocks? | No — returns in **0.1 ms** | measured | `measurements/smoke_20260829_000317.jsonl` stage 2 `forward_return` |
| Movement persists until `stop()` | Yes; walked the full 8 s window, never self-stopped | measured | same file, stage 2 `motion_window` + operator verdict |
| Turn rate vs commanded step | `turnleft(40)` → **39.2 °/s** over 385.6° in 9.8 s | measured | same file, stage 3 `yaw_turn` |
| Turn rate excluding startup | **42.5 °/s**, from the first yaw change to the end | measured | stage 3 `yaw_sample` series, derived for this archive |
| Turn onset latency | yaw first changes **0.78 s** after `turnleft(40)` is issued | measured | stage 3 `yaw_sample` series (constant 35.77° until t=0.779 s) |
| Yaw wobble while turning | 32 of 141 samples step **backward** during a CCW turn | measured | stage 3 `yaw_sample` series |
| Concurrent reads mid-motion | OK — `read_battery` 3.2 ms while walking | measured | stage 2 `concurrent_read` |
| `attitude('p', 8)` mid-walk | composes: pitch −0.3° → **7.3°**, gait smooth | measured | stage 4 `compose` + operator verdict |
| `attitude()` precondition | needs `imu(0)` (self-stabilisation off) | vendor + measured | `migration-notes.md` (course PDF 05), stage 4 `imu_mode` |
| SDK `turn_by(45°)` | **not closed-loop**: 45° commanded → **73.8°** measured; blocks 4.1 s = `mintime + θ·k` = 0.5 + 45 × 0.08 | measured | stage 6 `turn_by_return` / `turn_by_result` |
| `read_rotate_state()` | opaque ints (101, 234, 180, 219), not a usable "turning" flag | measured | stage 6 `settle_sample` |
| Teardown | no `close()` exists; dropping the object and reopening is clean | measured | stage 5 `closed` / `reopen` |
| SDK provenance | xgolib on vanilla trixie works standalone; Yahboom's `DOGZILLA` lib is a renamed fork of xgolib | measured + vendor | stage 0 `sdk`; `migration-notes.md` "S2 platform research" |
| SDK step ranges | forward/back step [0, 25]; strafe [0, 18]; turn ±100 (°/s) | vendor | `migration-notes.md` SDK facts 2–3 |
| Neutral servo pose | shoulder 0 / thigh 48 / calf 14; body z 105 mm (75–115) | vendor | `migration-notes.md` SDK fact 9 |
| Never call | `calibration()` — servo calibration register, can corrupt servo zeros | vendor | `migration-notes.md` safety note |

**Caveat on the smoke log:** stage 6's `turn_by_result` record carries the
note "delta within ±emax(4°) of 45 ⇒ closed-loop works", but its own
numbers say 73.8°. That note string was hardcoded in the instrument. Trust
the numbers.

## IMU and yaw

| Fact | Value | Tag | Source |
|---|---|---|---|
| Boot gyro-bias calibration | exists; yaw register reads **exactly 0.0** while it runs | measured | `measurements/smoke_20260828_235710.jsonl` (1,764/1,764 reads = 0.0) |
| Handling the dog during boot | corrupts the bias: **−9.89 °/s** drift, residual std 0.029° (a pure ramp) | measured | `migration-notes.md` "First hardware contact"; `measurements/smoke_20260828_234946.jsonl` stage 1 |
| "IMU ready" predicate | first nonzero yaw, latched — a state predicate, never a timer | measured → design | `migration-notes.md` Q2 resolved; `reference/motor_controller.py` |
| Yaw register format | unwrapped continuous degrees (no ±180 wrap); reached −59,307° after long drift | measured | stage 3 (`raw_wrap_jumps: 0`); `migration-notes.md` |
| Yaw sign | `turnleft` = **+yaw** (CCW positive) | measured | stage 3 `yaw_start` 35.8 → `yaw_end` 421.8 |
| `read_imu()` layout | `[ax, ay, az (m/s²), gx, gy, gz (rad/s, raw, NOT bias-subtracted), roll, pitch, yaw (rad)]` | measured | `migration-notes.md` "First hardware contact" |
| Magnetometer fusion | none — yaw is integrated gyro Z | measured | same section |
| Roll / pitch | accelerometer-referenced, clean (0.0 / −0.4° level) | measured | same section |
| Read latency, any `read_*` | **2.6–4.2 ms** mean, ~5 ms max | measured | both full smoke files, stage 0 `read` records |

### Corrections — what V2 got wrong about yaw

1. **"343 Hz read_yaw" was a call rate, not an update rate.** In the
   clean-boot run, stage 1 logged `call_rate_hz: 342.9` but
   `update_rate_hz: 0.0`. The register did not change once in 30 s
   (min 49.81, max 50.0). `migration-notes.md` and the bring-up report
   cite "343 Hz" as if it were a usable control rate. It isn't.
2. **The "−0.009 °/s clean-boot drift" was measured on a frozen register.**
   Same record. With zero updates, that slope says nothing about drift.
3. **V3 has since measured the freezes directly** (`../phase1-joint-control-results.md`):
   the whole IMU block holds an identical value for ~1 s at a time
   (995–1004 ms stretches; 77.5% of reads repeated with the dog still,
   85% in a run where it was handled), and yaw moved between −0.21 and
   +0.79 °/s across runs with the dog on a stand. V2's
   `migration-notes.md` saw the same thing and filed it as "holds
   near-frozen values (quantized/deadbanded) when still".
4. During motion the register **does** update: 130 of 141 samples changed
   at ~70 ms spacing during the stage 3 turn. The handled-boot run, which
   was drifting, logged `update_rate_hz: 149.3`.

## Power and battery

| Fact | Value | Tag | Source |
|---|---|---|---|
| Battery reading | **integer percent** (read 99), not volts; no voltage method on the SDK surface | measured | stage 0 `read_battery` + `voltage_methods: []` |
| Drain | **99% → 79%** over a ~3 min intermittent-motion session (load sag suspected, unproven) | measured | stage 5 `pre_teardown`; `migration-notes.md` battery flag |
| Low-battery behaviour | **≤9%** → dog lies down and locks out | vendor | `phase1-briefing.md` §3 |
| Charging | plugging the charger **hard-cuts robot power**: no run-while-charging tests | vendor | `phase1-briefing.md` §3 |
| Pack | 7.4 V 2,500 mAh (figures vary by generation) | vendor | `phase1-briefing.md` §3 |
| Torque release | `unload_allmotor()` / `load_allmotor()` exist (V1's PiDog had none) | vendor | `migration-notes.md` SDK fact 6 |

## Body

| Fact | Value | Tag | Source |
|---|---|---|---|
| Size / mass | 246.2 × 144.6 × 195.3 mm, ~972 g | vendor | `migration-notes.md` platform research |
| Servo IDs | `[11,12,13, 21,22,23, 31,32,33, 41,42,43]`; legs 1 LF / 2 RF / 3 RR / 4 LR | vendor | `migration-notes.md` SDK fact 9 |
| Turning | in-place spins, native strafe (`left()`/`right()`) | vendor + measured | `phase1-briefing.md` §2; smoke stage 3 |

## Wire protocol and ports (V2 Mac ↔ Pi)

| Fact | Value | Tag | Source |
|---|---|---|---|
| Commands | JSON; the **Mac binds PUB** on `PC_IP:5556`, the Pi **connects SUB** | code | `reference/motor_controller.py` header |
| Telemetry | JSON strings; the **Pi binds PUB** on `*:5558`, the Mac connects SUB | code | same |
| Telemetry fields | `action, yaw, roll, pitch, battery_pct, imu_ready, seq, fw` | code | same |
| Telemetry **absent** on purpose | `distance_cm`, `battery_v`, `danger`, `buffer_depth` | code | same |
| Motion vocabulary | `stop \| forward \| backward \| turn_left \| turn_right \| strafe_left \| strafe_right`, plus `head_pitch` → `attitude('p')` | code | same |
| Tolerated, ignored | `step_count`, `head_yaw`, `head_mode`, `owner_bbox`, `bark`, `bark_volume`, `idle_pose`, `one_shot`, `flush`; `thinking` maps to stop | code | same |
| Camera stream | **PUSH** (Pi, connects) → **PULL** (Mac, binds) on `50505`; message = `<qI` header (int64 capture µs, uint32 JPEG length) + JPEG | code | `bringup-report.md` W2; `migration-notes.md` camera section |
| Lidar stream | PUSH → PULL on `50507`; `send_string` of `{"n", "ts", "pts": [{"a": deg, "d": mm}]}`, angle 0 = forward | code | `bringup-report.md` W3 |
| Dead ports | `5557` (V1 teleop), `50506` (ribbon cam), `50508` (OAK-D depth), `9000` (MJPEG) | code | `reference/config.py` |
| One command socket | teleop and follower both bind 5556, so they can't run at once | code | `bringup-report.md` §4 |

**V3's `CLAUDE.md` says the camera and lidar streams are "ZMQ PUB".** In V2
they are PUSH/PULL, and a PUB sender never connects to the PULL receiver.

## motor_controller constants (`reference/config.py`)

| Constant | Value | Status | Notes |
|---|---|---|---|
| `V2_MOTION_PORT` | `/dev/ttyAMA0` @ 115200 | measured | ESP32 motion MCU; needs `dtparam=uart0=on` (`migration-notes.md`) |
| `V2_TURN_RATE_DPS` | 40 | measured | → 39.2 °/s (see above) |
| `V2_FORWARD_STEP_MAX` | 14 | unverified | of [0, 25]; "start moderate" |
| `V2_STRAFE_STEP` | 10 | unverified | of [0, 18] |
| `V2_ATTITUDE_PITCH_LIMIT` | 15° | vendor | SDK range ±15; 8° composes (Q7) |
| `V2_LOOP_HZ` | 50 | design | reads ~3 ms, so comfortable |
| `V2_TELEM_EVERY_TICKS` | 5 → **10 Hz** telemetry | design | |
| `V2_BATTERY_EVERY_TICKS` | 250 → ~5 s | design | |
| roll/pitch read cadence | every 25 ticks → ~2 Hz | code | `reference/motor_controller.py` |
| `V2_CMD_WATCHDOG_TICKS` | **75 ticks ≈ 1.5 s** of Mac silence → `stop()` | design | count predicate, not wall-clock |
| Startup | `imu(0)`, `pace("normal")`; refuses motion until imu_ready latches | code | `reference/motor_controller.py` |
| Shutdown | `stop()` + `attitude('p', 0)` | code | same |
| Identical setpoint | not re-sent (serial hygiene, not buffer protection) | code | same |

## Camera (`/dev/video0`, 2 MP wide-angle USB)

| Fact | Value | Tag | Source |
|---|---|---|---|
| Formats | MJPG 640×480 @ **120 fps**, 1280×720 @ 60, 1920×1080 @ 30; YUYV 640×480 @ 30 | measured | `migration-notes.md` camera section (`v4l2-ctl --list-formats-ext`) |
| Stream at 20 fps target, q75 | **20.0 fps**, **7.74 Mbps**, 48.3 kB/frame | measured | same; `bringup-report.md` §2 |
| Inter-frame gap | mean 50.0 ms, max 67.5 ms | measured | same |
| One-way latency (clock-corrected) | mean **10.9 ms**, median 10.4, p95 14.5, max 28.8 | measured | same |
| Uncapped headroom | **46.5 fps**: read 18.8 ms, encode 2.2 ms, send 0.07 ms | measured | same |
| Exposure | as-shipped auto exposure is correct (frame mean 114/255); every gain/exposure/YUYV override overexposed | measured | same |
| Connect burst | up to SNDHWM (5) queued frames flush at once, one seen 3.87 s stale | measured | same |
| FOV | unpublished by Yahboom | — | `phase1-briefing.md` §3 |

## Perception on the dog's camera (static ladder, 2026-09-04)

`measurements/ladder_20260904_204929.json`, commit `7f44ec8`. The operator
stood still at tape marks, 30 s per station, YOLO11s conf 0.5, 640×480.

| Distance | Hit rate | off_x σ (px) | Area ratio | bbox h (px) | Clipped |
|---|---|---|---|---|---|
| 1.0 m | 97.9% | **39.7** | 0.159 | 282 | 90% |
| 1.5 m | 67.7% ⚠ | 12.4 | 0.118 | 281 | 100% |
| 2.0 m | 98.7% | 2.6 | 0.099 | 263 | 100% |
| 3.0 m | 92.3% | 3.5 | 0.068 | 247 | 97% |
| 4.0 m | 98.0% | 11.5 | 0.033 | 173 | 0.3% |

- `V2_ARRIVAL_AREA_RATIO = 0.55` is **physically unreachable** on this lens.
  The ratio is only 0.159 at 1 m, so FOLLOW never declares arrival.
- bbox height saturates around 280 px below 2 m (frame clipping). Below
  2 m it is not a range proxy.
- The 1.5 m hit-rate dip is a single station. Repeat it before trusting it
  (commit `7f44ec8`).

## Networking and clocks

| Fact | Value | Tag | Source |
|---|---|---|---|
| Pi clock vs Mac | Pi **+484.4 ± 8 ms ahead**, stable to ~150 µs, though both report NTP sync | measured | `migration-notes.md` clock skew; `bringup-report.md` §2 |
| Consequence | uncorrected `recv − frame_ts` reads ≈ **−474 ms**; any staleness check that trusts a Pi timestamp is wrong by half a second | measured | `migration-notes.md` clock skew |
| Tailscale | the Mac had it, the Pi did not, so `.env` Tailscale IPs could not connect | measured | `migration-notes.md` network section |
| Pi serial devices | only `ttyAMA0` (motion, after the overlay) and `ttyAMA10` (Pi 5 debug connector) | measured | `migration-notes.md` |

## MS200 lidar

Protocol from Oradar's own SDK source (`ordlidar_protocol.h`,
`ord_lidar_driver.cpp`), not from inference (`migration-notes.md` MS200
section; `bringup-report.md` W3).

| Fact | Value | Tag |
|---|---|---|
| Serial | **230400 8N1**; free-runs on power, nothing needs writing to it | vendor |
| Frame | **47 bytes**, packed little-endian: `0x54` header, `0x2C` ver_len (v1, 12 points), uint16 speed (deg/s; rev/s = /360), uint16 start angle (0.01°), 12 × {uint16 distance mm, uint8 confidence}, uint16 end angle (0.01°), uint16 device timestamp, uint8 CRC8 | vendor |
| CRC8 | poly **0x4D**, init 0x00, non-reflected, no final XOR, over the leading 46 bytes | vendor |
| Angle interpolation | `diff = (end + 36000 − start) % 36000`; `step = diff / 11 / 100`; fold at 360 | vendor |
| Revolution boundary | angle steps backward by more than 1° (vendor driver's rule) | vendor |
| Range / rate | 0.03–12 m, 4,500 samples/s | vendor |
| UART on this Pi | **unknown** — cable never traced; Yahboom's image uses `ttyAMA1` | — |
| Live bytes | never read. The parser passed 41/41 synthetic checks only (`measurements/ms200_parser_20260828_174335.txt`) | — |

## Never measured on the S2 — do not treat as facts

These are in `reference/config.py` with V1 (PiDog / OAK-D) values or
guesses:

- `V2_TURN_BANDS` 220/160/100/60 px at area 0.08/0.15/0.30. The ladder
  showed static noise is small next to these, but they were never tuned.
- `V2_ARRIVAL_AREA_RATIO = 0.55` (shown unreachable, above),
  `V2_ARRIVAL_RECENTER_PX = 80`.
- All `LIDAR_*` and `COSTMAP_*` thresholds (V1 RPLidar, 13 cm PiDog body;
  the S2 is 14.5 cm wide).
- `ACTION_COMMIT_FRAMES = 3`, `CMD_INTERVAL = 0.1`,
  `TARGET_HOLDOVER_FRAMES = 15`, `FOLLOW_COAST_S = 1.5` (tied to the
  holdover by construction in commit `aba0477`, not by measurement).
- `TARGET_CENTER_WEIGHT = 0.3`, `TARGET_ACQUIRE_FRAMES = 3`: design values
  (`phase1-briefing.md` §5).
- Sustained-load runtime and thermal envelope: never measured.
