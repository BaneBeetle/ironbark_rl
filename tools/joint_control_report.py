"""Phase 1 joint-control gate: numbers and plots from pi/joint_control_probe.py logs (PC side).

  python tools/joint_control_report.py [docs/measurements] [--json out.json] [--figures docs/figures]

Uses the newest log of each test in the folder (`rate` keeps one per --read-every). Prints
measurements only, no interpretation (the analysis is Brian's).

Time base: a read's sample time is the midpoint of its read_motor() call (the firmware answers
somewhere inside it, so each read time is uncertain by +-half its latency, ~1.8 ms). A command's
time is the start of its write call. All clocks are the Pi's perf_counter_ns (CLOCK_MONOTONIC,
so they're comparable across runs of the same boot).

Definitions:
- step: x0 = mean of the last PRE_TAIL reads before the edge; x_end = mean of the last END_TAIL reads
  of the segment. Delay = first read with |x - x0| >= 10% of |x_end - x0|, measured from the command.
  Rise = time from the 10% to the 90% crossing. Overshoot = farthest point past x_end, as % of the
  step. Error = x_end - the commanded angle after xgolib's byte quantization.
- sine: least-squares fit of a*sin(wt) + b*cos(wt) + c to command and readback, each on its own
  times, at the commanded frequency; gain = |readback| / |command|, lag = phase difference / w.
- readback refresh: read_motor() answers in ~3.6 ms, but each joint's value only changes when the
  firmware re-polls that servo (measured 2026-11-07: round-robin, ~105 ms per joint). Step delay
  and rise are therefore quantized by that refresh, and a sine above half the refresh rate
  aliases (flagged `aliased`).
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
PRE_TAIL = 10  # reads averaged for the level before an edge
END_TAIL = 20  # reads averaged for the level at the end of a segment
RISE_LO, RISE_HI = 0.1, 0.9  # rise-time crossings, as fractions of the step
RATE_SKIP = 200  # `rate` iterations skipped before measuring the loop (the UART buffer fills first)


def load(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
    return {
        "path": str(path),
        "header": rows[0],
        "footer": rows[-1],
        "samples": [r for r in rows if r["type"] == "sample"],
        "events": [r for r in rows if r["type"] == "event"],
        "imu": [r for r in rows if r["type"] == "imu"],
        "hold": next((r["deg"] for r in rows if r["type"] == "hold"), None),
    }


def newest_logs(folder):
    by_key = {}
    for p in sorted(Path(folder).glob("joint_control_*.jsonl")):  # names sort by date
        log = load(p)
        key = log["header"]["test"]
        if key == "rate":
            key = f"rate_read_every_{log['header']['args']['read_every']}"
        by_key[key] = log
    return by_key


def read_time_s(read):
    return (read["t0"] + read["t1"]) / 2e9


def joint_index(log, jid):
    return log["header"]["read_order"].index(jid)


def quantize(log, jid, deg):
    """The angle actually sent: one of 256 bytes over the joint's limit range.

    xgolib's conver2u8 truncates; since 2026-11-07 (evening) the probe adds half a byte step first, so
    it rounds to nearest. The header's `command_rounding` says which (absent in older logs: truncate).
    """
    lo, hi = log["header"]["limits"][str(jid)]
    if log["header"].get("command_rounding") == "nearest":
        deg = deg + 0.5 * (hi - lo) / 255
    u8 = 255 if deg >= hi else 0 if deg <= lo else int(255 / (hi - lo) * (deg - lo))
    return lo + u8 / 255 * (hi - lo)


def lsb_deg(log, jid):
    lo, hi = log["header"]["limits"][str(jid)]
    return (hi - lo) / 255


def stats_ms(values_s):
    v = np.asarray(values_s) * 1e3
    return {"median": round(float(np.median(v)), 3), "p90": round(float(np.percentile(v, 90)), 3),
            "p99": round(float(np.percentile(v, 99)), 3), "max": round(float(v.max()), 3), "n": int(v.size)}


# ----------------------------------------------------------------------------------- metrics


def edge_metrics(t_cmd, t, x, x0, target_q):
    """Step-edge numbers from the reads after one command. t, x: arrays of read times (s) and angles (deg)."""
    x_end = float(np.mean(x[-END_TAIL:]))
    delta = x_end - x0
    out = {"x0": round(x0, 3), "x_end": round(x_end, 3), "step_deg": round(delta, 3),
           "error_deg": round(x_end - target_q, 3)}
    if abs(delta) < 1e-9:
        return out | {"delay_ms": None, "rise_ms": None, "overshoot_pct": None}
    frac = (x - x0) / delta  # 0 at the start level, 1 at the end level
    i_lo = int(np.argmax(frac >= RISE_LO))
    i_hi = int(np.argmax(frac >= RISE_HI))
    past = (x - x_end) * np.sign(delta)  # positive = beyond the end level
    return out | {
        "delay_ms": round((t[i_lo] - t_cmd) * 1e3, 2),
        "rise_ms": round((t[i_hi] - t[i_lo]) * 1e3, 2),
        "overshoot_pct": round(float(max(past.max(), 0.0) / abs(delta) * 100), 1),
        "first_read_frac": round(float(frac[0]), 3),  # ~1.0 here would mean readback echoes the setpoint
    }


def sine_fit(t, y, omega):
    """Least-squares a*sin(wt) + b*cos(wt) + c. Returns (amplitude, phase rad, offset)."""
    A = np.column_stack([np.sin(omega * t), np.cos(omega * t), np.ones_like(t)])
    (a, b, c), *_ = np.linalg.lstsq(A, y, rcond=None)
    return math.hypot(a, b), math.atan2(b, a), c


def gain_lag(t_cmd, c, t_read, y, omega):
    t0 = t_cmd[0]  # common origin: keeps the fit well conditioned
    amp_c, ph_c, _ = sine_fit(t_cmd - t0, c, omega)
    amp_y, ph_y, _ = sine_fit(t_read - t0, y, omega)
    dphi = (ph_c - ph_y + math.pi) % (2 * math.pi) - math.pi  # positive = readback behind
    return {"gain": round(amp_y / amp_c, 3), "lag_ms": round(dphi / omega * 1e3, 1),
            "cmd_amp_deg": round(amp_c, 2), "read_amp_deg": round(amp_y, 2)}


# ------------------------------------------------------------------------------------ tests


def report_read(log):
    reads = [s["read"] for s in log["samples"] if s["phase"] == "read"]
    lat = [(r["t1"] - r["t0"]) / 1e9 for r in reads]
    t = np.array([read_time_s(r) for r in reads])
    return {"read_latency_ms": stats_ms(lat), "read_period_ms": stats_ms(np.diff(t)),
            "reads_per_s": round(float((len(t) - 1) / (t[-1] - t[0])), 1)}


IMU_CHANNELS = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z", "roll", "pitch", "yaw"]  # read_imu() order


def report_imu(log):
    """Per IMU call: latency and rate; per channel: how often its value changes (its refresh)."""
    out = {}
    by_call = defaultdict(list)
    for r in log["imu"]:
        by_call[r["call"]].append(r)
    for call, rows in by_call.items():
        t = np.array([(r["t0"] + r["t1"]) / 2e9 for r in rows])
        good = [r for r in rows if r["v"] not in ([], None)]
        row = {"latency_ms": stats_ms([(r["t1"] - r["t0"]) / 1e9 for r in rows]),
               "calls_per_s": round(float((len(t) - 1) / (t[-1] - t[0])), 1), "failed": len(rows) - len(good)}
        tg = np.array([(r["t0"] + r["t1"]) / 2e9 for r in good])
        if call == "read_imu":
            V = np.array([r["v"] for r in good])
            channels = {name: V[:, i] for i, name in enumerate(IMU_CHANNELS)}
        else:
            channels = {call.removeprefix("read_"): np.array([r["v"] for r in good])}
        row["change_interval_ms"] = {}
        for name, x in channels.items():
            gaps = change_intervals(tg, x)
            row["change_interval_ms"][name] = stats_ms(gaps) if gaps.size else None
        out[call] = row
    return out


def report_map(log):
    """Brian's answers from the `map` run: xgolib id -> physical leg, joint, and the + direction of the foot."""
    summary = next((e for e in log["events"] if e["name"] == "map_summary"), None)
    skipped = [e["joint"] for e in log["events"] if e["name"] == "map_skip"]
    if summary is None:
        return {"error": "no map_summary event (run interrupted before the end?)", "skipped": skipped}
    return {"answers": summary["answers"], "duplicates": summary["duplicates"], "skipped": skipped}


