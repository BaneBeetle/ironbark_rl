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

- **Real S2 standing (Brian, tape + photo, hard floor):** body plate bottom ≈ 11 cm, top ≈ 15 cm, centre ≈ 13 cm (±0.7 cm). This isn't directly comparable to the sim's 0.1228 m. The sim `base` origin isn't the plate centre: in the standing pose the trunk mesh spans z 0.079–0.136 m, with `base` 1.3 cm below its top. And that mesh is Mini2S's. The thigh pivot is the landmark both share (leg kinematics match Yahboom's URDF to < 1 mm); Brian measures it next.
- **Decisions (Brian): fall handling → env v2, re-baselined as EXP-002.**
  1. Scoreboard fall line stays `FALL_TILT_DEG = 46` (sim recovery fails past it). The training tilt termination drops 70° → **50°**, so an episode ends just past the point the scoreboard calls a fall, instead of running on through 24° of tilt it can't recover from. Recheck 46° once Brian's policy is trained.
  2. Non-foot contact termination 10 N → **15% of body weight = 1.43 N**, because 10 N exceeded the S2's whole weight (9.54 N), so a resting trunk never tripped it.
  3. Found while checking 2: in Luwu's walk setup **only the 4 calves collide with the ground**, so the contact termination could never fire, `undesired_contacts` would always be 0, and a fallen trunk sank through the floor. Brian's call: **every collision mesh touches the ground** (no self-collision). Random actions, 4096 dogs × 5 s, before → after: contact terminations 0 → 2888, tilt terminations 4271 → 1745, lowest base z −0.018 → +0.060 m. Standing env step 58.3 → 57.7 ms (no speed cost), and no contact-buffer warnings.
  4. These are env changes, so they go into the baseline task `IronBark-S2-Walk-Flat` itself. Luwu's reward is retrained on env v2 as **EXP-002**, and Brian's reward is compared against EXP-002, not EXP-000. The scoreboard runs with terminations off, so 1–2 affect only training, but 3 also changes the physics during evaluation.
- **Decisions (Brian): glue for step 4.** Not built yet; it lands with the `-Brian` task.
  - `joint_acc` across policy steps: (vel_t − vel_{t−1}) / 0.02 s. The glue keeps the previous `joint_vel` (num_envs, 12), as a class-based mjlab reward term. On reset it copies the post-reset `joint_vel`, which is already correct at that point (reset events run before `reward_manager.reset`, and `joint_vel` reads `qvel` directly), so an episode's first step has no fake spike.
  - `action_rate` on joint targets (rad), `default_joint_pos + 0.25 × action` for both `action` and `prev_action`. Why: radians are physical units and stay correct if the action scale changes.
  - Requested (pre-clip) servo torque (num_envs, 12) for a saturation penalty. How MuJoCo computes it, as confirmed in mjlab's code and checked numerically:
    - Servo force = kp·(clamp(ctrl, ±1.57 rad) − q) − kv·q̇, then clamped to ±0.43 N·m, and that clamped value is `actuator_force`. kp = 1.15 in every env; kv = 0, so the servo has no damping term.
    - `ctrl` is the **delayed** target, 1–2 physics steps (4–8 ms) behind the policy's, so the glue reads `sim.data.ctrl`, not `default + 0.25·action`.
    - Joint damping (0.04 N·m·s/rad), armature (0.0025) and frictionloss (0.001) are passive and act outside the servo cap.
    - Check: the clamped request matches `actuator_force` to 7e-8 N·m. Under random actions (σ = 3), 62% of servo-steps saturate.
- **Step 1, batch 3 (contacts)**, on env v2:
  - `feet_air_time`: `feet = env.scene["feet_ground_contact"]` covers the 4 calf collision geoms, in the order fl, fr, br, bl (same as the joints).
    - `feet.data.found` (num_envs, 4): the number of contact points, 0 = in the air (standing reads 2–4, not 1).
    - `feet.data.current_air_time`, `last_air_time`, `current_contact_time`, `last_contact_time`: (num_envs, 4), s.
    - `feet.compute_first_contact(env.step_dt)` (num_envs, 4) bool: touchdown within the last policy step.
    - `feet.data.force` (num_envs, 4, 3): net force, world frame. z sums to −9.54 N standing (the whole weight; the sign points down).
  - `undesired_contacts`: `nonfoot = env.scene["nonfoot_ground_touch"]`, with `found` (num_envs, 22) and `force_history` (num_envs, 22, 4, 3), N, over the last 4 physics substeps (index 0 = newest), in the contact frame. The 22 slots are every robot geom except the 4 calf collisions; 13 are visual geoms that never touch. The 9 that can touch: `base_collision` and the 4 `*_hip_collision` and 4 `*_thigh_collision` geoms. It's the same sensor the 1.43 N contact termination reads.

- **Decision (Brian): `undesired_contacts` stays, at a small weight.** Anything above 1.43 N already ends the episode, so the penalty only sees light brushes: a thigh grazing on a low stride, a belly brush while crouching, a hip scuff in a tight turn. It's there for sloppy gaits and hardware wear. Big hits are already punished by termination, since the policy loses all its future reward.
- **Fall-on-purpose guard (Brian):** if a typical step's total reward is net negative, early termination pays and the policy learns to fall to escape the penalties. Built, with no weights changed (they're Brian's to tune):
  - `tools/reward_check.py TASK [--checkpoint …]` (library: `ironbark_rl/reward_audit.py`) reports the mean per-step total and each term's contribution (weight × value × dt, which sum to the total), sorted by size with each one's share. It runs two scenarios under scoreboard conditions: (a) standing still on a zero command, and (b) a policy on `COMMAND_GRID` (the EXP-002 baseline once trained), also broken down by command. A negative total is flagged and the tool exits 1.
  - TensorBoard: `per_step_reward_metrics()` adds mjlab metrics that log `Episode_Metrics/reward/<term>` and `/total`, each episode's true per-step mean. mjlab's own `Episode_Reward/*` divides episode sums by the 20 s maximum length, so early-terminated episodes read low there.
  - Verified on a throwaway 2-term task (alive +1, effort −3·Σ|τ|): the term contributions sum to the total (error 3e-8), the alive metric reads 0.0200 = 1 × dt, and the CLI flagged the negative totals (exit 1). It gets wired into `-Brian` in step 4.
  - Gotcha: mjlab skips computing a term whose weight is exactly 0.
- **Step 2 done.** `ironbark_rl/brian/rewards.py` has the 11 stubs, replacing v1's; the `-BrianReward` task is removed. `tests/brian/test_rewards.py` has 46 tests:
  - known cases per term: perfect tracking = 1, level = 0, at target height = 0, constant joint velocity = 0, held targets = 0, no touchdown = 0, only feet touching = 0, plus directions;
  - shape (num_envs,) for every term, and penalties ≥ 0;
  - 3 scenario rules: a normal walking step > 0, standing still on a zero command > 0, and standing still loses when ordered to walk.
  - 1 test passes now (every term has a weight slot). Widths and the base-height target are arguments, so the known cases hold for any value. No reference implementation was written; I checked the cases by hand and verified the fixtures.
- **Step 3 in place:** `reward_config.py` holds `WEIGHTS` (11 × None), `TRACK_LIN_VEL_WIDTH`, `TRACK_ANG_VEL_WIDTH` and `BASE_HEIGHT_TARGET_M`.
- **Typical walking step for the scenario tests** (EXP-000 seed-42 policy on env v2, 256 dogs × 9 s, medians, p90 in `rewards.py`):
  - tracking: planar error 0.026 m/s, yaw-rate error 0.067 rad/s;
  - body: |vz| 0.009 m/s, roll/pitch rate 0.15 rad/s, tilt 1.5°, base height 0.128 m;
  - joints: RMS torque 0.141 N·m (0.8% of servo-steps saturate), RMS joint acceleration 36 rad/s², target step 0.042 rad;
  - feet: 2.7 touchdowns per foot per second, swing time at touchdown 0.136 s.
  - EXP-000 still walks on env v2: 0 falls, no non-foot contact. Swing p10 is 0.008 s, which is contact flicker rather than real steps.

- **`feet_air_time` hypothesis (Brian):** paying raw air time at touchdown can't tell a 0.008 s flicker from a real step, since both just pay time airborne. So it gives no push toward real steps, and buzzing feet are bad for hobby servos that likely can't track them on the real dog. Paying (air_time − threshold) at touchdown makes flickers negative (0.008 − 0.1 = −0.092) while a normal 0.136 s swing still pays +0.036. The threshold must sit below the typical 0.136 s swing. → `FEET_AIR_TIME_THRESHOLD_S` in `reward_config.py`, passed to `feet_air_time(…, air_time_threshold_s)`.
- **Gating decision (Brian):** `feet_air_time` pays 0 without a real command, or the dog learns to step in place. Turning in place needs lifted feet too, so yaw commands count: `moving = (‖cmd_xy‖ > 0.1) | (|wz| > 0.1)`, Brian's own mask. Brian implements the function.
- Tests added: a flicker touchdown pays < 0, a 0.136 s swing pays > 0, a zero command pays exactly 0 even with every foot landing (flicker, typical and 0.5 s swings), and turning in place (0, 0, 0.5) still pays. Also: the configured threshold must sit between 0.008 and 0.136 s. The existing "no touchdown → 0" case stays.
- Command facts for the gate (Luwu's command class, unchanged):
  - The env zeroes a resampled command when the norm of the whole (vx, vy, wz) vector is ≤ 0.1 (mixed units). A command can survive that and still fail both halves of Brian's mask, e.g. (0.08, 0, 0.08). That's about 0.2% of samples, from the uniform ranges.
  - With `rel_standing_envs = 0`, zero commands come only from that zeroing, about 0.4% of training samples, while the scoreboard weights the stand command at 1/8.

- **Brian implemented `feet_air_time`** (9/9 of its tests pass) and set `FEET_AIR_TIME_THRESHOLD_S = 0.07` s. His mask's 0.1 is now `MOVING_CMD_THRESHOLD` in `reward_config.py`; his logic is unchanged.
- **Plan change (Brian): Claude implements the other ten terms** to get to training, overriding CLAUDE.md's `brian/` rule for these terms only. They follow his decisions: body-frame velocities, targets in rad for `action_rate`, `joint_acc` across policy steps, `torques` on the requested (pre-clip) torque, `undesired_contacts` as a light-brush count above `UNDESIRED_CONTACT_MIN_FORCE_N`. Every line has a WHY comment and its shape, and every docstring has a worked example with real tensors. 50/53 reward tests pass; the 3 scenario rules wait on the weights. A weight proposal (legged_gym recipe, Froude-scaled to the S2) is with Brian, **not committed until he approves**.
- **Learning protocol changed (Brian):** "I'm here to learn the concepts, not syntax." Claude writes the code (WHY comment on every line, example tensors before implementing, a plain-English summary after). Brian owns design decisions and analysis. After training, Claude walks him through the per-term TensorBoard curves and asks his read first. After each milestone, a 2–3 question "why" quiz, logged in `docs/notes/`. Now in CLAUDE.md and the project memory.
- **EXP-002 status:** not trained (no run folder; it needs Brian's hypothesis first). EXP-003 (Brian's reward) is compared against it.

- **Weights approved (Brian), as proposed.** All are in `reward_config.py` with a one-line reason each. The method is legged_gym's recipe rescaled by dynamic similarity (Froude) for the S2, which is ~0.5× an A1's height and ~0.08× its mass:

  | term | weight | term | weight |
  |---|---|---|---|
  | track_lin_vel_xy | 1.0 | torques (requested) | −0.125 |
  | track_ang_vel_z | 0.5 | joint_acc | −6e-8 |
  | lin_vel_z | −4.0 | action_rate (rad) | −0.08 |
  | ang_vel_xy | −0.025 | feet_air_time | 1.0 |
  | orientation | −5.0 | undesired_contacts | −0.25 |
  | base_height | −50 | | |

  Widths: 0.0625 (m/s)² planar, 0.16 (rad/s)² yaw. Contact noise floor 0.1 N.
  - Brian's answers: the interim `BASE_HEIGHT_TARGET_M = 0.123` (sim standing) is fine until the ruler number. Keep penalizing the requested torque. Keep `lin_vel_z`, `ang_vel_xy` and `joint_acc` weak; he'll raise each one if TensorBoard or the eval shows bouncing or wobble.
- **`IronBark-S2-Walk-Flat-Brian` registered** (`ironbark_rl/tasks/s2_walk_brian/`). The glue covers: body-frame tensors; requested torque from the delayed `ctrl`; previous joint velocity in a class term that reloads the post-reset velocity; joint targets in rad; the 9 non-foot collision slots by name; and the 12 `Episode_Metrics/reward/*` metrics. A `None` in `reward_config.py` fails loudly, because a None can't safely become 0: mjlab silently skips 0-weight terms.
  - Checked: the config equals the baseline except rewards/metrics (only two function addresses differ), and the rl config except `experiment_name`. Random actions, 64 dogs × 3 s: all terms finite, previous velocity = post-reset velocity on all 36 reset steps, metrics reach `extras["log"]`. All 88 tests pass.
- **`reward_check` on Brian's reward:**
  - (a) standing still on a zero command: **+0.0292** per step. Tracking is 98%. `lin_vel_z` is the largest penalty, from the drop off the spawn height.
  - (b) the EXP-000 policy (EXP-002 isn't trained yet) on the grid: **+0.0272** per step, every command positive (+0.0236 at 0.4 m/s, up to +0.0292 standing). Tracking 95%, torques 2.3%, `lin_vel_z` 1.4%. Not flagged.
- **EXP-002** hypothesis recorded (Brian, verbatim in its file). **Training started** 2026-11-06, seed 42. Then EXP-003 (Brian's reward, parent EXP-002), with his hypothesis recorded when it starts.
- **EXP-003 hypothesis (Brian, before the run):** "similar tracking error, but smoother and gentler: lower action rate, lower servo saturation %, and fewer flicker touchdowns (p10 swing time well above 0.008 s) thanks to the 0.07 s air-time threshold and requested-torque penalty. Risk: slightly worse tracking from the extra regularization."
  - Saturation % and swing-time p10 aren't on the frozen scoreboard. They'll be reported next to it as diagnostics; a new scoreboard metric would be Brian's call.

### Next session (open it on `C:\Users\lolly\dev\ironbark_rl`)
0. Done 2026-11-06: weights approved, `-Brian` task, `reward_check`, EXP-002 training. Next: EXP-002 eval + `reward_check` (b) with the EXP-002 policy → train EXP-003 → eval → Brian's TensorBoard walkthrough (his read first) → quiz.
00. (Superseded) Brian approves or edits the weight proposal, plus `TRACK_*_WIDTH`, `UNDESIRED_CONTACT_MIN_FORCE_N` and an interim `BASE_HEIGHT_TARGET_M`. Then: all reward tests, register `IronBark-S2-Walk-Flat-Brian`, `tools/reward_check.py`, EXP-002 then EXP-003 (hypotheses first).
1. Brian writes the EXP-002 hypothesis → train it (command in the file, ~1 h; seed 43 too for the env-v2 noise floor) → `tools/eval.py --exp EXP-002`. Nothing else on the GPU during eval.
2. Brian implements `rewards.py` (`python -m pytest tests/brian -q -k reward`), fills `reward_config.py` (weights, widths, `FEET_AIR_TIME_THRESHOLD_S`), and measures the thigh pivots → `BASE_HEIGHT_TARGET_M`.
3. Claude, step 4: register `IronBark-S2-Walk-Flat-Brian` with the glue (previous joint velocity, joint targets in rad, requested torque, the 9 non-foot contact parts, per-step reward metrics). Then `tools/reward_check.py IronBark-S2-Walk-Flat-Brian --checkpoint <EXP-002>` → numbers to Brian, who tunes.
4. Step 5: a new experiment vs EXP-002 (Brian's hypothesis first). Plus the `docs/roadmap.md` cerebellum/brain note.
5. Then items 3–4 of the 2026-10-30 list.

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
