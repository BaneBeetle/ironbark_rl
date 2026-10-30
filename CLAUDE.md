# IronBark — CLAUDE.md (PC home base)

You are helping Brian (M.S. CS @ Columbia, ML focus) on **IronBark**, his autonomous robot dog on a Yahboom DOGZILLA S2 (Raspberry Pi 5 onboard). This session runs on Brian's **always-on PC** (Ryzen 7 9800X3D, RTX 3090 24 GB), which is now the home base for development, training, and remote sessions.

**The big goal:** add real, measurable ML to IronBark (RL or imitation learning) that Brian deeply understands and can defend in an interview. You handle the grunt work. Brian implements the core ML pieces himself.

---

## Hard rules (non-negotiable)

- **Never run anything that moves the dog.** No motion SDK calls, no motor_controller launches, no `run.sh`, never open `/dev/ttyAMA0`. Brian runs every session that actuates motors. You may write motion/measurement scripts, but you hand them to Brian to run.
- Deploying files to the Pi and bench-testing the camera over SSH is fine.
- **Measure, don't assume.** Mark every value you couldn't measure with a `# MEASURE:` comment saying how it will be measured. Never invent hardware numbers.
- **Name thresholds by semantic role**, not magic numbers.
- **Single-variable commits.** One work item = at least one commit; never bundle two work items. Match the existing message style.
- **No wall-clock logic in Pi-side code.** Frame counts and state predicates only. PC-side timers are fine.
- **Do not change `pi/motor_controller.py` semantics** (it's measurement-derived). Additive telemetry fields are fine if needed. Say so in your report.
- Do not re-add identity (face/ReID). Do not build EXPLORE (Phase 3) unless Brian asks.
- Never write the implementation of anything in a `brian/` directory (see Division of labor).
- Keep replies short. Brian dislikes long explanations. Prefer one-line terminal commands.

---

## Ground truth (read before coding)

1. `docs/migration-notes.md` — every measured fact. Treat as ground truth.
2. `docs/measurements/*.jsonl` — the data behind those facts.
3. `pi/motor_controller.py` — header + code. The PC-side code talks to this.
4. `docs/phase1-briefing.md` — especially §5 (target-lock design).
5. `docs/handoffs/follow-bringup.md` — the previous FOLLOW bring-up handoff (W1–W5). It's old: **audit before trusting it.**

Known facts from the previous handoff (verify against the repo; **if the repo disagrees, the repo wins**, so flag it):
- Wire protocol: commands as JSON on PUB `PC_IP:5556` (Pi subscribes); telemetry JSON PUB'd by the Pi on `:5558` with fields `action, yaw, roll, pitch, battery_pct, imu_ready, seq, fw`.
- Camera stream: ZMQ PUB on 50505. Lidar scans: ZMQ PUB on 50507 (V1 schema).
- motor_controller motion vocabulary: `stop | forward | backward | turn_left | turn_right | strafe_left | strafe_right` (+ `head_pitch`). `turn_*` runs at a fixed `V2_TURN_RATE_DPS`.
- Camera: USB 2MP wide-angle at `/dev/video0` (not the OAK-D).
- MS200 lidar UART port: unknown until Brian traces the cable (`# MEASURE:`).
- Pi: `~/ironbark/` with `.venv` (xgolib, pyzmq, pyserial). Non-login shells miss `/usr/sbin` and `~/.local/bin`.

---

## Phase 0 — Move to the PC (do this first)

Some steps are Brian-only (keys, firewall, router). For those, give him exact one-line commands and wait.
- [ ] Detect the environment: native Linux, Windows, or WSL2. **If WSL2:** the Pi can't reach WSL ports under default NAT. Brian needs mirrored networking mode (or port forwarding). Tell him exactly how.
- [ ] Repo cloned on the PC; V1 reference repo cloned too (read-only, for wire formats).
- [ ] `ssh pi` works from the PC (Brian copies or creates the key + `~/.ssh/config` entry).
- [ ] `.env` updated with the PC's LAN IP; firewall allows the ZMQ ports; verify Pi → PC TCP 5556/5558/50505/50507.
- [ ] If project memory (`MEMORY.md`) lived in `~/.claude` on the Mac, Brian copies it over; otherwise skip.
- [ ] Perception uses CUDA on the 3090 (replace any hardcoded `mps` with device auto-select).
- [ ] Remote sessions: confirm Brian can reach this PC remotely (e.g. Tailscale + SSH).

## Phase 0.5 — Audit + finish FOLLOW bring-up

- [ ] Compare the repo to `docs/handoffs/follow-bringup.md` W1–W5. Write `docs/status.md` with each item marked **done / partial / not started**, plus evidence (file, commit).
- [ ] Finish the remaining items per that spec (adapting anything Mac-specific: the webcam dev mode uses the PC's webcam if present; W5's deadman can use real key-held detection on this OS).
- [ ] Write `docs/bringup-report.md` (what shipped, measured numbers, open `# MEASURE:` items, exact commands for Brian's next motion sessions: teleop first, then supervised FOLLOW).

## Phase 1 — Joint-control feasibility gate (decides the ML path)

RL locomotion needs per-joint position control at a usable rate. Today the firmware runs the gait from high-level commands.
- [ ] Find xgolib's per-joint / per-leg APIs (read the library source on the Pi, not memory).
- [ ] Write a measurement script **for Brian to run**: per-joint step + sine commands, logging timestamped angle readback to `docs/measurements/joint_control_*.jsonl`.
- [ ] From Brian's run, report: max sustained command rate, readback rate + latency, servo step response (delay, rise time), and whether gait-level and joint-level control conflict.
- [ ] Decision (Brian makes it, you recommend):
  - **Path A (locomotion RL):** if roughly ≥30–50 Hz joint commands with usable readback.
  - **Path B (learned FOLLOW policy):** otherwise. Learn a policy over the existing motion vocabulary (imitation from the rule-based follower and/or RL in sim), benchmarked against the rule-based follower.

---

## Division of labor

### 🧠 Brian implements: `ironbark_rl/brian/`
You may create stubs (signature, docstring with shapes/units, `raise NotImplementedError`, TODOs) and tests in `tests/brian/`. **Never the implementation.**

Path A: `obs.py`, `actions.py`, `rewards.py`, `actuator_model.py` (system ID fit), `randomization.py` (ranges justified by data), `metrics.py`, plus side quest `ppo_minimal.py` (GAE + clipped loss on CartPole).
Path B: `obs.py` (what the policy sees), `actions.py` (discrete motion vocab), `rewards.py` or `bc_loss.py`, `metrics.py` (success rate, target-loss rate, time-to-reacquire, command smoothness vs rule-based).

### 🛠️ You handle (grunt work)
Env setup, MJCF/model conversion, sim env boilerplate that imports Brian's functions, training scripts, configs, checkpointing, W&B logging, sweeps, eval harness plumbing, plots, data loggers, ONNX export, Pi runtime loop, safety layer (e-stop, joint clamps, tilt cutoff, watchdog), ZMQ/ROS2 glue, tests, CI, README.

### Learning protocol (like Brian's Supabase experience on RATA)
For each 🧠 piece: (1) explain the concept in ≤15 lines with 1–2 references, (2) stub it, (3) write tests, (4) stop and hand off, (5) on review: hints, Socratic questions, and point at *where* the bug is; no rewrites; full solution only if Brian explicitly asks, (6) afterwards, ask 2–3 interview-style questions and log his answers in `docs/notes/`.

---

## Phase 2A — RL locomotion (8 weeks, if Path A)

Sim stack: MuJoCo Playground (MJX/JAX) + Brax PPO on the 3090. Use an existing quadruped joystick env as the template. Check current docs/APIs before coding.
1. **Foundations:** DOGZILLA MJCF, standing test, sanity checks. 🧠 obs + action design. 📖 Rudin et al. 2021.
2. **System ID:** reuse Phase 1 logs + replay in sim. 🧠 actuator model fit. 📖 Hwangbo et al. 2019; Tan et al. 2018.
3. **First policy:** env + train script. 🧠 rewards v1; PPO side quest. 📖 Spinning Up PPO/GAE.
4. **Eval + ablations:** command-grid harness. 🧠 metrics; ≥3 reward ablations explained.
5. **Robustness:** randomization plumbing + pushes. 🧠 randomization ranges from data.
6. **Deploy:** ONNX, Pi runtime, safety, obs-parity test. 🧠 verify parity. Brian runs tethered first steps.
7. **Sim-to-real gap:** same metrics on real logs. 🧠 Brian leads debugging, documents fixes.
8. **Ship:** README, plots, demo shot list. 🧠 Brian writes the write-up + 5-min explanation.

## Phase 2B — Learned FOLLOW policy (if Path B)

1. Logging of (obs, rule-based action) pairs during Brian's supervised FOLLOW sessions + a simple 2D sim of target-following with the motion vocab and measured turn rate.
2. 🧠 BC baseline on logged data; metrics vs rule-based.
3. 🧠 RL fine-tune in sim (rewards), with randomized target motion + occlusion.
4. Deploy behind the deadman; benchmark learned vs rule-based on real runs.
5. Ship the write-up (Brian writes it).

Stretch (either path): learned "walk to object" policy vs the old Claude-API brain on success rate + latency.

---

Track progress in `docs/progress.md` (phase/week, done, key result, one interview talking point). Update it at the end of each session.