def report_passive(log):
    leg = log["header"]["args"]["leg"]
    out = {"leg": leg}
    for k in (1, 2, 3):
        jid = 10 * leg + k
        i = joint_index(log, jid)
        by_phase = defaultdict(list)
        for s in log["samples"]:
            if s["read"]["ok"]:
                by_phase[s["phase"]].append(s["read"]["deg"][i])
        un = np.array(by_phase["unloaded"])
        out[str(jid)] = {
            "hold": log["hold"][str(jid)],
            "loaded_range_deg": round(float(np.ptp(by_phase["loaded"])), 2),
            "unloaded_range_deg": round(float(np.ptp(un)), 2),
            "unloaded_min_max": [float(un.min()), float(un.max())],
            "unloaded_last": float(un[-1]),
            "reloaded_first": by_phase["reloaded"][0],
            "reloaded_last": by_phase["reloaded"][-1],
        }
    return out


def segments(log, phases, **match):
    """Consecutive runs of samples whose phase is in `phases` and whose tags match."""
    runs, cur, key = [], [], None
    for s in log["samples"]:
        ok = s["phase"] in phases and all(s.get(k) == v for k, v in match.items())
        k = (s["phase"], s.get("joint"), s.get("speed"), s.get("period")) if ok else None
        if k != key and cur:
            runs.append(cur)
            cur = []
        if ok:
            cur.append(s)
        key = k
    if cur:
        runs.append(cur)
    return runs


