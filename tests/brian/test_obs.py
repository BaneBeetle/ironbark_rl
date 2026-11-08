"""ironbark_rl/brian/obs.py: the round-robin readback model, on a CPU fake env with known motion."""

from types import SimpleNamespace

import pytest
import torch

from ironbark_rl.brian import latency_config as config
from ironbark_rl.brian import obs

JOINTS = ("fl_hip_joint", "fl_thigh_joint", "fl_calf_joint", "fr_hip_joint", "fr_thigh_joint", "fr_calf_joint",
          "br_hip_joint", "br_thigh_joint", "br_calf_joint", "bl_hip_joint", "bl_thigh_joint", "bl_calf_joint")
DT = 0.02  # policy step
PERIOD = config.JOINT_REFRESH_PERIOD_S


class FakeEnv:
    """Just what the readback reads: clock, robot joint state."""

    def __init__(self, num_envs=1):
        self.num_envs, self.device, self.step_dt = num_envs, "cpu", DT
        self.episode_length_buf = torch.zeros(num_envs, dtype=torch.long)
        data = SimpleNamespace(joint_pos=torch.zeros(num_envs, 12), default_joint_pos=torch.zeros(num_envs, 12))
        self.scene = {"robot": SimpleNamespace(joint_names=JOINTS, data=data)}

    def step(self, joint_pos):
        self.episode_length_buf += 1
        self.scene["robot"].data.joint_pos = joint_pos


def make(num_envs=1, phase=None):
    env = FakeEnv(num_envs)
    pos_term, vel_term = obs.stale_joint_pos(None, env), obs.stale_joint_vel(None, env)
    pos_term.reset(None)
    if phase is not None:
        pos_term.readback.phase[:] = phase
    return env, pos_term, vel_term


def test_readback_slots_follow_xgolib_id_order():
    slots = [config.readback_slot(n) for n in ("fl_calf_joint", "fl_thigh_joint", "fl_hip_joint", "fr_calf_joint",
                                                "br_calf_joint", "bl_hip_joint")]
    assert slots == [0, 1, 2, 3, 6, 11]


def test_docstring_example():
    env, pos, _ = make(phase=0.0)
    j = JOINTS.index("fr_thigh_joint")  # slot 4: polled at 34.7 ms and 164.7 ms
    true = [0.00, 0.05, 0.11, 0.16, 0.20, 0.22, 0.23, 0.22, 0.19, 0.15]
    seen = []
    for k, v in enumerate(true):
        if k:
            q = torch.zeros(1, 12)
            q[0, j] = v
            env.step(q)
        seen.append(round(float(pos(env)[0, j]), 3))
    assert seen == [0.0, 0.0, 0.094, 0.094, 0.094, 0.094, 0.094, 0.094, 0.094, 0.181]


def test_each_joint_refreshes_once_per_cycle():
    env, pos, _ = make(num_envs=4)
    changes = torch.zeros(4, 12)
    last = pos(env)
    steps = round(100 * PERIOD / DT)  # 100 cycles
    for k in range(1, steps + 1):
        env.step(torch.full((4, 12), float(k)))  # every joint moves every step, so every poll changes the reading
        now = pos(env)
        changes += (now != last).float()
        last = now
    assert changes.min() >= 99 and changes.max() <= 101


def test_reading_age_is_uniform_over_the_cycle():
    env, pos, _ = make(num_envs=64)
    ages = []
    for k in range(1, 400):
        t = k * DT
        env.step(torch.full((64, 12), t))  # true position = time, so the reading = the poll time
        if k > 10:
            ages.append(t - pos(env))  # (64, 12) s since the poll
        else:
            pos(env)
    ages = torch.stack(ages)
    assert ages.min() >= -1e-6 and ages.max() <= PERIOD + 1e-6
    assert float(ages.mean()) == pytest.approx(PERIOD / 2, abs=0.005)


def test_calling_twice_in_one_step_changes_nothing():
    env, pos, vel = make(phase=0.0)
    for k in range(1, 4):
        env.step(torch.full((1, 12), float(k)))
        a, va = pos(env), vel(env)
        b, vb = pos(env), vel(env)
        assert torch.equal(a, b) and torch.equal(va, vb)


