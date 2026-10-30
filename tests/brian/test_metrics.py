"""Spec for ironbark_rl/brian/metrics.py. These fail until Brian implements the module.

Run just these: python -m pytest tests/brian -q
"""

import numpy as np
import pytest

from ironbark_rl.brian import metrics

UPRIGHT = np.array([0.0, 0.0, -1.0])


def _gravity_at_tilt(deg: float) -> np.ndarray:
    """Body-frame gravity for a pure pitch of `deg` degrees."""
    rad = np.deg2rad(deg)
    return np.array([np.sin(rad), 0.0, -np.cos(rad)])


def _require(name: str):
    value = getattr(metrics, name)
    assert value is not None, f"set metrics.{name} first (it's a TODO in metrics.py)"
    return value


# --- constants -------------------------------------------------------------------


def test_scoreboard_version_is_a_string():
    assert isinstance(metrics.SCOREBOARD_VERSION, str) and metrics.SCOREBOARD_VERSION


def test_fall_tilt_is_between_upright_and_upside_down():
    tilt = _require("FALL_TILT_DEG")
    assert 0.0 < tilt < 180.0


def test_command_grid_shape_and_includes_standing_still():
    grid = np.asarray(_require("COMMAND_GRID"), dtype=float)
    assert grid.ndim == 2 and grid.shape[1] == 3
    assert np.isfinite(grid).all()
    assert (np.abs(grid).sum(axis=1) == 0).any(), "grid needs a (0, 0, 0) standing command"
    assert len(np.unique(grid, axis=0)) == len(grid), "duplicate grid rows"


def test_min_speed_for_cot_is_positive():
    assert _require("MIN_SPEED_FOR_COT_MPS") > 0.0


# --- tilt / falls ----------------------------------------------------------------


@pytest.mark.parametrize("deg", [0.0, 30.0, 45.0, 90.0, 135.0, 180.0])
def test_tilt_of_pitched_body(deg):
    assert metrics.tilt_deg(_gravity_at_tilt(deg)) == pytest.approx(deg, abs=1e-6)


def test_tilt_ignores_which_way_it_leans():
    left = np.array([0.0, np.sin(np.deg2rad(40)), -np.cos(np.deg2rad(40))])
    forward = _gravity_at_tilt(40.0)
    assert metrics.tilt_deg(left) == pytest.approx(metrics.tilt_deg(forward))


def test_tilt_keeps_leading_shape():
    g = np.broadcast_to(UPRIGHT, (5, 3, 3))
    assert metrics.tilt_deg(g).shape == (5, 3)


def test_is_fallen_threshold():
    tilt = _require("FALL_TILT_DEG")
    g = np.stack([UPRIGHT, _gravity_at_tilt(tilt - 1.0), _gravity_at_tilt(tilt + 1.0)])[:, None, :]  # (T=3, N=1, 3)
    np.testing.assert_array_equal(metrics.is_fallen(g)[:, 0], [False, False, True])


def test_fall_rate_counts_each_episode_once():
    fallen = np.array([
        [False, False, False, False],
        [True, False, False, False],
        [True, False, True, False],
        [True, False, False, False],
    ])  # episodes 0 and 2 fell (0 at several steps) -> 2 of 4
    assert metrics.fall_rate(fallen) == pytest.approx(0.5)


def test_fall_rate_none_fell():
    assert metrics.fall_rate(np.zeros((10, 3), dtype=bool)) == 0.0


def test_steps_before_fall_stops_at_first_fall_for_good():
    fallen = np.array([[False], [False], [True], [False]])  # "recovers" at t=3, still invalid
    np.testing.assert_array_equal(metrics.steps_before_fall(fallen)[:, 0], [True, True, False, False])


def test_steps_before_fall_no_fall_is_all_valid():
    assert metrics.steps_before_fall(np.zeros((6, 2), dtype=bool)).all()


# --- velocity tracking -----------------------------------------------------------


def _tracking_case(T=8, N=2):
    command = np.zeros((T, N, 3))
    command[..., 0] = 0.3
    velocity = command.copy()
    return command, velocity, np.ones((T, N), dtype=bool)


def test_perfect_tracking_is_zero():
    command, velocity, valid = _tracking_case()
    lin, yaw = metrics.velocity_tracking_error(command, velocity, valid)
    np.testing.assert_allclose(lin, 0.0, atol=1e-12)
    np.testing.assert_allclose(yaw, 0.0, atol=1e-12)


