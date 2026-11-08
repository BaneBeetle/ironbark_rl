#!/usr/bin/env python3
"""Phase 1 joint-control feasibility probe. Runs ON THE PI. Brian runs it; Claude never does.

Every subcommand opens the servo UART and can move the servos. Before each run: dog on a stand with
all four feet off the ground, motor_controller stopped, a hand on the power switch.

  cd ~/ironbark && .venv/bin/python joint_control_probe.py read                    # readback latency + max rate; no joint commands
  cd ~/ironbark && .venv/bin/python joint_control_probe.py imu                     # IMU refresh rate; no joint commands
  cd ~/ironbark && .venv/bin/python joint_control_probe.py map                     # wiggle each joint id; you name the leg/joint
  cd ~/ironbark && .venv/bin/python joint_control_probe.py passive --leg 1         # torque OFF on one leg, move it by hand
  cd ~/ironbark && .venv/bin/python joint_control_probe.py step --joints leg1      # step response per joint, per motor_speed
  cd ~/ironbark && .venv/bin/python joint_control_probe.py sine --joints leg1      # tracking vs. frequency
  cd ~/ironbark && .venv/bin/python joint_control_probe.py rate --read-every 1     # 12-joint command rate (also --read-every 0)
  cd ~/ironbark && .venv/bin/python joint_control_probe.py gait --joint 12         # firmware gait vs. motor(): which wins

Questions (docs/phase1-xgolib-api.md): max sustained 12-joint motor() rate; read_motor() latency and
rate; is readback the measured position or an echo of the setpoint (`passive`); step delay and rise
time vs. motor_speed; what motor() does while the firmware gait runs and how reset() hands back.
Not covered (needs xgolib internals, after the source read): one multi-register write, 2 Mbaud.

Output: <out-dir>/joint_control_<test>_<date>.jsonl. One header line, then one line per sample
(optional write, then one read_motor()) or event, then a footer. Fetch with scp into
docs/measurements/ on the PC; the analysis runs there.

Timing: every test length is a sample count, never seconds (Pi-side rule: no wall-clock logic).
The clock is only logged: time.perf_counter_ns() before and after every write and every read.
The date in the file name and header is a label.

Safety: nothing is commanded until the IMU has finished its power-on gyro-bias sampling (yaw reads
exactly 0.0 until then; moving the dog during it corrupts the bias, V2 smoke log). The first joint
command sends all 12 leg joints their measured angles (otherwise unsent joints jump to their last
joint-mode setpoints, measured 2026-11-07). Every command is
clamped to the joint's measured start pose +- MAX_EXCURSION_DEG and to xgolib's MOTOR_LIMIT minus
LIMIT_MARGIN_DEG. The probe aborts if a command at the start pose moves anything
(HOLD_DRIFT_ABORT_DEG), or if a step moves a joint other than the one commanded (READ_ORDER wrong).
On exit, Ctrl+C or error it re-sends the start pose (step/sine/rate), re-enables torque (passive),
or stops the gait and calls reset() (gait).

Written by Claude (2026-11-07). The xgolib block was checked against the Pi's xgolib 1.1.10
source; the probe refuses to run if xgolib_dog.py's hash differs.
"""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import select
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------------------------
# xgolib facts the probe depends on, read from the Pi's source (2026-11-07), never from memory:
# ~/ironbark/.venv/lib/python3.13/site-packages/xgolib/xgolib_dog.py, dist xgolib 1.1.10.
# If that file's hash changes, every test refuses to open the port until this block is rechecked.
# ---------------------------------------------------------------------------------------------
API_VERIFIED_SHA256 = "4371a423707b8225f1866ee01fa66ab9a57e5db9a7c42129bec51e15b94daaa8"  # xgolib_dog.py
# read_motor(): index i < 12 is MOTOR_ID[i] with MOTOR_LIMIT[i % 3]; 12..14 are the arm (rows 3..5).
# motor() uses the same MOTOR_ID list. An unpack failure (1 s busy-poll timeout) returns [].
READ_ORDER = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 51, 52, 53]
# __motor(index): leg joints use MOTOR_LIMIT[(index - 1) % 3], i.e. by joint position 1/2/3.
LIMIT_ROW = {1: 0, 2: 1, 3: 2}
# move_x(step) maps step over +-VX_LIMIT (25, xgomini) to one byte; the source gives no physical unit.
# motor_controller uses up to 14 (V2_FORWARD_STEP_MAX). Proposed by Claude; Brian's call.
GAIT_PROBE_STEP = 5.0
GAIT_STEP_MAX = 14.0  # never above what motor_controller already uses (V2_FORWARD_STEP_MAX)
COMMAND_ROUNDING = "nearest"  # XgoLink.write adds half a byte step; logs before 2026-11-07 evening are "truncate"
IMU_READY_MAX_READS = 5000  # read_yaw() polls before giving up. MEASURE: bias-sampling length after power-on

