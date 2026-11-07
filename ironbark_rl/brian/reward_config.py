"""Reward weights and parameters for IronBark-S2-Walk-Flat-Brian. Brian edits this file.

The task reads every weight and reward parameter from here; nothing else hardcodes one.
A value still None stops training with an error, so no term can run unset.
"""

# One weight per function in rewards.py. Positive = bonus, negative = penalty.
# mjlab pays weight * value * dt per step (dt = 0.02 s). A normal walking step's total must
# stay > 0, or falling early raises the return: tools/reward_check.py reports each term's
# per-step contribution (TensorBoard: Episode_Metrics/reward/<term>).
WEIGHTS: dict[str, float | None] = {
    "track_lin_vel_xy": None,
    "track_ang_vel_z": None,
    "lin_vel_z": None,
    "ang_vel_xy": None,
    "orientation": None,
    "base_height": None,
    "torques": None,
    "joint_acc": None,
    "action_rate": None,
    "feet_air_time": None,
    "undesired_contacts": None,
}

# Exp-kernel widths of the two tracking bonuses (units follow your kernel).
TRACK_LIN_VEL_WIDTH: float | None = None
TRACK_ANG_VEL_WIDTH: float | None = None

# feet_air_time: a touchdown after a swing shorter than this pays negative (Brian, 2026-11-06).
# Must sit above contact flicker (p10 swing 0.008 s) and below a typical swing (median 0.136 s),
# both EXP-000 on env v2; tests/brian/test_rewards.py checks both.
FEET_AIR_TIME_THRESHOLD_S: float | None = 0.07

# MEASURE: real S2 standing height of the sim's `base` frame origin, m. Brian measures it:
#   dog standing in its default pose on a flat floor, ruler from the floor to the centre of
#   each thigh (upper-leg) pivot, mean of the 4 legs, plus 0.021 m (the sim's offset from
#   the thigh pivot up to the `base` origin, S2 standing pose, 2026-11-06). For reference,
#   the sim's default pose stands at 0.123 m (thigh pivots at ~0.102 m), but that stance
#   is a Mini2S placeholder. EXP-000 walks at 0.128 m (median, env v2).
BASE_HEIGHT_TARGET_M: float | None = None