def test_planar_error_is_a_norm_and_yaw_is_separate():
    command, velocity, valid = _tracking_case()
    velocity[..., 0] += 0.3
    velocity[..., 1] += 0.4  # planar error 0.5 m/s
    velocity[..., 2] += 0.2  # yaw error 0.2 rad/s
    lin, yaw = metrics.velocity_tracking_error(command, velocity, valid)
    np.testing.assert_allclose(lin, 0.5)
    np.testing.assert_allclose(yaw, 0.2)


def test_invalid_steps_are_excluded():
    command, velocity, valid = _tracking_case(T=4, N=1)
    velocity[2:, 0, 0] += 100.0  # garbage after a fall
    valid[2:, 0] = False
    lin, _ = metrics.velocity_tracking_error(command, velocity, valid)
    np.testing.assert_allclose(lin, 0.0, atol=1e-12)


def test_episode_with_no_valid_steps_is_nan():
    command, velocity, valid = _tracking_case(T=4, N=2)
    valid[:, 1] = False
    lin, yaw = metrics.velocity_tracking_error(command, velocity, valid)
    assert np.isfinite(lin[0]) and np.isnan(lin[1]) and np.isnan(yaw[1])


# --- smoothness ------------------------------------------------------------------

DT = 0.02  # 50 Hz policy


def test_constant_targets_have_zero_rate():
    targets = np.ones((50, 2, 12)) * 0.7
    np.testing.assert_allclose(metrics.joint_target_rate(targets, DT), 0.0, atol=1e-12)


def test_steady_ramp_rate_is_its_slope():
    t = np.arange(51) * DT
    targets = np.broadcast_to((1.0 * t)[:, None, None], (51, 1, 12))  # every joint at 1 rad/s
    np.testing.assert_allclose(metrics.joint_target_rate(targets, DT), 1.0, rtol=1e-6)


def test_rate_scales_with_amplitude():
    rng = np.random.default_rng(0)
    targets = rng.normal(size=(100, 3, 12))
    np.testing.assert_allclose(metrics.joint_target_rate(3.0 * targets, DT), 3.0 * metrics.joint_target_rate(targets, DT))


def test_faster_oscillation_is_less_smooth():
    t = np.arange(200) * DT
    slow = np.sin(2 * np.pi * 1.0 * t)[:, None, None] * np.ones((1, 1, 12))
    fast = np.sin(2 * np.pi * 4.0 * t)[:, None, None] * np.ones((1, 1, 12))
    assert metrics.joint_target_rate(fast, DT)[0] > metrics.joint_target_rate(slow, DT)[0]


def test_rate_is_per_second_not_per_step():
    rng = np.random.default_rng(1)
    targets = rng.normal(size=(100, 2, 12))
    np.testing.assert_allclose(metrics.joint_target_rate(targets, DT / 2), 2.0 * metrics.joint_target_rate(targets, DT))


# --- cost of transport -----------------------------------------------------------


def test_cost_of_transport_known_value():
    T, N, J = 20, 1, 12
    torque = np.zeros((T, N, J))
    joint_vel = np.zeros((T, N, J))
    torque[..., 0] = 2.0      # N*m
    joint_vel[..., 0] = 0.5   # rad/s -> 1 W of positive mechanical power
    base_vel = np.zeros((T, N, 2))
    base_vel[..., 0] = 1.0    # 1 m/s
    cot = metrics.cost_of_transport(torque, joint_vel, base_vel, mass_kg=1.0, gravity_mps2=9.81)
    np.testing.assert_allclose(cot, 1.0 / 9.81, rtol=1e-6)


def test_cost_of_transport_undefined_when_standing():
    min_speed = _require("MIN_SPEED_FOR_COT_MPS")
    T, J = 20, 12
    torque = np.ones((T, 2, J))
    joint_vel = np.ones((T, 2, J))
    base_vel = np.zeros((T, 2, 2))
    base_vel[:, 0, 0] = 10 * min_speed
    base_vel[:, 1, 0] = 0.1 * min_speed
    cot = metrics.cost_of_transport(torque, joint_vel, base_vel, mass_kg=1.0)
    assert np.isfinite(cot[0]) and np.isnan(cot[1])


def test_heavier_robot_same_power_is_more_efficient():
    T, N, J = 20, 1, 12
    torque = np.full((T, N, J), 0.1)
    joint_vel = np.full((T, N, J), 1.0)
    base_vel = np.zeros((T, N, 2))
    base_vel[..., 0] = 0.5
    light = metrics.cost_of_transport(torque, joint_vel, base_vel, mass_kg=0.75)
    heavy = metrics.cost_of_transport(torque, joint_vel, base_vel, mass_kg=0.972)
    assert heavy[0] < light[0]