def test_reset_starts_from_the_true_pose_and_redraws_the_phase():
    env, pos, _ = make(num_envs=2, phase=0.0)
    env.step(torch.full((2, 12), 0.3))
    pos(env)
    pos.reset(torch.tensor([0]))
    env.episode_length_buf[0] = 0
    env.scene["robot"].data.joint_pos = torch.full((2, 12), 0.7)
    out = pos(env)
    assert torch.allclose(out[0], torch.full((12,), 0.7))  # env 0 reset: reads its true pose
    assert not torch.allclose(out[1], torch.full((12,), 0.7))  # env 1 still waits for its polls
    assert 0 <= float(pos.readback.phase[0]) < PERIOD


def test_velocity_is_the_change_of_the_reading_per_step():
    env, pos, vel = make(phase=0.0)
    j = JOINTS.index("fl_calf_joint")  # slot 0: polled at 0, 130, 260 ms...
    vs, ps = [], []
    for k in range(1, 15):
        env.step(torch.full((1, 12), 0.01 * k))
        ps.append(float(pos(env)[0, j]))
        vs.append(float(vel(env)[0, j]))
    assert sum(v != 0 for v in vs) == 2  # polls at 130 and 260 ms
    k = next(i for i, v in enumerate(vs) if v != 0)
    assert vs[k] == pytest.approx((ps[k] - ps[k - 1]) / DT)


# ----------------------------------------------------------------------------------- IMU freezes

def imu_env(num_envs):
    env = FakeEnv(num_envs)
    gyro = obs.imu_frozen(None, env)
    grav = obs.imu_frozen(None, env)
    gyro.reset(None)
    grav.reset(None)
    return env, gyro, grav


def truth(env, k):
    """A different true value every step and env: (num_envs, 3)."""
    return lambda e: torch.full((env.num_envs, 3), float(k)) + torch.arange(env.num_envs)[:, None] * 1000.0


def test_freeze_durations_are_the_logs():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("report", Path(__file__).resolve().parents[2] / "tools" / "joint_control_report.py")
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    frozen, live = report.imu_freeze_durations()
    assert tuple(frozen) == config.IMU_FROZEN_MS and tuple(live) == config.IMU_LIVE_MS


def test_frozen_share_and_stretch_lengths_match_the_logs():
    env, gyro, grav = imu_env(256)
    held = []
    for k in range(1, 3001):  # 60 s per env
        env.step(torch.zeros(256, 12))
        out = gyro(env, inner=truth(env, k), inner_params={})
        held.append((out[:, 0] != k + torch.arange(256) * 1000.0))  # (256,): not the fresh value = frozen
    frozen = torch.stack(held)  # (steps, envs)
    assert float(frozen.float().mean()) == pytest.approx(0.418, abs=0.03)
    runs = []  # lengths of completed frozen runs, in ms
    for e in range(256):
        col, k = frozen[:, e].tolist(), 0
        while k < len(col):
            j = k
            while j < len(col) and col[j] == col[k]:
                j += 1
            if col[k] and k > 1 and j < len(col):  # skip the stretch a reset started part-way through
                runs.append((j - k + 1) * DT * 1000)  # a freeze of n repeated steps spans n+1 reads
            k = j
    assert min(runs) >= min(config.IMU_FROZEN_MS) - 20 and max(runs) <= max(config.IMU_FROZEN_MS) + 40


def test_gyro_and_gravity_freeze_together_and_hold_the_last_live_value():
    env, gyro, grav = imu_env(8)
    for k in range(1, 400):
        env.step(torch.zeros(8, 12))
        g = gyro(env, inner=truth(env, k), inner_params={})
        v = grav(env, inner=truth(env, k), inner_params={})
        live = g[:, 0] == k + torch.arange(8) * 1000.0
        assert torch.equal(live, v[:, 0] == k + torch.arange(8) * 1000.0)  # same envs frozen in both terms
        if k > 1:  # step 1 after a reset always shows the true value (the dog has a reading), frozen or not
            assert torch.equal(gyro.schedule.frozen, ~live)
        if k > 1:
            stuck = ~live
            assert torch.equal(g[stuck], prev[stuck])  # frozen envs repeat their previous output
        prev = g.clone()


def test_imu_freeze_is_idempotent_within_a_step_and_resets_to_truth():
    env, gyro, grav = imu_env(4)
    env.step(torch.zeros(4, 12))
    a = gyro(env, inner=truth(env, 1), inner_params={})
    b = gyro(env, inner=truth(env, 1), inner_params={})
    assert torch.equal(a, b)
    gyro.reset(torch.tensor([2]))
    env.episode_length_buf[2] = 0
    out = gyro(env, inner=truth(env, 7), inner_params={})
    assert float(out[2, 0]) == 7 + 2 * 1000.0  # a reset env starts from the true value
