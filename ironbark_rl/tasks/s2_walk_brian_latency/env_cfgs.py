"""Brian's reward task plus the real dog's measured latency (EXP-009, EXP-010; Brian, 2026-11-07).

Built on IronBark-S2-Walk-Flat-Brian (EXP-005's config). Numbers and reasons: ironbark_rl/brian/latency_config.py.

- cmd_delay (EXP-009): every joint target reaches the servo COMMAND_DELAY_S late, fixed, in every env.
  It replaces Luwu's random 1-2 physics-step (4-8 ms) actuator delay. Nothing else changes: the actor's
  joint observations keep their 1-2 policy-step (20-40 ms) delay.
- stale_joints (EXP-010): cmd_delay, plus the actor's joint positions become read_motor()'s round-robin
  sample-and-hold (ironbark_rl/brian/obs.py), which replaces their 20-40 ms delay, and the actor's joint
  velocity is dropped (the dog has no velocity readback). The critic keeps the true joint state.
- stale_joints_vel_ref: stale_joints with the actor's joint velocity put back as the change of the
  stale reading per step. Never trained: only to score EXP-005's policy (which needs a velocity input)
  under EXP-010's conditions.
- luwu_stale_joints (EXP-011, Brian's "fair fight"): Luwu's reward (IronBark-S2-Walk-Flat, env v2) with
  exactly stale_joints' latency conditions and actor observations; only the reward differs from EXP-010.
- stale_joints_imu_freeze: stale_joints plus the measured IMU freezes on the actor's base_ang_vel and
  projected_gravity (ironbark_rl/brian/obs.py). Never trained: only to score EXP-010's policy under the
  freezes (Brian, 2026-11-07: "no retraining").

Scoring (Brian, 2026-11-07): these delays stay on in the play config too, so the scoreboard sees them.
Training's random joint-observation delay (1-2 policy steps) is kept on as well, so play matches training.
"""

from dataclasses import replace

from mjlab.actuator import DelayedActuatorCfg
from mjlab.entity import EntityArticulationInfoCfg
from mjlab.envs import ManagerBasedRlEnvCfg
from src.tasks.velocity.latency import JOINT_OBS_DELAY_MAX_LAG, JOINT_OBS_DELAY_MIN_LAG

from ironbark_rl.brian import latency_config, obs
from ironbark_rl.tasks.s2_walk.env_cfgs import s2_flat_walk_env_cfg
from ironbark_rl.tasks.s2_walk_brian.env_cfgs import s2_flat_walk_brian_env_cfg

_JOINT_OBS_TERMS = ("joint_pos", "joint_vel")


def command_delay_physics_steps(cfg: ManagerBasedRlEnvCfg) -> int:
    """COMMAND_DELAY_S in physics steps (mjlab's actuator delay unit). 40 ms / 4 ms = 10."""
    steps = latency_config.COMMAND_DELAY_S / cfg.sim.mujoco.timestep
    if abs(steps - round(steps)) > 1e-6:
        raise ValueError(f"COMMAND_DELAY_S must be a whole number of {cfg.sim.mujoco.timestep} s physics steps")
    return round(steps)


def _with_command_delay(cfg: ManagerBasedRlEnvCfg) -> None:
    robot = cfg.scene.entities["robot"]
    articulation = robot.articulation
    (actuator,) = articulation.actuators  # one position actuator group for all 12 joints
    base = actuator.base_cfg if isinstance(actuator, DelayedActuatorCfg) else actuator  # drop Luwu's 4-8 ms
    n = command_delay_physics_steps(cfg)
    delayed = DelayedActuatorCfg(base_cfg=base, delay_target="position", delay_min_lag=n, delay_max_lag=n)
    cfg.scene.entities["robot"] = replace(
        robot,
        articulation=EntityArticulationInfoCfg(
            actuators=(delayed,), soft_joint_pos_limit_factor=articulation.soft_joint_pos_limit_factor
        ),
    )


def _keep_training_joint_obs_delay(cfg: ManagerBasedRlEnvCfg) -> None:
    """Luwu's play config zeroes the joint-observation delay; scoring here keeps training's 1-2 steps."""
    for group in ("actor", "critic"):
        for name in _JOINT_OBS_TERMS:
            term = cfg.observations[group].terms.get(name)
            if term is not None:
                term.delay_min_lag = JOINT_OBS_DELAY_MIN_LAG
                term.delay_max_lag = JOINT_OBS_DELAY_MAX_LAG


def _stale_term(old, func):
    """Same slot, noise and scale as the term it replaces; no extra delay (the staleness is the delay)."""
    return replace(old, func=func, params={}, delay_min_lag=0, delay_max_lag=0)


def _with_cmd_delay_conditions(cfg: ManagerBasedRlEnvCfg, play: bool) -> None:
    """EXP-009's change: the 40 ms command delay; scoring keeps training's joint-observation delay too."""
    _with_command_delay(cfg)
    if play:
        _keep_training_joint_obs_delay(cfg)


def _with_stale_joints(cfg: ManagerBasedRlEnvCfg) -> None:
    """EXP-010's change: the actor's joint positions become the round-robin readback; joint velocity goes."""
    actor = cfg.observations["actor"].terms
    actor["joint_pos"] = _stale_term(actor["joint_pos"], obs.stale_joint_pos)
    del actor["joint_vel"]  # Brian: the dog has no joint-velocity readback


def s2_flat_walk_brian_cmd_delay_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    cfg = s2_flat_walk_brian_env_cfg(play=play)
    _with_cmd_delay_conditions(cfg, play)
    return cfg


def s2_flat_walk_brian_stale_joints_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    cfg = s2_flat_walk_brian_cmd_delay_env_cfg(play=play)
    _with_stale_joints(cfg)
    return cfg


def s2_flat_walk_luwu_stale_joints_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    """EXP-011: Luwu's reward under EXP-010's conditions (the baseline task, then the same two changes)."""
    cfg = s2_flat_walk_env_cfg(play=play)
    _with_cmd_delay_conditions(cfg, play)
    _with_stale_joints(cfg)
    return cfg


_IMU_TERMS = ("base_ang_vel", "projected_gravity")


def _with_imu_freezes(cfg: ManagerBasedRlEnvCfg) -> None:
    actor = cfg.observations["actor"].terms
    for name in _IMU_TERMS:
        old = actor[name]  # keep its slot, noise and scale; the freeze wraps its function
        actor[name] = replace(old, func=obs.imu_frozen, params={"inner": old.func, "inner_params": dict(old.params)})


def s2_flat_walk_brian_stale_joints_imu_freeze_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    cfg = s2_flat_walk_brian_stale_joints_env_cfg(play=play)
    _with_imu_freezes(cfg)
    return cfg


def s2_flat_walk_brian_stale_joints_vel_ref_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    cfg = s2_flat_walk_brian_cmd_delay_env_cfg(play=play)
    actor = cfg.observations["actor"].terms
    actor["joint_pos"] = _stale_term(actor["joint_pos"], obs.stale_joint_pos)
    actor["joint_vel"] = _stale_term(actor["joint_vel"], obs.stale_joint_vel)  # same slot: EXP-005's layout
    return cfg
