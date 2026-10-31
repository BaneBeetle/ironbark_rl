"""Reward v1 (EXP-001): Brian's design, Brian's implementation.

Claude wrote only the signatures, docstrings, the tests (tests/brian/test_rewards.py,
run: python -m pytest tests/brian -q -k reward) and the glue that feeds these functions
from the simulator (ironbark_rl/tasks/s2_walk_brian/). Every function body and the
WEIGHTS are Brian's.

The design (docs/experiments/EXP-001-reward-v1-tracking-bonus-stability-smoothness.md):
  1. tracking bonus: largest term, >= 0, peaks when the dog matches the command
  2. stability penalty: body tilt + wobble
  3. smoothness penalty: how fast joint targets change
  4. falls end the episode (the environment's job; no term here)

Conventions:
- Inputs are torch tensors for N dogs at ONE time step (rewards are paid per step, so
  there is no time axis here, unlike metrics.py).
- Every function returns a (N,) magnitude >= 0. Sign and size come from WEIGHTS:
  positive weight = bonus, negative weight = penalty.
- mjlab sums weight * value * dt (dt = 0.02 s) per step. That rescales everything
  equally, so it doesn't change signs or which behavior scores higher.

numpy -> torch (same ideas, slightly different names):
  np.sum(x, axis=-1)          -> x.sum(dim=-1)
  np.linalg.norm(x, axis=-1)  -> torch.linalg.norm(x, dim=-1)
  np.exp / np.abs / np.clip   -> torch.exp / torch.abs / torch.clamp
  x[..., :2], x[..., 2]       -> identical

Typical EXP-000 walking step (sim, measured 2026-10-30, 256 dogs x 9 s; median / p90):
  planar tracking error 0.036 / 0.088 m/s   tilt 1.5 / 2.7 deg
  roll/pitch rate 0.19 / 0.48 rad/s         RMS joint-target rate 2.6 / 4.0 rad/s
The tests use these numbers as "a normal walking step".
"""

import torch

# TODO(Brian): term weights. Your priorities: tracking largest (positive), stability
# medium (negative), smoothness small (negative). "Priority" means each term's
# contribution (weight x value) at a typical step, not the raw weight. A normal
# walking step's total must stay > 0, or falling early would raise the score.
WEIGHTS: dict[str, float | None] = {
    "tracking": None,
    "stability": None,
    "smoothness": None,
}


def tracking_bonus(command: torch.Tensor, velocity: torch.Tensor) -> torch.Tensor:
    """Bonus for doing what the dog was told: matching the commanded velocity.

    Args:
      command: (N, 3) commanded (vx, vy, wz) in the body frame: m/s, m/s, rad/s.
      velocity: (N, 3) achieved (vx, vy, wz), same layout.

    Returns:
      (N,) >= 0. Largest when velocity == command, smaller as the error grows.
      Yours to decide: how the planar (vx, vy) and turning (wz) errors combine, the
      shape (e.g. 1 / (1 + error), exp(-error**2 / width**2)), and any width
      parameter (a named constant with a why).
    """
    raise NotImplementedError


def stability_penalty(projected_gravity_b: torch.Tensor, angular_velocity_b: torch.Tensor) -> torch.Tensor:
    """Cost for being tilted and for wobbling.

    Args:
      projected_gravity_b: (N, 3) unit gravity in the body frame, upright = (0, 0, -1)
        (same as metrics.tilt_deg's input).
      angular_velocity_b: (N, 3) body rotation rate around (x, y, z) = (roll, pitch,
        yaw), rad/s.

    Returns:
      (N,) >= 0, exactly 0 when upright and not rotating. Careful: one of the three
      rotation rates is something the dog is *ordered* to do.
    """
    raise NotImplementedError


def smoothness_penalty(joint_targets: torch.Tensor, prev_joint_targets: torch.Tensor, dt: float) -> torch.Tensor:
    """Cost for changing joint targets quickly (the per-step cousin of metrics.joint_target_rate).

    Args:
      joint_targets: (N, J) joint position targets sent this step, rad.
      prev_joint_targets: (N, J) targets sent the step before, rad.
      dt: time between the two, s (the policy period, 0.02).

    Returns:
      (N,) >= 0, exactly 0 when the targets don't change. Based on rad/s, so it
      doesn't depend on the policy rate.
    """
    raise NotImplementedError
