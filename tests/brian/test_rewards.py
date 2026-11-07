"""Spec for ironbark_rl/brian/rewards.py (legged_gym-style terms). These fail until Brian implements them.

Known cases per term: exact values where the physics fixes them (perfect tracking = 1, level
body = 0, ...) and directions (more error -> less bonus, more tilt -> more penalty). Kernel
widths and the base-height target are passed in, so these hold for any value Brian picks.

Scenario rules (also need reward_config.py filled in):
- a normal walking step pays more than 0, so falling early never pays (carried over from
  reward v1, and the unit-level twin of tools/reward_check.py);
- standing still on a zero command pays more than 0 (the same guard, scenario (a));
- standing still loses when ordered to walk (carried over from reward v1).
"Normal walking step" numbers are measured (EXP-000 policy on env v2; see rewards.py).

Run just these: python -m pytest tests/brian -q -k reward
"""

import math

import pytest
import torch

from ironbark_rl.brian import reward_config as cfg
from ironbark_rl.brian import rewards

DT = 0.02  # policy period, s
J = 12  # S2 joints
FEET = 4
NONFOOT_PARTS = 9
SUBSTEPS = 4
ANY_WIDTH = 0.25  # the known cases hold for any positive kernel width
ANY_TARGET_M = 0.13  # likewise for any base-height target
SERVO_LIMIT_NM = 0.43
AIR_TIME_THRESHOLD_S = 0.1  # Brian's example; the feet_air_time cases hold for any value in (FLICKER_S, SWING_S)

# Measured typical walking step: EXP-000 policy on env v2, 256 dogs x 9 s, 2026-11-06 (medians).
PLANAR_ERROR_MPS = 0.026
YAW_RATE_ERROR_RADPS = 0.067
VZ_MPS = 0.009
ROLL_PITCH_RATE_RADPS = 0.15
TILT_DEG = 1.5
HEIGHT_SPREAD_M = 0.0023  # median |z - median z| while walking
WALK_TORQUE_NM = 0.141  # RMS over joints
JOINT_ACC_RADPS2 = 36.0  # RMS over joints
TARGET_STEP_RAD = 0.042  # RMS over joints
TOUCHDOWNS_PER_FOOT_PER_STEP = 0.0547  # 2.7 per foot per s
SWING_S = 0.136  # swing time at touchdown
FLICKER_S = 0.008  # p10 swing time at touchdown: a foot flickering on and off the ground, not a step
STAND_TORQUE_NM = 0.045  # mean |servo torque| standing at the default pose (2026-11-06 probe)

WALK_COMMAND = (0.3, 0.0, 0.0)  # m/s forward, inside COMMAND_GRID's range
STAND_COMMAND = (0.0, 0.0, 0.0)
TURN_IN_PLACE_COMMAND = (0.0, 0.0, 0.5)  # rad/s yaw, no planar velocity


def _t(*rows):
    return torch.tensor(rows, dtype=torch.float32)


def _gravity_at_tilt(deg: float, axis: str = "roll") -> torch.Tensor:
    """(3,) unit gravity in the body frame for a body tilted by `deg` about x (roll) or y (pitch)."""
    rad = math.radians(deg)
    if axis == "roll":
        return torch.tensor([0.0, math.sin(rad), -math.cos(rad)])
    return torch.tensor([math.sin(rad), 0.0, -math.cos(rad)])


# ---------------------------------------------------------------- every term

SHAPE_CASES = {
    "track_lin_vel_xy": lambda n: rewards.track_lin_vel_xy(torch.randn(n, 2), torch.randn(n, 2), ANY_WIDTH),
    "track_ang_vel_z": lambda n: rewards.track_ang_vel_z(torch.randn(n), torch.randn(n), ANY_WIDTH),
    "lin_vel_z": lambda n: rewards.lin_vel_z(torch.randn(n)),
    "ang_vel_xy": lambda n: rewards.ang_vel_xy(torch.randn(n, 2)),
    "orientation": lambda n: rewards.orientation(torch.nn.functional.normalize(torch.randn(n, 3), dim=-1)),
    "base_height": lambda n: rewards.base_height(ANY_TARGET_M + 0.02 * torch.randn(n), ANY_TARGET_M),
    "torques": lambda n: rewards.torques((0.6 * torch.randn(n, J)).clamp(-SERVO_LIMIT_NM, SERVO_LIMIT_NM), 0.6 * torch.randn(n, J), SERVO_LIMIT_NM),
    "joint_acc": lambda n: rewards.joint_acc(torch.randn(n, J), torch.randn(n, J), DT),
    "action_rate": lambda n: rewards.action_rate(torch.randn(n, J), torch.randn(n, J)),
    "feet_air_time": lambda n: rewards.feet_air_time(torch.rand(n, FEET) < 0.3, 0.3 * torch.rand(n, FEET), torch.randn(n, 3), AIR_TIME_THRESHOLD_S),
    "undesired_contacts": lambda n: rewards.undesired_contacts(torch.rand(n, NONFOOT_PARTS, SUBSTEPS, 3)),
}
PENALTIES = ["lin_vel_z", "ang_vel_xy", "orientation", "base_height", "torques", "joint_acc", "action_rate", "undesired_contacts"]


