"""pi/joint_control_probe.py against a fake servo link: safety envelope, restore, logging. No hardware."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROBE_PATH = Path(__file__).resolve().parents[1] / "pi" / "joint_control_probe.py"
spec = importlib.util.spec_from_file_location("joint_control_probe", PROBE_PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

ORDER = list(probe.LEG_IDS) + [51, 52, 53]  # a 15-long read order, like read_motor()'s


class FakeLink:
    """Servos that move halfway to their target on every read. Records everything sent."""

    def __init__(self, start=None, limits=(-40.0, 40.0), interrupt_on_write=None, swap=None, yaw_zero_reads=0,
                 refresh_every=1, slew_per_read=None, delay_reads=0):
        self.yaw_zero_reads = yaw_zero_reads  # IMU still sampling gyro bias for this many read_yaw() calls
        self.slew = slew_per_read  # max deg moved per read (None: half the remaining error)
        self.delay_reads = delay_reads  # a command takes effect this many reads later (servo dead time)
        self.pending = []  # (read count when it applies, joint, deg)
        self.refresh_every = refresh_every  # readings re-polled every N reads (the real firmware: ~28)
        self.n_reads, self.shown = 0, None
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
            self.pending.append((self.n_reads + self.delay_reads, j, d))

    def read(self):
        due = [p for p in self.pending if p[0] <= self.n_reads]
        self.pending = [p for p in self.pending if p[0] > self.n_reads]
        for _, j, d in due:
            self.target[j] = d
        for j in self.pos:
            err = self.target[j] - self.pos[j]
            self.pos[j] += 0.5 * err if self.slew is None else max(-self.slew, min(self.slew, err))
        if self.n_reads % self.refresh_every == 0:
            self.shown = [self.pos[j] for j in ORDER]  # sample-and-hold, like the firmware's round-robin poll
        self.n_reads += 1
        return list(self.shown)

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


def test_joint_already_inside_the_limit_margin_is_never_stepped(tmp_path):
    link = FakeLink(start={11: 38.5})  # beyond 40 - 3: the hold pose itself is in the margin
    code, rows = run(tmp_path, ["step", "--joints", "11", "--amp-deg", "5"], link)
    assert code == 0 and set(sent(link, 11)) == {38.5}  # only ever told to stay where it is
    assert any(r["type"] == "event" and r["name"] == "skip" for r in rows)


def test_ctrl_c_restores_the_hold_pose(tmp_path):
    link = FakeLink(start={11: 5.0}, interrupt_on_write=4)  # adopt, hold, step up, then Ctrl+C on step down
    code, rows = run(tmp_path, ["step", "--joints", "11"], link)
    assert rows[-1]["interrupted"] is True
    ids, deg = link.writes[-1]  # last thing sent: every touched joint at its measured start pose
    assert ids == probe.LEG_IDS and dict(zip(ids, deg))[11] == 5.0 and set(deg) == {0.0, 5.0}


def test_wrong_read_order_aborts_after_one_step(tmp_path):
    link = FakeLink(swap=(11, 12))
    code, rows = run(tmp_path, ["step", "--joints", "leg1"], link)
    assert code == 1 and "READ_ORDER is wrong" in rows[-1]["error"]
    assert link.writes[-1] == (probe.LEG_IDS, [0.0] * 12)  # restored after the abort


def test_sine_amplitude_and_room_check(tmp_path):
    link = FakeLink(start={12: 34.0})  # 3 deg of room up: joint 12 must be skipped
    code, _ = run(tmp_path, ["sine", "--joints", "11,12", "--amp-deg", "10", "--periods", "8", "--cycles", "1"], link)
    assert code == 0 and set(sent(link, 12)) == {34.0}  # adopt/restore only: never driven
    assert max(abs(d) for d in sent(link, 11)) <= 10.0 + 1e-9


def test_stale_readback_of_the_previous_joint_does_not_abort(tmp_path):
    # 2026-11-07 run: joint 11's reading was still pre-refresh when joint 12's drift check ran.
    # Like the real servo at ~3.7 ms per read: ~104 ms dead time, ~105 ms refresh, ~70 deg/s slew.
    link = FakeLink(refresh_every=28, slew_per_read=0.25, delay_reads=28)
    code, rows = run(tmp_path, ["sine", "--joints", "11,12", "--periods", "100", "--cycles", "3"], link)
    assert code == 0, rows[-1]["error"]


@pytest.mark.parametrize("test_args", [["step", "--joints", "11"], ["sine", "--joints", "11", "--periods", "8"],
                                       ["gait", "--joint", "12", "--samples", "20"]])
def test_first_joint_command_adopts_all_12(tmp_path, test_args):
    # 2026-11-07 gait run: a motor() call for one joint made the others jump to old joint-mode setpoints.
    start = {j: float(j % 10) for j in probe.LEG_IDS}
    link = FakeLink(start=start)
    run(tmp_path, test_args, link)
    assert link.writes[0] == (probe.LEG_IDS, [start[j] for j in probe.LEG_IDS])


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


def stub_xgolib():
    """Just enough of xgolib 1.1.10 for XgoLink.write: its conver2u8 and motor() byte bookkeeping."""
    import types

    def conver2u8(data, limit):  # copied from xgolib_dog.py (truncating)
        if data >= limit[1]:
            return 0xFF
        if data <= limit[0]:
            return 0
        return int(255 / (limit[1] - limit[0]) * (data - limit[0]))

    dog_mod = types.ModuleType("xgolib.xgolib_dog")
    dog_mod.XGOorder = {"MOTOR_ANGLE": [0x50] + [128] * 15}
    dog_mod.XGOparam = {"MOTOR_LIMIT": [[-73, 57], [-66, 93], [-31, 31], [-65, 65], [-85, 50], [-75, 90]]}

    class XGO_DOG:
        def __init__(self, port, baud=115200, version="xgomini", verbose=False):
            pass

        def motor(self, ids, data):
            for j, d in zip(ids, data):
                index = ORDER.index(j) + 1
                dog_mod.XGOorder["MOTOR_ANGLE"][index] = conver2u8(d, dog_mod.XGOparam["MOTOR_LIMIT"][(index - 1) % 3])

    dog_mod.XGO_DOG = XGO_DOG
    pkg = types.ModuleType("xgolib")
    pkg.xgolib_dog = dog_mod
    return pkg, dog_mod


@pytest.mark.parametrize("jid, deg, u8", [
    (11, 19.27, 181),  # joint 11's read-back start pose (byte 181): xgolib alone would send 180
    (11, 19.27 + 130 / 255 * 0.49, 181),  # just under half a step above byte 181: still 181
    (11, 19.27 + 130 / 255 * 0.51, 182),  # just over half a step: rounds up
    (13, 31.0, 255), (13, -31.0, 0),  # the ends stay the ends
])
def test_commands_round_to_the_nearest_byte(monkeypatch, jid, deg, u8):
    pkg, dog_mod = stub_xgolib()
    monkeypatch.setitem(sys.modules, "xgolib", pkg)
    monkeypatch.setitem(sys.modules, "xgolib.xgolib_dog", dog_mod)
    assert probe.XgoLink("/dev/null", 115200).write([jid], [deg]) == [u8]


def test_imu_reads_without_commanding_joints(tmp_path):
    link = FakeLink()
    link.imu_block = lambda: [0.1, 0.0, 9.8, 0.0, 0.0, 0.0, 0.01, 0.02, 1.0]
    link.roll, link.pitch = (lambda: 0.5), (lambda: -0.25)
    code, rows = run(tmp_path, ["imu", "--samples", "6"], link)
    imu = [r for r in rows if r["type"] == "imu"]
    assert code == 0 and link.writes == []
    assert [r["call"] for r in imu] == ["read_imu"] * 6 + ["read_roll", "read_pitch"] * 3
    assert all(r["t1"] >= r["t0"] for r in imu) and imu[-1]["v"] == -0.25


def run_map(tmp_path, argv, link, answers):
    replies = iter(answers)
    code = probe.main(["--out-dir", str(tmp_path), "map"] + argv, link=link,
                      ui={"prompt": lambda m: next(replies), "stop": lambda: False})
    (log,) = tmp_path.glob("joint_control_map_*.jsonl")
    return code, [json.loads(line) for line in log.read_text().splitlines()]


def test_map_records_one_answer_per_joint(tmp_path):
    link = FakeLink()
    code, rows = run_map(tmp_path, ["--joints", "11,12", "--samples", "5"], link, ["fl calf fwd", "fl thigh back"])
    (summary,) = [r for r in rows if r.get("name") == "map_summary"]
    assert code == 0 and summary["duplicates"] == {}
    assert summary["answers"] == {"11": {"leg": "fl", "part": "calf", "plus_dir": "fwd"},
                                  "12": {"leg": "fl", "part": "thigh", "plus_dir": "back"}}
    stepped = {ids[0] for ids, _ in link.writes if len(ids) == 1}
    assert stepped == {11, 12}  # only the joint being mapped moves on its own


def test_map_repeat_skip_reprompt_and_minus_wiggle(tmp_path):
    link = FakeLink(start={13: 30.0})  # no room up: joint 13 wiggles in the minus direction
    answers = ["r", "nonsense", "fl hip in", "s"]  # 13: wiggle again, bad answer, then the answer; 21: skip
    code, rows = run_map(tmp_path, ["--joints", "13,21", "--samples", "5", "--wiggles", "1"], link, answers)
    (ans,) = [r for r in rows if r.get("name") == "map_answer"]
    assert (ans["wiggle_sign"], ans["seen_dir"], ans["plus_dir"]) == (-1, "in", "out")
    assert [r["joint"] for r in rows if r.get("name") == "map_skip"] == [21]
    assert sum(1 for r in rows if r.get("phase") == "up" and r["cmd"] and r["joint"] == 13) == 2  # wiggled again on r


def test_map_flags_two_ids_named_as_the_same_joint(tmp_path):
    code, rows = run_map(tmp_path, ["--joints", "11,12", "--samples", "5", "--wiggles", "1"], FakeLink(),
                         ["fr calf fwd", "fr calf back"])
    (summary,) = [r for r in rows if r.get("name") == "map_summary"]
    assert summary["duplicates"] == {"fr calf": [11, 12]}


@pytest.mark.parametrize("text, parsed", [("FL Thigh Fwd", ("fl", "thigh", "fwd")), ("br hip out", ("br", "hip", "out")),
                                          ("fl hip fwd", None), ("xx calf fwd", None), (" s ", "s")])
def test_parse_map_answer(text, parsed):
    assert probe.parse_map_answer(text) == parsed


def test_imu_loop_holds_all_12_and_reads_both_every_step(tmp_path):
    link = FakeLink(start={j: float(j % 10) for j in probe.LEG_IDS})
    link.imu_block = lambda: [0.0, 0.0, -9.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    presses = iter([False, False, True] + [False] * 3 + [True] + [False] * 100)  # Enter at iterations 2 and 6
    code, rows = run(tmp_path, ["imu-loop", "--iters", "10", "--label", "tilt"], link, stop=lambda: next(presses))
    loop = [r for r in rows if r["type"] == "sample" and r["phase"] == "loop"]
    imu = [r for r in rows if r["type"] == "imu" and r["phase"] == "loop"]
    assert code == 0 and rows[0]["args"]["label"] == "tilt"
    assert len(loop) == len(imu) == 10
    assert all(r["cmd"]["ids"] == probe.LEG_IDS and r["read"]["ok"] for r in loop)
    assert all(r["cmd"]["deg"] == [float(j % 10) for j in probe.LEG_IDS] for r in loop)  # holds, never moved
    assert [r["i"] for r in rows if r.get("name") == "mark"] == [2, 6]
