"""tools/joint_control_report.py on synthetic signals with known answers."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1] / "tools" / "joint_control_report.py"
spec = importlib.util.spec_from_file_location("joint_control_report", PATH)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

LOG = {"header": {"limits": {"11": [-73, 57]}}}  # joint 1's xgomini MOTOR_LIMIT


def test_quantize_truncates_like_xgolib():
    # Readback 19.27 is byte 181; commanding it truncates to byte 180 (one 0.51 deg step low).
    assert report.quantize(LOG, 11, 19.27) == pytest.approx(-73 + 180 / 255 * 130)
    assert report.quantize(LOG, 11, 100.0) == 57.0 and report.quantize(LOG, 11, -100.0) == -73.0


def test_quantize_rounds_to_nearest_when_the_log_says_so():
    log = {"header": {"limits": {"11": [-73, 57]}, "command_rounding": "nearest"}}
    assert report.quantize(log, 11, 19.27) == pytest.approx(-73 + 181 / 255 * 130)  # the read-back byte


def test_edge_metrics_on_a_sample_and_hold_jump():
    t = np.arange(150) * 0.004  # reads every 4 ms
    x = np.where(t >= 0.1, 10.0, 0.0)  # readback jumps at 100 ms (a refresh), no intermediate value
    m = report.edge_metrics(0.0, t, x, x0=0.0, target_q=9.5)
    assert m["delay_ms"] == pytest.approx(100.0, abs=0.01)
    assert m["rise_ms"] == 0.0 and m["overshoot_pct"] == 0.0
    assert m["error_deg"] == pytest.approx(0.5) and m["first_read_frac"] == 0.0


def test_edge_metrics_on_a_ramp_with_overshoot():
    t = np.arange(200) * 0.001
    x = np.clip((t - 0.02) / 0.1, 0, 1) * 11.0  # 20 ms dead time, 100 ms ramp to 11
    x[150:] = 10.0  # settles at 10: 10% overshoot
    m = report.edge_metrics(0.0, t, x, x0=0.0, target_q=10.0)
    assert m["delay_ms"] == pytest.approx(20 + 9.09, abs=1.1)  # 10% of 10 reached at 1/11 of the ramp
    assert m["overshoot_pct"] == pytest.approx(10.0, abs=0.1)


def test_gain_lag_recovers_a_known_response():
    omega = 2 * math.pi * 1.5
    tc = np.arange(0, 3, 0.004)
    tr = tc + 0.002  # reads land 2 ms after each command
    c = 20 + 10 * np.sin(omega * tc)
    y = 21 + 8 * np.sin(omega * (tr - 0.05))  # gain 0.8, 50 ms behind, different offset
    g = report.gain_lag(tc, c, tr, y, omega)
    assert g["gain"] == pytest.approx(0.8, abs=0.002) and g["lag_ms"] == pytest.approx(50.0, abs=0.2)


def test_change_intervals_ignore_held_values():
    t = np.arange(10) * 0.01
    x = np.array([0, 0, 1, 1, 1, 2, 2, 2, 2, 3.0])  # changes at reads 2, 5, 9
    assert report.change_intervals(t, x) == pytest.approx([0.03, 0.04])


def test_imu_refresh_from_held_values():
    # read_imu every 2 ms; accel_x refreshes every 5 reads (10 ms), roll every 10 reads (20 ms).
    rows = []
    for k in range(100):
        v = [float(k // 5), 0, 9.8, 0, 0, 0, float(k // 10), 0, 0]
        rows.append({"call": "read_imu", "t0": k * 2_000_000, "t1": k * 2_000_000 + 1_000_000, "v": v})
    out = report.report_imu({"imu": rows})["read_imu"]
    assert out["change_interval_ms"]["accel_x"]["median"] == pytest.approx(10.0)
    assert out["change_interval_ms"]["roll"]["median"] == pytest.approx(20.0)
    assert out["change_interval_ms"]["accel_z"] is None and out["failed"] == 0


def test_report_map_reads_the_summary_and_skips():
    events = [{"name": "map_skip", "joint": 21},
              {"name": "map_summary", "answers": {"11": {"leg": "fl", "part": "calf", "plus_dir": "fwd"}}, "duplicates": {}}]
    out = report.report_map({"events": events})
    assert out == {"answers": {"11": {"leg": "fl", "part": "calf", "plus_dir": "fwd"}}, "duplicates": {}, "skipped": [21]}


def test_frozen_stretches_and_zero_vectors():
    rows = []
    for k in range(100):  # read every 2 ms; values update every read except reads 20-79 (120 ms frozen)
        x = float(min(k, 20) if k < 80 else k)
        v = [x, 0, -9.8, 0.1, 0, 0, 0, 0, 0] if k != 90 else [0, 0, 0, 0.1, 0, 0, 0, 0, 0]  # read 90: accel zeroed
        rows.append({"call": "read_imu", "t0": k * 2_000_000, "t1": k * 2_000_000 + 1_000_000, "v": v})
    out = report.report_imu({"imu": rows, "events": [{"name": "mark", "i": 5}]})
    row = out["read_imu"]
    assert row["frozen_over_100ms_ms"] == [118] and row["zero_vectors"] == 1 and out["marks"] == [5]
    assert row["period_ms"]["median"] == pytest.approx(2.0)
