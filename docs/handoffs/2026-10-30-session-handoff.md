# Handoff: 2026-10-30 session → next session

Read this, then `CLAUDE.md`, `docs/progress.md` (the "Next session" list), and `docs/experiments/README.md`.

## Where things live

| What | Path |
|---|---|
| Repo (moved off OneDrive 2026-10-30; the old OneDrive copy is stale, don't use it) | `C:\Users\lolly\dev\ironbark_rl` |
| Python env (native Windows, no WSL) | `C:\Users\lolly\anaconda3\envs\luwu_mjlab\python.exe` (`conda activate luwu_mjlab`); `ironbark_rl` editable-installed from the repo |
| Luwu's training env (mjlab + RSL-RL), imported as `src` | `C:\Users\lolly\dev\luwu_mjlab` |
| Training logs, checkpoints, videos | `C:\Users\lolly\dev\ironbark_runs` (`logs/rsl_rl/<experiment>/<timestamp>[_EXP-NNN]/`, `videos/`) |
| Yahboom S2 files (URDF extract, STEP CAD) | `C:\Users\lolly\dev\yahboom_dogzilla` |
| Luwu's Mini2S HF checkpoint (verified safe with `weights_only=True`) | `C:\Users\lolly\dev\luwu_ckpt\mini2s_walk` |
| V1 reference repo (read-only, push disabled) | WSL `~/ironbark-v1` |
| V2 repo (DogZilla FOLLOW work) | **Only on Brian's Mac**; stays a separate repo |

## Decisions made (don't relitigate)

- **Path A** (locomotion RL), chosen before the Phase 1 gate. Phase 1 still decides *how* it deploys.
- **Sim stack:** mjlab + RSL-RL starting from LuwuDynamics/luwu_mjlab (recorded in CLAUDE.md).
- **Native Windows** (luwu_mjlab verified: ~2.1 s/PPO iteration at 4096 envs, ~55 min per 1500-iteration run).
- **S2 model** = Luwu Mini2S MJCF (leg kinematics match Yahboom's URDF to <1 mm) minus the arm, plus lidar/camera payload, trunk rescaled to **0.972 kg** (`# MEASURE:` unverified online number). See `docs/s2-model-sources.md`, `ironbark_rl/assets/s2.py`.
- **Scoreboard v1 frozen** (`ironbark_rl/brian/metrics.py`). Brian wrote 4 functions + `FALL_TILT_DEG = 46` (provisional); Claude wrote the last 3 to his decisions (exception noted in CLAUDE.md and the file header).

## Experiment state (`docs/experiments/`)

- **EXP-000** (Luwu reward, task `IronBark-S2-Walk-Flat`): trained (seeds 42 and 43), scored on v1. Mean: 0 falls, planar 0.036 m/s, yaw 0.097 rad/s, joint-target rate 2.2 rad/s, CoT 1.38. **Seed noise ~3–5% tracking, ~7–9% smoothness/CoT.** Videos in `~/dev/ironbark_runs/videos/` (final walk + progression, already sent to Brian).
- **EXP-001** (Brian's reward v1: tracking bonus + stability + smoothness penalties): design and hypothesis recorded **before** training. Task `IronBark-S2-Walk-Flat-BrianReward` is wired (glue in `ironbark_rl/tasks/s2_walk_brian/`). **Blocked on Brian implementing `ironbark_rl/brian/rewards.py`** (3 functions + `WEIGHTS`; 15 spec tests in `tests/brian/test_rewards.py` encode his own design rules). The train command is in the EXP-001 file.

## Next steps (in order)

1. Brian implements `rewards.py` → `python -m pytest tests/brian -q -k reward` (15 must pass). Coach per the learning protocol and Brian's learning-style memory: **no near-finished code**; loops first, then vectorize; numpy/torch are new to him.
2. Train EXP-001 (command in its file; ~55 min). Tell Brian when the dog starts walking (watch `Metrics/twist/error_vel_xy` and episode length in the log or TensorBoard).
3. `python tools/eval.py IronBark-S2-Walk-Flat-BrianReward --exp EXP-001`, `tools/record.py` (final clip + progression), `tools/progress.py` for both runs and `--chart` them together. Compare against the EXP-000 noise floor.
4. Learning-protocol step 6 for `metrics.py`: 2–3 interview questions, answers in `docs/notes/`.
5. EXP-000 progress chart: rerun `tools/progress.py IronBark-S2-Walk-Flat --run-dir <seed-42 run> --label "EXP-000 (Luwu reward)"`. **The last attempt was killed after ~45 min (far slower than expected); profile it first.** Suspect the 7 per-step `.cpu().numpy()` syncs in `ironbark_rl/evaluation.py:rollouts`.
6. Still open: trained-policy tilt sweep (`tools/tilt_test.py --policy trained`) to confirm `FALL_TILT_DEG`; the Phase 1 joint-control measurement script (Claude writes, Brian runs); see `docs/phase1-xgolib-api.md`.
7. Phase 0 leftovers (Brian-side): Windows Defender inbound rule for TCP 5556/5558/50505/50507, Deco DHCP reservations (Pi .56, PC .55), Tailscale on the PC, V2 repo onto the PC, the Mac's Claude memory. Brian also wants to **stop using OneDrive entirely** (steps were given; he does it himself).

## Pi access

From WSL Ubuntu-24.04: `ssh pi` (alias → `lolly@192.168.68.56`, key `ironbark-pc`). Host key `SHA256:wqOZO9hVbi+SvpNwRq5HVHM1M877bQ1TpzFUTJUguZ8`; old `.56` known_hosts entries elsewhere belong to other devices. `raspberrypi.local` resolves on Windows but not in WSL. The Windows key is **not** authorized on the Pi. Never run anything that moves the dog.

## Gotchas learned this session

- Windows output is cp1252: tools call `sys.stdout.reconfigure(encoding="utf-8")`, or mjlab crashes printing Unicode.
- Use `torch.no_grad()`, not `inference_mode()`, when one env runs several checkpoints (inference tensors break the next reset).
- luwu's checkpoint lookup sorts alphabetically (model_900 > model_1499): use `ironbark_rl.runs.latest_checkpoint`.
- Brian's global pip config adds an unresolvable `pypi.ngc.nvidia.com` index, so every install retries slowly (still works). Use `--no-build-isolation --no-deps` for the editable install.
- Drive C: is nearly full (~13–29 GB free). OneDrive was holding ~29 GB of RAM.
- `rm -rf "$VAR"/…` is blocked by a safety check: use literal paths.
- An open MuJoCo viewer during training slows it 2–3×.
- Two `aws_api_mcp_server` processes (a Claude connector) were each pegging a CPU core; not ours, flagged to Brian.
- Brian designed reward v1 without reading Luwu's reward. Keep Luwu's reward terms and weights out of chat unless he asks (they appear in mjlab's startup printout).
- TensorBoard: `.claude/launch.json` in the repo has a `tensorboard` config (port 6006, logdir `~/dev/ironbark_runs/logs/rsl_rl`) for the browser pane. It's machine-local and gitignored.

## Working conventions

Short replies. Single-variable commits ending with the Co-Authored-By trailer, pushed to `github.com/BaneBeetle/ironbark_rl` (public). Every training run gets a `docs/experiments/` entry (`tools/new_experiment.py`); hypothesis, observations and why are Brian's (record them verbatim when he dictates); Claude fills Setup and Results. Update `docs/progress.md` at session end.