def test_every_term_has_a_weight_slot():
    assert set(cfg.WEIGHTS) == set(SHAPE_CASES), "reward_config.WEIGHTS keys must match the functions in rewards.py"


@pytest.mark.parametrize("term", list(SHAPE_CASES))
def test_returns_one_finite_value_per_dog(term):
    torch.manual_seed(0)
    out = SHAPE_CASES[term](5)  # (5,)
    assert out.shape == (5,), f"{term} must return (num_envs,), got {tuple(out.shape)}"
    assert torch.isfinite(out).all()


@pytest.mark.parametrize("term", PENALTIES)
def test_penalty_is_never_negative(term):
    torch.manual_seed(1)
    out = SHAPE_CASES[term](64)  # (64,)
    assert (out >= 0).all(), f"{term} is a penalty: return a magnitude >= 0, the weight gives the sign"


# ---------------------------------------------------------------- tracking bonuses

def test_track_lin_vel_xy_perfect_tracking_is_one():
    command = _t((0.3, 0.0), (0.0, -0.2), (0.0, 0.0))  # (3, 2)
    out = rewards.track_lin_vel_xy(command, command.clone(), ANY_WIDTH)  # (3,)
    assert torch.allclose(out, torch.ones(3))


def test_track_lin_vel_xy_shrinks_as_error_grows():
    errors = torch.tensor([0.0, 0.05, 0.1, 0.3])  # (4,) m/s
    command = torch.tensor([[0.3, 0.0]]).repeat(4, 1)  # (4, 2)
    velocity = command - torch.stack([errors, torch.zeros(4)], dim=-1)  # (4, 2)
    out = rewards.track_lin_vel_xy(command, velocity, ANY_WIDTH)  # (4,)
    assert (out[1:] < out[:-1]).all() and (out > 0).all() and (out <= 1).all()


def test_track_ang_vel_z_perfect_tracking_is_one():
    command = torch.tensor([0.5, -0.8, 0.0])  # (3,) rad/s
    out = rewards.track_ang_vel_z(command, command.clone(), ANY_WIDTH)  # (3,)
    assert torch.allclose(out, torch.ones(3))


def test_track_ang_vel_z_shrinks_as_error_grows():
    command = torch.full((4,), 0.5)  # (4,) rad/s
    yaw_rate = command - torch.tensor([0.0, 0.1, 0.2, 0.6])  # (4,)
    out = rewards.track_ang_vel_z(command, yaw_rate, ANY_WIDTH)  # (4,)
    assert (out[1:] < out[:-1]).all() and (out > 0).all() and (out <= 1).all()


# ---------------------------------------------------------------- body motion penalties

def test_lin_vel_z_is_zero_without_vertical_motion():
    assert torch.equal(rewards.lin_vel_z(torch.zeros(3)), torch.zeros(3))  # (3,)


def test_lin_vel_z_up_and_down_cost_the_same_and_grow():
    out = rewards.lin_vel_z(torch.tensor([0.05, -0.05, 0.01, 0.2]))  # (4,) m/s
    assert torch.isclose(out[0], out[1]) and out[0] > 0
    assert out[2] < out[0] < out[3]


def test_ang_vel_xy_is_zero_without_roll_or_pitch_rate():
    assert torch.equal(rewards.ang_vel_xy(torch.zeros(3, 2)), torch.zeros(3))  # (3, 2) -> (3,)


def test_ang_vel_xy_counts_roll_and_pitch_either_sign():
    out = rewards.ang_vel_xy(_t((0.2, 0.0), (-0.2, 0.0), (0.0, 0.2), (0.1, 0.0), (0.3, 0.0)))  # (5, 2) -> (5,)
    assert out[0] > 0 and out[2] > 0
    assert torch.isclose(out[0], out[1])
    assert out[3] < out[0] < out[4]


