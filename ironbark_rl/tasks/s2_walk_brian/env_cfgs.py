"""S2 flat walking with Brian's reward (EXP-001 onwards).

Identical to IronBark-S2-Walk-Flat (EXP-000) except the reward: all of Luwu's reward
terms are replaced by Brian's three terms. Terminations (falls end the episode),
observations, actions, commands and randomization are untouched, so the reward is
the one variable that changes.
"""

from mjlab.envs import ManagerBasedRlEnvCfg
from mjlab.managers.reward_manager import RewardTermCfg

from ironbark_rl.brian import rewards as brian
from ironbark_rl.tasks.s2_walk.env_cfgs import s2_flat_walk_env_cfg

from . import rewards_glue

# Unset weights become 0 here only so the task can register on import; the glue
# refuses to compute a term whose weight is still None, so training can't silently
# run with a missing term.
_UNSET_WEIGHT = 0.0


def _weight(name: str) -> float:
    value = brian.WEIGHTS[name]
    return _UNSET_WEIGHT if value is None else value


def s2_flat_walk_brian_reward_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    cfg = s2_flat_walk_env_cfg(play=play)
    cfg.rewards = {
        "tracking": RewardTermCfg(func=rewards_glue.tracking, weight=_weight("tracking")),
        "stability": RewardTermCfg(func=rewards_glue.stability, weight=_weight("stability")),
        "smoothness": RewardTermCfg(func=rewards_glue.smoothness, weight=_weight("smoothness")),
    }
    return cfg
