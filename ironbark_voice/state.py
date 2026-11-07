"""Robot state the voice reacts to, and where it comes from.

Two sources, same output (a stream of RobotState):
- ReplaySource: a scripted JSONL scenario. Dev mode until the V2 repo (perception +
  behavior) is on this PC (Brian, 2026-11-07).
- TelemetrySource: the Pi's telemetry PUB on :5558, read-only. It only has data while Brian
  runs motor_controller; the voice never starts it and never sends commands.
"""

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, fields
from pathlib import Path

from ironbark_voice import config


@dataclass(frozen=True)
class RobotState:
    frame: int  # tick index from the source: triggers compare frames, not wall-clock times
    # From V2 PC-side code (not on this PC yet), so only replays fill these for now:
    behavior: str | None = None  # e.g. "IDLE", "FOLLOW"
    target_visible: bool | None = None  # perception: is the locked target in view
    # From Pi telemetry (CLAUDE.md field names; VERIFY against V2 pi/motor_controller.py when it lands):
    action: str | None = None  # motion vocab: stop | forward | backward | turn_* | strafe_*
    battery_pct: float | None = None
    # Degrees per the V2 attitude test in docs/progress.md (pitch -0.3 -> 7.3); VERIFY in V2 code.
    roll_deg: float | None = None
    pitch_deg: float | None = None
    yaw_deg: float | None = None
    imu_ready: bool | None = None
    seq: int | None = None  # Pi's message counter: a jump means dropped telemetry


# Telemetry JSON key -> RobotState field. Kept explicit so a renamed key in V2 fails loudly
# in one place instead of silently reading None.
TELEMETRY_KEYS = {
    "action": "action",
    "battery_pct": "battery_pct",
    "roll": "roll_deg",
    "pitch": "pitch_deg",
    "yaw": "yaw_deg",
    "imu_ready": "imu_ready",
    "seq": "seq",
}


def parse_telemetry(message: dict, frame: int) -> RobotState:
    """One telemetry JSON message -> RobotState. Missing keys become None; unknown keys are ignored.

    Example: {"action": "forward", "battery_pct": 62, "roll": 1.2, "pitch": -0.4, "yaw": 88.0,
              "imu_ready": true, "seq": 1041, "fw": "M-4.0.1-Y"}, frame=7
             -> RobotState(frame=7, action="forward", battery_pct=62, roll_deg=1.2, ...)
    """
    return RobotState(frame=frame, **{field: message.get(key) for key, field in TELEMETRY_KEYS.items()})


def state_summary(state: RobotState) -> str:
    """Compact text for the Haiku prompt; unknown fields are left out rather than shown as None.

    Example: RobotState(frame=7, behavior="FOLLOW", target_visible=False, action="turn_left",
                        battery_pct=62) -> "behavior=FOLLOW target=not visible action=turn_left battery=62%"
    """
    parts = []
    if state.behavior is not None:
        parts.append(f"behavior={state.behavior}")
    if state.target_visible is not None:
        parts.append(f"target={'visible' if state.target_visible else 'not visible'}")
    if state.action is not None:
        parts.append(f"action={state.action}")
    if state.battery_pct is not None:
        parts.append(f"battery={state.battery_pct:.0f}%")
    if state.roll_deg is not None and state.pitch_deg is not None:
        parts.append(f"roll={state.roll_deg:.0f}deg pitch={state.pitch_deg:.0f}deg")
    return " ".join(parts)


_STATE_FIELDS = {f.name for f in fields(RobotState)} - {"frame"}

# Replays tick at the rate V1's motor_controller published telemetry ("~5 Hz",
# ~/ironbark-v1/pi/motor_controller.py:615). MEASURE: V2's real rate from seq counts over a
# logged session once telemetry is flowing.
REPLAY_TICK_HZ = 5.0


class ReplaySource:
    """Plays a scripted scenario. Each JSONL line is a state held for `hold` ticks.

    Line example: {"hold": 15, "behavior": "FOLLOW", "target_visible": false, "action": "turn_left"}
    Fields not on a line carry over from the line before, so scenarios only list what changes.
    """

    def __init__(self, path: Path, tick_hz: float | None = REPLAY_TICK_HZ):
        self.path = Path(path)
        self.tick_hz = tick_hz  # None = as fast as possible (tests)

    def states(self) -> Iterator[RobotState]:
        current: dict = {}
        frame = 0
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip() or line.lstrip().startswith("//"):
                continue  # blank lines and // comments keep scenarios readable
            step = json.loads(line)
            hold = int(step.pop("hold", 1))
            unknown = set(step) - _STATE_FIELDS
            if unknown:
                raise ValueError(f"{self.path}:{line_number}: unknown fields {sorted(unknown)}")
            current.update(step)  # carry-over: only the changes are written in the file
            for _ in range(hold):
                yield RobotState(frame=frame, **current)
                frame += 1
                if self.tick_hz:
                    time.sleep(1.0 / self.tick_hz)  # PC-side pacing only; triggers still count frames


class TelemetrySource:
    """Subscribes to the Pi's telemetry PUB. Read-only: a SUB socket cannot send anything.

    V1 binds the PUB on the Pi and sends one JSON string per message; ZMQ PUB fans out to any
    number of subscribers, so listening here does not disturb the follower.
    """

    def __init__(self, host: str = config.PI_HOST, port: int = config.TELEMETRY_PORT, poll_ms: int = 200):
        self.address = f"tcp://{host}:{port}"
        self.poll_ms = poll_ms  # how often states() wakes to check stop() when the Pi is silent
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def states(self) -> Iterator[RobotState]:
        import zmq

        context = zmq.Context.instance()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")  # V1 sends no topic prefix, so take everything
        socket.setsockopt(zmq.LINGER, 0)  # don't hang on exit
        socket.connect(self.address)  # connect, not bind: the Pi owns the port
        frame = 0
        try:
            while not self._stopped:
                if not socket.poll(self.poll_ms):
                    continue  # no telemetry yet (motor_controller not running) - keep waiting
                message = json.loads(socket.recv_string())
                yield parse_telemetry(message, frame)
                frame += 1
        finally:
            socket.close()
