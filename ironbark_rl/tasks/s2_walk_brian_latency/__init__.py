from dataclasses import replace

from mjlab.tasks.registry import register_mjlab_task
from src.tasks.velocity.rl import VelocityOnPolicyRunner

from ironbark_rl.tasks.s2_walk.rl_cfg import s2_walk_ppo_runner_cfg

from .env_cfgs import (
    s2_flat_walk_brian_cmd_delay_env_cfg,
    s2_flat_walk_brian_stale_joints_env_cfg,
    s2_flat_walk_brian_stale_joints_imu_freeze_env_cfg,
    s2_flat_walk_brian_stale_joints_vel_ref_env_cfg,
)

_TASKS = (
    ("IronBark-S2-Walk-Flat-Brian-CmdDelay", s2_flat_walk_brian_cmd_delay_env_cfg, "ironbark_s2_walk_brian_cmd_delay"),
    ("IronBark-S2-Walk-Flat-Brian-StaleJoints", s2_flat_walk_brian_stale_joints_env_cfg, "ironbark_s2_walk_brian_stale_joints"),
    # Scoring only (EXP-005 under EXP-010's conditions); never trained.
    ("IronBark-S2-Walk-Flat-Brian-StaleJoints-VelRef", s2_flat_walk_brian_stale_joints_vel_ref_env_cfg,
     "ironbark_s2_walk_brian_stale_joints_vel_ref"),
    # Scoring only (EXP-010 under the measured IMU freezes); never trained.
    ("IronBark-S2-Walk-Flat-Brian-StaleJoints-ImuFreeze", s2_flat_walk_brian_stale_joints_imu_freeze_env_cfg,
     "ironbark_s2_walk_brian_stale_joints_imu_freeze"),
)

for task_id, env_cfg_fn, experiment_name in _TASKS:
    register_mjlab_task(
        task_id=task_id,
        env_cfg=env_cfg_fn(),
        play_env_cfg=env_cfg_fn(play=True),
        rl_cfg=replace(s2_walk_ppo_runner_cfg(), experiment_name=experiment_name),
        runner_cls=VelocityOnPolicyRunner,
    )
