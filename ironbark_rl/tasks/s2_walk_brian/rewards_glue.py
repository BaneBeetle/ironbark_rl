"""Simulator -> Brian's reward terms (ironbark_rl/brian/rewards.py).

Claude's glue: it only pulls tensors out of the simulator, in the frames and units Brian chose,
and hands them over. No reward logic lives here. Tensor sources were checked in the S2 env
(docs/progress.md, 2026-11-06). mjlab calls each term once per policy step, after the 5
physics substeps and before resets.
"""

import torch

from ironbark_rl.brian import reward_config as config
from ironbark_rl.brian import rewards as brian

ROBOT = "robot"
TWIST_COMMAND = "twist"  # the velocity command term
JOINT_ACTION = "joint_pos"  # the joint-position action term
FEET_SENSOR = "feet_ground_contact"  # the 4 calf collision geoms vs the terrain
NONFOOT_SENSOR = "nonfoot_ground_touch"  # every other robot geom vs the terrain
# Axis-1 order of rewards.undesired_contacts' input: the non-foot parts that can touch the ground.
NONFOOT_PARTS = ("base", "fl_hip", "fl_thigh", "fr_hip", "fr_thigh", "br_hip", "br_thigh", "bl_hip", "bl_thigh")


def _robot(env):
    return env.scene[ROBOT]


def track_lin_vel_xy(env) -> torch.Tensor:
    command = env.command_manager.get_command(TWIST_COMMAND)  # (num_envs, 3) body-frame (vx, vy, wz)
    velocity = _robot(env).data.root_link_lin_vel_b  # (num_envs, 3) body frame, same as the scoreboard
    return brian.track_lin_vel_xy(command[:, :2], velocity[:, :2], config.TRACK_LIN_VEL_WIDTH)


def track_ang_vel_z(env) -> torch.Tensor:
    command = env.command_manager.get_command(TWIST_COMMAND)  # (num_envs, 3)
    yaw_rate = _robot(env).data.root_link_ang_vel_b[:, 2]  # (num_envs,)
    return brian.track_ang_vel_z(command[:, 2], yaw_rate, config.TRACK_ANG_VEL_WIDTH)


def lin_vel_z(env) -> torch.Tensor:
    return brian.lin_vel_z(_robot(env).data.root_link_lin_vel_b[:, 2])  # (num_envs,) body frame (Brian)


def ang_vel_xy(env) -> torch.Tensor:
    return brian.ang_vel_xy(_robot(env).data.root_link_ang_vel_b[:, :2])  # (num_envs, 2) body frame (Brian)


def orientation(env) -> torch.Tensor:
    return brian.orientation(_robot(env).data.projected_gravity_b)  # (num_envs, 3)


def base_height(env) -> torch.Tensor:
    # Flat plane at z = 0 and every env origin at z = 0, so world z is the height above the floor.
    return brian.base_height(_robot(env).data.root_link_pos_w[:, 2], config.BASE_HEIGHT_TARGET_M)  # (num_envs,)


