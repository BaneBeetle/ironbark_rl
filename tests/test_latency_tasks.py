"""EXP-009/010 task configs (no simulation): delays where Brian put them, and nowhere else."""

import contextlib
import io

import pytest
from mjlab.actuator import DelayedActuatorCfg, XmlPositionActuatorCfg

with contextlib.redirect_stdout(io.StringIO()):  # mjlab prints a banner on import
    import ironbark_rl.tasks  # noqa: F401  (registers the tasks)
    from mjlab.tasks.registry import load_env_cfg

CMD = "IronBark-S2-Walk-Flat-Brian-CmdDelay"
STALE = "IronBark-S2-Walk-Flat-Brian-StaleJoints"
REF = "IronBark-S2-Walk-Flat-Brian-StaleJoints-VelRef"


def cfg(task, play):
    with contextlib.redirect_stdout(io.StringIO()):
        return load_env_cfg(task, play=play)


def actuator(c):
    (a,) = c.scene.entities["robot"].articulation.actuators
    return a


@pytest.mark.parametrize("task", [CMD, STALE, REF])
@pytest.mark.parametrize("play", [False, True])
def test_command_delay_is_40_ms_fixed_in_training_and_scoring(task, play):
    a = actuator(cfg(task, play))
    assert isinstance(a, DelayedActuatorCfg) and isinstance(a.base_cfg, XmlPositionActuatorCfg)
    assert (a.delay_min_lag, a.delay_max_lag) == (10, 10)  # 10 x 4 ms physics steps


def test_baseline_task_is_untouched():
    a = actuator(cfg("IronBark-S2-Walk-Flat-Brian", False))
    assert (a.delay_min_lag, a.delay_max_lag) == (1, 2)  # Luwu's 4-8 ms
    assert isinstance(actuator(cfg("IronBark-S2-Walk-Flat-Brian", True)), XmlPositionActuatorCfg)


def test_cmd_delay_changes_only_the_actuator():
    base, new = cfg("IronBark-S2-Walk-Flat-Brian", False), cfg(CMD, False)
    for group in ("actor", "critic"):
        assert list(base.observations[group].terms) == list(new.observations[group].terms)
    assert base.rewards.keys() == new.rewards.keys()


@pytest.mark.parametrize("play", [False, True])
def test_stale_joints_actor_and_critic(play):
    c = cfg(STALE, play)
    actor, critic = c.observations["actor"].terms, c.observations["critic"].terms
    assert "joint_vel" not in actor and actor["joint_pos"].func.__name__ == "stale_joint_pos"
    assert (actor["joint_pos"].delay_min_lag, actor["joint_pos"].delay_max_lag) == (0, 0)
    assert critic["joint_pos"].func.__name__ == "joint_pos_rel" and critic["joint_vel"].func.__name__ == "joint_vel_rel"
    assert list(actor) == [k for k in cfg(CMD, play).observations["actor"].terms if k != "joint_vel"]  # same order


def test_vel_ref_keeps_exp005s_actor_layout():
    assert list(cfg(REF, True).observations["actor"].terms) == list(cfg(CMD, True).observations["actor"].terms)