def report_step(log):
    out = []
    samples = log["samples"]
    for n, s in enumerate(samples):
        if s["phase"] not in ("up", "down") or s["cmd"] is None:
            continue
        jid, speed, i = s["joint"], s["speed"], joint_index(log, s["joint"])
        before = [p["read"]["deg"][i] for p in samples[max(0, n - PRE_TAIL):n] if p["read"]["ok"]]
        seg = [s]
        for p in samples[n + 1:]:
            if p["phase"] != s["phase"] or p.get("joint") != jid or p["cmd"] is not None:
                break
            seg.append(p)
        t = np.array([read_time_s(p["read"]) for p in seg])
        x = np.array([p["read"]["deg"][i] for p in seg])
        target = s["cmd"]["deg"][0]
        m = edge_metrics(s["cmd"]["t0"] / 1e9, t, x, float(np.mean(before)), quantize(log, jid, target))
        out.append({"joint": jid, "speed": speed, "edge": s["phase"], "target_deg": target} | m)
    return out


def report_sine(log):
    out = []
    for seg in segments(log, {"sine"}):
        jid, period = seg[0]["joint"], seg[0]["period"]
        i = joint_index(log, jid)
        tc = np.array([p["cmd"]["t0"] / 1e9 for p in seg])
        c = np.array([p["cmd"]["deg"][0] for p in seg])
        tr = np.array([read_time_s(p["read"]) for p in seg])
        y = np.array([p["read"]["deg"][i] for p in seg])
        dt = float(np.median(np.diff(tc)))
        omega = 2 * math.pi / (period * dt)
        update_s = change_intervals(tr, y)
        freq = omega / (2 * math.pi)
        out.append({"joint": jid, "period_samples": period, "freq_hz": round(freq, 2), "sample_ms": round(dt * 1e3, 2),
                    "readback_update_ms": round(float(np.median(update_s)) * 1e3, 1) if update_s.size else None,
                    "aliased": bool(update_s.size and freq > 0.5 / float(np.median(update_s)))}
                   | gain_lag(tc, c, tr, y, omega))
    # Where each joint ended after its last sweep (the abort check compares against the start pose).
    for seg in segments(log, {"post"}):
        jid = seg[0]["joint"]
        i = joint_index(log, jid)
        tail = [p["read"]["deg"][i] for p in seg[-END_TAIL:]]
        out.append({"joint": jid, "post_after_period": seg[0]["period"], "hold": log["hold"][str(jid)],
                    "post_end_deg": round(float(np.mean(tail)), 3),
                    "post_offset_deg": round(float(np.mean(tail)) - log["hold"][str(jid)], 3)})
    return out