def test_orientation_is_zero_when_level():
    level = torch.tensor([[0.0, 0.0, -1.0]]).repeat(3, 1)  # (3, 3)
    assert torch.allclose(rewards.orientation(level), torch.zeros(3), atol=1e-7)


def test_orientation_grows_with_tilt_in_roll_and_pitch():
    gravity = torch.stack([_gravity_at_tilt(d, "roll") for d in (5, 15, 30)] + [_gravity_at_tilt(5, "pitch")])  # (4, 3)
    out = rewards.orientation(gravity)  # (4,)
    assert (out > 0).all()
    assert out[0] < out[1] < out[2]


def test_orientation_rolling_left_or_right_costs_the_same():
    gravity = torch.stack([_gravity_at_tilt(10, "roll"), _gravity_at_tilt(-10, "roll")])  # (2, 3)
    out = rewards.orientation(gravity)  # (2,)
    assert torch.isclose(out[0], out[1])


def test_base_height_is_zero_at_target():
    assert torch.allclose(rewards.base_height(torch.full((3,), ANY_TARGET_M), ANY_TARGET_M), torch.zeros(3))


def test_base_height_costs_above_and_below_and_grows():
    z = ANY_TARGET_M + torch.tensor([0.01, -0.01, 0.001])  # (3,) m
    out = rewards.base_height(z, ANY_TARGET_M)  # (3,)
    assert (out > 0).all()
    assert out[2] < out[0]


# ---------------------------------------------------------------- joint-space penalties

def test_torques_is_zero_when_no_servo_pushes():
    zero = torch.zeros(3, J)  # (3, 12)
    assert torch.equal(rewards.torques(zero, zero.clone(), SERVO_LIMIT_NM), torch.zeros(3))


def test_torques_sees_a_saturated_servo():
    requested = torch.zeros(1, J)  # (1, 12)
    requested[0, 4] = 2 * SERVO_LIMIT_NM  # one thigh asks for twice the cap
    applied = requested.clamp(-SERVO_LIMIT_NM, SERVO_LIMIT_NM)  # (1, 12), what the servo delivers
    assert rewards.torques(applied, requested, SERVO_LIMIT_NM)[0] > 0


def test_joint_acc_is_zero_at_constant_joint_velocity():
    velocity = torch.full((3, J), 1.5)  # (3, 12) rad/s, joints moving but not accelerating
    assert torch.allclose(rewards.joint_acc(velocity, velocity.clone(), DT), torch.zeros(3))


def test_joint_acc_grows_with_the_velocity_change():
    prev = torch.zeros(3, J)  # (3, 12)
    now = torch.stack([torch.full((J,), dv) for dv in (0.1, 0.5, 2.0)])  # (3, 12) rad/s
    out = rewards.joint_acc(now, prev, DT)  # (3,)
    assert (out > 0).all() and out[0] < out[1] < out[2]


def test_joint_acc_depends_on_acceleration_not_policy_rate():
    prev = torch.zeros(1, J)  # (1, 12)
    # 5 rad/s^2 either way: +0.1 rad/s over 0.02 s, or +0.05 rad/s over 0.01 s.
    fast = rewards.joint_acc(torch.full((1, J), 0.1), prev, 0.02)  # (1,)
    faster = rewards.joint_acc(torch.full((1, J), 0.05), prev, 0.01)  # (1,)
    assert torch.allclose(fast, faster)


def test_action_rate_is_zero_when_targets_hold():
    targets = torch.full((3, J), 0.7)  # (3, 12) rad, a held (non-default) pose
    assert torch.allclose(rewards.action_rate(targets, targets.clone()), torch.zeros(3))


def test_action_rate_grows_with_the_target_change():
    prev = torch.zeros(3, J)  # (3, 12)
    now = torch.stack([torch.full((J,), d) for d in (0.01, 0.05, 0.2)])  # (3, 12) rad
    out = rewards.action_rate(now, prev)  # (3,)
    assert (out > 0).all() and out[0] < out[1] < out[2]


# ---------------------------------------------------------------- contacts

def test_feet_air_time_is_zero_without_a_touchdown():
    first_contact = torch.zeros(3, FEET, dtype=torch.bool)  # (3, 4), no foot lands this step
    last_air_time = torch.tensor([[0.0, 0.1, 0.3, 0.6]]).repeat(3, 1)  # (3, 4) s, earlier swings
    command = torch.tensor([WALK_COMMAND, STAND_COMMAND, (0.0, 0.0, 0.5)])  # (3, 3)
    assert torch.equal(rewards.feet_air_time(first_contact, last_air_time, command, AIR_TIME_THRESHOLD_S), torch.zeros(3))


