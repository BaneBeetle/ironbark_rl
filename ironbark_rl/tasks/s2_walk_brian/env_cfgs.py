"""S2 flat walking with Brian's legged_gym-style reward (EXP-003 onwards).

Identical to IronBark-S2-Walk-Flat (env v2: EXP-002) except the reward: Luwu's reward terms
are replaced by Brian's eleven (ironbark_rl/brian/rewards.py, weights and parameters in
ironbark_rl/brian/reward_config.py). Terminations, observations, actions, commands,
randomization and collisions are untouched, so the reward is the one variable that changes.
Each term's per-step contribution is logged to TensorBoard as Episode_Metrics/reward/<term>.
"""

from mjlab.envs import ManagerBasedRlEnvCfg
from mjlab.managers.reward_manager import RewardTermCfg

from ironbark_rl.brian import reward_config as config
from ironbark_rl.reward_audit import per_step_reward_metrics
from ironbark_rl.tasks.s2_walk.env_cfgs import s2_flat_walk_env_cfg

from . import rewards_glue

_PARAMETERS = ("TRACK_LIN_VEL_WIDTH", "TRACK_ANG_VEL_WIDTH", "FEET_AIR_TIME_THRESHOLD_S",
               "UNDESIRED_CONTACT_MIN_FORCE_N", "BASE_HEIGHT_TARGET_M")


def _check_config() -> None:
    """Fail loudly on an unset value. A None weight can't become 0 here: mjlab skips 0-weight terms silently."""
    missing = [f"WEIGHTS['{k}']" for k, w in config.WEIGHTS.items() if w is None]
    missing += [name for name in _PARAMETERS if getattr(config, name) is None]
    if missing:
        raise ValueError("set these in ironbark_rl/brian/reward_config.py: " + ", ".join(missing))


def s2_flat_walk_brian_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    _check_config()
    cfg = s2_flat_walk_env_cfg(play=play)
    cfg.rewards = {name: RewardTermCfg(func=getattr(rewards_glue, name), weight=weight)
                   for name, weight in config.WEIGHTS.items()}
    cfg.metrics.update(per_step_reward_metrics(cfg.rewards))
    return cfg
