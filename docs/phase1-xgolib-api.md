# Phase 1, step 1: xgolib joint-control API

Read from source on the Pi (2026-10-30), not from memory:
`~/ironbark/.venv/lib/python3.13/site-packages/xgolib/xgolib_dog.py`, xgolib **1.1.10**.
Firmware reports **`M-4.0.1-Y`** (V2 smoke log, 2026-08-28), so xgolib applies its `xgomini` limits.

Nothing below was run against the dog. Numbers marked "arithmetic" come from the code and the baud rate, not from measurement.

## Per-joint and per-leg calls

| Call | What it does | On the wire |
|---|---|---|
| `motor(ids, angles)` | Per-servo angle (deg). ids `11..43` = leg 1–4 × joint 1–3; `51..53` = arm | One 9-byte packet **per joint** (8 framing + 1 data), register `0x50 + i`. Write-only, no ack. |
| `leg(leg_id, [x, y, z])` | Foot position; firmware does the IK | 3 packets per leg (register `0x40 + i`) |
| `motor_speed(1..255)` | Servo speed. Docstring: "only effective when controlling servos separately" | 1 packet |
| `read_motor()` | All 15 servo angles in one request/response | 9-byte request; reply parsed by `__unpack` (busy-poll, 1 s timeout) |
| `unload_motor(leg)` / `load_motor(leg)` | Torque off/on per leg (`5` = arm) | 1 packet |
| `read_imu()` | 24-byte IMU block, register `0x65` | request/response |

The high-level gait path (`move_x`, `move_y`, `turn`, `pace`, `gait_type`, `attitude`, `translation`) writes velocity/pose registers (`0x30`–`0x3F`). The firmware runs the gait itself. That's what `pi/motor_controller.py` uses today.

## Angle encoding

Each angle is **one byte**, linear over that joint's limit range (`conver2u8`, truncating). xgolib's comment labels the three joints of a leg lower / middle / upper:

| Joint (per xgolib comment) | `MOTOR_LIMIT` (deg) | Resolution (arithmetic) |
|---|---|---|
| joint 1, "lower" | [-73, 57] | 130/255 ≈ 0.51° |
| joint 2, "middle" | [-66, 93] | 159/255 ≈ 0.62° |
| joint 3, "upper" | [-31, 31] | 62/255 ≈ 0.24° |

Values outside the range are clamped silently. Readback uses the same byte encoding.

`# MEASURE:` which physical joint (hip abduction / thigh / calf) each index drives, and its sign. Command each servo by a small step with the dog on a stand, and record the result.

## Wire-time budget at 115200 baud (arithmetic)

8N1 at 115200 is about 11,520 bytes/s. Every frame is 8 bytes of framing plus the data bytes.

- 12 joint commands = 12 × 9 B = 108 B ≈ **9.4 ms**.
- `read_motor()` = 9 B request + 23 B reply ≈ 2.8 ms on the wire, plus firmware turnaround. For reference, `read_firmware()` round trips measured **3.2–4.2 ms mean** (V2 smoke logs).
- `read_imu()` = 9 B request + 32 B reply ≈ 3.6 ms on the wire.
- One 50 Hz step (20 ms) with 12 writes, a joint read and an IMU read is ≈ 15.8 ms of wire time alone, before firmware turnaround and Python overhead. That's tight.

`xgolib/__init__.py` says the firmware defaults to 115200, but that **"RL programs" switch to a high-speed serial link (e.g. 2,000,000)**. It auto-probes `[115200, 2000000, 500000, 921600, 1000000, 1500000]`. This xgolib has no call that tells the firmware to change baud: `__change_baud` only reopens the host side.

## Questions the Phase 1 measurement script must answer

1. Max sustained `motor()` rate for all 12 joints with no dropped commands. There's no ack, so infer drops from readback.
2. Does one multi-register write (`MOTOR_ANGLE`, length 12) work? It would be 20 B ≈ 1.7 ms instead of 9.4 ms.
3. `read_motor()` latency and max rate. **Does it return the measured servo position, or just echo the last setpoint?** System ID depends on this.
4. Step response per joint (delay, rise time) vs. `motor_speed`.
5. Gait vs. joint control: what `motor()` does while the firmware gait is active, and how to hand control back (`reset()`?).
6. Can the firmware run at 2 Mbaud, and how is it switched?

## Starting point found: Luwu's own RL env