def _one_touchdown(air_time_s: float, command) -> torch.Tensor:
    """(1,) feet_air_time for one dog whose fl foot lands this step after an `air_time_s` swing."""
    first_contact = torch.zeros(1, FEET, dtype=torch.bool)  # (1, 4)
    first_contact[0, 0] = True  # fl touches down
    last_air_time = torch.full((1, FEET), air_time_s)  # (1, 4) s
    return rewards.feet_air_time(first_contact, last_air_time, torch.tensor([command]), AIR_TIME_THRESHOLD_S)  # (1,)


def test_feet_air_time_flicker_touchdown_pays_negative():
    assert _one_touchdown(FLICKER_S, WALK_COMMAND)[0] < 0


def test_feet_air_time_real_swing_touchdown_pays_positive():
    assert _one_touchdown(SWING_S, WALK_COMMAND)[0] > 0


@pytest.mark.parametrize("air_time_s", [FLICKER_S, SWING_S, 0.5])
def test_feet_air_time_is_zero_on_a_zero_command_even_with_touchdowns(air_time_s):
    first_contact = torch.ones(2, FEET, dtype=torch.bool)  # (2, 4), every foot lands
    last_air_time = torch.full((2, FEET), air_time_s)  # (2, 4) s
    command = torch.tensor([STAND_COMMAND, STAND_COMMAND])  # (2, 3)
    assert torch.equal(rewards.feet_air_time(first_contact, last_air_time, command, AIR_TIME_THRESHOLD_S), torch.zeros(2))


def test_feet_air_time_pays_for_steps_when_turning_in_place():
    assert _one_touchdown(SWING_S, TURN_IN_PLACE_COMMAND)[0] > 0


def test_undesired_contacts_is_zero_when_only_feet_touch():
    assert torch.equal(rewards.undesired_contacts(torch.zeros(3, NONFOOT_PARTS, SUBSTEPS, 3)), torch.zeros(3))


def test_undesired_contacts_sees_a_thigh_brush():
    forces = torch.zeros(1, NONFOOT_PARTS, SUBSTEPS, 3)  # (1, 9, 4, 3)
    forces[0, 2, 0] = torch.tensor([0.0, 0.0, 1.0])  # fl_thigh, newest substep: 1 N, under the 1.43 N termination
    assert rewards.undesired_contacts(forces)[0] > 0


# ---------------------------------------------------------------- scenario rules (need reward_config.py)

N_DOGS = 1000  # touchdowns spread over many dogs at the measured rate, so the batch mean is a typical step


def _require_config() -> None:
    missing = [f"WEIGHTS['{k}']" for k, w in cfg.WEIGHTS.items() if w is None]
    missing += [n for n in ("TRACK_LIN_VEL_WIDTH", "TRACK_ANG_VEL_WIDTH", "FEET_AIR_TIME_THRESHOLD_S", "BASE_HEIGHT_TARGET_M")
                if getattr(cfg, n) is None]
    if missing:
        pytest.fail("set these in ironbark_rl/brian/reward_config.py first: " + ", ".join(missing))


def _step(command, lin_vel_b, ang_vel_b, tilt_deg, height_offset_m, torque_nm, joint_dv, target_step_rad, touchdown_share) -> dict:
    """A batch of N_DOGS identical dogs at one policy step; a `touchdown_share` of (dog, foot) pairs land."""
    n = N_DOGS
    first_contact = torch.zeros(n, FEET, dtype=torch.bool)  # (n, 4)
    landing = round(touchdown_share * n)
    for foot in range(FEET):  # stagger the feet over different dogs
        start = foot * n // FEET
        first_contact[start:start + landing, foot] = True
    return {
        "command": torch.tensor(command).repeat(n, 1),  # (n, 3)
        "lin_vel_b": torch.tensor(lin_vel_b).repeat(n, 1),  # (n, 3)
        "ang_vel_b": torch.tensor(ang_vel_b).repeat(n, 1),  # (n, 3)
        "gravity": _gravity_at_tilt(tilt_deg, "pitch").repeat(n, 1),  # (n, 3)
        "base_z": torch.full((n,), cfg.BASE_HEIGHT_TARGET_M + height_offset_m),  # (n,)
        "applied": torch.full((n, J), torque_nm),  # (n, 12), below the cap, so requested == applied
        "requested": torch.full((n, J), torque_nm),  # (n, 12)
        "prev_joint_vel": torch.zeros(n, J),  # (n, 12)
        "joint_vel": torch.full((n, J), joint_dv),  # (n, 12)
        "prev_targets": torch.full((n, J), 0.5),  # (n, 12)
        "targets": torch.full((n, J), 0.5 + target_step_rad),  # (n, 12)
        "first_contact": first_contact,  # (n, 4)
        "last_air_time": torch.full((n, FEET), SWING_S),  # (n, 4)
        "contact_forces": torch.zeros(n, NONFOOT_PARTS, SUBSTEPS, 3),  # (n, 9, 4, 3)
    }


