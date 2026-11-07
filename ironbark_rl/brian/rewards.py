"""Brian's legged_gym-style reward (Rudin et al. 2021): one function per term. Brian's implementation.

Claude wrote only the signatures, docstrings and the tests (tests/brian/test_rewards.py,
run: python -m pytest tests/brian -q -k reward). Every function body is Brian's. Weights and
tunable parameters live in reward_config.py (Brian edits it); nothing is hardcoded here.

Conventions:
- Inputs are torch tensors for num_envs dogs at ONE policy step (0.02 s); there's no time axis.
- Every function returns (num_envs,).
- A term's weight in reward_config.WEIGHTS sets bonus (positive) or penalty (negative). The
  penalty functions return a magnitude >= 0 (legged_gym's convention); the sign comes from
  the weight.
- mjlab pays weight * value * dt per step (dt = 0.02 s). tools/reward_check.py and the
  TensorBoard tags Episode_Metrics/reward/<term> show each term's per-step contribution.

numpy -> torch (same ideas, slightly different names):
  np.sum(x, axis=-1)          -> x.sum(dim=-1)
  np.linalg.norm(x, axis=-1)  -> torch.linalg.norm(x, dim=-1)
  np.exp / np.abs / np.clip   -> torch.exp / torch.abs / torch.clamp
  np.max(x, axis=-1)          -> x.amax(dim=-1)
  x[..., :2], x[..., 2]       -> identical
  bool_mask.astype(float)     -> bool_mask.float()

Typical walking step: EXP-000 policy on env v2 (scoreboard conditions, 256 dogs x 9 s,
2026-11-06), median / p90. The scenario tests use these as "a normal walking step".
  planar tracking error 0.026 / 0.069 m/s     yaw-rate error 0.067 / 0.200 rad/s
  |vz| 0.009 / 0.029 m/s                      |roll, pitch rate| 0.15 / 0.38 rad/s
  tilt 1.5 / 2.8 deg                          base height 0.128 m (p10 0.124, p90 0.131)
  RMS servo torque 0.141 / 0.208 N*m (requested 0.141 / 0.212; 0.8% of servo-steps saturate)
  RMS joint acceleration 36 / 55 rad/s^2      RMS joint-target step 0.042 / 0.076 rad
  touchdowns 2.7 per foot per s; swing time at touchdown 0.136 s (p10 0.008, p90 0.192)
  non-foot ground contact: never
"""

import torch


def track_lin_vel_xy(command_xy: torch.Tensor, lin_vel_xy: torch.Tensor, width: float) -> torch.Tensor:
    """Bonus for matching the commanded planar velocity (an exp kernel).

    Args:
      command_xy: (num_envs, 2) commanded (vx, vy), body frame, m/s.
      lin_vel_xy: (num_envs, 2) achieved (vx, vy), body frame, m/s.
      width: kernel width, reward_config.TRACK_LIN_VEL_WIDTH. Yours: how it enters the
        kernel, its units, its value and a why.

    Returns:
      (num_envs,) in (0, 1]: exactly 1 when lin_vel_xy == command_xy, smaller as the error grows.
    """
    raise NotImplementedError


def track_ang_vel_z(command_wz: torch.Tensor, ang_vel_z: torch.Tensor, width: float) -> torch.Tensor:
    """Bonus for matching the commanded yaw rate (an exp kernel).

    Args:
      command_wz: (num_envs,) commanded yaw rate, rad/s.
      ang_vel_z: (num_envs,) achieved yaw rate, body frame, rad/s.
      width: kernel width, reward_config.TRACK_ANG_VEL_WIDTH.

    Returns:
      (num_envs,) in (0, 1]: exactly 1 when ang_vel_z == command_wz, smaller as the error grows.
    """
    raise NotImplementedError


def lin_vel_z(lin_vel_z_b: torch.Tensor) -> torch.Tensor:
    """Penalty for bouncing: the body's vertical velocity (body frame, your 2026-11-06 call).

    Args:
      lin_vel_z_b: (num_envs,) body-frame z velocity, m/s.

    Returns:
      (num_envs,) >= 0, exactly 0 when the body isn't moving along its z axis.
    """
    raise NotImplementedError


def ang_vel_xy(ang_vel_xy_b: torch.Tensor) -> torch.Tensor:
    """Penalty for wobbling: roll and pitch rates (body frame). Yaw rate is commanded, so it's not here.

    Args:
      ang_vel_xy_b: (num_envs, 2) body-frame (roll rate, pitch rate), rad/s.

    Returns:
      (num_envs,) >= 0, exactly 0 when not rolling or pitching.
    """
    raise NotImplementedError


