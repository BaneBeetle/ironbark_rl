# IronBark — CLAUDE.md (PC home base)

You are helping Brian (M.S. CS @ Columbia, ML focus) on **IronBark**, his autonomous robot dog on a Yahboom DOGZILLA S2 (Raspberry Pi 5 onboard). This session runs on Brian's **always-on PC** (Ryzen 7 9800X3D, RTX 3090 24 GB), which is now the home base for development, training, and remote sessions.

**The big goal:** add real, measurable ML to IronBark (RL or imitation learning) that Brian deeply understands and can defend in an interview. You write the code. Brian owns the design decisions and the analysis (protocol below, Brian's call 2026-11-06).

---

## Hard rules (non-negotiable)

- **Never run anything that moves the dog.** No motion SDK calls, no motor_controller launches, no `run.sh`, never open `/dev/ttyAMA0`. Brian runs every session that actuates motors. You may write motion/measurement scripts, but you hand them to Brian to run.
- Deploying files to the Pi and bench-testing the camera over SSH is fine.
- **Measure, don't assume.** Mark every value you couldn't measure with a `# MEASURE:` comment saying how it will be measured. Never invent hardware numbers.
- **Name thresholds by semantic role**, not magic numbers.
- **Single-variable commits.** One work item = at least one commit; never bundle two work items. Match the existing message style.
- **No wall-clock logic in Pi-side code.** Frame counts and state predicates only. PC-side timers are fine.
- **Do not change the Pi's `~/ironbark/motor_controller.py` semantics** (it's measurement-derived; read-only reference copy: `docs/v2-archive/reference/motor_controller.py`). Additive telemetry fields are fine if needed. Say so in your report.
- Do not re-add identity (face/ReID), with one exception (Brian, 2026-11-08): owner verify by VLM with multi-reference photos, as in `docs/roadmap.md` Phase 1. Do not build EXPLORE (Phase 3) unless Brian asks.
- In `brian/`, design decisions are Brian's (thresholds, frames, weights, trade-offs): ask, don't decide. Never rewrite code Brian wrote himself (e.g. `feet_air_time`, his `metrics.py` functions) without asking (see Division of labor).
- Keep replies short. Brian dislikes long explanations. Prefer one-line terminal commands.

---

## Ground truth (read before coding)

The V2 material lives in `docs/v2-archive/` (reference only; start with its `README.md`).
1. `docs/v2-archive/MEASURED_FACTS.md` — every V2 measured constant and protocol fact, sourced, plus what was never measured. `docs/v2-archive/migration-notes.md` — the dated log behind it. Treat as ground truth.
2. `docs/v2-archive/measurements/` — the V2 data behind those facts. V3's own probe logs are in `docs/measurements/`.
3. `docs/v2-archive/reference/motor_controller.py` (+ `reference/config.py` for its constants) — header + code; a read-only copy of the controller on the Pi. The PC-side code talks to it.
4. `docs/v2-archive/phase1-briefing.md` — especially §5 (target-lock design).
5. `docs/v2-archive/handoffs/coding-handoff-follow-bringup.md` — the previous FOLLOW bring-up handoff (W1–W5); its report is `docs/v2-archive/bringup-report.md`. It's old: **audit before trusting it.**
6. `docs/v2-archive/LESSONS.md` and `findings/` — what made V2 finicky and what V3 should do differently.

Known facts from the previous handoff (verify against the repo; **if the repo disagrees, the repo wins**, so flag it):
- Wire protocol: commands as JSON on PUB `PC_IP:5556` (Pi subscribes); telemetry JSON PUB'd by the Pi on `:5558` with fields `action, yaw, roll, pitch, battery_pct, imu_ready, seq, fw`.
- Camera stream: ZMQ **PUSH (Pi, connects) → PULL (PC, binds)** on 50505; message = `<qI` header (int64 capture µs, uint32 JPEG length) + JPEG. Lidar scans: **PUSH → PULL** on 50507 (V1 schema). Not PUB: a PUB sender never reaches a PULL receiver (`docs/v2-archive/MEASURED_FACTS.md`).
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

