"""S2 flat-ground walking task.

Luwu's Mini2S walking task, unchanged (rewards, observations, commands, randomization,
latency), with the S2 robot swapped in. Luwu's reward is the baseline Brian's reward
gets compared against, so nothing here tunes it.
"""

from mjlab.envs import ManagerBasedRlEnvCfg
from src.tasks.velocity.config.mini2s_walk.env_cfgs import mini2s_flat_walk_env_cfg
from src.tasks.velocity.latency import with_delayed_articulation

from ironbark_rl.assets.s2 import get_s2_walk_robot_cfg

# The Mini2S pose reward has per-joint entries for its arm joints; the S2 has none.
_MINI2S_ARM_JOINT_MARKER = "arm_"
_POSE_STD_KEYS = ("std_standing", "std_walking", "std_running")


def s2_flat_walk_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    cfg = mini2s_flat_walk_env_cfg(play=play)
    cfg.scene.entities = {
        "robot": with_delayed_articulation(get_s2_walk_robot_cfg(), play=play),
    }
    pose_params = cfg.rewards["pose"].params
    for key in _POSE_STD_KEYS:
        pose_params[key] = {
            pattern: std
            for pattern, std in pose_params[key].items()
            if _MINI2S_ARM_JOINT_MARKER not in pattern
        }
    return cfg