def change_intervals(t, x):
    """Seconds between consecutive changes of a reading (one segment, so idle gaps don't count)."""
    changed = np.nonzero(np.diff(x) != 0)[0] + 1
    return np.diff(t[changed])


def report_refresh(logs):
    """How often each joint's readback actually changes, from the step edges and the 12-joint rate run."""
    out = {}
    if "step" in logs:
        log = logs["step"]
        per_joint = defaultdict(list)
        for seg in segments(log, {"up", "down"}):
            jid = seg[0]["joint"]
            i = joint_index(log, jid)
            t = np.array([read_time_s(p["read"]) for p in seg])
            per_joint[jid] += list(change_intervals(t, np.array([p["read"]["deg"][i] for p in seg])))
        out["step_change_interval_ms"] = {str(j): stats_ms(v) for j, v in per_joint.items() if v}
    if "rate_read_every_1" in logs:
        log = logs["rate_read_every_1"]
        reads = [s["read"] for s in log["samples"] if s["phase"] == "rate" and s["read"]]
        D = np.array([r["deg"][:12] for r in reads])
        n_changed = (np.diff(D, axis=0) != 0).sum(axis=1)  # joints whose value changed between consecutive reads
        out["rate_joints_changed_per_read"] = {"max": int(n_changed.max()), "median": float(np.median(n_changed)),
                                               "read_period_ms": round(float(np.median(np.diff([read_time_s(r) for r in reads]))) * 1e3, 2)}
    return out


def report_rate(log):
    rate = [s for s in log["samples"] if s["phase"] == "rate"]
    steady = rate[RATE_SKIP:]
    t_cmd = np.array([s["cmd"]["t0"] / 1e9 for s in steady])
    write_s = [(s["cmd"]["t1"] - s["cmd"]["t0"]) / 1e9 for s in steady]
    period = np.diff(t_cmd)
    out = {"iterations": len(rate), "skipped": RATE_SKIP, "loop_period_ms": stats_ms(period),
           "loop_hz": round(float(1 / np.median(period)), 1), "write_call_ms": stats_ms(write_s),
           "bytes_per_s": round(float(12 * 9 / np.median(period)), 0),
           "total_s": round(float((rate[-1]["cmd"]["t0"] - rate[0]["cmd"]["t0"]) / 1e9), 3)}
    with_read = [s for s in steady if s["read"] is not None]
    if with_read:
        out["read_latency_ms"] = stats_ms([(s["read"]["t1"] - s["read"]["t0"]) / 1e9 for s in with_read])
        omega = 2 * math.pi / (log["header"]["args"]["period"] * float(np.median(period)))
        out["sine_hz"] = round(omega / (2 * math.pi), 3)
        tracks = {}
        for k, jid in enumerate(with_read[0]["cmd"]["ids"]):
            i = joint_index(log, jid)
            tc = np.array([s["cmd"]["t0"] / 1e9 for s in with_read])
            c = np.array([s["cmd"]["deg"][k] for s in with_read])
            tr = np.array([read_time_s(s["read"]) for s in with_read])
            y = np.array([s["read"]["deg"][i] for s in with_read])
            tracks[str(jid)] = gain_lag(tc, c, tr, y, omega)
        out["tracking"] = tracks
    return out


