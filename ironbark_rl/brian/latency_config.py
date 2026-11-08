"""Real-dog latency model for the sim (Brian's numbers, 2026-11-07; data: docs/phase1-joint-control-results.md).

Brian's Phase 1 read: the servos are fast (spec 0.1 s/60 deg), the lag is the motion board's firmware
and bus polling, so model it as a command-pipeline delay plus readback staleness, not as slow motors.
Claude wrote this file; every value is Brian's call (he chose each recommendation in the 2026-11-07
design questions).
"""

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

# Slot of each sim joint in that cycle. xgolib numbers leg 1-4 x joint 1-3 and labels its joint limits
# lower / middle / upper; the measured stance (joint 1 ~19 deg, joint 2 ~40 deg, joint 3 ~0 deg) fits
# calf / thigh / hip. The leg order follows the vendor MJCF's (fl, fr, br, bl).
# MEASURE: which physical leg and joint each xgolib id drives (probe `step`: watch which joint moves).
# With a random phase per env, each joint's reading age is uniform over 0-130 ms whatever its slot;
# only the timing between joints depends on this mapping.
XGO_LEG_ORDER = ("fl", "fr", "br", "bl")  # xgolib legs 1, 2, 3, 4
XGO_JOINT_ORDER = ("calf", "thigh", "hip")  # xgolib joints 1, 2, 3


def readback_slot(sim_joint_name: str) -> int:
    """Polling slot (0-11) of a sim joint such as 'fr_thigh_joint' -> leg 2, joint 2 -> slot 4."""
    leg, part, _ = sim_joint_name.split("_")  # "fr", "thigh", "joint"
    return 3 * XGO_LEG_ORDER.index(leg) + XGO_JOINT_ORDER.index(part)  # ID order: leg-major, then joint
