"""EXP-009/010 tasks in simulation. GPU, ~1-2 min, opt-in: python -m pytest -m sim tests/test_latency_tasks_sim.py

Checks the delays happen in the real env, not just in the config:
- CmdDelay: a new joint command reaches the servo (sim.data.ctrl) exactly 40 ms = 2 policy steps later.
- StaleJoints: each joint's actor reading changes about once per 130 ms cycle, and lags the true pose.
- VelRef: EXP-005's actor layout, so its checkpoint can be scored there.
"""

import contextlib
import io

import pytest
import torch

pytestmark = pytest.mark.sim

DOGS = 8


def build(task):
    if not torch.cuda.is_available():
        pytest.skip("needs the GPU")
    with contextlib.redirect_stdout(io.StringIO()):
        import ironbark_rl.tasks  # noqa: F401
        from mjlab.envs import ManagerBasedRlEnv
        from mjlab.tasks.registry import load_env_cfg

        cfg = load_env_cfg(task, play=True)  # scoring conditions: delays on, no pushes, no noise
        cfg.scene.num_envs = DOGS
        cfg.terminations = {}
        env = ManagerBasedRlEnv(cfg=cfg, device="cuda:0")
        env.reset()
    return env


def actor_dim(env):
    return env.observation_manager.group_obs_dim["actor"][0]


def test_command_reaches_the_servo_40_ms_later():
    env = build("IronBark-S2-Walk-Flat-Brian-CmdDelay")
    try:
        n_act = env.action_manager.total_action_dim
        a = torch.zeros(DOGS, n_act, device=env.device)
        for _ in range(5):
            env.step(a)
        ctrl_a = env.sim.data.ctrl.clone()  # (DOGS, 12): targets for action A
        b = torch.full_like(a, 0.4)  # action B: every target +0.1 rad
        seen = []
        for _ in range(4):
            env.step(b)
            seen.append(bool(torch.allclose(env.sim.data.ctrl, ctrl_a, atol=1e-5)))
        assert seen == [True, True, False, False]  # still A for 2 policy steps (40 ms), then B
    finally:
        env.close()


def test_stale_readings_refresh_once_per_cycle_and_lag():
    from ironbark_rl.brian import obs

    env = build("IronBark-S2-Walk-Flat-Brian-StaleJoints")
    try:
        readback = obs.round_robin_readback(env)
        robot = env.scene["robot"]
        n_act = env.action_manager.total_action_dim
        steps, changes, last = 65, torch.zeros(DOGS, 12, device=env.device), readback.held.clone()
        gaps = []
        for k in range(steps):  # 1.3 s = 10 cycles; a moving command so every poll changes the reading
            action = 0.5 * torch.sin(torch.full((DOGS, n_act), 0.3 * k, device=env.device))
            env.step(action)
            changes += (readback.held != last).float()
            last = readback.held.clone()
            true = robot.data.joint_pos - robot.data.default_joint_pos
            gaps.append((readback.held - true).abs().mean().item())
        assert 9 <= changes.mean().item() <= 11  # ~10 polls per joint in 10 cycles
        assert sum(gaps) / len(gaps) > 1e-3  # readings really are behind the true pose
    finally:
        env.close()


def test_vel_ref_matches_exp005_actor_size():
    base = build("IronBark-S2-Walk-Flat-Brian")
    try:
        base_dim = actor_dim(base)
    finally:
        base.close()
    for task, expected in (("IronBark-S2-Walk-Flat-Brian-StaleJoints-VelRef", base_dim),
                           ("IronBark-S2-Walk-Flat-Brian-StaleJoints", base_dim - 12)):
        env = build(task)
        try:
            assert actor_dim(env) == expected
        finally:
            env.close()
