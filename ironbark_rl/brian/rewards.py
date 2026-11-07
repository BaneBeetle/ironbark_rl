"""Brian's legged_gym-style reward (Rudin et al. 2021): one function per term.

Who wrote what: Brian designed every term (frames, units, what each one penalizes) and wrote
feet_air_time. Claude wrote the other ten bodies on Brian's explicit request (2026-11-06,
overriding CLAUDE.md's "never write brian/" rule for these terms), with a WHY comment on
every line, plus the signatures, docstrings and tests (tests/brian/test_rewards.py, run:
python -m pytest tests/brian -q -k reward). Weights and tunable parameters live in
reward_config.py (Brian edits it); nothing is hardcoded here.

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

from ironbark_rl.brian import reward_config


def track_lin_vel_xy(command_xy: torch.Tensor, lin_vel_xy: torch.Tensor, width: float) -> torch.Tensor:
    """Bonus for matching the commanded planar velocity (an exp kernel).

    Args:
      command_xy: (num_envs, 2) commanded (vx, vy), body frame, m/s.
      lin_vel_xy: (num_envs, 2) achieved (vx, vy), body frame, m/s.
      width: kernel width, reward_config.TRACK_LIN_VEL_WIDTH. Yours: how it enters the
        kernel, its units, its value and a why.

    Returns:
      (num_envs,) in (0, 1]: exactly 1 when lin_vel_xy == command_xy, smaller as the error grows.

    Example (row 0: a typical walking step; row 1: lagging and drifting sideways), width 0.0625:
      command_xy (2, 2) [[0.30, 0.00], [0.30, 0.00]]
      lin_vel_xy (2, 2) [[0.274, 0.00], [0.10, 0.05]]
      ->         (2,)   [0.9892, 0.5066]
    """
    error = command_xy - lin_vel_xy  # (num_envs, 2) how far off we are in x and y, m/s
    squared_error = (error**2).sum(dim=-1)  # (num_envs,) squared length: any direction counts the same, big misses count more
    return torch.exp(-squared_error / width)  # (num_envs,) exp kernel: exactly 1 at zero error, fades smoothly toward 0, never negative


def track_ang_vel_z(command_wz: torch.Tensor, ang_vel_z: torch.Tensor, width: float) -> torch.Tensor:
    """Bonus for matching the commanded yaw rate (an exp kernel).

    Args:
      command_wz: (num_envs,) commanded yaw rate, rad/s.
      ang_vel_z: (num_envs,) achieved yaw rate, body frame, rad/s.
      width: kernel width, reward_config.TRACK_ANG_VEL_WIDTH.

    Returns:
      (num_envs,) in (0, 1]: exactly 1 when ang_vel_z == command_wz, smaller as the error grows.

    Example (row 0: typical; row 1: ordered to turn but not turning), width 0.16:
      command_wz (2,) [0.5, 0.5]
      ang_vel_z  (2,) [0.433, 0.0]
      ->         (2,) [0.9723, 0.2096]
    """
    squared_error = (command_wz - ang_vel_z) ** 2  # (num_envs,) square: over- and under-turning cost the same
    return torch.exp(-squared_error / width)  # (num_envs,) same kernel as planar tracking: 1 when perfect, in (0, 1]


def lin_vel_z(lin_vel_z_b: torch.Tensor) -> torch.Tensor:
    """Penalty for bouncing: the body's vertical velocity (body frame, your 2026-11-06 call).

    Args:
      lin_vel_z_b: (num_envs,) body-frame z velocity, m/s.

    Returns:
      (num_envs,) >= 0, exactly 0 when the body isn't moving along its z axis.

    Example (row 0: typical walking; row 1: a hop):
      lin_vel_z_b (2,) [0.009, -0.05]
      ->          (2,) [8.1e-05, 0.0025]
    """
    return lin_vel_z_b**2  # (num_envs,) square: bouncing up or down costs the same, and a big bounce costs far more than a tiny one


def ang_vel_xy(ang_vel_xy_b: torch.Tensor) -> torch.Tensor:
    """Penalty for wobbling: roll and pitch rates (body frame). Yaw rate is commanded, so it's not here.

    Args:
      ang_vel_xy_b: (num_envs, 2) body-frame (roll rate, pitch rate), rad/s.

    Returns:
      (num_envs,) >= 0, exactly 0 when not rolling or pitching.

    Example (row 0: typical walking; row 1: wobbling):
      ang_vel_xy_b (2, 2) [[0.15, 0.0], [0.3, -0.2]]
      ->           (2,)   [0.0225, 0.13]
    """
    return (ang_vel_xy_b**2).sum(dim=-1)  # (num_envs,) square each rate (sign-free, big wobbles dominate), then add roll + pitch


def orientation(projected_gravity_b: torch.Tensor) -> torch.Tensor:
    """Penalty for a tilted body.

    Args:
      projected_gravity_b: (num_envs, 3) unit gravity in the body frame. Level = (0, 0, -1);
        tilting moves weight into the x (pitch) and y (roll) components.

    Returns:
      (num_envs,) >= 0, exactly 0 when level.

    Example (row 0: 1.5 deg pitch, typical walking; row 1: 20 deg roll):
      projected_gravity_b (2, 3) [[0.0262, 0.0, -0.9997], [0.0, 0.342, -0.9397]]
      ->                  (2,)   [0.000685, 0.117]
    """
    tilt_xy = projected_gravity_b[:, :2]  # (num_envs, 2) gravity leaking into body x (pitch) and y (roll); (0, 0) only when level
    return (tilt_xy**2).sum(dim=-1)  # (num_envs,) equals sin^2(tilt): 0 when level, grows with tilt, same for left/right and fore/aft


def base_height(base_z: torch.Tensor, target_m: float) -> torch.Tensor:
    """Penalty for the body riding away from its target height.

    Args:
      base_z: (num_envs,) height of the `base` frame origin above the floor, m.
      target_m: reward_config.BASE_HEIGHT_TARGET_M (your ruler measurement).

    Returns:
      (num_envs,) >= 0, exactly 0 at target_m, > 0 above or below it.

    Example (row 0: typical walking spread; row 1: 2 cm sag), target_m 0.128:
      base_z (2,) [0.1303, 0.108]
      ->     (2,) [5.29e-06, 0.0004]
    """
    return (base_z - target_m) ** 2  # (num_envs,) square: too low and too high both cost, and a 2 cm sag costs 4x a 1 cm one


def torques(applied: torch.Tensor, requested: torch.Tensor, servo_limit_nm: float) -> torch.Tensor:
    """Penalty for servo effort.

    Args:
      applied: (num_envs, 12) torque each servo actually applies, N*m. It's clamped to
        +/- servo_limit_nm, so it can't show pushing past the cap.
      requested: (num_envs, 12) what each servo asks for before the clamp, N*m:
        kp * (delayed target - q) - kv * qd. Equal to applied below the cap.
      servo_limit_nm: the clamp, 0.43 N*m (a Mini2S placeholder, MEASURE in Phase 1).

    Returns:
      (num_envs,) >= 0, exactly 0 when no servo pushes. Penalizes the requested torque (Brian
      offered requested or the excess over the cap; requested also costs normal effort).

    Example (row 0: typical walking, 0.141 N*m on every joint; row 1: same, but one thigh
    requests 0.86 N*m, twice the cap), servo_limit_nm 0.43:
      requested (2, 12) [[0.141] * 12, [0.141] * 4 + [0.86] + [0.141] * 7]
      applied   (2, 12) requested clamped to +/- 0.43 (row 1's thigh delivers 0.43)
      ->        (2,)    [0.2386, 0.9583]
    """
    # `applied` and `servo_limit_nm` go unused on purpose: applied is clamped at the cap, so it can't see a servo pushing past it.
    return (requested**2).sum(dim=-1)  # (num_envs,) square the pre-clip request (legged_gym's effort cost); pushing past 0.43 N*m keeps costing more


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

    Example (row 0: typical walking, 36 rad/s^2 per joint; row 1: a jerk, 100 rad/s^2), dt 0.02:
      joint_vel      (2, 12) [[0.72] * 12, [2.0] * 12]
      prev_joint_vel (2, 12) zeros
      ->             (2,)    [15550, 120000]
    """
    acceleration = (joint_vel - prev_joint_vel) / dt  # (num_envs, 12) rad/s^2: velocity change per second, so it doesn't depend on the policy rate
    return (acceleration**2).sum(dim=-1)  # (num_envs,) square (sign-free, jerks dominate), then add all 12 joints


def action_rate(joint_targets: torch.Tensor, prev_joint_targets: torch.Tensor) -> torch.Tensor:
    """Penalty for changing the joint targets between policy steps (radians, your 2026-11-06 call).

    Args:
      joint_targets: (num_envs, 12) joint position targets this step, rad
        (default_joint_pos + 0.25 * action).
      prev_joint_targets: (num_envs, 12) last step's targets, rad. On an episode's first step
        it's the default pose (mjlab zeroes the stored actions on reset).

    Returns:
      (num_envs,) >= 0, exactly 0 when the targets don't change.

    Example (row 0: typical walking step, 0.042 rad per joint; row 1: a 0.2 rad jump):
      joint_targets      (2, 12) [[0.542] * 12, [0.7] * 12]
      prev_joint_targets (2, 12) [[0.5] * 12, [0.5] * 12]
      ->                 (2,)    [0.02117, 0.48]
    """
    change = joint_targets - prev_joint_targets  # (num_envs, 12) rad each joint target moved since the last policy step
    return (change**2).sum(dim=-1)  # (num_envs,) square (sign-free, big jumps dominate), then add all 12 joints


def feet_air_time(first_contact: torch.Tensor, last_air_time: torch.Tensor, command: torch.Tensor,
                  air_time_threshold_s: float) -> torch.Tensor:
    """Bonus for real steps, cost for flickers, paid at touchdown.

    Brian's spec (2026-11-06): a touchdown after a swing shorter than air_time_threshold_s
    pays negative (contact flicker, which hobby servos can't track), a longer swing pays
    positive, and nothing is paid unless the command asks the dog to move (forward,
    sideways or turning; turning in place needs steps too).

    Args:
      first_contact: (num_envs, 4) bool, True for a foot that touched down during this step.
        Feet in order fl, fr, br, bl.
      last_air_time: (num_envs, 4) s, how long each foot's last swing lasted. Where
        first_contact is True, that's the swing that just ended.
      command: (num_envs, 3) commanded (vx, vy, wz), m/s, m/s, rad/s.
      air_time_threshold_s: reward_config.FEET_AIR_TIME_THRESHOLD_S.

    Returns:
      (num_envs,), exactly 0 on a step where no foot touches down, or when the command is zero.
    """
    pay = last_air_time - air_time_threshold_s
    pay = pay * first_contact
    total = pay.sum(dim=1)
    moving = (torch.norm(command[:, :2], dim=1) > reward_config.MOVING_CMD_THRESHOLD) | (torch.abs(command[:, 2]) > reward_config.MOVING_CMD_THRESHOLD)
    return total * moving


def undesired_contacts(contact_forces: torch.Tensor, min_force_n: float) -> torch.Tensor:
    """Penalty for non-foot parts brushing the ground (anything over 1.43 N already ends the episode).

    Args:
      contact_forces: (num_envs, 9, 4, 3) ground-contact force on each non-foot part, N.
        Axis 1, the 9 parts: base, fl_hip, fl_thigh, fr_hip, fr_thigh, br_hip, br_thigh,
        bl_hip, bl_thigh. Axis 2: the last 4 physics substeps (4 ms each), index 0 newest.
        Axis 3: the force vector in the contact frame (use its length).
      min_force_n: reward_config.UNDESIRED_CONTACT_MIN_FORCE_N, below which a contact counts as solver noise.

    Returns:
      (num_envs,) >= 0, the number of non-foot parts touching; exactly 0 when only the feet touch.

    Example (row 0: only feet touch; row 1: fl_thigh brushes the floor at 1 N), min_force_n 0.1:
      contact_forces (2, 9, 4, 3) zeros, except [1, 2, 0] = (0, 0, 1.0)
      ->             (2,)         [0, 1]
    """
    force = torch.linalg.norm(contact_forces, dim=-1)  # (num_envs, 9, 4) N: force size; its contact-frame direction doesn't matter
    peak = force.amax(dim=-1)  # (num_envs, 9) N: hardest push over the last 4 substeps, so a brush between policy steps isn't missed
    touching = peak > min_force_n  # (num_envs, 9) bool: a real touch, not solver noise
    return touching.float().sum(dim=-1)  # (num_envs,) count of parts touching: a light, bounded cost per brush (big hits end the episode)