# Leg joint ids, leg 1-4 x joint 1-3 (xgolib numbering, docs/phase1-xgolib-api.md). Arm ids 51-53 unused.
LEG_IDS = [11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43]

# Safety envelope. Proposed by Claude; Brian's call.
MAX_EXCURSION_DEG = 15.0  # no command goes further than this from the joint's measured start pose
LIMIT_MARGIN_DEG = 3.0  # stay this far inside MOTOR_LIMIT: xgolib clamps silently at the limit
HOLD_DRIFT_ABORT_DEG = 3.0  # commanding the start pose must not move any leg joint more than this

# Stimulus sizes. Proposed by Claude; Brian's call.
STEP_AMP_DEG = 10.0  # ~20x joint 1's byte resolution (0.51 deg), so the edge stands well above quantization
SINE_AMP_DEG = 10.0  # same reasoning as the step
RATE_AMP_DEG = 3.0  # all 12 joints move at once in `rate`: keep it small
MOTOR_SPEED_MAX = 255  # top of motor_speed()'s 1..255 range. MEASURE: does 255 mean fastest? `step --speeds`

# Test lengths in samples (one sample = an optional write + one read_motor()).
# MEASURE: samples per second. `read` measures it (the docs' wire arithmetic gives ~3-4 ms per read).
SETTLE_SAMPLES = 40  # reads before a test; their median per joint is the start ("hold") pose
# Readback refresh, measured 2026-11-07: read_motor() answers in ~3.6 ms, but the firmware re-polls
# each servo only every ~105 ms (round-robin), so a reading can be up to ~105 ms (~28 reads) stale.
PRE_SAMPLES = 100  # quiet reads after commanding the hold pose: >= 3 refreshes, so the last joint has settled
STILL_CHECK_TAIL = 40  # the drift check uses only the last 40 reads (> 1 refresh): earlier ones can be stale
STEP_SAMPLES = 150  # reads after each step edge. MEASURE: must outlast the rise; check in the plots
MAP_WIGGLES = 2  # `map`: out-and-back moves per joint before asking (r repeats)
READ_SAMPLES = 2000  # `read`: back-to-back read_motor() calls
IMU_SAMPLES = 2000  # `imu`: reads per phase (read_imu blocks, then read_roll/read_pitch alternating)
PASSIVE_MAX_SAMPLES = 20000  # `passive`: upper bound; Enter ends it earlier
SINE_PERIODS = "200,100,50,25"  # sine periods in samples; the analysis converts to Hz with the logged clock
SINE_CYCLES = 3  # cycles per period: enough to fit gain and phase
RATE_ITERS = 2000  # `rate`: 12-joint writes; long enough to fill the UART buffer and see steady state
RATE_PERIOD = 100  # `rate` sine period, in iterations
GAIT_SAMPLES = 300  # reads per gait-test phase. MEASURE: reset() and gait start must settle within it


class ProbeError(RuntimeError):
    """A safety check failed: stop the test, restore, and log why."""


def ns():
    return time.perf_counter_ns()  # monotonic; only logged, never used to decide anything


