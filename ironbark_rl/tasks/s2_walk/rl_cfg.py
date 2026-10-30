"""PPO settings for the S2 walking task: Luwu's Mini2S settings, own experiment name."""

from dataclasses import replace

from mjlab.rl import RslRlOnPolicyRunnerCfg
from src.tasks.velocity.config.mini2s_walk.rl_cfg import mini2s_walk_ppo_runner_cfg


def s2_walk_ppo_runner_cfg() -> RslRlOnPolicyRunnerCfg:
    return replace(mini2s_walk_ppo_runner_cfg(), experiment_name="ironbark_s2_walk")
