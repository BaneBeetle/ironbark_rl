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

## 2026-10-30 (evening): scoreboard v1, reward v1 design, eval + video tooling

- **Scoreboard v1 frozen** (`ironbark_rl/brian/metrics.py`, 29 tests). Brian wrote `tilt_deg`, `is_fallen`, `fall_rate`, `steps_before_fall` and chose `FALL_TILT_DEG`. Claude wrote the last three functions to Brian's decisions (an exception recorded in CLAUDE.md and the file header).
- **EXP-000 scored on v1** (`tools/eval.py`: 8 commands × 32 dogs × 10 s). Mean of seeds 42/43: 0 falls, planar 0.036 m/s, yaw 0.097 rad/s, joint-target rate 2.2 rad/s, CoT 1.38. **Seed noise floor ~3–5% (tracking), ~7–9% (smoothness, CoT).** Sim walking tilt p99 ≈ 5°, far below `FALL_TILT_DEG`.
- **Reward v1 designed by Brian** (EXP-001: tracking bonus ≥ 0 as the largest term, stability and smoothness penalties, falls end the episode). Hypothesis recorded before the run. `brian/rewards.py` stubbed with 15 spec tests that encode his own rules (positive steps, no standing-still loophole, priority order). Glue task `IronBark-S2-Walk-Flat-BrianReward` wired and smoke-tested.
- **Tools:** `tools/eval.py` (scoreboard → experiment file), `tools/record.py` (labeled side-on clips and progression videos to `~/dev/ironbark_runs/videos`), `tools/progress.py` (scoreboard over training iterations → `docs/figures/`), `tools/tilt_test.py`.

**Interview talking point:** before comparing rewards, I froze a scoreboard in physical units and measured the seed-to-seed noise floor (~3–9%), so "my reward beat the baseline" only counts if the gap is bigger than what a different random seed alone produces.

### Next session
1. Brian implements `ironbark_rl/brian/rewards.py` (3 functions + `WEIGHTS`) until `python -m pytest tests/brian -q -k reward` passes.
2. Train EXP-001 (command in its experiment file, ~55 min), then `tools/eval.py ... --exp EXP-001`, `tools/record.py`, `tools/progress.py --chart` against EXP-000.
3. Learning-protocol step 6 for `metrics.py`: 2–3 interview questions, answers in `docs/notes/`.
4. Still open: trained-policy tilt sweep to confirm `FALL_TILT_DEG`; Phase 1 joint-control measurement script (Claude writes, Brian runs on the dog); real-dog mass and walking tilt (`# MEASURE:`).

**Interview talking point:** I didn't build the robot model from scratch. I checked that the vendor-family model's kinematics matched ours to within 1 mm, kept its physics, and changed only what differed (arm, payload, mass), with each change tested and each unknown marked for measurement.

## 2026-11-06: EXP-000 progress chart, reward plan change, off OneDrive

- **EXP-000 progress chart** ([figure](figures/EXP-000--Luwu-reward_progress.png), seed 42): speed-tracking error 0.152 → 0.041 m/s by iteration 200, ~0.036 after. 0 falls at every checkpoint, iteration 0 included (with terminations off, an untrained dog doesn't tip past 46°). The sweep takes 241 s on a free GPU; the earlier 45-min attempt shared the GPU with seed-43 training. Recording is ~1 ms of a ~29 ms env step, so `evaluation.py` is unchanged. **Run eval/progress/record only while nothing is training.**
- **Plan change (Brian):** reward v1's three terms give way to Brian's own legged_gym-style terms (Rudin et al. 2021), one function each returning (num_envs,): `track_lin_vel_xy`, `track_ang_vel_z` (exp kernels), `lin_vel_z`, `ang_vel_xy`, `orientation`, `base_height`, `torques`, `joint_acc`, `action_rate`, `feet_air_time`, `undesired_contacts`. None implemented yet. Brian writes every term; never show or summarize Luwu's reward code; stubs and reviews annotate tensor shapes on every line.
- Claude's part: (1) per term, which mjlab tensors and shapes, no math; (2) stubs + known-case tests in `tests/brian/test_rewards.py`; (3) weights in a config file Brian edits; (4) task `IronBark-S2-Walk-Flat-Brian`, baseline except the reward; (5) compare on `metrics.py` only, never reward values. Note in `docs/roadmap.md` (don't build): RL policy as the fast "cerebellum", a VLM as the slow "brain" sending (vx, vy, yaw_rate).
- Step 1 done for `track_ang_vel_z` and `orientation`, checked in the S2 training env: `env.command_manager.get_command("twist")` (num_envs, 3) = (vx, vy, wz), body frame, wz ∈ [−0.8, 0.8] rad/s, resampled every 3–8 s, zeroed when its norm < 0.1; yaw rate `robot.data.root_link_ang_vel_b[:, 2]` (body; `_w` is world); `robot.data.projected_gravity_b` (num_envs, 3), level (0, 0, −1), standing S2 ≈ (0.025, −0.007, −0.9997).
- Off OneDrive: Claude memory merged into the dev-folder project; code docstrings no longer mention OneDrive. Brian deletes the OneDrive copy himself.
- **Decisions (Brian):** the new term set **replaces reward v1**. EXP-001 is marked superseded, never trained. The v1 stubs, 15 spec tests and `-BrianReward` glue go when the new stubs land. Two v1 rules carry over as scenario tests: a normal walking step pays > 0, and standing still loses when ordered to walk. **Task name: `IronBark-S2-Walk-Flat-Brian`.**
- **Step 1, batch 1 (base state)**, checked in the S2 training env (16 envs, 2 s at zero action, default pose). All tensors are on `robot = env.scene["robot"]`, body frame unless marked `_w`:
  - `track_lin_vel_xy`: `command[:, :2]` (num_envs, 2) vs `robot.data.root_link_lin_vel_b[:, :2]` (num_envs, 2), m/s. Command ranges vx ∈ [−0.5, 0.6] and vy ∈ [−0.3, 0.3]. `heading_command` is off, so wz is commanded directly.
  - `lin_vel_z`: `root_link_lin_vel_b[:, 2]` (num_envs,), m/s. Standing: |.| ≤ 0.001.
  - `ang_vel_xy`: `root_link_ang_vel_b[:, :2]` (num_envs, 2), roll and pitch rate, rad/s. Standing: |.| ≤ 0.007.
  - `base_height`: `root_link_pos_w[:, 2]` (num_envs,), m. The terrain is a plane at z = 0 and every env origin has z = 0, so world z is the height above ground. Standing at the default pose: 0.1228 m (spawn height 0.20). The target height is Brian's call.
  - Gotcha: the root body `base` is a massless frame (the trunk mass sits in its child `base_model`), so `root_com_*` is meaningless on this model (`root_com_pos_w` z reads 0.273). Use `root_link_*`, which the scoreboard (`evaluation.py`) also reads.
