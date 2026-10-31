from dataclasses import replace

from mjlab.tasks.registry import register_mjlab_task
from src.tasks.velocity.rl import VelocityOnPolicyRunner

from ironbark_rl.tasks.s2_walk.rl_cfg import s2_walk_ppo_runner_cfg

from .env_cfgs import s2_flat_walk_brian_reward_env_cfg

register_mjlab_task(
    task_id="IronBark-S2-Walk-Flat-BrianReward",
    env_cfg=s2_flat_walk_brian_reward_env_cfg(),
    play_env_cfg=s2_flat_walk_brian_reward_env_cfg(play=True),
    rl_cfg=replace(s2_walk_ppo_runner_cfg(), experiment_name="ironbark_s2_walk_brian_reward"),
    runner_cls=VelocityOnPolicyRunner,
)
