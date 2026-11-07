# Handoff: 2026-11-06/07 session → next session

Read this first, then `CLAUDE.md` (the learning protocol changed this session), the top of `docs/progress.md`, `docs/journal.md`, and `docs/experiments/README.md`. The previous handoff (`2026-10-30-session-handoff.md`) is mostly superseded: its next steps 1–3 are done and EXP-001 was never trained.

## Paste-ready prompt for the next session

> Continue IronBark (RL locomotion on the Yahboom DOGZILLA S2, mjlab + RSL-RL PPO from luwu_mjlab). The repo is `C:\Users\lolly\dev\ironbark_rl`, and only that path: never the OneDrive copy, even if the session opens there. Python is `C:\Users\lolly\anaconda3\envs\luwu_mjlab\python.exe`. Read `docs/handoffs/2026-11-07-session-handoff.md`, `CLAUDE.md`, the top of `docs/progress.md`, `docs/journal.md` and `docs/experiments/README.md`, then follow their rules. Current state: my 11-term legged_gym-style reward (task `IronBark-S2-Walk-Flat-Brian`) with `feet_air_time` at weight 3.0 (EXP-005) is the current best. Across 3 seeds it matches Luwu's baseline (EXP-002) on servo saturation and planar tracking, and cuts flicker touchdowns from 23.6% to 17.2%. Learning protocol: I'm here for the concepts, not the syntax. You write the code (a WHY comment and the tensor shape on every line, example tensors before implementing, a plain-English summary after). I own every design decision and all the analysis: ask for my read before giving yours, and quiz me after milestones. Don't start training until I give a hypothesis and say go.

## Where things live

