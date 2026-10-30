from mjlab.tasks.registry import register_mjlab_task
from src.tasks.velocity.rl import VelocityOnPolicyRunner

from .env_cfgs import s2_flat_walk_env_cfg
from .rl_cfg import s2_walk_ppo_runner_cfg

register_mjlab_task(
    task_id="IronBark-S2-Walk-Flat",
    env_cfg=s2_flat_walk_env_cfg(),
    play_env_cfg=s2_flat_walk_env_cfg(play=True),
    rl_cfg=s2_walk_ppo_runner_cfg(),
    runner_cls=VelocityOnPolicyRunner,
)