- **Decision (Brian): body frame (`root_link_*_b`) for `lin_vel_z` and `ang_vel_xy`.** Why: on a slope the body z axis follows the slope normal. World-frame z velocity would punish ordinary downhill walking (it's negative the whole way down), but body-frame z velocity stays ≈ 0 unless the dog is bouncing. On flat ground the two are nearly identical, so body frame costs nothing now and carries over to slopes and rough terrain. It's also the legged_gym convention.
- **Base-height target:** Brian measures the real S2 standing with a ruler. Until then it's `BASE_HEIGHT_TARGET_M = None` in `ironbark_rl/brian/reward_config.py`, whose `# MEASURE:` comment says how: floor → thigh-pivot centre, mean of 4 legs, + 0.021 m (sim offset from the thigh pivot to the `base` origin).
- **Fall terminations as the task stands (train and play alike):**
  - `fell_over` (mjlab `bad_orientation`): tilt > 1.2217 rad = **70°**, using the same tilt as `metrics.tilt_deg` (angle between body z and gravity).
  - `illegal_contact`: any non-foot geom (everything except the 4 calf collision geoms) touching the ground with > 10 N in any of the last 4 physics substeps.
  - Episodes time out at 20 s.
  - Open for Brian: the scoreboard counts a fall at 46° (`FALL_TILT_DEG`) but training only ends at 70°. And 10 N is more than the S2's whole weight (9.54 N), so a trunk resting on the floor may never trip `illegal_contact`; only impacts would.
- **Step 1, batch 2 (joint space)**, same probe (16 envs, 2 s standing at the default pose). 12 joints, ordered fl, fr, br, bl × (hip, thigh, calf). Actuator and action order match.
  - `torques`: `robot.data.actuator_force` (num_envs, 12), N·m. These are MuJoCo position servos, gear 1, clamped at ±0.43 N·m (`forcerange`, a Mini2S placeholder, `# MEASURE:` in Phase 1). mjlab's `joint_torques` raises NotImplementedError. Standing: max 0.125, mean 0.045 N·m.
  - `joint_acc`: `robot.data.joint_acc` (num_envs, 12), rad/s² (MuJoCo `qacc`). Standing: max 1.4, mean 0.05 rad/s², so it isn't 0 even at rest. mjlab doesn't keep the previous step's `joint_vel` (num_envs, 12), so a per-policy-step difference would need glue state.
  - `action_rate`: `env.action_manager.action` and `.prev_action`, both (num_envs, 12), the raw policy output (unitless). Joint target = `default_joint_pos` + 0.25 × action, no clip. `prev_prev_action` also exists. On reset mjlab zeroes all three, so an episode's first step compares against 0.
  - Timing: the reward runs once per 20 ms policy step, after 5 physics substeps of 4 ms. `actuator_force` and `joint_acc` are the last substep's values, not averages.

### Next session (open it on `C:\Users\lolly\dev\ironbark_rl`)
1. Brian reviews batch 2 and the two termination questions (46° vs 70°, the 10 N contact threshold). Then step 1, batch 3 (contacts: `feet_air_time`, `undesired_contacts`), waiting for Brian.
2. Steps 2–5: stubs + known-case tests (replacing v1's), weights in `reward_config.py`, register `IronBark-S2-Walk-Flat-Brian` (drop `-BrianReward`), a new experiment entry (Brian's hypothesis first), eval vs EXP-000 on `metrics.py`. Plus the `docs/roadmap.md` cerebellum/brain note.
3. Then items 3–4 of the 2026-10-30 list.

### Open: Brian
- [ ] Ruler: real S2 standing thigh-pivot height → `BASE_HEIGHT_TARGET_M` (how: `ironbark_rl/brian/reward_config.py`)
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