def report_gait(log):
    jid = log["header"]["args"]["joint"]
    i = joint_index(log, jid)
    legs = [j for j in log["header"]["read_order"] if j < 50]
    out = {"joint": jid, "phases": {}}
    for seg in segments(log, {s["phase"] for s in log["samples"]}):
        ph = seg[0]["phase"]
        x = np.array([p["read"]["deg"] for p in seg if p["read"]["ok"]])
        other = [joint_index(log, j) for j in legs if j != jid]
        row = {"n": len(seg), "joint_mean": round(float(x[:, i].mean()), 2),
               "joint_end": round(float(x[-END_TAIL:, i].mean()), 2), "joint_range": round(float(np.ptp(x[:, i])), 2),
               "other_legs_mean_range": round(float(np.ptp(x[:, other], axis=0).mean()), 2)}
        if seg[0]["cmd"] is not None and jid in seg[0]["cmd"]["ids"]:
            row["target_deg"] = seg[0]["cmd"]["deg"][seg[0]["cmd"]["ids"].index(jid)]
        out["phases"][ph] = row
    return out


def report_yaw(logs):
    pts = sorted((e["t"] / 1e9, e["yaw"], name) for name, log in logs.items()
                 for e in log["events"] if e["name"] == "imu_ready")
    rates = [{"from": a[2], "to": b[2], "dt_s": round(b[0] - a[0], 1), "deg_per_s": round((b[1] - a[1]) / (b[0] - a[0]), 3)}
             for a, b in zip(pts, pts[1:])]
    return {"points": [{"test": n, "t_s": round(t, 1), "yaw": y} for t, y, n in pts], "rates": rates}


REPORTS = {"read": report_read, "imu": report_imu, "map": report_map, "passive": report_passive, "step": report_step, "sine": report_sine,
           "rate_read_every_0": report_rate, "rate_read_every_1": report_rate, "gait": report_gait}


# ----------------------------------------------------------------------------------- figures


