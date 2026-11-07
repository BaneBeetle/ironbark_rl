"""State parsing and replay: no robot, no network."""

import json

import pytest

from ironbark_voice import config
from ironbark_voice.state import ReplaySource, RobotState, parse_telemetry, state_summary

DEMO = config.REPO_ROOT / "docs" / "voice" / "replays" / "follow_demo.jsonl"


def test_parse_telemetry_maps_fields_and_ignores_extras():
    msg = {"action": "forward", "battery_pct": 62, "roll": 1.2, "pitch": -0.4, "yaw": 88.0,
           "imu_ready": True, "seq": 1041, "fw": "M-4.0.1-Y"}
    state = parse_telemetry(msg, frame=7)
    assert state == RobotState(frame=7, action="forward", battery_pct=62, roll_deg=1.2, pitch_deg=-0.4,
                               yaw_deg=88.0, imu_ready=True, seq=1041)


def test_parse_telemetry_missing_keys_are_none():
    state = parse_telemetry({"action": "stop"}, frame=0)
    assert state.action == "stop" and state.battery_pct is None and state.roll_deg is None


def test_summary_skips_unknowns():
    state = RobotState(frame=7, behavior="FOLLOW", target_visible=False, action="turn_left", battery_pct=62)
    assert state_summary(state) == "behavior=FOLLOW target=not visible action=turn_left battery=62%"
    assert state_summary(RobotState(frame=0)) == ""


def test_demo_replay_frames_and_carry_over():
    states = list(ReplaySource(DEMO, tick_hz=None).states())
    assert len(states) == 10 + 25 + 15 + 20 + 10 + 10
    assert [s.frame for s in states] == list(range(len(states)))  # frames count up with no gaps
    lost = states[10 + 25]  # first tick of the "target lost" line
    assert lost.target_visible is False and lost.action == "turn_left"
    assert lost.behavior == "FOLLOW" and lost.battery_pct == 80  # carried over
    assert states[-1].roll_deg == 70.0 and states[-1].battery_pct == 19


def test_telemetry_source_reads_a_local_pub():
    import threading
    import time

    import zmq

    from ironbark_voice.state import TelemetrySource

    pub = zmq.Context.instance().socket(zmq.PUB)
    port = pub.bind_to_random_port("tcp://127.0.0.1")  # stands in for the Pi's :5558
    stop = threading.Event()

    def publish():  # ZMQ "slow joiner": keep sending until the subscriber has connected
        while not stop.is_set():
            pub.send_string(json.dumps({"action": "forward", "seq": 1, "fw": "M-4.0.1-Y"}))
            time.sleep(0.02)

    sender = threading.Thread(target=publish, daemon=True)
    sender.start()
    source = TelemetrySource(host="127.0.0.1", port=port, poll_ms=50)
    states = source.states()
    try:
        first = next(states)
    finally:
        stop.set()
        sender.join()
        source.stop()
        states.close()
        pub.close(linger=0)
    assert first.frame == 0 and first.action == "forward" and first.seq == 1


def test_replay_rejects_unknown_fields(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"hold": 1, "batery_pct": 50}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="batery_pct"):
        list(ReplaySource(bad, tick_hz=None).states())
