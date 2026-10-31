"""Scoreboard metrics: the fixed yardstick every experiment is compared on.

Who wrote what (an exception to "Claude never implements brian/", Brian's call on
2026-10-30, so the time goes to reward design):
- Brian: tilt_deg, is_fallen, fall_rate, steps_before_fall, FALL_TILT_DEG.
- Claude, implementing Brian's decisions: velocity_tracking_error, joint_target_rate
  (RMS), cost_of_transport (|torque x velocity|), COMMAND_GRID, MIN_SPEED_FOR_COT_MPS.
  Brian reviews these and must be able to explain every line.
- Claude also wrote the signatures, docstrings and tests in tests/brian/test_metrics.py
  (run: python -m pytest tests/brian).
Scoreboard rules: docs/experiments/README.md.

Design constraints, from the 2026-10-30 discussion:
- Comparable across rewards AND action spaces: physical units only. Never reward
  values, never normalized actions.
- Computable on the real dog wherever possible. The S2 reports IMU roll/pitch/yaw and
  joint *angles* only: no joint torques, no joint velocities, no body velocity.
  Mark sim-only metrics as such.
- A fall is defined here, not by the environment's termination terms. Otherwise
  changing the terminations would quietly change the score.

Array conventions (numpy):
  T = time steps, N = episodes (one per env), J = joints (12 on the S2).
  Base-frame velocity / command vectors are (vx, vy, wz) in (m/s, m/s, rad/s).

The evaluation harness (Claude's) runs the policy on COMMAND_GRID, converts the
rollout to these arrays, calls these functions, and records SCOREBOARD_VERSION with
every result.
"""

import numpy as np

# Frozen 2026-10-30. Any change to this file means bumping the version and
# re-evaluating every experiment you compare against (checkpoints are kept, so it's cheap).
# FALL_TILT_DEG is still provisional: re-check it with the trained-policy tilt sweep.
SCOREBOARD_VERSION = "v1"

# TODO(Brian): tilt from vertical (degrees) beyond which the dog counts as fallen.
# Justify it in a comment. What tilt can the S2 still recover from? What does the
# IMU read when the dog walks normally?
FALL_TILT_DEG: float = 46 # Mathematically, it would be able to handle 36.8 degrees. We will give 10 whole degrees of room and if it hits 46, I'm fairly certain it fell over (this would be a point of no return). This is our first place holder
# Fixed command grid, shape (K, 3): rows of (vx [m/s], vy [m/s], wz [rad/s]).
# (Claude, Brian's accepted default.) Inside the training command ranges (vx -0.5..0.6,
# vy +-0.3, wz +-0.8) and below the real S2's measured firmware turn rate (39.2 deg/s =
# 0.68 rad/s). MEASURE: the S2's real forward top speed (tape + phone timer); revisit
# the 0.4 m/s row once known.
COMMAND_GRID: np.ndarray = np.array([
    [0.0, 0.0, 0.0],    # stand still
    [0.2, 0.0, 0.0],    # walk forward
    [0.4, 0.0, 0.0],    # walk forward, faster
    [-0.2, 0.0, 0.0],   # walk backward
    [0.0, 0.2, 0.0],    # sidestep left
    [0.0, -0.2, 0.0],   # sidestep right
    [0.0, 0.0, 0.5],    # turn left in place
    [0.0, 0.0, -0.5],   # turn right in place
])

# Below this mean ground speed, cost of transport is undefined (it divides by speed and
# blows up as the dog stands still). (Claude, Brian's accepted default.) The standing
# row of COMMAND_GRID will report NaN CoT by design.
MIN_SPEED_FOR_COT_MPS: float = 0.05

UPRIGHT_GRAVITY = (0, 0, -1)

def tilt_deg(projected_gravity_b: np.ndarray) -> np.ndarray:
    """Body tilt from vertical, in degrees.

    Args:
      projected_gravity_b: (..., 3) unit gravity direction in the body frame.
        Upright = (0, 0, -1). Sim: robot.data.projected_gravity_b. Real dog: built
        from IMU roll/pitch.

    Returns:
      (...) degrees: 0 = upright, 90 = on its side, 180 = upside down.

    """
    

    cos_tilt = np.dot(projected_gravity_b, UPRIGHT_GRAVITY)
    cos_tilt = np.clip(cos_tilt, -1.0, 1.0)
    return np.degrees(np.arccos(cos_tilt))


def is_fallen(projected_gravity_b: np.ndarray) -> np.ndarray:
    """Per-step fall flag, using FALL_TILT_DEG.

    Args:
      projected_gravity_b: (T, N, 3), as in tilt_deg.

    Returns:
      (T, N) bool, True where the dog counts as fallen at that step.
    """
    return tilt_deg(projected_gravity_b) >= FALL_TILT_DEG
    


