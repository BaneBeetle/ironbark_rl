"""Spec for ironbark_rl/brian/rewards.py. These fail until Brian implements the module.

The scenario tests encode Brian's own design rules (EXP-001):
- a normal walking step is worth more than 0 (so falling early never pays),
- standing still loses when ordered to walk, and wins when ordered to stand,
- tracking contributes most, then stability, then smoothness.
"Normal walking step" numbers are the measured EXP-000 medians / p90s (see rewards.py).

Run just these: python -m pytest tests/brian -q -k reward
"""

import math

import pytest
import torch

from ironbark_rl.brian import rewards

DT = 0.02  # policy period, s
J = 12  # S2 joints

# Measured EXP-000 walking step (sim, 2026-10-30).
MEDIAN_PLANAR_ERROR_MPS, P90_PLANAR_ERROR_MPS = 0.036, 0.088
MEDIAN_TILT_DEG, P90_TILT_DEG = 1.5, 2.7
MEDIAN_ROLL_PITCH_RATE, P90_ROLL_PITCH_RATE = 0.19, 0.48
MEDIAN_JOINT_TARGET_RATE, P90_JOINT_TARGET_RATE = 2.6, 4.0

WALK_COMMAND = (0.3, 0.0, 0.0)  # m/s forward, inside COMMAND_GRID's range
STAND_COMMAND = (0.0, 0.0, 0.0)


def _t(*rows):
    return torch.tensor(rows, dtype=torch.float32)


def _gravity_at_tilt(deg: float) -> torch.Tensor:
    rad = math.radians(deg)
    return _t((math.sin(rad), 0.0, -math.cos(rad)))


def _weights():
    w = rewards.WEIGHTS
    missing = [k for k, v in w.items() if v is None]
    assert not missing, f"set rewards.WEIGHTS first (missing: {missing})"
    return w


def _step(command, planar_error, tilt_deg, roll_pitch_rate, joint_target_rate):
    """Weighted per-term contributions for one dog at one step (dt left out: it scales all equally)."""
    w = _weights()
    cmd = _t(command)
    vel = cmd.clone()
    vel[0, 0] -= planar_error  # lagging the command along x by `planar_error`
    prev_q = torch.zeros(1, J)
    q = torch.full((1, J), joint_target_rate * DT)  # every joint moves at `joint_target_rate`
    return {
        "tracking": w["tracking"] * rewards.tracking_bonus(cmd, vel)[0].item(),
        "stability": w["stability"] * rewards.stability_penalty(_gravity_at_tilt(tilt_deg), _t((roll_pitch_rate, 0.0, 0.0)))[0].item(),
        "smoothness": w["smoothness"] * rewards.smoothness_penalty(q, prev_q, DT)[0].item(),
    }


def _total(**step) -> float:
    return sum(_step(**step).values())


def _standing_still(command):
    """Upright, motionless, targets unchanged: velocity 0 regardless of the command."""
    w = _weights()
    cmd = _t(command)
    zero = torch.zeros(1, 3)
    q = torch.zeros(1, J)
    return (w["tracking"] * rewards.tracking_bonus(cmd, zero)[0].item()
            + w["stability"] * rewards.stability_penalty(_gravity_at_tilt(0.0), zero)[0].item()
            + w["smoothness"] * rewards.smoothness_penalty(q, q, DT)[0].item())


# --- weights / design rules --------------------------------------------------------


def test_weight_signs():
    w = _weights()
    assert w["tracking"] > 0, "tracking is a bonus"
    assert w["stability"] < 0 and w["smoothness"] < 0, "stability and smoothness are penalties"


def test_priorities_at_a_typical_step():
    c = _step(WALK_COMMAND, MEDIAN_PLANAR_ERROR_MPS, MEDIAN_TILT_DEG, MEDIAN_ROLL_PITCH_RATE, MEDIAN_JOINT_TARGET_RATE)
    assert abs(c["tracking"]) > abs(c["stability"]) > abs(c["smoothness"]), f"contributions: {c}"


def test_a_somewhat_rough_walking_step_is_still_worth_more_than_falling():
    total = _total(command=WALK_COMMAND, planar_error=P90_PLANAR_ERROR_MPS, tilt_deg=P90_TILT_DEG,
                   roll_pitch_rate=P90_ROLL_PITCH_RATE, joint_target_rate=P90_JOINT_TARGET_RATE)
    assert total > 0, f"a p90 walking step totals {total:.4f}; falling (reward 0 from then on) would beat it"


