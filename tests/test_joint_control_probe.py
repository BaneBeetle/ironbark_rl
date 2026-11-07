"""pi/joint_control_probe.py against a fake servo link: safety envelope, restore, logging. No hardware."""

import importlib.util
import json
from pathlib import Path

import pytest

PROBE_PATH = Path(__file__).resolve().parents[1] / "pi" / "joint_control_probe.py"
spec = importlib.util.spec_from_file_location("joint_control_probe", PROBE_PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

ORDER = list(probe.LEG_IDS) + [51, 52, 53]  # a 15-long read order, like read_motor()'s


class FakeLink:
    """Servos that move halfway to their target on every read. Records everything sent."""

    def __init__(self, start=None, limits=(-40.0, 40.0), interrupt_on_write=None, swap=None, yaw_zero_reads=0):
        self.yaw_zero_reads = yaw_zero_reads  # IMU still sampling gyro bias for this many read_yaw() calls
        self.pos = {j: 0.0 for j in ORDER} | (start or {})
        self.target = dict(self.pos)
        self.lim = limits
        self.writes, self.calls = [], []
        self.interrupt_on_write = interrupt_on_write
        self.swap = swap  # (a, b): joint a's motor actually drives joint b (a wrong READ_ORDER)

    def write(self, ids, deg):
        self.writes.append((list(ids), list(deg)))
        if self.interrupt_on_write is not None and len(self.writes) == self.interrupt_on_write:
            raise KeyboardInterrupt
        for j, d in zip(ids, deg):
            if self.swap and j == self.swap[0]:
                j = self.swap[1]
            self.target[j] = d

    def read(self):
        for j in self.pos:
            self.pos[j] += 0.5 * (self.target[j] - self.pos[j])
        return [self.pos[j] for j in ORDER]

    def limits(self):
        return {j: self.lim for j in probe.LEG_IDS}

    def yaw(self):
        self.yaw_zero_reads -= 1
        return 0.0 if self.yaw_zero_reads >= 0 else 12.5

    def __getattr__(self, name):  # speed, unload, load, reset, gait_*, firmware, battery
        return lambda *a: self.calls.append((name, a))


def test_api_block_matches_the_pi_source():
    # Read from xgolib_dog.py on the Pi (2026-11-07): MOTOR_ID order, MOTOR_LIMIT row by joint position.
    assert probe.READ_ORDER == ORDER
    assert probe.LIMIT_ROW == {1: 0, 2: 1, 3: 2}
    assert len(probe.API_VERIFIED_SHA256) == 64


def run(tmp_path, argv, link, stop=lambda: False):
    code = probe.main(["--out-dir", str(tmp_path)] + argv, link=link, ui={"prompt": lambda m: "", "stop": stop})
    (log,) = tmp_path.glob("joint_control_*.jsonl")
    return code, [json.loads(line) for line in log.read_text().splitlines()]


def sent(link, jid):
    return [d for ids, degs in link.writes for j, d in zip(ids, degs) if j == jid]


def test_log_has_header_samples_footer(tmp_path):
    code, rows = run(tmp_path, ["read", "--samples", "50"], FakeLink())
    assert code == 0
    assert rows[0]["type"] == "header" and rows[-1]["type"] == "footer"
    samples = [r for r in rows if r["type"] == "sample"]
    assert len(samples) == probe.SETTLE_SAMPLES + 50
    assert all(r["read"]["t1"] >= r["read"]["t0"] and len(r["read"]["deg"]) == 15 for r in samples)
    assert rows[-1]["n_bad_reads"] == 0 and rows[-1]["error"] is None


def test_read_sends_no_joint_commands(tmp_path):
    link = FakeLink()
    run(tmp_path, ["read", "--samples", "20"], link)
    assert link.writes == []


def test_step_stays_inside_the_safety_band(tmp_path):
    link = FakeLink()
    code, _ = run(tmp_path, ["step", "--joints", "leg1", "--amp-deg", "10", "--speeds", "255,64"], link)
    assert code == 0
    for jid in (11, 12, 13):
        assert set(sent(link, jid)) == {0.0, 10.0}  # hold, hold + amp; nothing else
    assert ("speed", (64,)) in link.calls


def test_step_flips_direction_near_the_upper_limit(tmp_path):
    link = FakeLink(start={11: 30.0})  # band top = min(40 - 3, 30 + 15) = 37: only 7 deg of room up
    run(tmp_path, ["step", "--joints", "11", "--amp-deg", "10"], link)
    assert min(sent(link, 11)) == pytest.approx(20.0)
    assert max(sent(link, 11)) == pytest.approx(30.0)


def test_joint_already_inside_the_limit_margin_is_never_commanded(tmp_path):
    link = FakeLink(start={11: 38.5})  # beyond 40 - 3: the hold pose itself is in the margin
    code, rows = run(tmp_path, ["step", "--joints", "11", "--amp-deg", "5"], link)
    assert code == 0 and sent(link, 11) == []
    assert any(r["type"] == "event" and r["name"] == "skip" for r in rows)


def test_ctrl_c_restores_the_hold_pose(tmp_path):
    link = FakeLink(start={11: 5.0}, interrupt_on_write=3)  # hold, step up, then Ctrl+C on step down
    code, rows = run(tmp_path, ["step", "--joints", "11"], link)
    assert rows[-1]["interrupted"] is True
    assert link.writes[-1] == ([11], [5.0])  # last thing sent: the measured start pose


def test_wrong_read_order_aborts_after_one_step(tmp_path):
    link = FakeLink(swap=(11, 12))
    code, rows = run(tmp_path, ["step", "--joints", "leg1"], link)
    assert code == 1 and "READ_ORDER is wrong" in rows[-1]["error"]
    assert link.writes[-1] == ([11], [0.0])  # restored after the abort


def test_sine_amplitude_and_room_check(tmp_path):
    link = FakeLink(start={12: 34.0})  # 3 deg of room up: joint 12 must be skipped
    code, _ = run(tmp_path, ["sine", "--joints", "11,12", "--amp-deg", "10", "--periods", "8", "--cycles", "1"], link)
    assert code == 0 and sent(link, 12) == []
    assert max(abs(d) for d in sent(link, 11)) <= 10.0 + 1e-9


@pytest.mark.parametrize("read_every, reads", [(1, 40), (0, 0), (4, 10)])
def test_rate_writes_all_12_joints_every_iteration(tmp_path, read_every, reads):
    link = FakeLink()
    _, rows = run(tmp_path, ["rate", "--iters", "40", "--read-every", str(read_every)], link)
    rate = [r for r in rows if r["type"] == "sample" and r["phase"] == "rate"]
    assert len(rate) == 40 and all(r["cmd"]["ids"] == probe.LEG_IDS for r in rate)
    assert sum(r["read"] is not None for r in rate) == reads


def test_passive_turns_torque_back_on(tmp_path):
    link = FakeLink()
    stops = iter([False] * 9 + [True])
    _, rows = run(tmp_path, ["passive", "--leg", "2"], link, stop=lambda: next(stops))
    names = [c[0] for c in link.calls]
    assert names.index("unload") < names.index("load")
    assert sum(r["type"] == "sample" and r["phase"] == "unloaded" for r in rows) == 10


def test_gait_ends_with_stop_and_reset(tmp_path):
    link = FakeLink()
    code, _ = run(tmp_path, ["gait", "--joint", "12", "--gait-step", "5", "--samples", "20"], link)
    assert code == 0
    names = [c[0] for c in link.calls if c[0] not in ("firmware", "battery")]  # header/footer info reads
    assert names[-2:] == ["gait_stop", "reset"] and ("gait_forward", (5.0,)) in link.calls


def test_nothing_moves_before_the_imu_is_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "IMU_READY_MAX_READS", 50)
    link = FakeLink(yaw_zero_reads=1000)  # still sampling bias
    code, rows = run(tmp_path, ["step", "--joints", "11"], link)
    assert code == 1 and "IMU" in rows[-1]["error"] and link.writes == []