| What | Path |
|---|---|
| Repo (pushed to `github.com/BaneBeetle/ironbark_rl`, branch `main`) | `C:\Users\lolly\dev\ironbark_rl` |
| Python env | `C:\Users\lolly\anaconda3\envs\luwu_mjlab\python.exe` |
| Luwu's mjlab env (imported as `src`) | `C:\Users\lolly\dev\luwu_mjlab` |
| Run folders (logs, checkpoints, `eval_v1_model_1499.json`, `gait_model_1499.json`) | `C:\Users\lolly\dev\ironbark_runs\logs\rsl_rl\{ironbark_s2_walk, ironbark_s2_walk_brian}\<timestamp>_EXP-NNN[-sSEED]` |
| Claude project memory | `C:\Users\lolly\.claude\projects\C--Users-lolly-dev-ironbark-rl\memory\` (Path A choice, Brian's learning style) |
| Last session's scratch helpers (temp dir, may be cleaned; not in the repo) | `C:\Users\lolly\AppData\Local\Temp\claude\55ed83b4bd977ac3\eff8332e-ff94-4225-b6c7-1487d92c41fc\scratchpad\` (`sweep_pre.py`, `sweep_post.py`, `seed_run.py`, `final_summary.py`, train logs) |

Best policy so far (EXP-005, seed 42): `C:\Users\lolly\dev\ironbark_runs\logs\rsl_rl\ironbark_s2_walk_brian\2026-11-07_02-47-40_EXP-005\model_1499.pt`. Seeds 43 and 44 are in the `*_EXP-005-s43` and `*_EXP-005-s44` folders.

## What was done this session (2026-11-06 → 11-07)

1. **The reward plan changed.** Reward v1 (EXP-001) was superseded before it trained. It was replaced by Brian's 11 legged_gym-style terms (Rudin et al. 2021) in `ironbark_rl/brian/rewards.py`, each returning `(num_envs,)`: `track_lin_vel_xy`, `track_ang_vel_z` (exp kernels), `lin_vel_z`, `ang_vel_xy`, `orientation`, `base_height`, `torques` (requested, pre-clip torque), `joint_acc` (across policy steps), `action_rate` (joint targets in rad), `feet_air_time`, `undesired_contacts`.
   - **Brian wrote `feet_air_time` himself.** It pays (last air time − 0.07 s) at each touchdown, gated by his mask `moving = ‖cmd_xy‖ > 0.1 | |wz| > 0.1`. Don't rewrite it without asking.
   - **Claude wrote the other ten** at Brian's request, with WHY and shape comments and a worked example in each docstring.
2. **The learning protocol changed** (Brian, 2026-11-06: "concepts, not syntax"). It's now in `CLAUDE.md` and the project memory.
3. **Env v2 is the baseline task `IronBark-S2-Walk-Flat`** (Brian's decisions):
   - training tilt termination 70° → 50°;
   - non-foot contact termination 10 N → 1.43 N (15% of body weight);
   - every collision mesh touches the ground (in Luwu's setup only the calves did).
   - The scoreboard's fall line stays `FALL_TILT_DEG = 46`.
4. **The weights are Brian's, approved as proposed.** They follow legged_gym's recipe, Froude-scaled to the S2. Each has a one-line reason in `ironbark_rl/brian/reward_config.py`. `feet_air_time` is now **3.0** (commit `e520970`). The interim `BASE_HEIGHT_TARGET_M = 0.123` waits on a ruler measurement.
5. **Task `IronBark-S2-Walk-Flat-Brian`** (`ironbark_rl/tasks/s2_walk_brian/`): the baseline env plus Brian's reward and the `Episode_Metrics/reward/<term>` logging. Any `None` in the config raises.
6. **New tools:**
   - `tools/reward_check.py` (library `ironbark_rl/reward_audit.py`): the fall-on-purpose guard. It flags a negative per-step total (standing still, and a policy on the command grid) and exits 1 when flagged.
   - `tools/gait_check.py`: servo saturation, swing p10/median/p90, flicker share (swings < 0.02 s, Brian's cutoff), touchdown rate. `--exp` appends the results.
   - `tools/term_curves.py`: per-term training curves into an experiment file. It prints tiny values in scientific notation.
   - `tests/test_brian_task_sim.py`: opt-in, `pytest -m sim`.
   - The default `pytest` run: **88 passed, 1 deselected**.
7. **`undesired_contacts` was investigated: not a bug.** Contacts above 1.43 N end the episode first, and light brushes never occur. Brian's verdict: dormant on flat ground, keep it unchanged.
8. **Experiments run** (all 4096 envs, 1500 iterations, 0 falls, no crashes):
   - EXP-002: Luwu's reward on env v2, the baseline. Seeds 42/43/44.
   - EXP-003: Brian's reward, `feet_air_time` 1.0.
   - EXP-004: 7.5, seeds 42/43/44.
   - EXP-005: 3.0, seeds 42/43/44.
   - EXP-006: 15. EXP-007: 30. EXP-008: 5.
9. **Quiz after the reward-terms milestone:** Brian's answers are verbatim in `docs/notes/2026-11-06-reward-terms.md`, with follow-up questions at the bottom.
10. **2026-11-07 01:56:** at Brian's request, stopped two `aws_api_mcp_server` workers that were each holding a CPU core. They haven't come back.

### Results (scoreboard v1 + `gait_check`; mean ± sample SD [min–max] across seeds)

| Run | feet_air_time weight | Seeds | Saturation [%] | Planar err [m/s] | Flicker [%] |
|---|---|---|---|---|---|
| EXP-002 (Luwu baseline) | — | 3 | 0.57 ± 0.20 [0.40–0.79] | 0.0360 ± 0.0011 | 23.6 ± 1.2 |
| EXP-003 | 1 | 1 | 1.03 | 0.0389 | 24.9 |
| **EXP-005** | **3** | 3 | **0.48 ± 0.08 [0.39–0.53]** | **0.0347 ± 0.0024** | **17.2 ± 0.7** |
| EXP-008 | 5 | 1 | 0.87 | 0.0392 | 18.5 |
| EXP-004 | 7.5 | 3 | 0.96 ± 0.20 [0.75–1.15] | 0.0372 ± 0.0009 | 15.6 ± 0.0 |
| EXP-006 | 15 | 1 | 5.34 | 0.0664 | 9.9 |
| EXP-007 | 30 | 1 | 11.72 | 0.1087 | 7.4 |

**Ranking objective (Brian):** servo saturation first, then planar tracking, then flicker share; 0 falls required.

**Verdict (Brian, verbatim in `docs/journal.md` and EXP-005):** EXP-005 wins.
- Saturation beats EXP-004's: the ranges don't overlap.
- It ties the baseline on saturation and tracking, with less spread.
- Flicker is about 27% lower than the baseline's, with no overlap.

Headline: "my reward matches the baseline on servo strain and tracking while cutting flickers ~27% across 3 seeds."

## Open items

**Brian's calls (don't decide for him):**
- [ ] Next experiment, with its hypothesis. None is chosen.
- [ ] More seeds for EXP-008 (5.0) or EXP-003 (1.0)? He hasn't asked for them.
- [ ] Final verdict lines. The status lines of EXP-002/003/004/006/007/008 still say "verdict pending". Their Verdict sections hold only his interim notes (EXP-004 "finalist", EXP-006/007 "out"), and EXP-002/003/008 have none. The "What I saw" sections are empty in every file.
- [ ] Ruler: the real S2's standing thigh-pivot height → `BASE_HEIGHT_TARGET_M`. The method is in its `# MEASURE:` comment.
- [ ] Recheck `FALL_TILT_DEG = 46` against his trained policy. Note that `tools/tilt_test.py --task IronBark-S2-Walk-Flat-Brian --policy trained` has no `--checkpoint` flag: it loads the **newest** run, which is EXP-008, not EXP-005. It needs a `--checkpoint` flag first.

