"""S2 flat-ground walking task.

Luwu's Mini2S walking task (rewards, observations, commands, randomization, latency)
with the S2 robot swapped in. Luwu's reward is the baseline Brian's reward gets compared
against, so nothing here tunes the reward. Env changes since EXP-000 (Brian, 2026-11-06,
baselined in EXP-002): the fall-tilt and non-foot-contact terminations below, and
non-foot ground collisions (S2_WALK_COLLISION in ironbark_rl/assets/s2.py).
"""

import math

from mjlab.envs import ManagerBasedRlEnvCfg
from src.tasks.velocity.config.mini2s_walk.env_cfgs import mini2s_flat_walk_env_cfg
from src.tasks.velocity.latency import with_delayed_articulation

from ironbark_rl.assets.s2 import S2_TOTAL_MASS_KG, get_s2_walk_robot_cfg

# The Mini2S pose reward has per-joint entries for its arm joints; the S2 has none.
_MINI2S_ARM_JOINT_MARKER = "arm_"
_POSE_STD_KEYS = ("std_standing", "std_walking", "std_running")

# Training ends an episode once the body tilts past this (Brian, 2026-11-06; Luwu's task
# used 70). The scoreboard's fall line is metrics.FALL_TILT_DEG = 46, where passive sim
# recovery fails, so 50 ends an episode just past the point the scoreboard calls a fall.
# Recheck both once Brian's policy is trained.
FALL_TILT_TERMINATION_DEG = 50.0

# Training ends an episode when any non-foot part (trunk, hip, thigh) presses on the ground
# harder than this share of the dog's weight (Brian, 2026-11-06). Luwu's 10 N exceeded the
# S2's whole weight (9.54 N), so a trunk resting on the floor never tripped it.
NONFOOT_CONTACT_LIMIT_FRACTION_OF_WEIGHT = 0.15
_GRAVITY_MPS2 = 9.81
NONFOOT_CONTACT_LIMIT_N = NONFOOT_CONTACT_LIMIT_FRACTION_OF_WEIGHT * S2_TOTAL_MASS_KG * _GRAVITY_MPS2


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
    cfg.terminations["fell_over"].params["limit_angle"] = math.radians(FALL_TILT_TERMINATION_DEG)
    cfg.terminations["illegal_contact"].params["force_threshold"] = NONFOOT_CONTACT_LIMIT_N
    return cfg