class XgoLink:
    """Every xgolib call the probe makes, in one place (checked against xgolib_dog.py, see the block above)."""

    def __init__(self, port, baud):
        # Importing xgolib runs only definitions (no port access). XGO_DOG directly, not the XGO()
        # factory: with version "auto" the factory probes bauds and calls reset(), which moves the dog.
        from xgolib import xgolib_dog

        self.xd = xgolib_dog
        # Opens the port, reads firmware/yaw, sets the global XGOparam limits by firmware. No motion.
        self.dog = xgolib_dog.XGO_DOG(port, baud, version="xgomini", verbose=False)
        self.last_u8 = None  # raw bytes of the last good read_motor()

    def write(self, ids, deg):
        # xgolib's conver2u8 truncates: int(255 / range * (deg - lo)). Adding half a byte step first
        # makes that round-to-nearest, so commanding a read-back angle sends the same byte (Brian, 2026-11-07).
        nudged = [d + 0.5 * self.byte_step(j) for j, d in zip(ids, deg)]
        self.dog.motor(ids, nudged)  # one write-only packet per joint (register 0x50 + i), no ack
        table = self.xd.XGOorder["MOTOR_ANGLE"]  # xgolib keeps the last byte sent per joint here
        return [table[READ_ORDER.index(j) + 1] for j in ids]  # exact bytes on the wire

    def byte_step(self, jid):
        lo, hi = self.xd.XGOparam["MOTOR_LIMIT"][LIMIT_ROW[jid % 10]]
        return (hi - lo) / 255

    def read(self):
        deg = list(self.dog.read_motor())  # [] when __unpack times out (1 s busy-poll)
        self.last_u8 = list(self.dog.rx_data[: len(deg)]) if deg else None
        return deg

    def yaw(self):
        return self.dog.read_yaw()  # 0 while the IMU samples gyro bias (and on a failed read)

    def imu_block(self):
        # read_imu(): 24-byte register 0x65. unpack_imu -> accel xyz (int16 / 16384 * 9.8, m/s^2),
        # gyro xyz (int16 / 16.4, deg/s), roll/pitch/yaw (float deg / 180 * 3.14, ~rad). [] on failure.
        return list(self.dog.read_imu())

    def roll(self):
        return self.dog.read_roll()  # float deg, rounded to 2 dp; 0 on failure

    def pitch(self):
        return self.dog.read_pitch()

    def speed(self, value):
        self.dog.motor_speed(value)  # 0..255 (0 becomes 1); "only effective when controlling servos separately"

    def unload(self, leg):
        self.dog.unload_motor(leg)  # 1..4 legs, 5 arm

    def load(self, leg):
        self.dog.load_motor(leg)

    def reset(self):
        self.dog.reset()  # action(255): stop and return every parameter to its initial state

    def gait_forward(self, step):
        self.dog.move_x(step)  # VX register, step clipped to +-VX_LIMIT

    def gait_stop(self):
        self.dog.stop()  # move_x(0), move_y(0), mark_time(0), turn(0)

    def firmware(self):
        return self.dog.read_firmware()

    def battery(self):
        return self.dog.read_battery()

    def limits(self):
        rows = self.xd.XGOparam["MOTOR_LIMIT"]  # module global, chosen by firmware letter in XGO_DOG.__init__
        return {jid: tuple(rows[LIMIT_ROW[jid % 10]]) for jid in LEG_IDS}


class Recorder:
    """JSONL writer: header, samples and events, footer. Line-buffered so a crash keeps the data."""

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.f = open(path, "w", encoding="utf-8", buffering=1)
        self.n = 0

    def write(self, kind, **fields):
        self.f.write(json.dumps({"type": kind, "n": self.n, **fields}, default=str) + "\n")
        self.n += 1

    def close(self):
        self.f.close()