def test_imu_ready_after_some_zero_yaw_reads(tmp_path):
    code, rows = run(tmp_path, ["read", "--samples", "5"], FakeLink(yaw_zero_reads=7))
    (ready,) = [r for r in rows if r["type"] == "event" and r["name"] == "imu_ready"]
    assert code == 0 and ready["reads"] == 8


def test_unverified_api_refuses_to_open_the_port(monkeypatch):
    monkeypatch.setattr(probe, "API_VERIFIED_SHA256", None)
    with pytest.raises(SystemExit, match="not verified"):
        probe.main(["read"])


def test_changed_xgolib_refuses_to_open_the_port(monkeypatch):
    monkeypatch.setattr(probe, "xgolib_dog_sha256", lambda: "0" * 64)
    with pytest.raises(SystemExit, match="recheck the API block"):
        probe.main(["read"])


def test_gait_step_above_motor_controllers_max_is_rejected():
    with pytest.raises(SystemExit, match="gait-step"):
        probe.main(["gait", "--gait-step", str(probe.GAIT_STEP_MAX + 1)], link=FakeLink())


def test_amplitude_above_the_excursion_cap_is_rejected():
    with pytest.raises(SystemExit, match="amp-deg"):
        probe.main(["step", "--amp-deg", str(probe.MAX_EXCURSION_DEG + 1)], link=FakeLink())