class torques:
    """Applied and requested (pre-clip) servo torque. MuJoCo position servo: force = kp * ctrl + b0 + b1*q + b2*qd,
    ctrl clamped to ctrlrange, then the force clamped to forcerange (= actuator_force). Checked to 7e-8 N*m."""

    def __init__(self, cfg, env):
        robot = _robot(env)
        self.ctrl_ids = robot.indexing.ctrl_ids  # (12,) this robot's servos in the global ctrl vector
        ctrlrange = env.sim.mj_model.actuator_ctrlrange[self.ctrl_ids.cpu()]  # (12, 2) rad
        self.ctrl_lo = torch.as_tensor(ctrlrange[:, 0], dtype=torch.float32, device=env.device)  # (12,)
        self.ctrl_hi = torch.as_tensor(ctrlrange[:, 1], dtype=torch.float32, device=env.device)  # (12,)
        self.servo_limit_nm = float(env.sim.mj_model.actuator_forcerange[self.ctrl_ids.cpu(), 1].max())  # 0.43

    def __call__(self, env) -> torch.Tensor:
        robot, model, data = _robot(env), env.sim.model, env.sim.data
        kp = model.actuator_gainprm[:, self.ctrl_ids, 0]  # (num_envs, 12) per env, in case it's ever randomized
        bias = model.actuator_biasprm[:, self.ctrl_ids, :3]  # (num_envs, 12, 3) = (0, -kp, -kv)
        ctrl = data.ctrl[:, self.ctrl_ids].clamp(self.ctrl_lo, self.ctrl_hi)  # (num_envs, 12) the delayed target
        q, qd = robot.data.joint_pos, robot.data.joint_vel  # (num_envs, 12) each
        requested = kp * ctrl + bias[..., 0] + bias[..., 1] * q + bias[..., 2] * qd  # (num_envs, 12) N*m
        return brian.torques(robot.data.actuator_force, requested, self.servo_limit_nm)


class joint_acc:
    """Keeps the previous policy step's joint velocity (Brian: acceleration across policy steps)."""

    def __init__(self, cfg, env):
        self.robot = _robot(env)  # reset() gets only env_ids, so keep the robot
        self.prev_joint_vel = self.robot.data.joint_vel.clone()  # (num_envs, 12)

    def __call__(self, env) -> torch.Tensor:
        joint_vel = self.robot.data.joint_vel  # (num_envs, 12)
        out = brian.joint_acc(joint_vel, self.prev_joint_vel, env.step_dt)  # (num_envs,)
        self.prev_joint_vel[:] = joint_vel  # this step becomes next step's "previous"
        return out

    def reset(self, env_ids):
        # Runs after mjlab wrote the reset state, and joint_vel reads qvel directly, so this is the
        # post-reset velocity: an episode's first step sees no fake spike.
        env_ids = slice(None) if env_ids is None else env_ids
        self.prev_joint_vel[env_ids] = self.robot.data.joint_vel[env_ids]


def _joint_targets(env, raw_action: torch.Tensor) -> torch.Tensor:
    """Policy action -> joint position targets, rad: the joint_pos action term's own mapping."""
    robot = _robot(env)
    return robot.data.default_joint_pos + env.cfg.actions[JOINT_ACTION].scale * raw_action  # (num_envs, 12)


def action_rate(env) -> torch.Tensor:
    actions = env.action_manager
    # Brian: targets in radians, not raw actions. On reset mjlab zeroes the stored actions, so an
    # episode's first step compares against the default pose.
    return brian.action_rate(_joint_targets(env, actions.action), _joint_targets(env, actions.prev_action))


def feet_air_time(env) -> torch.Tensor:
    feet = env.scene[FEET_SENSOR]
    first_contact = feet.compute_first_contact(env.step_dt)  # (num_envs, 4) bool, feet fl, fr, br, bl
    command = env.command_manager.get_command(TWIST_COMMAND)  # (num_envs, 3)
    return brian.feet_air_time(first_contact, feet.data.last_air_time, command, config.FEET_AIR_TIME_THRESHOLD_S)


class undesired_contacts:
    """Picks the 9 non-foot collision geoms (in NONFOOT_PARTS order) out of the sensor's 22 slots."""

    def __init__(self, cfg, env):
        sensor = env.scene[NONFOOT_SENSOR]
        primaries = list(dict.fromkeys(slot.primary_name for slot in sensor._slots))  # 22 geoms, force_history's axis 1
        self.slots = torch.tensor([primaries.index(f"{part}_collision") for part in NONFOOT_PARTS], device=env.device)  # (9,)

    def __call__(self, env) -> torch.Tensor:
        forces = env.scene[NONFOOT_SENSOR].data.force_history[:, self.slots]  # (num_envs, 9, 4, 3) N, last 4 substeps
        return brian.undesired_contacts(forces, config.UNDESIRED_CONTACT_MIN_FORCE_N)