def _walking_step(command=WALK_COMMAND) -> dict:
    # Base height: assumes the target sits near the height EXP-000 walks at (0.128 m), so only the
    # walking spread counts here. If the measured target is far off, tools/reward_check.py shows the real cost.
    vx, vy, wz = command
    return _step(command, (vx - PLANAR_ERROR_MPS, vy, VZ_MPS), (ROLL_PITCH_RATE_RADPS, 0.0, wz + YAW_RATE_ERROR_RADPS),
                 TILT_DEG, HEIGHT_SPREAD_M, WALK_TORQUE_NM, JOINT_ACC_RADPS2 * DT, TARGET_STEP_RAD, TOUCHDOWNS_PER_FOOT_PER_STEP)


def _standing_still_step(command) -> dict:
    return _step(command, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0, 0.0, STAND_TORQUE_NM, 0.0, 0.0, 0.0)


def _total(s: dict) -> float:
    """Mean over the batch of the weighted sum of all 11 terms (mjlab's extra x dt scales every term alike)."""
    values = {
        "track_lin_vel_xy": rewards.track_lin_vel_xy(s["command"][:, :2], s["lin_vel_b"][:, :2], cfg.TRACK_LIN_VEL_WIDTH),
        "track_ang_vel_z": rewards.track_ang_vel_z(s["command"][:, 2], s["ang_vel_b"][:, 2], cfg.TRACK_ANG_VEL_WIDTH),
        "lin_vel_z": rewards.lin_vel_z(s["lin_vel_b"][:, 2]),
        "ang_vel_xy": rewards.ang_vel_xy(s["ang_vel_b"][:, :2]),
        "orientation": rewards.orientation(s["gravity"]),
        "base_height": rewards.base_height(s["base_z"], cfg.BASE_HEIGHT_TARGET_M),
        "torques": rewards.torques(s["applied"], s["requested"], SERVO_LIMIT_NM),
        "joint_acc": rewards.joint_acc(s["joint_vel"], s["prev_joint_vel"], DT),
        "action_rate": rewards.action_rate(s["targets"], s["prev_targets"]),
        "feet_air_time": rewards.feet_air_time(s["first_contact"], s["last_air_time"], s["command"], cfg.FEET_AIR_TIME_THRESHOLD_S),
        "undesired_contacts": rewards.undesired_contacts(s["contact_forces"]),
    }  # each (n,)
    return float(sum(cfg.WEIGHTS[name] * value for name, value in values.items()).mean())


def test_air_time_threshold_sits_between_flicker_and_a_typical_swing():
    if cfg.FEET_AIR_TIME_THRESHOLD_S is None:
        pytest.fail("set FEET_AIR_TIME_THRESHOLD_S in ironbark_rl/brian/reward_config.py first")
    assert FLICKER_S < cfg.FEET_AIR_TIME_THRESHOLD_S < SWING_S, "flickers must pay negative and a typical swing positive"


def test_normal_walking_step_pays_more_than_zero():
    _require_config()
    total = _total(_walking_step())
    assert total > 0, f"a typical walking step totals {total:.4f}: falling early would raise the return"


def test_standing_still_on_a_zero_command_pays_more_than_zero():
    _require_config()
    total = _total(_standing_still_step(STAND_COMMAND))
    assert total > 0, f"standing still on a zero command totals {total:.4f}: falling early would raise the return"


def test_standing_still_loses_when_ordered_to_walk():
    _require_config()
    walking, standing = _total(_walking_step()), _total(_standing_still_step(WALK_COMMAND))
    assert walking > standing, f"ordered to walk 0.3 m/s: walking {walking:.4f} vs standing still {standing:.4f}"