def fall_rate(fallen: np.ndarray) -> float:
    """Fraction of episodes that fell at least once.

    Args:
      fallen: (T, N) bool from is_fallen.

    Returns:
      float in [0, 1]. An episode that is flagged at several steps counts once.
    """
    return float(fallen.any(axis=0).mean())

def steps_before_fall(fallen: np.ndarray) -> np.ndarray:
    """Mask of the steps that count for the other metrics: everything before an episode's first fall.

    Args:
      fallen: (T, N) bool from is_fallen.

    Returns:
      (T, N) bool. True strictly before the first fall in each episode, False from
      the first fall onwards, even if the dog is later flagged upright again.
    """
    return np.cumsum(fallen, axis=0) == 0


def velocity_tracking_error(command: np.ndarray, velocity: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """How far the achieved base velocity is from the command, per episode.

    Args:
      command: (T, N, 3) commanded (vx, vy, wz), base frame.
      velocity: (T, N, 3) achieved (vx, vy, wz), base frame. Real dog: wz comes from
        the IMU; vx, vy need an external estimate (sim-only until we have one).
      valid: (T, N) bool, steps to include (e.g. steps_before_fall).

    Returns:
      (linear_error, yaw_rate_error), each (N,):
        linear_error: mean over valid steps of the planar (vx, vy) error norm, m/s.
        yaw_rate_error: mean over valid steps of |wz error|, rad/s.
      NaN for an episode with no valid steps.
    """
    # (Claude) Error at every step for every dog, then average only the valid steps.
    error = velocity - command                                   # (T, N, 3)
    planar_error = np.linalg.norm(error[..., :2], axis=-1)       # (T, N), m/s
    yaw_rate_error = np.abs(error[..., 2])                       # (T, N), rad/s
    return _mean_over_valid_steps(planar_error, valid), _mean_over_valid_steps(yaw_rate_error, valid)


def _mean_over_valid_steps(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """(Claude) Per-episode mean over time of `values` (T, N), using only `valid` steps; NaN if none."""
    valid_count = valid.sum(axis=0)                              # (N,) how many steps count
    valid_total = np.where(valid, values, 0.0).sum(axis=0)       # (N,) sum of the steps that count
    with np.errstate(invalid="ignore", divide="ignore"):         # 0/0 for no-valid episodes -> NaN below
        return np.where(valid_count > 0, valid_total / valid_count, np.nan)


def joint_target_rate(joint_targets: np.ndarray, dt: float) -> np.ndarray:
    """Smoothness of the commanded joint targets, per episode, in rad/s (lower = smoother).

    Uses the targets sent to the servos, not the policy's raw actions, so it compares
    fairly across action spaces. Works on the real dog: the Pi logs what it sends.
    You choose the statistic (mean |rate|, RMS, ...); say why in a comment.

    Args:
      joint_targets: (T, N, J) joint position targets, rad.
      dt: time between consecutive targets, s (the policy period).

    Returns:
      (N,) rad/s.
    """
    # (Claude, Brian's choice: RMS.) RMS weights big sudden target jumps more than mean
    # |rate| does, and sudden jumps are what stress servos and transfer badly to hardware.
    rate = np.diff(joint_targets, axis=0) / dt                   # (T-1, N, J) rad/s
    return np.sqrt(np.mean(rate ** 2, axis=(0, 2)))              # (N,) over time and joints


def cost_of_transport(
    joint_torque: np.ndarray,
    joint_velocity: np.ndarray,
    base_velocity_xy: np.ndarray,
    mass_kg: float,
    gravity_mps2: float = 9.81,
) -> np.ndarray:
    """Dimensionless energy efficiency: mechanical power / (weight x speed), per episode.

    SIM ONLY: the S2 has no torque or joint-velocity sensing.

    Args:
      joint_torque: (T, N, J) actuator torques, N*m.
      joint_velocity: (T, N, J) joint velocities, rad/s.
      base_velocity_xy: (T, N, 2) planar base velocity, m/s.
      mass_kg: total robot mass.
      gravity_mps2: gravitational acceleration.

    Returns:
      (N,) dimensionless. NaN where the episode's mean ground speed is below
      MIN_SPEED_FOR_COT_MPS. Decide (and justify) how negative mechanical power
      (joints being back-driven) is counted.
    """
    # (Claude, Brian's choice: absolute power.) Hobby servos draw current to brake as well
    # as to drive and can't recover energy, so back-driven (negative) power still costs.
    power_w = np.abs(joint_torque * joint_velocity).sum(axis=-1)     # (T, N) summed over joints
    mean_power_w = power_w.mean(axis=0)                              # (N,)
    mean_speed_mps = np.linalg.norm(base_velocity_xy, axis=-1).mean(axis=0)  # (N,)
    with np.errstate(invalid="ignore", divide="ignore"):
        cot = mean_power_w / (mass_kg * gravity_mps2 * mean_speed_mps)
    return np.where(mean_speed_mps >= MIN_SPEED_FOR_COT_MPS, cot, np.nan)