- [ ] Compare the repo to `docs/v2-archive/handoffs/coding-handoff-follow-bringup.md` W1–W5. Write `docs/status.md` with each item marked **done / partial / not started**, plus evidence (file, commit).
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

### 🧠 Brian owns the design: `ironbark_rl/brian/`
Brian is here to learn the concepts, not the syntax (his call, 2026-11-06). Claude writes the code in `brian/` too, but every design decision in it is Brian's: what a term measures, frames, units, thresholds, weights, trade-offs. Ask him; record his answer and his reasoning in `docs/progress.md`. Each file's header records who wrote what. Code Brian wrote himself stays his (`feet_air_time`; `tilt_deg`, `is_fallen`, `fall_rate`, `steps_before_fall` in `metrics.py`): don't rewrite it without asking.

History: until 2026-11-06 Brian implemented `brian/` himself, with Claude limited to stubs and tests. Exceptions before the switch: Claude wrote the last three `metrics.py` functions (2026-10-30) and ten of the eleven reward terms in `rewards.py` (2026-11-06), both on Brian's request.

Path A: `obs.py`, `actions.py`, `rewards.py`, `actuator_model.py` (system ID fit), `randomization.py` (ranges justified by data), `metrics.py`, plus side quest `ppo_minimal.py` (GAE + clipped loss on CartPole).
Path B: `obs.py` (what the policy sees), `actions.py` (discrete motion vocab), `rewards.py` or `bc_loss.py`, `metrics.py` (success rate, target-loss rate, time-to-reacquire, command smoothness vs rule-based).

### 🛠️ You handle (grunt work)
Env setup, MJCF/model conversion, sim env boilerplate that imports Brian's functions, training scripts, configs, checkpointing, W&B logging, sweeps, eval harness plumbing, plots, data loggers, ONNX export, Pi runtime loop, safety layer (e-stop, joint clamps, tilt cutoff, watchdog), ZMQ/ROS2 glue, tests, CI, README.

### Learning protocol (Brian, 2026-11-06: concepts, not syntax)
For each 🧠 piece:
1. **Before implementing**, show the function signature with real example input and output tensors: actual numbers, with shapes, e.g. `command_xy (2, 2) [[0.30, 0.00], [0.30, 0.00]] -> (2,) [0.9892, 0.5066]`. Brian should always know what the arguments look like.
2. **Ask the design questions** (thresholds, frames, units, weights, trade-offs) and wait for his answers. Those are the skills he wants to build. Give a recommendation with a reason, but the call is his.
3. **Write the code** with a comment on every line saying WHY (e.g. `# square: symmetric, and punishes big tilts more`), plus the tensor shape on every line (e.g. `# (num_envs, 3)`). Write tests with known cases.
4. **When done, summarize each function in plain English**: what it rewards or penalizes, and why it's built that way.
5. **After training**, walk Brian through the per-term TensorBoard curves (`Episode_Metrics/reward/<term>`) and the scoreboard, and ask what he thinks is driving the behavior *before* giving your own read.
6. **After each milestone**, quiz him with 2–3 interview-style "why" questions and log his answers verbatim in `docs/notes/`.

---

## Phase 2A — RL locomotion (8 weeks, if Path A)

Sim stack: mjlab (MuJoCo Warp) + RSL-RL PPO on the 3090, starting from [LuwuDynamics/luwu_mjlab](https://github.com/LuwuDynamics/luwu_mjlab)'s XGO Mini2S velocity env (chosen 2026-10-30 over MuJoCo Playground/MJX + Brax, because the vendor's MJCF exists for the XGO Mini family). Use its MJCF, env plumbing and trainer as infrastructure; Brian's obs/actions/rewards replace its own, and its reward is the baseline to beat. Check current docs/APIs before coding.
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

Every training run gets an entry in `docs/experiments/` (`python tools/new_experiment.py "title" --parent EXP-NNN`). Follow the rules in `docs/experiments/README.md`: hypothesis before the run, one change per experiment, compare only on the frozen `metrics.py` scoreboard. Hypothesis / observations / why are Brian's; Claude fills Setup and Results.