class Session:
    """One test run: logs every write and read, owns the hold pose and the safety checks."""

    def __init__(self, link, rec):
        self.link, self.rec = link, rec
        self.limits = link.limits()  # {motor id: (lo, hi)} deg, xgolib's MOTOR_LIMIT
        self.hold = {}  # {motor id: deg}, measured start pose
        self.touched = set()  # joints this run has commanded: restore re-sends their hold
        self.n_clamped = 0
        self.n_bad_reads = 0
        self.read_t = []  # (t0, t1) of every read, for the end-of-run summary only

    def event(self, name, **fields):
        self.rec.write("event", name=name, t=ns(), **fields)

    def band(self, jid):
        """Allowed command range: hold +- excursion, inside the limit margin."""
        lo, hi = self.limits[jid]
        h = self.hold[jid]
        return max(lo + LIMIT_MARGIN_DEG, h - MAX_EXCURSION_DEG), min(hi - LIMIT_MARGIN_DEG, h + MAX_EXCURSION_DEG)

    def room(self, jid):
        """(room below hold, room above hold) in deg. Negative: the hold pose is already outside the margin."""
        lo, hi = self.band(jid)
        return self.hold[jid] - lo, hi - self.hold[jid]

    def step_sign(self, jid, amp):
        down, up = self.room(jid)
        if min(down, up) < 0:
            return None  # hold sits inside the limit margin: never command this joint
        if up >= amp:
            return 1
        if down >= amp:
            return -1
        return None

    def sine_ok(self, jid, amp):
        return min(self.room(jid)) >= amp

    def clamp(self, jid, deg):
        lo, hi = self.band(jid)
        return min(max(deg, lo), hi)

    def write(self, targets, clamp=True):
        ids = list(targets)
        req = [round(float(targets[j]), 3) for j in ids]
        sent = [round(self.clamp(j, d), 3) for j, d in zip(ids, req)] if clamp else req
        self.n_clamped += sum(a != b for a, b in zip(req, sent))
        t0 = ns()
        u8 = self.link.write(ids, sent)
        t1 = ns()
        self.touched.update(ids)
        return {"ids": ids, "req_deg": req, "deg": sent, "u8": u8, "t0": t0, "t1": t1}

    def read(self):
        t0 = ns()
        deg = self.link.read()
        t1 = ns()
        ok = len(deg) == len(READ_ORDER)
        self.n_bad_reads += not ok
        self.read_t.append((t0, t1))
        u8 = getattr(self.link, "last_u8", None) if ok else None
        return {"t0": t0, "t1": t1, "deg": [round(float(d), 3) for d in deg], "u8": u8, "ok": ok}

    def wait_imu_ready(self):
        """Command nothing until yaw is non-zero: the same latch motor_controller uses (a state, not a timer)."""
        for i in range(IMU_READY_MAX_READS):
            yaw = self.link.yaw()
            if yaw:
                self.event("imu_ready", reads=i + 1, yaw=yaw)
                return
        raise ProbeError(f"yaw still 0.0 after {IMU_READY_MAX_READS} reads: IMU bias sampling not done; rerun later")

    def tick(self, phase, targets=None, read=True, clamp=True, **tags):
        cmd = self.write(targets, clamp) if targets else None
        rd = self.read() if read else None
        self.rec.write("sample", phase=phase, cmd=cmd, read=rd, **tags)
        return rd

    def segment(self, phase, targets, n, **tags):
        """Command once (if targets), then read n samples in total. Returns the reads."""
        reads = [self.tick(phase, targets, **tags)]
        reads += [self.tick(phase, **tags) for _ in range(n - 1)]
        return reads

    def measure_hold(self, phase="settle"):
        good = [r["deg"] for r in (self.tick(phase) for _ in range(SETTLE_SAMPLES)) if r["ok"]]
        if len(good) < SETTLE_SAMPLES // 2:
            raise ProbeError(f"only {len(good)}/{SETTLE_SAMPLES} good reads while settling")
        self.hold = {jid: statistics.median(r[i] for r in good) for i, jid in enumerate(READ_ORDER)}
        self.rec.write("hold", deg=self.hold)

    def max_dev(self, reads):
        """{leg joint id: max |deg - hold|} over the good reads."""
        dev = {jid: 0.0 for jid in LEG_IDS}
        for r in reads:
            if r and r["ok"]:
                for i, jid in enumerate(READ_ORDER):
                    if jid in dev:
                        dev[jid] = max(dev[jid], abs(r["deg"][i] - self.hold[jid]))
        return dev

    def check_still(self, reads, what):
        dev = self.max_dev(reads[-STILL_CHECK_TAIL:])  # only reads that had time to refresh
        worst = max(dev, key=dev.get)
        if dev[worst] > HOLD_DRIFT_ABORT_DEG:
            raise ProbeError(f"{what}: joint {worst} moved {dev[worst]:.1f} deg after commanding the hold pose")

    def check_mover(self, reads, jid):
        dev = self.max_dev(reads)
        mover = max(dev, key=dev.get)
        self.event("mover", commanded=jid, moved=mover, dev_deg=round(dev[mover], 3))
        if dev[mover] <= HOLD_DRIFT_ABORT_DEG:
            raise ProbeError(f"commanded joint {jid}, but no joint moved more than {HOLD_DRIFT_ABORT_DEG} deg")
        if mover != jid:
            raise ProbeError(f"commanded joint {jid}, but joint {mover} moved most: READ_ORDER is wrong")

    def adopt(self):
        """Send every leg joint its measured angle, before any single-joint command.

        Measured 2026-11-07 (gait test): the first motor() call puts the firmware in joint mode, and
        every joint then drives to its *last* joint-mode setpoint, so joints not in that call can jump
        (~8 deg seen). Sending all 12 at their current angles first makes that switch a no-op.
        The 12 packets take ~9.7 ms on the wire; joints later in the burst can still twitch in between.
        """
        reads = self.segment("adopt", {j: self.hold[j] for j in LEG_IDS}, PRE_SAMPLES, clamp=False)
        self.check_still(reads, "adopting the start pose")

    def restore(self):
        if self.touched:
            self.segment("restore", {j: self.hold[j] for j in sorted(self.touched)}, PRE_SAMPLES, clamp=False)


# ------------------------------------------------------------------------------------- tests


def run_read(s, args, ui):
    s.segment("read", None, args.samples)


def run_imu(s, args, ui):
    """Back-to-back IMU reads; no joint commands. Refresh rate = how often each channel's value changes."""
    calls = {"read_imu": s.link.imu_block, "read_roll": s.link.roll, "read_pitch": s.link.pitch}
    for phase, names in (("imu_block", ["read_imu"]), ("roll_pitch", ["read_roll", "read_pitch"])):
        for k in range(args.samples):
            name = names[k % len(names)]  # roll_pitch alternates the two registers
            t0 = ns()
            value = calls[name]()
            t1 = ns()
            s.rec.write("imu", phase=phase, call=name, t0=t0, t1=t1, v=value)


