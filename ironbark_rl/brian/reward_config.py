"""Reward weights and parameters for IronBark-S2-Walk-Flat-Brian. Brian edits this file.

The task reads every weight and reward parameter from here; nothing else hardcodes one.
A value still None stops training with an error, so no term can run unset.
"""

# One weight per function in rewards.py. Positive = bonus, negative = penalty.
# mjlab pays weight * value * dt per step (dt = 0.02 s). A normal walking step's total must
# stay > 0, or falling early raises the return: tools/reward_check.py reports each term's
# per-step contribution (TensorBoard: Episode_Metrics/reward/<term>).
# Starting weights (Brian approved 2026-11-06): legged_gym's recipe (Rudin et al. 2021), rescaled by
# dynamic similarity (Froude) for the S2, which is ~0.5x an A1's height (0.123 vs 0.25 m) and ~0.08x its mass.
WEIGHTS: dict[str, float | None] = {
    "track_lin_vel_xy": 1.0,  # the main job; every other weight is sized against it (legged_gym 1.0)
    "track_ang_vel_z": 0.5,  # turning counts half as much as going where told (legged_gym 0.5)
    "lin_vel_z": -4.0,  # legged_gym -2.0, x2: a small dog moves ~0.7x as fast, so v^2 is ~0.5x
    "ang_vel_xy": -0.025,  # legged_gym -0.05, x0.5: a small dog rotates ~1.4x faster, so w^2 is ~2x
    "orientation": -5.0,  # legged_gym ANYmal-C flat; tilt has no units, so no rescaling
    "base_height": -50.0,  # weak while the target is unmeasured: 2 cm off costs 2% of the tracking bonus
    "torques": -0.125,  # legged_gym A1 -0.0002, x600: torque ~ mass x length is ~0.04x an A1's
    "joint_acc": -6e-8,  # legged_gym -2.5e-7, /4: joint accelerations ~2x an A1's; a light regularizer
    "action_rate": -0.08,  # legged_gym -0.01 on raw actions = -0.16 on targets (/0.25^2), x0.5 for faster joints
    "feet_air_time": 30.0,  # sweep run (Brian, 2026-11-07): EXP-003 had 1.0, EXP-004 7.5; after the sweep this goes back to EXP-004's 7.5
    "undesired_contacts": -0.25,  # Brian's small weight: a brushing part costs a quarter of the planar tracking bonus. Dormant on flat ground (Brian, 2026-11-07): contacts over 1.43 N end the episode first, and lighter brushes never occur
}

# Exp-kernel widths of the two tracking bonuses (units follow your kernel).
TRACK_LIN_VEL_WIDTH: float | None = 0.0625  # (m/s)^2: legged_gym's 0.25 x (our ~0.5 m/s commands / its ~1 m/s)^2; 1/e at a 0.25 m/s miss
TRACK_ANG_VEL_WIDTH: float | None = 0.16  # (rad/s)^2: legged_gym's 0.25 x 0.8^2 (our +/-0.8 rad/s yaw range vs its +/-1)

# feet_air_time: a touchdown after a swing shorter than this pays negative (Brian, 2026-11-06).
# Must sit above contact flicker (p10 swing 0.008 s) and below a typical swing (median 0.136 s),
# both EXP-000 on env v2; tests/brian/test_rewards.py checks both.
FEET_AIR_TIME_THRESHOLD_S: float | None = 0.07

# feet_air_time's gate (Brian's mask): a command counts as "move" when its planar speed (m/s) or
# its yaw rate (rad/s) exceeds this. One number for both units, Brian's 0.1.
MOVING_CMD_THRESHOLD = 0.1

# undesired_contacts: a non-foot part counts as touching only above this force, so contact-solver
# noise isn't penalized. Anything over 1.43 N already ends the episode.
UNDESIRED_CONTACT_MIN_FORCE_N: float | None = 0.1  # legged_gym's contact threshold

# MEASURE: real S2 standing height of the sim's `base` frame origin, m. Brian measures it:
#   dog standing in its default pose on a flat floor, ruler from the floor to the centre of
#   each thigh (upper-leg) pivot, mean of the 4 legs, plus 0.021 m (the sim's offset from
#   the thigh pivot up to the `base` origin, S2 standing pose, 2026-11-06). For reference,
#   the sim's default pose stands at 0.123 m (thigh pivots at ~0.102 m), but that stance
#   is a Mini2S placeholder. EXP-000 walks at 0.128 m (median, env v2).
# Interim (Brian, 2026-11-06): the sim's default-pose standing height, until the ruler measurement.
BASE_HEIGHT_TARGET_M: float | None = 0.123
