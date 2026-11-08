"""Pacing rules with hand-set times."""

import pytest

from ironbark_voice.speech_policy import SpeechPolicy
from ironbark_voice.state import RobotState
from ironbark_voice.triggers import Event


def E(name, t=0.0, urgent=False, **detail):
    return Event(name=name, frame=0, time_s=t, urgent=urgent, detail=detail)


def policy_after(line_end=None, haiku_end=None):
    p = SpeechPolicy()
    p.last_line_end_s, p.last_haiku_end_s = line_end, haiku_end
    return p


def test_first_line_is_allowed():
    assert SpeechPolicy().decide(E("target_found"), "cache", now_s=0.0, busy=False).speak


def test_cooldown_4s_after_any_line():
    p = policy_after(line_end=9.1)
    d = p.decide(E("target_lost"), "cache", now_s=12.4, busy=False)
    assert not d.speak and d.reason.startswith("cooldown: 3.3 s")
    assert p.decide(E("target_lost"), "cache", now_s=13.2, busy=False).speak


def test_haiku_needs_30s_since_last_haiku_and_4s_since_any_line():
    p = policy_after(line_end=40.0, haiku_end=20.0)
    assert not p.decide(E("behavior_changed"), "haiku", now_s=42.0, busy=False).speak  # 4 s quiet first
    d = p.decide(E("behavior_changed"), "haiku", now_s=45.0, busy=False)
    assert not d.speak and d.reason.startswith("haiku spacing: 25.0 s")
    assert p.decide(E("behavior_changed"), "haiku", now_s=50.5, busy=False).speak
    assert p.decide(E("target_lost"), "cache", now_s=45.0, busy=False).speak  # the 30 s rule is Haiku-only


def test_busy_drops_normal_events():
    d = SpeechPolicy().decide(E("target_lost"), "cache", now_s=0.0, busy=True)
    assert not d.speak and "busy" in d.reason


@pytest.mark.parametrize("busy", [False, True])
def test_fall_skips_cooldown_and_interrupts_only_when_busy(busy):
    d = policy_after(line_end=9.9).decide(E("fell", urgent=True), "cache", now_s=10.0, busy=busy)
    assert d.speak and d.interrupt is busy and not d.queue


def test_battery_low_skips_cooldown_when_idle():
    d = policy_after(line_end=9.9).decide(E("battery_low", urgent=True), "cache", now_s=10.0, busy=False)
    assert d.speak and not d.interrupt and not d.queue


def test_battery_low_queues_instead_of_interrupting():
    d = SpeechPolicy().decide(E("battery_low", urgent=True), "cache", now_s=10.0, busy=True)
    assert not d.speak and not d.interrupt and d.queue  # Brian: wait for the line, never dropped


def test_line_finished_starts_the_gaps():
    p = SpeechPolicy()
    p.line_finished("haiku", 5.0)
    assert (p.last_line_end_s, p.last_haiku_end_s) == (5.0, 5.0)
    p.line_finished("cache", 9.0)
    assert (p.last_line_end_s, p.last_haiku_end_s) == (9.0, 5.0)


def test_stale_by_age_or_condition():
    p = SpeechPolicy()
    lost = E("target_lost", t=10.0)
    assert p.stale_reason(lost, RobotState(frame=0, target_visible=False), now_s=11.0) is None
    assert p.stale_reason(lost, RobotState(frame=0, target_visible=False), now_s=11.7).startswith("too old: 1.70 s")
    assert p.stale_reason(lost, RobotState(frame=0, target_visible=True), now_s=10.2) == "event no longer true"