def run_passive(s, args, ui):
    leg = args.leg
    s.segment("loaded", None, PRE_SAMPLES, leg=leg)
    s.event("unload", leg=leg)
    s.link.unload(leg)
    try:
        print(f"Torque is OFF on leg {leg}. Move its joints slowly by hand, one at a time. Press Enter when done.")
        for _ in range(args.max_samples):
            s.tick("unloaded", leg=leg)
            if ui["stop"]():
                break
        ui["prompt"]("Put the leg back near its start pose, then press Enter to turn torque back on. ")
    finally:
        s.event("load", leg=leg)
        s.link.load(leg)  # never leave a leg limp: the next session may put the dog on the ground
    s.segment("reloaded", None, STEP_SAMPLES, leg=leg)


def run_step(s, args, ui):
    try:
        s.adopt()
        for speed in args.speeds:
            s.event("motor_speed", speed=speed)
            s.link.speed(speed)
            for jid in args.joints:
                sign = s.step_sign(jid, args.amp_deg)
                if sign is None:
                    s.event("skip", joint=jid, reason="no room for the step inside the safety band", room=s.room(jid))
                    print(f"skip joint {jid}: no room for a {args.amp_deg} deg step")
                    continue
                tags = {"joint": jid, "speed": speed}
                s.check_still(s.segment("pre", {jid: s.hold[jid]}, PRE_SAMPLES, **tags), f"joint {jid}")
                up = s.segment("up", {jid: s.hold[jid] + sign * args.amp_deg}, args.samples, **tags)
                s.check_mover(up, jid)
                s.segment("down", {jid: s.hold[jid]}, args.samples, **tags)
    finally:
        s.restore()


def run_sine(s, args, ui):
    try:
        s.adopt()
        s.event("motor_speed", speed=args.speed)
        s.link.speed(args.speed)
        for jid in args.joints:
            if not s.sine_ok(jid, args.amp_deg):
                s.event("skip", joint=jid, reason="no room for +-amp inside the safety band", room=s.room(jid))
                print(f"skip joint {jid}: no room for +-{args.amp_deg} deg")
                continue
            s.check_still(s.segment("pre", {jid: s.hold[jid]}, PRE_SAMPLES, joint=jid), f"joint {jid}")
            for period in args.periods:
                for k in range(args.cycles * period):
                    target = s.hold[jid] + args.amp_deg * math.sin(2 * math.pi * k / period)
                    s.tick("sine", {jid: target}, joint=jid, period=period, k=k)
                s.segment("post", {jid: s.hold[jid]}, PRE_SAMPLES, joint=jid, period=period)
    finally:
        s.restore()


def run_rate(s, args, ui):
    blocked = [jid for jid in LEG_IDS if not s.sine_ok(jid, args.amp_deg)]
    if blocked:
        raise ProbeError(f"joints {blocked} have no room for +-{args.amp_deg} deg; `rate` needs all 12")
    try:
        s.event("motor_speed", speed=args.speed)
        s.link.speed(args.speed)
        s.check_still(s.segment("pre", {j: s.hold[j] for j in LEG_IDS}, PRE_SAMPLES), "all legs")
        for i in range(args.iters):
            offset = args.amp_deg * math.sin(2 * math.pi * i / args.period)
            read = args.read_every > 0 and i % args.read_every == 0
            s.tick("rate", {j: s.hold[j] + offset for j in LEG_IDS}, read=read, i=i)
        s.segment("post", {j: s.hold[j] for j in LEG_IDS}, PRE_SAMPLES)
    finally:
        s.restore()


def run_gait(s, args, ui):
    jid = args.joint
    try:
        s.event("reset")
        s.link.reset()
        s.segment("reset_settle", None, args.samples)
        s.measure_hold("hold_after_reset")
        s.adopt()  # without it the other 11 joints jump to their old joint-mode setpoints (2026-11-07)
        sign = s.step_sign(jid, args.amp_deg)
        if sign is None:
            raise ProbeError(f"joint {jid}: no room for a {args.amp_deg} deg step after reset()")
        s.segment("idle_joint_up", {jid: s.hold[jid] + sign * args.amp_deg}, args.samples, joint=jid)
        s.segment("idle_joint_down", {jid: s.hold[jid]}, args.samples, joint=jid)
        s.event("gait_on", step=args.gait_step)
        s.link.gait_forward(args.gait_step)
        s.segment("gait", None, args.samples)
        s.segment("gait_joint_up", {jid: s.hold[jid] + sign * args.amp_deg}, args.samples, joint=jid)
        s.segment("gait_joint_down", {jid: s.hold[jid]}, args.samples, joint=jid)
        s.event("gait_off")
        s.link.gait_stop()
        s.segment("gait_stopped", None, args.samples)
    finally:
        s.event("reset_end")
        s.link.gait_stop()
        s.link.reset()  # hand control back to the firmware's default stand
        s.segment("reset_end", None, args.samples)


