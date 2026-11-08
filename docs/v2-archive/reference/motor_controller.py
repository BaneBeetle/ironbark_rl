#!/usr/bin/env python3
"""
IronBark V2 motor controller — DogZilla S2 body node.

Rewritten from scratch. V1's PiDog controller was 1,172 lines, most of it
scaffolding around a queued-gait-frame SDK (buffer accounting, one_shot,
flush, leap-prone interpolation). The S2 is a velocity-setpoint machine —
movement calls are non-blocking and continuous until stop() — so none of
that scaffolding exists here. If this file grows toward V1's size, question
what is being ported.

Wire protocol is V1's, unchanged, so pc/ runs as-is:
  SUB  tcp://PC_IP:CMD_PORT        JSON commands (follower.Command.to_json)
  PUB  tcp://*:REMOTE_TELEM_PORT   JSON telemetry (send_string)

Command fields consumed: action (stop|forward|backward|turn_left|
turn_right|strafe_left|strafe_right), speed (0-100, scales forward/back
step), head_pitch (→ attitude('p') trim, clamped). Tolerated and ignored:
step_count (no gait queue), head_yaw/head_mode/owner_bbox (S2 has no head
servos — camera aim = body aim), bark/bark_volume (no speaker path yet),
idle_pose, one_shot, flush (no buffer to protect), thinking (maps to stop).

Measured facts this design leans on (docs/measurements/smoke_*.jsonl):
  - forward/back/turnleft/turnright are non-blocking setpoints, continuous
    until stop(); turn step ≈ °/s (39.2 measured at commanded 40).
  - Sensor reads are ~3 ms and safe during motion.
  - Yaw register: unwrapped continuous degrees, turnleft = positive (CCW).
    The firmware serves EXACTLY 0.0 while it samples gyro bias after
    power-on; moving the dog during that window corrupts the bias
    (measured: -9.9°/s drift from a handled boot vs -0.009°/s clean).
    So: imu_ready is a first-nonzero-yaw LATCH, and motion commands are
    REFUSED until it latches. State predicate, not a timer.
  - attitude() composes with walking, but only with self-stabilization
    off — imu(0) at startup. SDK turn_by is dead-reckoned open-loop
    (45° commanded → 73.8° measured); accurate turns are closed Mac-side
    on telemetry yaw, never via SDK convenience turns.
  - No sudo needed: the serial device is root:dialout and lolly is in
    dialout. Run: .venv/bin/python -u motor_controller.py

Telemetry payload: {"action", "yaw", "roll", "pitch", "battery_pct",
"imu_ready", "seq", "fw"}. V1 fields distance_cm / battery_v / danger /
buffer_depth are NOT sent — no ultrasonic, battery is percent, and there
is no buffer. Mac-side consumers of buffer_depth (v3 EXECUTING gate) are
rewritten in Phase 3 to gate on yaw/frame predicates instead.
"""

import json
import signal
import sys
import time

import zmq

import config
from xgolib import XGO

MOVE_ACTIONS = {"forward", "backward", "turn_left", "turn_right",
                "strafe_left", "strafe_right"}