def plot_all(logs, out_dir):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if "step" in logs:
        log = logs["step"]
        joints = log["header"]["args"]["joints"]
        fig, axes = plt.subplots(1, len(joints), figsize=(4.2 * len(joints), 3.4), sharey=False)
        for ax, jid in zip(np.atleast_1d(axes), joints):
            i = joint_index(log, jid)
            for n, s in enumerate(log["samples"]):
                if s["phase"] == "up" and s["cmd"] is not None and s["joint"] == jid:
                    seg = [p for p in log["samples"][n:n + log["header"]["args"]["samples"]]]
                    t = np.array([read_time_s(p["read"]) for p in seg]) - s["cmd"]["t0"] / 1e9
                    x = np.array([p["read"]["deg"][i] for p in seg])
                    ax.plot(t * 1e3, x - log["hold"][str(jid)], marker=".", ms=2, lw=0.8, label=f"speed {s['speed']}")
            ax.axhline(log["header"]["args"]["amp_deg"], color="k", lw=0.5, ls="--")
            ax.set(title=f"joint {jid}: +step", xlabel="ms after command", ylabel="readback - start pose [deg]")
            ax.legend(fontsize=7)
        fig.tight_layout()
        written.append(out_dir / "phase1_step.png")
        fig.savefig(written[-1], dpi=130)
        plt.close(fig)
    if "sine" in logs:
        log = logs["sine"]
        segs = segments(log, {"sine"})
        fig, axes = plt.subplots(len(segs), 1, figsize=(9, 2.0 * len(segs)))
        for ax, seg in zip(np.atleast_1d(axes), segs):
            jid, i = seg[0]["joint"], joint_index(log, seg[0]["joint"])
            t0 = seg[0]["cmd"]["t0"] / 1e9
            ax.plot([(p["cmd"]["t0"] / 1e9 - t0) * 1e3 for p in seg], [p["cmd"]["deg"][0] for p in seg], lw=0.8, label="command")
            ax.plot([(read_time_s(p["read"]) - t0) * 1e3 for p in seg], [p["read"]["deg"][i] for p in seg], lw=0.8, label="readback")
            ax.set(title=f"joint {jid}, period {seg[0]['period']} samples", xlabel="ms", ylabel="deg")
            ax.legend(fontsize=7, loc="upper right")
        fig.tight_layout()
        written.append(out_dir / "phase1_sine.png")
        fig.savefig(written[-1], dpi=130)
        plt.close(fig)
    if "gait" in logs:
        log = logs["gait"]
        jid = log["header"]["args"]["joint"]
        fig, ax = plt.subplots(figsize=(11, 3.6))
        t0 = log["samples"][0]["read"]["t0"]
        for j in (jid, 11, 22):
            i = joint_index(log, j)
            ax.plot([(s["read"]["t0"] - t0) / 1e9 for s in log["samples"]], [s["read"]["deg"][i] for s in log["samples"]],
                    lw=0.7, label=f"joint {j}")
        for seg in segments(log, {s["phase"] for s in log["samples"]}):
            x = (seg[0]["read"]["t0"] - t0) / 1e9
            ax.axvline(x, color="k", lw=0.4)
            ax.text(x, ax.get_ylim()[1], seg[0]["phase"], rotation=90, fontsize=6, va="top")
        ax.set(xlabel="s", ylabel="readback [deg]", title=f"gait test: motor({jid}) vs move_x")
        ax.legend(fontsize=7, loc="lower right")
        fig.tight_layout()
        written.append(out_dir / "phase1_gait.png")
        fig.savefig(written[-1], dpi=130)
        plt.close(fig)
    if "passive" in logs:
        log = logs["passive"]
        leg = log["header"]["args"]["leg"]
        fig, ax = plt.subplots(figsize=(10, 3.2))
        t0 = log["samples"][0]["read"]["t0"]
        for k in (1, 2, 3):
            i = joint_index(log, 10 * leg + k)
            ax.plot([(s["read"]["t0"] - t0) / 1e9 for s in log["samples"]], [s["read"]["deg"][i] for s in log["samples"]],
                    lw=0.7, label=f"joint {10 * leg + k}")
        for e in log["events"]:
            if e["name"] in ("unload", "load"):
                ax.axvline((e["t"] - t0) / 1e9, color="k", lw=0.5)
                ax.text((e["t"] - t0) / 1e9, ax.get_ylim()[1], e["name"], fontsize=7, va="top")
        ax.set(xlabel="s", ylabel="readback [deg]", title=f"passive: torque off on leg {leg}, moved by hand")
        ax.legend(fontsize=7)
        fig.tight_layout()
        written.append(out_dir / "phase1_passive.png")
        fig.savefig(written[-1], dpi=130)
        plt.close(fig)
    return written


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", nargs="?", type=Path, default=REPO / "docs" / "measurements")
    p.add_argument("--json", type=Path, help="also write the numbers here")
    p.add_argument("--figures", type=Path, help="write phase1_*.png here")
    args = p.parse_args(argv)
    logs = newest_logs(args.folder)
    result = {"files": {k: Path(v["path"]).name for k, v in logs.items()},
              "footers": {k: {f: v["footer"].get(f) for f in ("interrupted", "error", "n_clamped", "n_bad_reads", "battery")}
                          for k, v in logs.items()}}
    for key, log in logs.items():
        result[key] = REPORTS[key](log)
    result["readback_refresh"] = report_refresh(logs)
    result["yaw_between_runs"] = report_yaw(logs)
    print(json.dumps(result, indent=1))
    if args.json:
        args.json.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    if args.figures:
        for f in plot_all(logs, args.figures):
            print("wrote", f)


if __name__ == "__main__":
    main()
