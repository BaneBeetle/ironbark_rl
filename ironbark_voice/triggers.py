"""When has something happened? One RobotState per frame in, zero or more events out.

Design: Brian (T1-T4 in docs/voice/decisions.md). Code: Claude. Everything here counts frames
or compares state, never wall-clock time; time_s on an Event is only for the PC-side staleness
check (P4).
"""

import time
from dataclasses import dataclass, field

import numpy as np

from ironbark_rl.brian.metrics import is_fallen  # T4: Brian's own fall definition, used read-only
from ironbark_voice import config
from ironbark_voice.state import RobotState

# T1 (Brian): count frames, not seconds. MEASURE: the real number depends on V2's perception
# rate (target_visible updates per second); set it once V2 is on the PC. 3 is a placeholder:
# 0.6 s at the replay's 5 Hz. Perception flickers, so 1 frame would chatter.
TARGET_LOST_FRAMES = 3
BATTERY_LOW_PCT = 20.0  # T3 (Brian): announce at or below 20 %
BATTERY_REARM_PCT = 30.0  # T3 (Brian): announce again only after charging above 30 %


@dataclass(frozen=True)
class Event:
    name: str  # "target_found", "target_lost", "battery_low", "fell", "behavior_changed", ...
    frame: int  # frame it was detected on
    time_s: float  # perf_counter at detection; staleness (P4) ages from here
    urgent: bool  # in config.URGENT_EVENTS: skips the cooldown and cuts off a playing line
    detail: dict = field(default_factory=dict)  # e.g. {"from": "IDLE", "to": "FOLLOW"}


def gravity_from_roll_pitch(roll_deg: float, pitch_deg: float) -> np.ndarray:
    """IMU roll/pitch -> unit gravity direction in the body frame, the input Brian's tilt_deg takes.

    For roll r and pitch p: g_b = (sin p, -cos p sin r, -cos p cos r). Upright (0, 0) -> (0, 0, -1).
    tilt_deg only uses g_b . (0, 0, -1) = cos p cos r, so yaw and the sign conventions of r and p
    don't change the answer.

    Example: (0.0, 0.0) -> [0, 0, -1] (tilt 0 deg);  (70.0, 0.0) -> [0, -0.940, -0.342] (tilt 70 deg)
    """
    r, p = np.radians(roll_deg), np.radians(pitch_deg)  # (,) each
    return np.array([np.sin(p), -np.cos(p) * np.sin(r), -np.cos(p) * np.cos(r)])  # (3,)


def fallen(state: RobotState) -> bool | None:
    """Brian's is_fallen (tilt >= FALL_TILT_DEG) on telemetry roll/pitch; None if the IMU gave nothing."""
    if state.roll_deg is None or state.pitch_deg is None:
        return None  # unknown is not "upright": don't re-arm or fire on missing data
    return bool(is_fallen(gravity_from_roll_pitch(state.roll_deg, state.pitch_deg)))


class TriggerDetector:
    """Turns a stream of states into events. Each event fires once per crossing, not every frame."""

    def __init__(self, clock=time.perf_counter):
        self._clock = clock  # injectable so tests control time
        self.target = "unseen"  # unseen -> visible -> lost -> visible ... (T2: found vs reacquired)
        self._frames_out_of_view = 0  # T1 debounce counter
        self._battery_armed = True  # T3 hysteresis: False after a warning until charged above 30 %
        self._fall_armed = True  # True while upright; a fall fires once, then waits to be upright again
        self._prev_behavior: str | None = None

    def _event(self, name: str, state: RobotState, now: float, **detail) -> Event:
        return Event(name=name, frame=state.frame, time_s=now, urgent=name in config.URGENT_EVENTS, detail=detail)

    def update(self, state: RobotState) -> list[Event]:
        now = self._clock()
        events: list[Event] = []

        # Target (T1, T2). target_visible None = no perception data: change nothing.
        if state.target_visible is True:
            self._frames_out_of_view = 0  # any sighting resets the lost countdown
            if self.target == "unseen":
                events.append(self._event("target_found", state, now))  # first time ever
            elif self.target == "lost":
                events.append(self._event("target_reacquired", state, now))  # back after a "lost you"
            self.target = "visible"
        elif state.target_visible is False and self.target == "visible":
            self._frames_out_of_view += 1
            if self._frames_out_of_view >= TARGET_LOST_FRAMES:  # out of view long enough to be real
                events.append(self._event("target_lost", state, now))
                self.target = "lost"

        # Battery (T3): warn once at <= 20 %, re-arm only above 30 % so a wobbly reading can't repeat it.
        if state.battery_pct is not None:
            if self._battery_armed and state.battery_pct <= BATTERY_LOW_PCT:
                events.append(self._event("battery_low", state, now, battery_pct=state.battery_pct))
                self._battery_armed = False
            elif not self._battery_armed and state.battery_pct > BATTERY_REARM_PCT:
                self._battery_armed = True

        # Fall (T4): fires on the upright -> fallen transition, re-arms once upright again.
        is_down = fallen(state)
        if is_down is True and self._fall_armed:
            events.append(self._event("fell", state, now))
            self._fall_armed = False
        elif is_down is False:
            self._fall_armed = True

        # Behavior change: not cached, so Haiku voices it (C2).
        if state.behavior is not None:
            if self._prev_behavior is not None and state.behavior != self._prev_behavior:
                events.append(self._event("behavior_changed", state, now, **{"from": self._prev_behavior, "to": state.behavior}))
            self._prev_behavior = state.behavior

        return events


def still_true(event: Event, state: RobotState) -> bool:
    """P4 condition check: is what the line is about still the case? Unknown data counts as true.

    Example: still_true(Event("target_lost", ...), RobotState(..., target_visible=True)) -> False
    """
    if event.name in ("target_found", "target_reacquired"):
        return state.target_visible is not False
    if event.name == "target_lost":
        return state.target_visible is not True
    if event.name == "battery_low":
        return state.battery_pct is None or state.battery_pct <= BATTERY_LOW_PCT
    if event.name == "fell":
        return fallen(state) is not False
    if event.name == "behavior_changed":
        return state.behavior is None or state.behavior == event.detail.get("to")
    return True  # an event type with no condition can only go stale by age
