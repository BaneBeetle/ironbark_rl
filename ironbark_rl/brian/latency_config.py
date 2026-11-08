"""Real-dog latency model for the sim (Brian's numbers, 2026-11-07; data: docs/phase1-joint-control-results.md).

Brian's Phase 1 read: the servos are fast (spec 0.1 s/60 deg), the lag is the motion board's firmware
and bus polling, so model it as a command-pipeline delay plus readback staleness, not as slow motors.
Claude wrote this file; every value is Brian's call (he chose each recommendation in the 2026-11-07
design questions).
"""

from ironbark_rl.assets.s2_joint_map import SIM_JOINT_TO_XGO_ID, XGO_ID_TO_SIM_JOINT

# EXP-009. Time from a joint command leaving the Pi to the servo starting to move.
# Brian chose 40 ms over his first estimate of ~100 ms: the earliest of 18 measured step responses moved
# 50 ms after the command, and the sine lag (88 ms) minus the mean readback age (~52 ms) is ~36 ms.
# The rest of the ~100 ms seen in readback is staleness, which EXP-010 models separately.
# Fixed, the same in every env (one change; randomization is Phase 2A week 5). Replaces Luwu's 4-8 ms.
COMMAND_DELAY_S = 0.040

# EXP-010. The firmware re-polls the servos one at a time and read_motor() returns the last polled
# value, so each joint's reading is a sample-and-hold refreshed once per cycle.
# 130 ms: the cycle measured while all 12 joints were commanded at 55 Hz, like a policy does
# (coarse: 126-144 ms, reads were 18 ms apart). With single-joint commands it was 105 ms.
JOINT_REFRESH_PERIOD_S = 0.130

# Slots per polling cycle: the 12 leg joints in ID order 11, 12, 13, 21, ..., 43, then about 3 empty
# slots where the absent arm (51-53) would be (the 43 -> 11 gap was ~3 slots long in the rate log).
READBACK_SLOTS = 15

# Slot of each sim joint in that cycle: its xgolib id's position in ID order (11, 12, 13, 21, ..., 43).
# The id <-> sim joint map was verified on the dog by Brian (ironbark_rl/assets/s2_joint_map.py).
_POLL_ORDER = sorted(XGO_ID_TO_SIM_JOINT)  # [11, 12, 13, 21, ..., 43]


def readback_slot(sim_joint_name: str) -> int:
    """Polling slot (0-11) of a sim joint, e.g. 'fr_thigh_joint' -> xgolib id 22 -> slot 4."""
    return _POLL_ORDER.index(SIM_JOINT_TO_XGO_ID[sim_joint_name])  # ID order is the firmware's poll order


# IMU freezes (scoring only, no training; Brian, 2026-11-07: "Score EXP-010's policy with simulated IMU
# freezes matching our logs (no retraining)"). The whole IMU block (accel, gyro, roll/pitch/yaw) repeats an
# identical value for ~1 s at a time, then updates live for a while. Durations in ms, from every IMU run's
# read_imu() series (docs/measurements/joint_control_imu*_20261108-*.jsonl), a "frozen" stretch being a
# repeat run longer than 100 ms; the first and last stretch of each run are dropped (cut off by the run's
# start or end). Recomputed from the logs by tests/brian/test_obs.py (tools/joint_control_report.py).
# Overall the IMU was frozen 41.8% of the time.
IMU_FROZEN_MS = (882, 882, 884, 886, 886, 966, 966, 980, 982, 983, 987, 987, 987, 987, 987, 987, 987, 987, 987,
                 987, 987, 987, 987, 992, 992, 995, 999, 999, 999, 999, 999, 999, 1001, 1001, 1002, 1003, 1003, 1004)
IMU_LIVE_MS = (25, 42, 46, 71, 98, 101, 118, 126, 202, 252, 273, 315, 378, 378, 420, 445, 483, 513, 546, 602, 630,
               691, 763, 945, 966, 1004, 1047, 1186, 1596, 1876, 2121, 2276, 2670, 2870, 3108, 3213, 3258, 3388,
               5923, 6630)