def orientation(projected_gravity_b: torch.Tensor) -> torch.Tensor:
    """Penalty for a tilted body.

    Args:
      projected_gravity_b: (num_envs, 3) unit gravity in the body frame. Level = (0, 0, -1);
        tilting moves weight into the x (pitch) and y (roll) components.

    Returns:
      (num_envs,) >= 0, exactly 0 when level.
    """
    raise NotImplementedError


def base_height(base_z: torch.Tensor, target_m: float) -> torch.Tensor:
    """Penalty for the body riding away from its target height.

    Args:
      base_z: (num_envs,) height of the `base` frame origin above the floor, m.
      target_m: reward_config.BASE_HEIGHT_TARGET_M (your ruler measurement).

    Returns:
      (num_envs,) >= 0, exactly 0 at target_m, > 0 above or below it.
    """
    raise NotImplementedError


def torques(applied: torch.Tensor, requested: torch.Tensor, servo_limit_nm: float) -> torch.Tensor:
    """Penalty for servo effort.

    Args:
      applied: (num_envs, 12) torque each servo actually applies, N*m. It's clamped to
        +/- servo_limit_nm, so it can't show pushing past the cap.
      requested: (num_envs, 12) what each servo asks for before the clamp, N*m:
        kp * (delayed target - q) - kv * qd. Equal to applied below the cap.
      servo_limit_nm: the clamp, 0.43 N*m (a Mini2S placeholder, MEASURE in Phase 1).

    Returns:
      (num_envs,) >= 0, exactly 0 when no servo pushes. Yours: penalize applied, requested,
      the excess over the cap, or a mix.
    """
    raise NotImplementedError


def joint_acc(joint_vel: torch.Tensor, prev_joint_vel: torch.Tensor, dt: float) -> torch.Tensor:
    """Penalty for jerky joints: acceleration across one policy step (your 2026-11-06 call).

    Args:
      joint_vel: (num_envs, 12) joint velocities now, rad/s.
      prev_joint_vel: (num_envs, 12) joint velocities one policy step ago, rad/s. After a
        reset it's the reset velocity, so an episode's first step has no fake spike.
      dt: the policy period, s (0.02).

    Returns:
      (num_envs,) >= 0, exactly 0 when no joint velocity changed (even if the joints move).
      Based on rad/s^2, so it doesn't depend on the policy rate.
    """
    raise NotImplementedError


def action_rate(joint_targets: torch.Tensor, prev_joint_targets: torch.Tensor) -> torch.Tensor:
    """Penalty for changing the joint targets between policy steps (radians, your 2026-11-06 call).

    Args:
      joint_targets: (num_envs, 12) joint position targets this step, rad
        (default_joint_pos + 0.25 * action).
      prev_joint_targets: (num_envs, 12) last step's targets, rad. On an episode's first step
        it's the default pose (mjlab zeroes the stored actions on reset).

    Returns:
      (num_envs,) >= 0, exactly 0 when the targets don't change.
    """
    raise NotImplementedError


def feet_air_time(first_contact: torch.Tensor, last_air_time: torch.Tensor, command: torch.Tensor) -> torch.Tensor:
    """Bonus (or cost) tied to each foot's swing, paid at touchdown.

    Args:
      first_contact: (num_envs, 4) bool, True for a foot that touched down during this step.
        Feet in order fl, fr, br, bl.
      last_air_time: (num_envs, 4) s, how long each foot's last swing lasted. Where
        first_contact is True, that's the swing that just ended.
      command: (num_envs, 3) commanded (vx, vy, wz), if your design depends on it.

    Returns:
      (num_envs,), exactly 0 on a step where no foot touches down. Any parameters (named
      constants with a why) go in reward_config.py.
    """
    raise NotImplementedError


def undesired_contacts(contact_forces: torch.Tensor) -> torch.Tensor:
    """Penalty for non-foot parts brushing the ground (anything over 1.43 N already ends the episode).

    Args:
      contact_forces: (num_envs, 9, 4, 3) ground-contact force on each non-foot part, N.
        Axis 1, the 9 parts: base, fl_hip, fl_thigh, fr_hip, fr_thigh, br_hip, br_thigh,
        bl_hip, bl_thigh. Axis 2: the last 4 physics substeps (4 ms each), index 0 newest.
        Axis 3: the force vector in the contact frame (use its length).

    Returns:
      (num_envs,) >= 0, exactly 0 when nothing but the feet touches the ground.
    """
    raise NotImplementedError