MAP_LEGS = ("fl", "fr", "br", "bl")  # front-left, front-right, back-right, back-left: the dog's own left and right
MAP_PARTS = ("hip", "thigh", "calf")  # hip: sideways swing; thigh: upper leg; calf: lower leg
MAP_DIRS = {"hip": ("out", "in"), "thigh": ("fwd", "back"), "calf": ("fwd", "back")}  # where the foot moves
_OPPOSITE = {"out": "in", "in": "out", "fwd": "back", "back": "fwd"}


def parse_map_answer(text):
    """'fl thigh fwd' -> ("fl", "thigh", "fwd"); 'r' / 's' pass through; anything else -> None."""
    words = text.strip().lower().split()
    if words in (["r"], ["s"]):
        return words[0]
    if len(words) == 3 and words[0] in MAP_LEGS and words[1] in MAP_PARTS and words[2] in MAP_DIRS[words[1]]:
        return tuple(words)
    return None


def run_map(s, args, ui):
    """Wiggle one xgolib joint id at a time; Brian says which physical leg/joint moved and where the foot went.

    Before any policy deployment (Brian, 2026-11-07): the sim-joint <-> xgolib-id mapping stays # MEASURE:
    until this run confirms it; Claude then locks it in a tested config.
    """
    answers = {}
    try:
        s.adopt()
        s.event("motor_speed", speed=args.speed)
        s.link.speed(args.speed)
        for jid in args.joints:
            sign = s.step_sign(jid, args.amp_deg)
            if sign is None:
                s.event("skip", joint=jid, reason="no room for the wiggle inside the safety band", room=s.room(jid))
                print(f"skip joint {jid}: no room for a {args.amp_deg} deg wiggle")
                continue
            while True:
                print(f"\nJoint {jid}: {args.wiggles} wiggles of {args.amp_deg:g} deg. Watch which foot moves, and where.")
                tags = {"joint": jid}
                s.check_still(s.segment("pre", {jid: s.hold[jid]}, PRE_SAMPLES, **tags), f"joint {jid}")
                for _ in range(args.wiggles):
                    s.check_mover(s.segment("up", {jid: s.hold[jid] + sign * args.amp_deg}, args.samples, **tags), jid)
                    s.segment("down", {jid: s.hold[jid]}, args.samples, **tags)
                answer = None
                while answer is None:
                    answer = parse_map_answer(ui["prompt"](
                        f"Joint {jid}: '<leg> <joint> <where the foot went>', legs {'/'.join(MAP_LEGS)}, joints "
                        "hip (out/in) thigh (fwd/back) calf (fwd/back); r = wiggle again, s = skip: "))
                    if answer is None:
                        print("  not understood, e.g. 'fl thigh fwd'")
                if answer == "r":
                    continue
                if answer == "s":
                    s.event("map_skip", joint=jid)
                    break
                leg, part, seen = answer
                plus = seen if sign > 0 else _OPPOSITE[seen]  # the wiggle went in the minus direction if sign < 0
                answers[jid] = {"leg": leg, "part": part, "plus_dir": plus}
                s.event("map_answer", joint=jid, leg=leg, part=part, seen_dir=seen, wiggle_sign=sign, plus_dir=plus)
                break
    finally:
        s.restore()
        taken = defaultdict(list)
        for jid, a in answers.items():
            taken[(a["leg"], a["part"])].append(jid)
        duplicates = {f"{leg} {part}": ids for (leg, part), ids in taken.items() if len(ids) > 1}
        s.event("map_summary", answers=answers, duplicates=duplicates)
        print(json.dumps({"map": answers, "duplicates": duplicates}, indent=1))


TESTS = {"read": run_read, "imu": run_imu, "map": run_map, "passive": run_passive, "step": run_step, "sine": run_sine, "rate": run_rate, "gait": run_gait}


# ---------------------------------------------------------------------------------- plumbing


def installed_xgolib():
    try:
        return importlib.metadata.version("xgolib")  # reads package metadata; does not import xgolib
    except importlib.metadata.PackageNotFoundError:
        return None


def xgolib_dog_sha256():
    spec = importlib.util.find_spec("xgolib")  # locates the package without executing it
    if spec is None or spec.origin is None:
        return None
    return hashlib.sha256((Path(spec.origin).parent / "xgolib_dog.py").read_bytes()).hexdigest()