def test_standing_still_loses_when_ordered_to_walk():
    walking = _total(command=WALK_COMMAND, planar_error=MEDIAN_PLANAR_ERROR_MPS, tilt_deg=MEDIAN_TILT_DEG,
                     roll_pitch_rate=MEDIAN_ROLL_PITCH_RATE, joint_target_rate=MEDIAN_JOINT_TARGET_RATE)
    assert walking > _standing_still(WALK_COMMAND), "the standing-still loophole is open"


def test_standing_still_wins_when_ordered_to_stand():
    fidgeting = _total(command=STAND_COMMAND, planar_error=MEDIAN_PLANAR_ERROR_MPS, tilt_deg=MEDIAN_TILT_DEG,
                       roll_pitch_rate=MEDIAN_ROLL_PITCH_RATE, joint_target_rate=MEDIAN_JOINT_TARGET_RATE)
    assert _standing_still(STAND_COMMAND) > fidgeting


# --- tracking_bonus ---------------------------------------------------------------


def test_tracking_peaks_at_zero_error_and_decreases():
    cmd = _t(WALK_COMMAND).repeat(4, 1)
    vel = cmd.clone()
    vel[:, 0] -= torch.tensor([0.0, 0.1, 0.3, 1.0])
    bonus = rewards.tracking_bonus(cmd, vel)
    assert bonus.shape == (4,)
    assert torch.all(bonus[:-1] > bonus[1:]), f"should shrink as error grows: {bonus.tolist()}"


def test_tracking_is_never_negative():
    cmd = _t(WALK_COMMAND, STAND_COMMAND)
    vel = _t((-5.0, 4.0, 3.0), (6.0, -6.0, -6.0))  # wildly wrong
    assert torch.all(rewards.tracking_bonus(cmd, vel) >= 0)


def test_turning_error_counts_too():
    cmd = _t((0.0, 0.0, 0.5), (0.0, 0.0, 0.5))
    vel = _t((0.0, 0.0, 0.5), (0.0, 0.0, 0.0))  # second dog doesn't turn
    bonus = rewards.tracking_bonus(cmd, vel)
    assert bonus[0] > bonus[1]


# --- stability_penalty ------------------------------------------------------------


def test_stability_zero_when_upright_and_still():
    assert rewards.stability_penalty(_gravity_at_tilt(0.0), torch.zeros(1, 3)).item() == pytest.approx(0.0, abs=1e-7)


def test_stability_grows_with_tilt():
    g = torch.cat([_gravity_at_tilt(d) for d in (0.0, 10.0, 30.0)])
    p = rewards.stability_penalty(g, torch.zeros(3, 3))
    assert p.shape == (3,) and p[0] < p[1] < p[2]


def test_stability_grows_with_wobble():
    g = _gravity_at_tilt(0.0).repeat(3, 1)
    w = _t((0.0, 0.0, 0.0), (0.3, 0.0, 0.0), (0.0, 1.0, 0.0))
    p = rewards.stability_penalty(g, w)
    assert p[0] < p[1] < p[2]


def test_turning_on_command_is_not_wobble():
    g = _gravity_at_tilt(0.0).repeat(2, 1)
    p = rewards.stability_penalty(g, _t((0.0, 0.0, 0.0), (0.0, 0.0, 0.5)))
    assert p[1].item() == pytest.approx(p[0].item(), abs=1e-7), "yaw rate is commanded, not wobble"


# --- smoothness_penalty -----------------------------------------------------------


def test_smoothness_zero_when_targets_hold():
    q = torch.randn(3, J)
    torch.testing.assert_close(rewards.smoothness_penalty(q, q.clone(), DT), torch.zeros(3))


def test_smoothness_grows_with_change():
    prev = torch.zeros(3, J)
    q = torch.stack([torch.full((J,), d) for d in (0.0, 0.01, 0.05)])
    p = rewards.smoothness_penalty(q, prev, DT)
    assert p.shape == (3,) and p[0] < p[1] < p[2]


def test_smoothness_is_per_second_not_per_step():
    prev, q = torch.zeros(1, J), torch.full((1, J), 0.02)
    assert rewards.smoothness_penalty(q, prev, DT / 2).item() > rewards.smoothness_penalty(q, prev, DT).item()