**Claude's, when Brian says go:**
- [ ] Protocol step 5 for the sweep: walk Brian through EXP-005's per-term curves (`Episode_Metrics/reward/*`), his read first.
- [ ] Protocol step 6 for the sweep/seed milestone: a 2–3 question "why" quiz, logged in `docs/notes/`. Not done yet.
- [ ] `docs/roadmap.md`: a note only, don't build. The RL policy is the fast "cerebellum"; a VLM is the slow "brain" that sends (vx, vy, yaw_rate).
- [ ] Older items: the Phase 1 joint-control measurement script (Claude writes it, Brian runs it; `docs/phase1-xgolib-api.md`), and the Phase 0 leftovers in `docs/progress.md` ("Open: Brian" / "Open: Claude").

## How each experiment was run (README rules)

1. Brian gives the hypothesis **before** training. It's recorded verbatim; if it comes late, note when.
2. One change only, in its own commit. Run `pytest -q` (88 must pass) and the guard, `tools/reward_check.py IronBark-S2-Walk-Flat-Brian --checkpoint <a recent Brian-reward policy>`. Skip the guard for Luwu-reward runs.
3. `tools/new_experiment.py "title" --parent EXP-NNN --task IronBark-S2-Walk-Flat-Brian --experiment-name ironbark_s2_walk_brian`. Claude fills Setup.
4. Train: `tools/run.py train IronBark-S2-Walk-Flat-Brian --env.scene.num-envs 4096 --agent.max-iterations 1500 --agent.seed 42 --agent.run-name EXP-NNN` (about 50–60 min). Seed replicates use run name `EXP-NNN-s43`.
5. Score, with nothing else training: `tools/eval.py <task> --checkpoint <run>/model_1499.pt --exp EXP-NNN`, `tools/gait_check.py … --exp EXP-NNN`, `tools/term_curves.py <run> --exp EXP-NNN`. Results are append-only.
6. Compare **only** on the scoreboard and diagnostics, never on reward values. Hypothesis, observations, why/next and the verdict are Brian's.
7. If a run crashes, resume it once from its last checkpoint: pass the exact checkpoint file name, and `--agent.max-iterations` = 1500 − N.

Watch a policy without disturbing training (CPU only):
`python tools/run.py play IronBark-S2-Walk-Flat-Brian --checkpoint-file <run>\model_1499.pt --viewer native --device cpu`

## Gotchas learned this session

- **The desktop session may open on the OneDrive path.** Always `cd /c/Users/lolly/dev/ironbark_rl` (Bash resets the working directory after each call).
- mjlab silently skips a reward term whose weight is exactly 0. That's why `None` raises and doesn't default to 0.
- The root body `base` is massless, so `root_com_*` is meaningless. Use `root_link_*`.
- The servos are MuJoCo position actuators: kp 1.15, kv 0, target clamped to ±1.57 rad, force to ±0.43 N·m. `actuator_force` is the post-clamp value. The controller sees a target delayed 1–2 physics steps, so the requested torque must come from `sim.data.ctrl`.
- Step order: action → 5 physics substeps → terminations → **reward** → metrics → reset → commands/observations. A termination step still gets its reward.
- Call `env.reset()` before reading `env.extras["log"]`. Joint names need the `robot/` prefix for `mj_model` lookups.
- The checkpoint lookup sorts alphabetically (model_900 > model_1499). Pass exact file names. Without `--checkpoint`, `tools/eval.py`, `tools/tilt_test.py` and `tools/run.py play` load the newest run (EXP-008 now), not the best one.
- Never round a tiny value to 0 and report it as "exactly 0". It caused the false `undesired_contacts` bug report. `term_curves` now prints scientific notation.
- Windows: use raw strings for paths in inline Python (`\U` breaks). `grep -c` exits 1 on zero matches, which breaks `&&` chains. Repo files use **LF** line endings. Tools call `sys.stdout.reconfigure(encoding="utf-8")`.
- Inline Python: implicit string concatenation followed by a parenthesized expression is a call, `"str"(...)` → TypeError. That bug crashed the EXP-008 setup helper.
- Run eval, `gait_check`, `progress` and `record` only while nothing is training. CPU playback is fine during training.
- Never show or summarize Luwu's reward code to Brian. It appears in mjlab's startup printout; tools hide that output.

## Working conventions

- Short replies.
- Single-variable commits ending with the `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` trailer, pushed to `main`.
- Update `docs/progress.md` at the end of each session, and Brian's decisions in `docs/journal.md`, newest first, in his words.
- When Brian is away (Remote Control), summaries are numbers only, with no interpretation, until he gives his read.
