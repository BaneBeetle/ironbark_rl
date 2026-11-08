# Deployment notes: Pi policy runtime (Phase 2A week 6)

Requirements found so far for the runtime that runs a trained policy on the dog. Nothing here is built yet. Each line names its source. Thresholds are Brian's calls when the runtime gets built; until then they're `# MEASURE:`.

## IMU (Brian, 2026-11-07)

- **The runtime needs an IMU sanity filter.** Brian: "the runtime needs an IMU sanity filter (reject zeroed/impossible vectors, detect freezes)."
  - Reject zeroed vectors: the 2026-11-07 `imu` run had 5 of 2000 `read_imu()` reads with a whole accel or gyro vector at exactly 0.00.
  - Reject impossible values: e.g. gyro (−1513.7, +1623.4, +768.8) °/s in the same run. `# MEASURE:` the limits (gyro range, how far |accel| may sit from 9.8 m/s²); Brian's call.
  - Detect freezes: the whole IMU block repeated exactly for ~1 s at a time (999–1004 ms; 85% of reads). `# MEASURE:` how many identical reads count as frozen, once the `imu --label still` and `imu-loop` reruns show the refresh at rest and at a policy's read rate.
  - Open (Brian's design): what the policy does while the IMU is rejected or frozen (hold the last good value? stop?).
- **Fallback option, not decided:** if the onboard IMU proves unusable, wire a separate IMU to the Pi over I2C and read it directly, bypassing the motion board. Brian: "If the onboard IMU proves unusable, the fallback is a separate I2C IMU wired directly to the Pi; log that as an option." (The Pi user `lolly` is already in the `i2c` group.)
- **Gyro units and bias** (V2 archive `MEASURED_FACTS.md` vs. xgolib source): xgolib divides the raw gyro by 16.4 (deg/s on the usual scale); V2 lists rad/s, raw, **not bias-subtracted**. The sim's `base_ang_vel` is bias-free rad/s. `# MEASURE:` the unit (rotate by a known angle, integrate) and the bias at rest before a policy uses the gyro.
- **Treat an exact 0.0 from any `read_*` as a possible failure sentinel** (V2 LESSONS A2; xgolib returns 0 on a failed read).
- **Wait for the IMU's gyro-bias sampling** after power-on before any motion: yaw reads exactly 0.0 until it's done, and moving the dog then corrupts the bias (V2 smoke log). The probe uses the same non-zero-yaw latch as `motor_controller.py`.

## Joints

- **Never call `calibration()`**: it's the servo calibration register and can corrupt servo zeros (V2 archive, vendor).
- **Joint map:** verified by Brian (`ironbark_rl/assets/s2_joint_map.py`). `# MEASURE:` each joint's sign and zero offset vs. the sim before deployment (rerun the probe's `map` answering foot directions; command 0° against the MJCF default pose).
- **Command all 12 joints together, starting from their measured angles.** The first `motor()` call puts the firmware in joint mode, and every joint then drives to its last joint-mode setpoint, so unsent joints jump (~8° seen). Source: Phase 1 `gait` run.
- **Round commands to the nearest byte:** xgolib's `conver2u8` truncates (up to 0.62° low). The probe adds half a byte step first (Brian, 2026-11-07).
- **Build `XGO_DOG(port, 115200, version="xgomini")` directly.** The `XGO()` factory (which `motor_controller.py` uses) calls `reset()`, which moves the dog.
- **`motor()` stops the firmware gait; `stop()` hands control back.** The runtime and `motor_controller.py` can't both drive the dog.

## Sessions

- **Battery:** 99% -> 79% in ~3 min of intermittent motion in V2; the dog locks out at <= 9%, so a full charge lasts roughly 13 min of that use. Plugging in the charger cuts power (no tethered runs). Log `battery_pct` in every run (the probe does). (V2 archive LESSONS A5.)

## Timing the sim was trained with

- 12-joint command rate: 102 Hz max (wire-bound); 55.6 Hz with one `read_motor()` per loop. A 50 Hz policy loop with a joint read and an IMU read is tight; `imu-loop` measures it.
- Command delay modeled as 40 ms (EXP-009). Joint readback modeled as a 130 ms round-robin sample-and-hold (EXP-010). The runtime should feed the policy the raw stale readings the same way the sim does (the obs-parity test, week 6).

Results behind these lines: [phase1-joint-control-results.md](phase1-joint-control-results.md), [phase1-xgolib-api.md](phase1-xgolib-api.md).
