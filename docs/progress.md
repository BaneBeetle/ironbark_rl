# Progress

## 2026-10-30: Phase 0 (move to PC), in progress

**Decision:** Path A, locomotion RL with MuJoCo Playground/MJX + Brax PPO. Brian chose it before the Phase 1 gate ran. Phase 1 now decides *how* the policy deploys on the real dog (joint-level commands vs. a lower-rate action space), not A vs. B.

**PC environment:** Windows 11 + WSL2 Ubuntu-24.04 (Python 3.12, RTX 3090 visible, driver 610.88). Plan: run everything in WSL2 with mirrored networking, because JAX has no GPU builds for native Windows.

### Done
- Environment detected (above). PC LAN IP `192.168.68.55` (DHCP, no reservation yet).
- V1 reference repo cloned read-only to WSL `~/ironbark-v1` (push URL disabled).
- Pi located: `raspberrypi.local` → `192.168.68.56` (fixed MAC). ED25519 host key verified: `SHA256:wqOZO9hVbi+SvpNwRq5HVHM1M877bQ1TpzFUTJUguZ8`.
- `ssh pi` works from WSL (key `ironbark-pc`, alias points at `192.168.68.56` until mirrored mode makes `.local` resolve). Pi `authorized_keys` holds only `ironbark-mac` and `ironbark-pc`.
- Pi state: Debian 13, Python 3.13.5. `~/ironbark` is a deployed copy from 2026-08-29 (Pi-side files + smoke logs), not a git checkout.
- Decision: `ironbark_rl` is a separate repo. The V2 repo (DogZilla FOLLOW work on the Mac) stays separate and serves as a read-only reference.
- Phase 1, step 1 started: xgolib joint-control API read from source → [phase1-xgolib-api.md](phase1-xgolib-api.md). Firmware `M-4.0.1-Y` (XGO Mini family).
- Found Luwu's own RL env, [luwu_mjlab](https://github.com/LuwuDynamics/luwu_mjlab) (mjlab + RSL-RL, Mini2S MJCF, 50 Hz joint targets).
- Decision: **sim stack = mjlab + RSL-RL, starting from luwu_mjlab** (replaces the brief's MuJoCo Playground/MJX + Brax). Its MJCF and trainer are used as infrastructure; Brian writes his own obs/actions/rewards, and luwu's reward is the baseline to beat.

- **luwu_mjlab runs natively on Windows** (conda env `luwu_mjlab` in Anaconda: Python 3.11, torch 2.12+cu130, warp 1.12.1, mujoco 3.6.0, mjlab 1.2.0; repo at `~/dev/luwu_mjlab`). The conda CUDA toolkit wasn't needed.
  - Luwu's Mini2S walk policy (HF `robomotic/XGO`, `model_1499.pt`; loads under `weights_only=True`), headless over 256 envs × 10 s sim: **0 falls, velocity-tracking error 0.044 m/s** (commanded |vx| 0.203, achieved 0.202 m/s).
  - Training throughput, `Mini2S-Walk-Flat` with 4096 envs × 24 steps: **~2.0–2.3 s per PPO iteration (~45k env-steps/s)**. A full 1500-iteration run (Luwu's setting) is ≈ 55 min on the 3090. Not compared against Linux.

- Decision: **native Windows** for everything (training and Pi-facing tools). WSL2 isn't needed; skip mirrored mode and the Hyper-V firewall rule.

## 2026-10-30: Phase 2A step 1 started: S2 sim model

- `ironbark_rl` package (editable-installed into the `luwu_mjlab` env). [ironbark_rl/assets/s2.py](../ironbark_rl/assets/s2.py) builds the S2 from Luwu's Mini2S MJCF at load time: arm removed, lidar + camera added as mass bodies placed from Yahboom's URDF, trunk rescaled to the 0.972 kg working mass. Trunk 0.537 kg (Mini2S 0.284 kg). Sources and trust levels: [s2-model-sources.md](s2-model-sources.md). `pytest` passes (6 model checks).
- Task `IronBark-S2-Walk-Flat` = Luwu's Mini2S walk task unchanged, S2 swapped in. Policy I/O: 47 obs → 12 joint targets (Mini2S: 56 → 15).
- Launcher: `python tools/run.py {train|play} IronBark-S2-Walk-Flat ...`, which logs to `~/dev/ironbark_runs` (outside OneDrive). A 2-iteration smoke train runs end to end (checkpoints + ONNX export).
- Zero-action standing test (`tools/stand_test.py`, 16 envs × 5 s), Mini2S → S2: body height 0.124 → 0.122 m, max joint sag 0.113 → 0.136 rad, peak servo torque 0.105 → 0.139 N·m (limit 0.43), tilt 1.5° → 1.9°, **0 falls**. The S2 stands on the Mini2S servo model.
- Still Mini2S placeholders, all `# MEASURE:`: servo kp/torque/delay (Phase 1), stance and joint zero offsets, total mass, payload masses.
- `# MEASURE:` real-dog roll/pitch during normal walking and turning. The V2 smoke logs only recorded yaw (plus one attitude test: pitch −0.3° → 7.3°), so there's no real "normal tilt" baseline for `FALL_TILT_DEG` yet. Record telemetry roll/pitch in the next supervised walking session.
- `tools/tilt_test.py`: tilt-recovery sweep (one sim dog per starting angle, passive or trained policy) for picking `FALL_TILT_DEG`. Uses Brian's `tilt_deg`.
- **EXP-000 baseline trained** (Luwu reward, S2, 1500 iterations, 1 h 12 min). Interim check: **0 falls, 0.052 m/s planar speed error** (Luwu's own Mini2S policy: 0, 0.044). The S2 model can learn to walk. Scoreboard numbers wait on `metrics.py` v1. See [EXP-000](experiments/EXP-000-luwu-reward-on-s2-baseline.md).
- Brian's `metrics.py` in progress: `tilt_deg`, `is_fallen`, `FALL_TILT_DEG = 46` (provisional: passive sim recovery ≤30° pitch / 25–30° roll; rigid-leg tipping 36.8° / 30.1°; +10° margin).

**Interview talking point:** I didn't build the robot model from scratch. I checked that the vendor-family model's kinematics matched ours to within 1 mm, kept its physics, and changed only what differed (arm, payload, mass), with each change tested and each unknown marked for measurement.

### Open: Brian
- [ ] V2 repo onto the PC as a read-only reference (only on the Mac today)
- [ ] Windows Defender inbound rule for TCP 5556/5558/50505/50507 from `192.168.68.0/22` (only needed once the Pi connects back to the PC)
- [ ] Deco DHCP reservations: Pi `.56`, PC `.55`
- [ ] Mac's Claude memory folder copied to the PC
- [ ] Remote access to the PC (Tailscale)

### Open: Claude (after the above)
- [ ] Verify Pi → PC TCP on the four ZMQ ports
- [ ] `.env` `PC_IP`; perception device auto-select (CUDA instead of `mps`)

### Notes
- Old `known_hosts` entries for `192.168.68.56` (on the Mac and the PC) belong to other devices that held that lease earlier, not the Pi. Connect by `raspberrypi.local` and check the fingerprint above.
- The Pi offers password auth as well as keys (the earlier handoff said key-only).

**Interview talking point:** the OS follows from the simulator, not the GPU. MJX runs thousands of environments in parallel on one GPU, which is what makes on-policy PPO for locomotion practical on a single 3090, and JAX's GPU support is Linux-only.
