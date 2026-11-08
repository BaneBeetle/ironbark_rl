# Phase 1 gate: joint-control measurements (2026-11-07)

Brian ran `pi/joint_control_probe.py` (commit `8e1cab7`) with the dog on a stand: `read`, `passive --leg 1`, `step --joints leg1 --speeds 255,128,64`, `sine --joints leg1`, `rate --read-every 0`, `rate --read-every 1`, `gait --joint 12`. Firmware `M-4.0.1-Y`, xgolib 1.1.10, 115200 baud, battery 99–100%.
Logs: `docs/measurements/joint_control_*_20261107-*.jsonl`. Numbers: `python tools/joint_control_report.py`. Plots: `docs/figures/phase1_{step,sine,gait,passive}.png`.

Measurements only. Brian's read and the Path A/B decision go at the bottom.

## Command rate (all 12 joints)

| Loop | Period, median [p99] | Rate |
|---|---|---|
| 12-joint `motor()` only (`rate --read-every 0`) | 9.80 ms [9.83] | **102 Hz** |
| 12-joint `motor()` + one `read_motor()` (`--read-every 1`) | 18.0 ms [18.3] | **55.6 Hz** |

- With no reads, each 12-joint `motor()` call blocks for 9.72 ms. That is 11,019 B/s, 96% of what 115200 baud can carry (11,520 B/s).
- With a read every loop, `read_motor()` takes 17.8 ms (median): it waits behind the 108 queued command bytes. `motor()` itself returns in 0.13 ms.
- `n_clamped` = 0 and `n_bad_reads` = 0 in every run.

## Readback

- `read_motor()` alone: latency **3.63 ms** median (p99 4.56, max 6.96); **265 reads/s**.
- **Each joint's value only changes every ~105 ms** (median interval between changes during steps: 105.3 ms for joints 11, 12 and 13). In the 12-joint run, at most **2** joints changed between consecutive reads (18 ms apart). So the firmware re-polls the servos one at a time, and each reading is 0–105 ms old.
- **Measured position, not an echo:** with torque off (`passive`), the readings followed Brian's hand over each joint's whole byte range (11: −73…57, 12: −47…93, 13: −31…31), pinned at the encodable limits. With torque on, at rest, they never changed (range 0.00°).
- After torque came back on, joints 12 and 13 returned to their pre-unload angles (39.38 → 39.38, −0.61 → −0.36). Joint 11 was still moving at the end of the 150-read window (−23.6 → 8.1, start 19.3).
- Arm channels 51–53 read their limit values (bytes 0/255/0): there is no arm.

## Step response (10° steps, leg 1)

Delay = first reading ≥ 10% of the step, timed from the command. Because of the ~105 ms refresh, a reading often jumps straight from 0% to ≥ 90% (rise shown as 0).

| Joint | speed | up: delay / rise [ms] | down: delay / rise [ms] | Final error up / down [°] |
|---|---|---|---|---|
| 11 | 255 | 75 / 109 | 50 / 102 | +0.51 / +0.51 |
| 11 | 128 | 128 / 0 | 101 / 0 | +0.51 / +0.51 |
| 11 | 64 | 83 / 105 | 58 / 109 | +0.51 / −0.01 |
| 12 | 255 | 133 / 0 | 112 / 0 | −0.00 / −1.25 |
| 12 | 128 | 83 / 102 | 58 / 106 | −0.00 / −1.25 |
| 12 | 64 | 144 / 0 | 123 / 107 | −0.62 / −0.63 |
| 13 | 255 | 87 / 0 | 61 / 109 | −0.49 / −0.73 |
| 13 | 128 | 142 / 0 | 123 / 0 | −0.49 / −0.73 |
| 13 | 64 | 105 / 105 | 82 / 106 | −0.49 / −0.73 |

- Across all 18 edges: delay 50–144 ms; every edge at ≥ 90% within 250 ms; overshoot 0–7.1%; final error within ±1.25° (≤ 2 byte steps).
- The first reading after each command is always 0% of the step.

## Sine tracking

Joint 11, 10° amplitude, one command + one read per sample (4.65 ms):

| Frequency | Gain | Lag |
|---|---|---|
| 1.07 Hz | 0.96 | 88 ms |
| 2.15 Hz | 0.89 | 86 ms |
| 4.31 Hz | 0.32 | 108 ms |
| 8.59 Hz | 0.12 | aliased (above half the ~9.5 Hz refresh rate) |

All 12 joints together, 3° at 0.556 Hz (the `--read-every 1` run): gain 0.92–0.98 and lag 151–162 ms, except joints 12 and 42 (gain 0.81 / 0.83, lag 200 / 201 ms).

**The sine run aborted after joint 11.** Joint 12's drift check saw joint 11 5.6° off its start pose, but that reading was stale: joint 11 read exactly its start pose 56 ms later. Fixed in commit `e1cc046` (longer settle, check only refreshed reads). Joints 12 and 13 were not measured.

## Gait vs. joint control (`gait --joint 12`, `move_x(5)`)

