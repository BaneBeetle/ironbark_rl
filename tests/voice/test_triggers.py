"""Trigger detector on hand-built frames and on the demo replay."""

import numpy as np
import pytest

from ironbark_rl.brian.metrics import FALL_TILT_DEG, tilt_deg
from ironbark_voice import config
from ironbark_voice.state import ReplaySource, RobotState
from ironbark_voice.triggers import (
    BATTERY_LOW_PCT,
    TARGET_LOST_FRAMES,
    Event,
    TriggerDetector,
    gravity_from_roll_pitch,
    still_true,
)

DEMO = config.REPO_ROOT / "docs" / "voice" / "replays" / "follow_demo.jsonl"


def run(states):
    det = TriggerDetector(clock=lambda: 0.0)
    return [(e.frame, e.name) for s in states for e in det.update(s)]


def S(frame, **kw):
    return RobotState(frame=frame, **kw)


def test_gravity_matches_brians_tilt():
    assert np.allclose(gravity_from_roll_pitch(0.0, 0.0), [0, 0, -1])
    assert tilt_deg(gravity_from_roll_pitch(70.0, 0.0)) == pytest.approx(70.0)
    assert tilt_deg(gravity_from_roll_pitch(0.0, -30.0)) == pytest.approx(30.0)
    assert np.linalg.norm(gravity_from_roll_pitch(12.0, 34.0)) == pytest.approx(1.0)  # unit vector


def test_found_lost_reacquired_with_debounce():
    frames = [S(0, target_visible=False), S(1, target_visible=True)]  # found on first sighting
    frames += [S(2 + i, target_visible=False) for i in range(TARGET_LOST_FRAMES)]  # lost after N frames
    frames += [S(10, target_visible=True)]  # back -> reacquired, not found
    assert run(frames) == [(1, "target_found"), (1 + TARGET_LOST_FRAMES, "target_lost"), (10, "target_reacquired")]


def test_short_flicker_is_not_lost():
    frames = [S(0, target_visible=True)] + [S(1 + i, target_visible=False) for i in range(TARGET_LOST_FRAMES - 1)]
    frames += [S(9, target_visible=True)]
    assert run(frames) == [(0, "target_found")]  # never out long enough; no reacquired either


def test_battery_warns_once_and_rearms_above_30():
    pcts = [25, 20, 18, 22, 29, 30, 31, 19]
    assert run([S(i, battery_pct=p) for i, p in enumerate(pcts)]) == [(1, "battery_low"), (7, "battery_low")]
    # 20 is "at" the line (fires); 22..30 doesn't re-arm; 31 re-arms; 19 fires again


def test_fall_uses_brians_threshold_and_rearms_when_upright():
    below, above = FALL_TILT_DEG - 1, FALL_TILT_DEG + 1
    frames = [S(0, roll_deg=0, pitch_deg=0), S(1, roll_deg=above, pitch_deg=0), S(2, roll_deg=above + 10, pitch_deg=0),
              S(3, roll_deg=below, pitch_deg=0), S(4, roll_deg=0, pitch_deg=above)]
    assert run(frames) == [(1, "fell"), (4, "fell")]


def test_missing_imu_neither_fires_nor_rearms():
    above = FALL_TILT_DEG + 1
    frames = [S(0, roll_deg=above, pitch_deg=0), S(1), S(2, roll_deg=above, pitch_deg=0)]
    assert run(frames) == [(0, "fell")]  # the gap (None) didn't count as upright


def test_behavior_change_carries_from_to():
    det = TriggerDetector(clock=lambda: 0.0)
    det.update(S(0, behavior="IDLE"))
    (event,) = det.update(S(1, behavior="FOLLOW"))
    assert event.name == "behavior_changed" and event.detail == {"from": "IDLE", "to": "FOLLOW"} and not event.urgent


def test_urgent_flag_from_config():
    det = TriggerDetector(clock=lambda: 0.0)
    (event,) = det.update(S(0, battery_pct=BATTERY_LOW_PCT))
    assert event.urgent


def test_demo_replay_events():
    events = run(ReplaySource(DEMO, tick_hz=None).states())
    assert events == [
        (10, "target_found"), (10, "behavior_changed"),
        (47, "target_lost"),
        (80, "target_reacquired"),
        (105, "battery_low"),
        (110, "fell"),
        (145, "behavior_changed"),
    ]


@pytest.mark.parametrize("name,state,expected", [
    ("target_lost", S(0, target_visible=True), False),
    ("target_lost", S(0, target_visible=False), True),
    ("target_found", S(0, target_visible=False), False),
    ("battery_low", S(0, battery_pct=35), False),
    ("fell", S(0, roll_deg=0, pitch_deg=0), False),
    ("fell", S(0), True),  # unknown -> still true
    ("something_new", S(0), True),
])
def test_still_true(name, state, expected):
    assert still_true(Event(name=name, frame=0, time_s=0.0, urgent=False), state) is expected


def test_behavior_change_goes_stale_when_behavior_moves_on():
    e = Event("behavior_changed", 0, 0.0, False, {"from": "IDLE", "to": "FOLLOW"})
    assert still_true(e, S(1, behavior="FOLLOW")) and not still_true(e, S(2, behavior="IDLE"))