class MotorController:
    def __init__(self):
        print(f"[Motor] V2 config V2_FORWARD_STEP_MAX={config.V2_FORWARD_STEP_MAX} "
              f"V2_TURN_RATE_DPS={config.V2_TURN_RATE_DPS} "
              f"V2_LOOP_HZ={config.V2_LOOP_HZ} "
              f"V2_CMD_WATCHDOG_TICKS={config.V2_CMD_WATCHDOG_TICKS}")

        self.dog = XGO(port=config.V2_MOTION_PORT)
        fw = self.dog.read_firmware()
        print(f"[Motor] firmware={fw} battery={self.dog.read_battery()}%")
        self.fw = fw
        # Self-stabilization owns posture when on and rejects attitude();
        # FOLLOW wants camera-pitch trim while walking (smoke Q7), so off.
        self.dog.imu(0)
        self.dog.pace("normal")

        self.ctx = zmq.Context()
        self.cmd_sock = self.ctx.socket(zmq.SUB)
        self.cmd_sock.setsockopt(zmq.LINGER, 0)
        self.cmd_sock.connect(f"tcp://{config.PC_IP}:{config.CMD_PORT}")
        self.cmd_sock.subscribe(b"")
        self.telem_sock = self.ctx.socket(zmq.PUB)
        self.telem_sock.setsockopt(zmq.LINGER, 0)
        self.telem_sock.bind(f"tcp://*:{config.REMOTE_TELEM_PORT}")
        print(f"[Motor] SUB tcp://{config.PC_IP}:{config.CMD_PORT}  "
              f"PUB tcp://*:{config.REMOTE_TELEM_PORT}")

        self.imu_ready = False
        self.current_action = "stop"
        self.current_step = 0
        self.current_pitch_trim = 0.0
        self.ticks_since_cmd = 0
        self.telem_seq = 0
        self.last_yaw = 0.0
        self.last_roll = 0.0
        self.last_pitch = 0.0
        self.battery_pct = -1
        self._refusal_logged = False
        self._watchdog_logged = False

    # ── dispatch ──────────────────────────────────────────────────────

    def dispatch(self, msg):
        action = msg.get("action", "stop")
        speed = max(0, min(100, msg.get("speed", 80)))

        if action in MOVE_ACTIONS and not self.imu_ready:
            # Boot gyro-bias calibration is in progress (yaw register still
            # 0.0). Motion now would bake a bias error into every future
            # yaw read this power cycle. Refuse until the latch.
            if not self._refusal_logged:
                print("[Motor] REFUSING motion: IMU boot calibration not "
                      "finished (yaw register still 0.0). Keep the dog still.")
                self._refusal_logged = True
            action = "stop"

        step = 0
        if action == "forward" or action == "backward":
            step = round(speed / 100.0 * config.V2_FORWARD_STEP_MAX)
        elif action in ("turn_left", "turn_right"):
            step = config.V2_TURN_RATE_DPS
        elif action in ("strafe_left", "strafe_right"):
            step = config.V2_STRAFE_STEP
        elif msg.get("thinking"):
            action = "stop"

        # Setpoints persist on the MCU; re-sending an identical one is just
        # serial noise (hygiene skip — NOT buffer protection, there is none).
        if (action, step) != (self.current_action, self.current_step):
            if action == "stop":
                self.dog.stop()
            elif action == "forward":
                self.dog.forward(step)
            elif action == "backward":
                self.dog.back(step)
            elif action == "turn_left":
                self.dog.turnleft(step)
            elif action == "turn_right":
                self.dog.turnright(step)
            elif action == "strafe_left":
                self.dog.left(step)
            elif action == "strafe_right":
                self.dog.right(step)
            else:
                print(f"[Motor] unknown action {action!r} → stop")
                self.dog.stop()
                action, step = "stop", 0
            self.current_action, self.current_step = action, step

        # Camera-pitch trim: composes with gait (smoke Q7: commanded 8°,
        # read back 7.3° mid-walk, gait smooth). Only touch on real change.
        pitch = msg.get("head_pitch")
        if isinstance(pitch, (int, float)) and self.imu_ready:
            lim = config.V2_ATTITUDE_PITCH_LIMIT
            target = max(-lim, min(lim, float(pitch)))
            if abs(target - self.current_pitch_trim) >= 0.5:
                self.dog.attitude("p", target)
                self.current_pitch_trim = target

    # ── main loop ─────────────────────────────────────────────────────

    def run(self):
        period = 1.0 / config.V2_LOOP_HZ
        tick = 0
        print("[Motor] running (waiting for IMU boot calibration to finish"
              " — yaw register nonzero)")
        while True:
            t0 = time.perf_counter()
            tick += 1

            # Drain to the newest command; ZMQ CONFLATE isn't set on this
            # socket, so old queued commands are skipped explicitly.
            msg = None
            while True:
                try:
                    raw = self.cmd_sock.recv(zmq.NOBLOCK)
                except zmq.Again:
                    break
                try:
                    msg = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    msg = None
            if msg is not None:
                self.ticks_since_cmd = 0
                self._watchdog_logged = False
                self.dispatch(msg)
            else:
                self.ticks_since_cmd += 1
                if (self.ticks_since_cmd >= config.V2_CMD_WATCHDOG_TICKS
                        and self.current_action != "stop"):
                    if not self._watchdog_logged:
                        print(f"[Motor] watchdog: no command for "
                              f"{self.ticks_since_cmd} ticks → stop")
                        self._watchdog_logged = True
                    self.dog.stop()
                    self.current_action, self.current_step = "stop", 0

            yaw = self.dog.read_yaw()
            if isinstance(yaw, (int, float)):
                self.last_yaw = float(yaw)
                if not self.imu_ready and yaw != 0.0:
                    # Latched for the rest of the process lifetime. A later
                    # true 0.0 crossing can't unlatch it.
                    self.imu_ready = True
                    print(f"[Motor] IMU ready (first nonzero yaw {yaw}) — "
                          "motion commands accepted")

            if tick % 25 == 0:
                self.last_roll = self.dog.read_roll()
                self.last_pitch = self.dog.read_pitch()
            if tick % config.V2_BATTERY_EVERY_TICKS == 0 or self.battery_pct < 0:
                self.battery_pct = self.dog.read_battery()

            if tick % config.V2_TELEM_EVERY_TICKS == 0:
                self.telem_seq += 1
                self.telem_sock.send_string(json.dumps({
                    "action": self.current_action,
                    "yaw": round(self.last_yaw, 2),
                    "roll": round(float(self.last_roll), 2),
                    "pitch": round(float(self.last_pitch), 2),
                    "battery_pct": self.battery_pct,
                    "imu_ready": self.imu_ready,
                    "seq": self.telem_seq,
                    "fw": self.fw,
                }))

            elapsed = time.perf_counter() - t0
            if elapsed < period:
                time.sleep(period - elapsed)

    def shutdown(self):
        try:
            self.dog.stop()
            self.dog.attitude("p", 0)
        except Exception:  # noqa: BLE001 — best-effort on the way down
            pass
        try:
            self.cmd_sock.close(linger=0)
            self.telem_sock.close(linger=0)
            self.ctx.term()
        except Exception:  # noqa: BLE001
            pass


def main():
    mc = MotorController()

    def _sigint(_sig, _frm):
        print("\n[Motor] SIGINT — stopping dog")
        mc.shutdown()
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)
    try:
        mc.run()
    finally:
        mc.shutdown()


if __name__ == "__main__":
    main()