[LuwuDynamics/luwu_mjlab](https://github.com/LuwuDynamics/luwu_mjlab) is an mjlab (MuJoCo Warp) + RSL-RL PPO training env for Luwu's XGO **Mini2S**, Mini2SW and Lite3. It includes MJCF models, 50 Hz joint-position-target policies (action scale 0.25, `decimation 5` × `timestep 0.004`) and ONNX export. Trained policies are on Hugging Face: [robomotic/XGO](https://huggingface.co/robomotic/XGO). Its README documents Linux and native Windows.

Our firmware string starts with `M`, the XGO Mini family. So the Mini2S model is the closest candidate, but not yet a confirmed match:

- `# MEASURE:` S2 link lengths, total mass and joint limits vs. the Mini2S MJCF (tape measure + scale + the `MOTOR_LIMIT` table above).
- The Mini2S model includes 3 arm joints. Drop them if the S2 has no arm.
- Deployment code isn't published. The HF card says the policies weren't validated on hardware, though the repo shows real-robot clips.
- `mini2s_constants.py` has a docstring reading "Unitree Mini2S constants". Provenance is unclear.

## Re-read from source, 2026-11-07 (for `pi/joint_control_probe.py`)

Same install: dist `xgolib 1.1.10` (`__init__.py` says 1.1.9, `xgolib_dog.py` says 1.4.1). `xgolib_dog.py` sha256 `4371a423707b8225f1866ee01fa66ab9a57e5db9a7c42129bec51e15b94daaa8`; the probe refuses to run if it changes.

- **`XGO()` is a factory, not a class.** With `version="auto"` (the default) and a port, it scans bauds, then calls **`reset()`** (an action, so the dog moves) before building the real object. `motor_controller.py` calls `XGO(port=...)`, so its startup resets the dog. The probe builds `XGO_DOG(port, 115200, version="xgomini")` directly.
- **`XGO_DOG.__init__`** opens the port, reads firmware and yaw, and picks the limit table by the firmware's first letter (`M` → `xgomini`). It sends no motion. Limits live in the module global `XGOparam["MOTOR_LIMIT"]`, not on the instance.
- **`read_motor()` order** = `MOTOR_ID` = `[11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53]`. Leg index `i` uses `MOTOR_LIMIT[i % 3]`; `motor()` uses the same rows by joint position. Every read flushes input first; a failed unpack returns `[]` after a 1 s busy-poll.
- **Commands truncate:** `conver2u8` is `int(255 / range * (deg - lo))`, so commanding a read-back angle can land one byte low (0.24–0.62°). The probe logs the exact bytes sent (`cmd.u8`) and read (`read.u8`).
- **No `ser.flush()` after writes.** A read issued right after a 12-joint write waits behind those bytes in the TX queue; the probe's read latency includes that.
- `motor_speed(0..255)`, 0 becomes 1. Whether 255 is fastest: `# MEASURE:` `step --speeds 255,128,64`.
- `move_x(step)`: one byte over ±`VX_LIMIT` = 25; the source gives no physical unit. `stop()` = `move_x(0)`, `move_y(0)`, `mark_time(0)`, `turn(0)`. `reset()` = `action(255)`.
- `SCAN_PORTS = ["/dev/ttyAMA5", "/dev/ttyAMA0"]`; this Pi has `/dev/ttyAMA0` and `/dev/ttyAMA10` only. `config.V2_MOTION_PORT` = `/dev/ttyAMA0` @ 115200.

## IMU freezes: firmware and config check, 2026-11-07 (Brian's request; nothing changed on the dog)

- **Firmware:** `M-4.0.1-Y`, from `read_firmware()` in every probe log header (Brian's runs; Claude never opens the port).
- **Newer firmware / update tool:** no public motion-board firmware release, changelog or file found. Checked: Yahboom's DOGZILLA tutorial index (no firmware-update lesson; downloads are Pi system images, apps, "Software calibration", "Communication Protocol"), Luwu's XGO-PythonLib README ("burn the latest official image", i.e. the Pi image, plus `pip install --upgrade`), web search, the Pi's disk (no `.bin` or other XGO/Yahboom library), PyPI. xgolib has `upgrade(filename)`: register `0x05`, then the raw `.bin` at 350000 baud; its own docstring says "testing phase, do not use". Getting a newer firmware would mean asking Yahboom (support@yahboom.com).
- **xgolib version:** 1.1.10 is the newest on PyPI (2026-08-26; 16 releases since 2025-10-28). No notes anywhere tie xgolib versions to firmware versions; xgolib only switches its limit table on the firmware's first letter.
- **Every IMU-related call in `xgolib_dog.py`:**
  - `imu(mode)`: writes register `0x61`, self-stabilization 0 off / 1 on. Yahboom: "the robot dog will automatically adjust the posture angle to keep the back at the horizontal position". With 1, the firmware moves the legs.
  - `read_imu()`: `0x65`, 24-byte block. `read_roll/pitch/yaw()`: `0x62-0x64` floats. `read_imu_int16(axis)`: `0x66-0x68` int16, not yet tested.
  - `set_yaw_init()`: a Pi-side offset only. `calibration(state)` (`0x04`, "use with caution!!!") is servo software calibration, not IMU.
  - No IMU refresh-rate, filter or IMU-calibration setting exists.
- **Yahboom's protocol PDF** ("DOGZILLA STM32 serial communication protocol", 2022-08-30, Google Drive linked from the tutorial): `0x61` "IMU state", **read/write, default 0x00**, 0x00 close / 0x01 self-stable mode; `0x62-0x64` roll/pitch/yaw read. It has no `0x65-0x68` and no IMU rate setting; it predates this firmware (the S2's motion board is an ESP32).
- **Unknown:** whether self-stabilization was on during the IMU runs. The probe never calls `imu()`; `motor_controller.py` sends `imu(0)` at its startup; the 2022 doc's default is off. Register `0x61` can be read, which changes nothing.