| Phase | Joint 12 at end [°] (target) | Other 11 legs' mean range [°] |
|---|---|---|
| after `reset()` | 43.74 | 0.00 |
| `motor(12)` +10°, idle | 52.47 (53.74) | **4.05** |
| `move_x(5)`, gait on | 42.65 | 17.14 |
| `motor(12)` +10° during gait | 53.09 (53.74) | 10.45, then 0.05 in the next phase |
| `stop()` | 43.12 | 4.16 |
| `reset()` | 43.12 | 0.00 |

- A `motor()` call **stops the firmware gait**: every other leg's reading stops changing within 231 ms of the command (about 2 refreshes).
- **The other 11 joints jump to their last joint-mode setpoints**, not their current angle. After `reset()`, `motor(12)` alone moved joint 11 from 12.1° to ~19.8°, which is where the earlier tests left it (19.27°). The gait-time `motor(12)` did the same. Fixed in the probe in commit `f9a9f4f`: all 12 joints are sent their measured angles first.
- `stop()` hands control back to the firmware: the legs return to its stance (joint 11 → 12.1°).

## Other numbers

- **IMU yaw** between run starts: 135.9° → 206.9° over 177 s, with the dog on a stand. Rates between consecutive runs: 0.40, 0.40, 0.79, −0.21, 0.03 and 0.62 °/s. The V2 smoke log's clean boot drifted −0.009 °/s, and a boot where the dog was handled during bias sampling drifted −9.9 °/s.
- **xgolib truncates commands:** commanding a read-back angle can land one byte low. Example: joint 11 reads 19.27° (byte 181); commanding 19.27° sends byte 180 (18.76°).

## IMU (`imu` run, 2026-11-07, Pi clock 11-08 00:13; numbers only)

Back-to-back reads, no joint commands; `joint_control_imu_20261108-001338.jsonl`.

- `read_imu()` (accel, gyro, roll/pitch/yaw in one 24-byte block): **4.15 ms** median (p99 4.54), 238 calls/s, 0 failures. `read_roll()` / `read_pitch()`: 2.68 ms each.
- **All nine channels change together, in bursts.** 7 bursts in 8.4 s, starting 1.0-1.6 s apart and lasting 21-597 ms, with a change on nearly every read (median 4.35 ms apart). Between bursts every channel holds exactly the same value for 1-1.6 s, gyro included (e.g. gyro_z held at 30.2 deg/s, then 11.6, then 3.4).
- Within bursts: roll -15.9 to +19.3 deg, pitch -26.7 to +9.7 deg, accel_z mostly -9.3 to -10.0 m/s^2 but also 0.00 and +9.80, gyro_z up to 768.8 deg/s once.
- Brian (2026-11-07): "Yes, I moved it. I set it down on the floor." So the large roll/pitch values are real handling.
- **Frozen stretches** (`tools/joint_control_report.py`: from the last update to the next): 6 of the 7 last 999-1004 ms, the other 685 ms; 85% of reads repeat the previous one exactly. `read_roll()` shows the same: 997-1003 ms. Yaw is constant through them too, so the register stopped updating, not the dog.
- **Suspect reads:** 5 of 2000 have whole vectors at exactly 0.00 (accel xyz, or gyro xyz), one with gyro (-1513.7, +1623.4, +768.8) deg/s.
- `read_roll()` phase (5.6 s): the value changed on 99 of 1000 reads.
- Not yet measured: the refresh with the dog still, and at a policy-like read rate (one IMU read per ~20 ms loop).

## Open

- Re-run `sine` with the fixed probe if Brian wants joints 12 and 13. The Pi went offline before the fixed probe could be deployed (it still has `8e1cab7`).
- The real servo response is hidden under the 105 ms refresh. Seeing it needs an external measurement (`# MEASURE:` e.g. high-speed video of a leg against a protractor) or a faster readback path.

## Brian's read (2026-11-07, verbatim)

> My Phase 1 read: Path A is conditionally alive. Command rate (102 Hz) is fine, but servos lag ~100 ms (tracking falls off above ~2 Hz) and joint readback refreshes only every ~105 ms round-robin, while the sim models 4–8 ms of delay. Servo spec is 0.1 s/60° (a 10° move ≈ 17 ms unloaded) and 4.5 kg·cm ≈ 0.44 N·m (matches our 0.43 cap), so the motors are fast: the lag is mostly the motion board firmware and bus polling. Model it as command-pipeline delay + readback staleness, not slow motors.

## Decision (Brian, 2026-11-07, verbatim)

> Two experiments, both from EXP-005's config (feet_air_time 3.0), seed 42, one at a time:
> - EXP-009: add ~100 ms actuator/command delay (based on Phase 1 data). Nothing else changes.
> - EXP-010: EXP-009 + joint-position observations that refresh round-robin every ~105 ms (stale between refreshes).
>
> Hypothesis: both still walk, but slower and less precisely: higher tracking error, lower step frequency, more falls than EXP-005, with EXP-010 worse than EXP-009. If either can't walk or falls go high, next experiment adds the last ~5 actions to the observation (action history) so the policy knows what's in flight. If that fails too, we go Path B.