def check_api_verified():
    if API_VERIFIED_SHA256 is None or READ_ORDER is None or LIMIT_ROW is None:
        sys.exit("xgolib API block not verified yet (top of this file). Claude fills it from the Pi's source first.")
    found = xgolib_dog_sha256()
    if found != API_VERIFIED_SHA256:
        sys.exit(f"xgolib_dog.py hash {found} != verified {API_VERIFIED_SHA256}: xgolib changed, recheck the API block")


def motor_controller_running():
    try:
        out = subprocess.run(["pgrep", "-f", "motor_controller"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return None  # no pgrep: the safety prompt asks Brian to check by hand
    return [int(p) for p in out.split() if int(p) != os.getpid()]


def enter_pressed():
    ready, _, _ = select.select([sys.stdin], [], [], 0)  # non-blocking: a state check, not a timer
    if ready:
        sys.stdin.readline()
    return bool(ready)


def safe_call(fn):
    try:
        return fn()
    except Exception as e:  # header info only: never worth aborting for
        return {"error": repr(e)}


def parse_joints(text):
    if text == "all":
        return list(LEG_IDS)
    if text.startswith("leg"):
        leg = int(text[3:])
        if leg not in (1, 2, 3, 4):
            raise argparse.ArgumentTypeError(f"no leg {leg}")
        return [10 * leg + 1, 10 * leg + 2, 10 * leg + 3]
    ids = [int(t) for t in text.split(",")]
    bad = [j for j in ids if j not in LEG_IDS]
    if bad:
        raise argparse.ArgumentTypeError(f"not leg joints: {bad}")
    return ids


def parse_ints(text):
    return [int(t) for t in text.split(",")]


def build_parser():
    p = argparse.ArgumentParser(description="Phase 1 joint-control probe (Brian runs it; moves servos).")
    p.add_argument("--port", default="/dev/ttyAMA0")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--out-dir", type=Path, default=Path("measurements"))
    sub = p.add_subparsers(dest="test", required=True)
    r = sub.add_parser("read", help="back-to-back read_motor(); no joint commands")
    r.add_argument("--samples", type=int, default=READ_SAMPLES)
    im = sub.add_parser("imu", help="back-to-back IMU reads; no joint commands")
    im.add_argument("--samples", type=int, default=IMU_SAMPLES)
    mp = sub.add_parser("map", help="wiggle each joint id; say which physical leg/joint moved")
    mp.add_argument("--joints", type=parse_joints, default=parse_joints("all"))
    mp.add_argument("--amp-deg", type=float, default=STEP_AMP_DEG)
    mp.add_argument("--wiggles", type=int, default=MAP_WIGGLES)
    mp.add_argument("--samples", type=int, default=STEP_SAMPLES)
    mp.add_argument("--speed", type=int, default=MOTOR_SPEED_MAX)
    pa = sub.add_parser("passive", help="torque off on one leg; move it by hand")
    pa.add_argument("--leg", type=int, choices=[1, 2, 3, 4], required=True)
    pa.add_argument("--max-samples", type=int, default=PASSIVE_MAX_SAMPLES)
    st = sub.add_parser("step", help="step response per joint and motor_speed")
    st.add_argument("--joints", type=parse_joints, default=parse_joints("leg1"))
    st.add_argument("--amp-deg", type=float, default=STEP_AMP_DEG)
    st.add_argument("--speeds", type=parse_ints, default=[MOTOR_SPEED_MAX])
    st.add_argument("--samples", type=int, default=STEP_SAMPLES)
    si = sub.add_parser("sine", help="sine tracking per joint and period")
    si.add_argument("--joints", type=parse_joints, default=parse_joints("leg1"))
    si.add_argument("--amp-deg", type=float, default=SINE_AMP_DEG)
    si.add_argument("--periods", type=parse_ints, default=parse_ints(SINE_PERIODS))
    si.add_argument("--cycles", type=int, default=SINE_CYCLES)
    si.add_argument("--speed", type=int, default=MOTOR_SPEED_MAX)
    ra = sub.add_parser("rate", help="all 12 joints commanded every iteration")
    ra.add_argument("--amp-deg", type=float, default=RATE_AMP_DEG)
    ra.add_argument("--iters", type=int, default=RATE_ITERS)
    ra.add_argument("--read-every", type=int, default=1, help="read_motor() every N writes; 0 = never")
    ra.add_argument("--period", type=int, default=RATE_PERIOD)
    ra.add_argument("--speed", type=int, default=MOTOR_SPEED_MAX)
    ga = sub.add_parser("gait", help="motor() while the firmware gait runs")
    ga.add_argument("--joint", type=int, default=12, choices=LEG_IDS)
    ga.add_argument("--amp-deg", type=float, default=STEP_AMP_DEG)
    ga.add_argument("--gait-step", type=float, default=GAIT_PROBE_STEP)
    ga.add_argument("--samples", type=int, default=GAIT_SAMPLES)
    return p


def validate(args):
    amp = getattr(args, "amp_deg", None)
    if amp is not None and not 0 < amp <= MAX_EXCURSION_DEG:
        sys.exit(f"--amp-deg must be in (0, {MAX_EXCURSION_DEG}]")
    for v in getattr(args, "speeds", []) + [getattr(args, "speed", MOTOR_SPEED_MAX)]:
        if not 1 <= v <= MOTOR_SPEED_MAX:
            sys.exit(f"motor_speed must be in 1..{MOTOR_SPEED_MAX}")
    if any(p < 4 for p in getattr(args, "periods", [])):
        sys.exit("sine periods need at least 4 samples")
    if getattr(args, "wiggles", 1) < 1:
        sys.exit("--wiggles must be >= 1")
    if getattr(args, "read_every", 0) < 0:
        sys.exit("--read-every must be >= 0")
    if args.test == "gait" and not 0 < abs(args.gait_step) <= GAIT_STEP_MAX:
        sys.exit(f"--gait-step must be in (0, {GAIT_STEP_MAX}] in magnitude")


def confirm(prompt):
    running = motor_controller_running()
    if running:
        sys.exit(f"motor_controller is running (pids {running}). Stop it first: it owns the servo UART.")
    print("SAFETY: dog on a stand, all four feet off the ground; hand on the power switch.")
    if running is None:
        print("        pgrep not found: check by hand that motor_controller is NOT running.")
    if prompt("Type 'yes' to open the servo port and start: ").strip().lower() != "yes":
        sys.exit("aborted")


def summarize(s):
    lat = [(t1 - t0) / 1e6 for t0, t1 in s.read_t]
    if len(s.read_t) < 2:
        return {"reads": len(s.read_t)}
    span_s = (s.read_t[-1][1] - s.read_t[0][0]) / 1e9
    return {
        "reads": len(s.read_t),
        "read_latency_ms_median": round(statistics.median(lat), 3),
        "read_latency_ms_max": round(max(lat), 3),
        "reads_per_s": round((len(s.read_t) - 1) / span_s, 1) if span_s > 0 else None,
    }


def run(args, link, ui):
    stamp = time.strftime("%Y%m%d-%H%M%S")  # label only
    rec = Recorder(args.out_dir / f"joint_control_{args.test}_{stamp}.jsonl")
    s = Session(link, rec)
    rec.write(
        "header", test=args.test, args=vars(args), date=stamp, host=platform.node(), python=platform.python_version(),
        xgolib=installed_xgolib(), xgolib_dog_sha256=safe_call(xgolib_dog_sha256), firmware=safe_call(link.firmware),
        command_rounding=COMMAND_ROUNDING,
        battery=safe_call(link.battery), read_order=READ_ORDER, limits=s.limits, clock="perf_counter_ns",
        safety={"max_excursion_deg": MAX_EXCURSION_DEG, "limit_margin_deg": LIMIT_MARGIN_DEG,
                "hold_drift_abort_deg": HOLD_DRIFT_ABORT_DEG},
    )
    interrupted, error = False, None
    try:
        s.wait_imu_ready()  # before anything moves, even by hand (passive)
        if args.test != "gait":
            s.measure_hold()  # gait measures its hold after reset()
        TESTS[args.test](s, args, ui)
    except KeyboardInterrupt:
        interrupted = True
    except Exception as e:  # ProbeError or anything else: logged in the footer, then re-raised as exit 1
        error = f"{type(e).__name__}: {e}"
    summary = summarize(s)
    rec.write("footer", interrupted=interrupted, error=error, n_clamped=s.n_clamped, n_bad_reads=s.n_bad_reads,
              battery=safe_call(link.battery), **summary)
    rec.close()
    print(json.dumps({"file": str(rec.path), "interrupted": interrupted, "error": error,
                      "n_clamped": s.n_clamped, "n_bad_reads": s.n_bad_reads, **summary}, indent=1))
    return 1 if error else 0


def main(argv=None, link=None, ui=None):
    args = build_parser().parse_args(argv)
    validate(args)
    ui = ui or {"prompt": input, "stop": enter_pressed}
    if link is None:  # the real dog
        check_api_verified()
        confirm(ui["prompt"])
        link = XgoLink(args.port, args.baud)
    return run(args, link, ui)


if __name__ == "__main__":
    sys.exit(main())
