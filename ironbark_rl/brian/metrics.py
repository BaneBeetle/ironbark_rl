"""Scoreboard metrics: the fixed yardstick every experiment is compared on.

Brian implements this file. Claude wrote only the signatures, docstrings and the tests
in tests/brian/test_metrics.py (run: python -m pytest tests/brian). Scoreboard rules:
docs/experiments/README.md.

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

# Bump to "v1" when you freeze the scoreboard. Once frozen, any change to this file
# means re-evaluating every experiment you compare against.
SCOREBOARD_VERSION = "v0-draft"

# TODO(Brian): tilt from vertical (degrees) beyond which the dog counts as fallen.
# Justify it in a comment. What tilt can the S2 still recover from? What does the
# IMU read when the dog walks normally?
FALL_TILT_DEG: float | None = None

# TODO(Brian): the fixed command grid, shape (K, 3): rows of (vx, vy, wz).
# Must include standing still. Stay inside what the real S2 can do. Measured so far:
# the firmware turns at 39.2 deg/s (0.68 rad/s) when commanded 40. Forward speed is
# not yet measured (# MEASURE: firmware gait top speed, tape + phone timer).
COMMAND_GRID: np.ndarray | None = None

# TODO(Brian): below this mean ground speed (m/s), cost of transport is undefined
# (it divides by speed). Pick a value and say why.
MIN_SPEED_FOR_COT_MPS: float | None = None


def tilt_deg(projected_gravity_b: np.ndarray) -> np.ndarray:
    """Body tilt from vertical, in degrees.

    Args:
      projected_gravity_b: (..., 3) unit gravity direction in the body frame.
        Upright = (0, 0, -1). Sim: robot.data.projected_gravity_b. Real dog: built
        from IMU roll/pitch.

    Returns:
      (...) degrees: 0 = upright, 90 = on its side, 180 = upside down.
    """
    raise NotImplementedError


def is_fallen(projected_gravity_b: np.ndarray) -> np.ndarray:
    """Per-step fall flag, using FALL_TILT_DEG.

    Args:
      projected_gravity_b: (T, N, 3), as in tilt_deg.

    Returns:
      (T, N) bool, True where the dog counts as fallen at that step.
    """
    raise NotImplementedError


def fall_rate(fallen: np.ndarray) -> float:
    """Fraction of episodes that fell at least once.

    Args:
      fallen: (T, N) bool from is_fallen.

    Returns:
      float in [0, 1]. An episode that is flagged at several steps counts once.
    """
    raise NotImplementedError


def steps_before_fall(fallen: np.ndarray) -> np.ndarray:
    """Mask of the steps that count for the other metrics: everything before an episode's first fall.

    Args:
      fallen: (T, N) bool from is_fallen.

    Returns:
      (T, N) bool. True strictly before the first fall in each episode, False from
      the first fall onwards, even if the dog is later flagged upright again.
    """
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError
