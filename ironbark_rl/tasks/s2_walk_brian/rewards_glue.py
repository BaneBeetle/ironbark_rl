"""Simulator -> Brian's reward functions (ironbark_rl/brian/rewards.py).

Claude's glue: it only pulls tensors out of the simulator and hands them over. No
reward logic lives here; every number the dog is paid comes from brian/rewards.py.
"""

import torch

from ironbark_rl.brian import rewards as brian

ROBOT = "robot"
TWIST_COMMAND = "twist"  # the velocity command term
JOINT_ACTION = "joint_pos"  # the joint-position action term


def _require_weight(name: str) -> None:
    if brian.WEIGHTS[name] is None:
        raise RuntimeError(f"set WEIGHTS['{name}'] in ironbark_rl/brian/rewards.py before training")


def _body_velocity(robot) -> torch.Tensor:
    """(N, 3) achieved (vx, vy, wz) in the body frame, same layout as the command."""
    return torch.cat([robot.data.root_link_lin_vel_b[:, :2], robot.data.root_link_ang_vel_b[:, 2:3]], dim=-1)


def tracking(env) -> torch.Tensor:
    _require_weight("tracking")
    command = env.command_manager.get_command(TWIST_COMMAND)
    return brian.tracking_bonus(command, _body_velocity(env.scene[ROBOT]))


def stability(env) -> torch.Tensor:
    _require_weight("stability")
    robot = env.scene[ROBOT]
    return brian.stability_penalty(robot.data.projected_gravity_b, robot.data.root_link_ang_vel_b)


def smoothness(env) -> torch.Tensor:
    _require_weight("smoothness")
    # Joint targets = default pose + scale * action (the joint_pos action term's mapping).
    scale = env.cfg.actions[JOINT_ACTION].scale
    default_q = env.scene[ROBOT].data.default_joint_pos
    actions = env.action_manager
    return brian.smoothness_penalty(default_q + scale * actions.action, default_q + scale * actions.prev_action, env.step_dt)
