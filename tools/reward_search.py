"""Bayesian search (Optuna) over three of Brian's reward weights, under EXP-010's latency conditions.

Brian's spec (2026-11-08) is quoted in SPEC and in the search page (SEARCH_DOC). Each trial is a
numbered experiment (docs/experiments/EXP-NNN-*.md), trained with seed 42 on EXP-010's task and
scored like EXP-010. The study lives in ~/dev/ironbark_runs/optuna/; the ranked table in SEARCH_DOC.

Stages (one Optuna study each, since a study's ranges can't change): stage 1 = Brian's spec
(action_rate 0.5x-4x); stage 2 = Brian's change (action_rate 4x-10x), seeded with the stage-1
trials at the 4x ceiling as known points. The search page ranks the trials of both together.

  python tools/reward_search.py run [--stage 1|2]   # loop until STOP: ask -> entry -> train -> score -> tell -> table
  python tools/reward_search.py table    # rewrite the search page from the studies (CPU only)
  python tools/reward_search.py replicate EXP-017 EXP-018 EXP-015 --seeds 43 44   # Brian's picks, other seeds

Control files in the study folder, checked between trials only (a running trial always finishes):
  PAUSE   wait with the GPU free until the file is removed (e.g. while another session renders)
  STOP    exit before the next trial

Before training, every trial runs the reward guard (tools/reward_check.py) with its weights:
standing still, and EXP-010's policy on the command grid. A negative standing or walking
per-step total is flagged in the entry, the index and the table; the trial trains anyway (Brian).

The driver commits each trial's entry before training and its results after scoring
(only the files it wrote), and stops at the first failed trial.

replicate: re-trains search trials Brian picked with other seeds (same weights, task and scoring),
one run at a time, honoring PAUSE and STOP; results go into each trial's entry (a Seed replicates
block, then a mean ± SD table once every seed is in), the index, the search page, and
optuna/replicates.json. The study itself stays seed 42 only.
"""

import argparse
import datetime
import importlib.util
import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
RUNS_DIR = Path(os.environ.get("IRONBARK_RUNS", Path.home() / "dev" / "ironbark_runs"))  # same rule as ironbark_rl/runs.py
STUDY_DIR = RUNS_DIR / "optuna"
STUDY_NAME = "exp010_reward_weights"
STORAGE = f"sqlite:///{(STUDY_DIR / (STUDY_NAME + '.db')).as_posix()}"
PAUSE_FILE, STOP_FILE = STUDY_DIR / "PAUSE", STUDY_DIR / "STOP"
REPLICATES = STUDY_DIR / "replicates.json"  # {exp: {seed: metrics + run, minutes}}: Brian's picks re-run with other seeds
EXPERIMENTS = REPO / "docs" / "experiments"
INDEX = EXPERIMENTS / "README.md"
SEARCH_DOC = EXPERIMENTS / "SEARCH-exp010-reward-weights.md"
REWARD_CONFIG = REPO / "ironbark_rl" / "brian" / "reward_config.py"
TRAILER = "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"

# EXP-010's conditions: Brian's reward, 40 ms command delay, 130 ms round-robin joint readback.
TASK = "IronBark-S2-Walk-Flat-Brian-StaleJoints"
EXPERIMENT_NAME = "ironbark_s2_walk_brian_stale_joints"  # the task's rl_cfg experiment_name
PARENT = "EXP-010"
PARENT_RUN = "2026-11-07_20-02-00_EXP-010"  # seed 42, the start weights: the study's known point
SEED, ITERATIONS, ENVS = 42, 1500, 4096
CHECKPOINT = f"model_{ITERATIONS - 1}.pt"
PARENT_CHECKPOINT = RUNS_DIR / "logs/rsl_rl" / EXPERIMENT_NAME / PARENT_RUN / CHECKPOINT  # the guard's walking policy

SPEC = """\
After the 4 seed runs finish and are scored, start an Optuna search (Bayesian optimization) on MY reward under EXP-010's latency conditions:
- Tune 3 weights: feet_air_time (1.0–7.5), action_rate (0.5x–4x current), torques (0.5x–2x current). Everything else fixed.
- Objective: servo saturation ≤ 0.9% AND planar tracking ≤ 0.035 m/s, then minimize flicker. Trials failing a constraint rank below all that pass.
- Seed 42, one trial at a time, each a numbered experiment with its weights recorded. Keep going until I stop you.
- Leave the GPU free when the website session asks.
- Morning summary: ranked table of trials. Don't interpret. I'll pick the top 2–3 to re-run with seeds 43/44."""

# Brian, 2026-11-08 (verbatim), after the first 8 trials: the search's stage 2.
SPEC_2 = ("Pause the search after EXP-019. Run seeds 43 and 44 for EXP-017, EXP-018 and EXP-015 (my top 3; I rank by "
          "saturation first, then tracking, then flicker). Then resume with action_rate's range extended to 4x–10x, "
          "since all the top trials hit the 4x ceiling.")

# Brian's spec.
FEET_AIR_TIME_RANGE = (1.0, 7.5)  # absolute weight
ACTION_RATE_SCALE_RANGE = (0.5, 4.0)  # x action_rate's weight at the search's start
TORQUES_SCALE_RANGE = (0.5, 2.0)  # x torques' weight at the search's start
SATURATION_MAX = 0.009  # servo saturation <= 0.9% (gait_check saturated_share)
PLANAR_ERROR_MAX_MPS = 0.035  # planar tracking <= 0.035 m/s (scoreboard v1 overall)
# Claude's defaults, listed on the search page for Brian to change.
LOG_SCALE = True  # the ranges are multiples, so sample ratios evenly
N_STARTUP_TRIALS = 4  # random trials before the GP takes over, EXP-010 included (Optuna's default 10 = ~11 h of random)
SAMPLER_SEED = 42


@dataclass(frozen=True)
class Stage:
    number: int
    study_name: str
    action_rate_scale_range: tuple[float, float]  # x action_rate's weight at the search's start
    random_trials: int  # random trials after the known points, before the GP picks (Claude's default)
    sampler_seed: int  # a new seed per stage, so a stage's random start doesn't repeat the last one's draws


STAGES = {
    1: Stage(1, STUDY_NAME, ACTION_RATE_SCALE_RANGE, N_STARTUP_TRIALS - 1, SAMPLER_SEED),  # Brian's spec; EXP-010 is the known point
    2: Stage(2, "exp010_reward_weights_ar4to10", (4.0, 10.0), 3, SAMPLER_SEED + 1),  # Brian (2026-11-08): action_rate 4x–10x
}
LATEST_STAGE = 2


def storage_url(stage: int) -> str:
    return f"sqlite:///{(STUDY_DIR / (STAGES[stage].study_name + '.db')).as_posix()}"

# Brian, 2026-11-08, verbatim (the part about seeds; the rest of the message is in docs/journal.md).
REPLICATE_REQUEST = ("Run seeds 43 and 44 for EXP-017, EXP-018 and EXP-015 (my top 3; I rank by saturation first, "
                     "then tracking, then flicker).")
REPLICATE_HEADING = "### Seed replicates (same setup, different seed: measures the noise floor, rule 4)"
RESULTS_HEADING = "## Results (scoreboard: `metrics.py`)"

TUNED = ("feet_air_time", "action_rate", "torques")
EVAL_KEYS = ("fall_rate", "planar_error_mps", "yaw_rate_error_radps", "joint_target_rate_radps", "cost_of_transport")
GAIT_KEYS = ("saturated_share", "flicker_share", "swing_median_s")


class TrialFailed(RuntimeError):
    pass


# ---------- pure helpers (tested) ----------

def config_weights(path: Path = REWARD_CONFIG) -> dict[str, float]:
    """reward_config.WEIGHTS as the file says now (read fresh, no package import)."""
    spec = importlib.util.spec_from_file_location("_reward_config_now", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.WEIGHTS)


def distributions(stage: int = 1):
    from optuna.distributions import FloatDistribution

    return {
        "feet_air_time": FloatDistribution(*FEET_AIR_TIME_RANGE, log=LOG_SCALE),
        "action_rate_scale": FloatDistribution(*STAGES[stage].action_rate_scale_range, log=LOG_SCALE),
        "torques_scale": FloatDistribution(*TORQUES_SCALE_RANGE, log=LOG_SCALE),
    }


def trial_weights(params: dict[str, float], start: dict[str, float]) -> dict[str, float]:
    """The three weights a trial trains with, rounded to the 6 significant digits passed on the command line."""
    w = {
        "feet_air_time": params["feet_air_time"],
        "action_rate": start["action_rate"] * params["action_rate_scale"],
        "torques": start["torques"] * params["torques_scale"],
    }
    return {k: float(f"{v:.6g}") for k, v in w.items()}


def trial_label(stage: int, number: int) -> str:
    return f"trial {number}" if stage == 1 else f"stage-{stage} trial {number}"


def override_args(weights: dict[str, float]) -> list[str]:
    args = []
    for name in TUNED:
        args += [f"--env.rewards.{name}.weight", f"{weights[name]:.6g}"]
    return args


def train_args(run_name: str, weights: dict[str, float], seed: int = SEED) -> list[str]:
    return ["tools/run.py", "train", TASK, "--env.scene.num-envs", str(ENVS), "--agent.max-iterations", str(ITERATIONS),
            "--agent.seed", str(seed), "--agent.run-name", run_name, *override_args(weights)]


def constraint_values(m: dict[str, float]) -> tuple[float, float]:
    """Optuna's convention: <= 0 is feasible."""
    return (m["saturated_share"] - SATURATION_MAX, m["planar_error_mps"] - PLANAR_ERROR_MAX_MPS)


def failed_constraints(m: dict[str, float]) -> list[str]:
    sat, planar = constraint_values(m)
    return [name for name, c in (("saturation", sat), ("planar", planar)) if c > 0]


def overshoots(m: dict[str, float]) -> dict[str, float]:
    """How far each constraint is missed, as a fraction of its limit (0 = met)."""
    return {"saturation": max(0.0, m["saturated_share"] / SATURATION_MAX - 1.0),
            "planar": max(0.0, m["planar_error_mps"] / PLANAR_ERROR_MAX_MPS - 1.0)}


def constraint_miss(m: dict[str, float]) -> float:
    """Brian (2026-11-08): failing trials rank by how far they miss the constraints. Claude's reading: the overshoots summed."""
    return sum(overshoots(m).values())


def ranked(rows: list[dict]) -> list[dict]:
    """Brian: trials failing a constraint rank below all that pass, passing ones by flicker (lower first),
    failing ones by how far they miss (smaller first; flicker breaks a tie)."""
    def key(r):
        miss = constraint_miss(r["metrics"])
        return (miss > 0, miss, r["metrics"]["flicker_share"])

    return sorted(rows, key=key)


def _num(x: float) -> str:
    return f"{x:.4g}"


def change_text(weights: dict[str, float], start: dict[str, float]) -> str:
    parts = [f"feet_air_time {_num(start['feet_air_time'])} -> {_num(weights['feet_air_time'])}"]
    for name in ("action_rate", "torques"):
        parts.append(f"{name} {_num(start[name])} -> {_num(weights[name])} ({weights[name] / start[name]:.2f}x)")
    return "; ".join(parts)


def summary_text(m: dict[str, float]) -> str:
    return (f"v1 (conditions on), seed {SEED}: falls {m['fall_rate']:.3f} · planar {m['planar_error_mps']:.3f} m/s · "
            f"yaw {m['yaw_rate_error_radps']:.3f} rad/s · smooth {m['joint_target_rate_radps']:.2f} rad/s · "
            f"CoT {m['cost_of_transport']:.2f}; flicker {m['flicker_share']:.1%} · swing median {m['swing_median_s']:.3f} s · "
            f"saturation {m['saturated_share']:.2%}")


def constraints_cell(m: dict[str, float]) -> str:
    over = {k: v for k, v in overshoots(m).items() if v > 0}
    return "pass" if not over else "fail: " + ", ".join(f"{k} +{v:.1%}" for k, v in over.items())


def constraints_text(m: dict[str, float]) -> str:
    cell = constraints_cell(m)
    return "constraints pass" if cell == "pass" else f"constraints {cell.replace('fail: ', 'fail (')} over the limit)"


def guard_flags(g: dict) -> list[str]:
    """Brian (2026-11-08): flag, but don't skip, a trial whose standing or walking per-step total is negative."""
    return [name for name in ("standing", "walking") if g[f"{name}_total"] < 0]


def guard_text(g: dict) -> str:
    text = f"standing {g['standing_total']:+.4f}, walking {g['walking_total']:+.4f} per step"
    negative = [c for c in g["walking_by_command"] if c["total"] < 0]
    if negative:
        text += "; negative commands (vx, vy, wz): " + ", ".join(
            f"({c['command'][0]:+.1f}, {c['command'][1]:+.1f}, {c['command'][2]:+.1f}) {c['total']:+.4f}" for c in negative)
    flags = guard_flags(g)
    return text + (". OK" if not flags else f". **FLAG: {' and '.join(flags)} total negative**; trained anyway (Brian: flag, don't skip)")


def guard_line(g: dict) -> str:
    return (f"- Guard: `tools/reward_check.py {TASK} --checkpoint <{PARENT} run>/{CHECKPOINT}` with this trial's three weights "
            f"(standing still; {PARENT}'s policy on the command grid): {guard_text(g)}")


def add_guard_line(text: str, line: str) -> str:
    old = "\n- Run folder:"
    if text.count(old) != 1:
        raise ValueError("no Run folder line")
    return text.replace(old, "\n" + line + old, 1)


def guard_short(g: dict | None) -> str:
    if g is None:
        return "–"
    flags = guard_flags(g)
    return f"{g['standing_total']:+.4f} / {g['walking_total']:+.4f}" + (f" **FLAG: {', '.join(flags)}**" if flags else "")


def fill_entry(text: str, label: str, weights: dict[str, float], start: dict[str, float], cmd: str) -> str:
    """new_experiment.py's template -> a search-trial entry (status, hypothesis note, change, train command)."""
    edits = [
        ("**Status:** planned", f"**Status:** search {label} (Optuna), training"),
        ("> What will change on the scoreboard compared to the parent, and why?",
         f"> Search {label}: no per-trial hypothesis. Brian's search spec (2026-11-08), verbatim, is on "
         f"[{SEARCH_DOC.name}]({SEARCH_DOC.name})."),
        (f"vs. {PARENT}:\n",
         f"vs. {PARENT}: three reward weights, picked by the search (Brian's search varies them together): "
         f"{change_text(weights, start)}. Everything else is {PARENT}'s: task `{TASK}` (40 ms command delay, "
         f"130 ms round-robin joint readback, actor joint velocity dropped), Brian's other weights, same PPO settings, "
         f"seed {SEED}, {ITERATIONS} iterations. Scored like {PARENT}: the delay and the staleness stay on.\n"),
    ]
    for old, new in edits:
        if old not in text:
            raise ValueError(f"template text not found: {old!r}")
        text = text.replace(old, new, 1)
    text, n = re.subn(r"^- Train: `.*`$", lambda _: f"- Train: `{cmd}`", text, count=1, flags=re.M)
    if n != 1:
        raise ValueError("no Train line")
    return text


def fill_index_change(index: str, exp_id: str, label: str, weights: dict[str, float], start: dict[str, float]) -> str:
    old = f"| vs. {PARENT}: _fill in_ | _pending_ |"
    return _edit_row(index, exp_id, old, f"| vs. {PARENT}: search {label}: {change_text(weights, start)} | _pending_ |")


def fill_index_verdict(index: str, exp_id: str, text: str) -> str:
    return _edit_row(index, exp_id, "| _pending_ |", f"| {text} |")


def _edit_row(index: str, exp_id: str, old: str, new: str) -> str:
    lines = index.split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith(f"| [{exp_id}](") and line.endswith(old)]
    if len(hits) != 1:
        raise ValueError(f"index row for {exp_id} ending {old!r}: {len(hits)} found")
    i = hits[0]
    lines[i] = lines[i][: -len(old)] + new
    return "\n".join(lines)


def set_status(text: str, status: str) -> str:
    text, n = re.subn(r"^\*\*Status:\*\* .*? · \*\*Parent:\*\*", lambda _: f"**Status:** {status} · **Parent:**",
                      text, count=1, flags=re.M)
    if n != 1:
        raise ValueError("no Status line")
    return text


def saved_weights(env_yaml: str) -> dict[str, float]:
    """The tuned weights a run actually trained with, from its params/env.yaml."""
    block = env_yaml.split("\nrewards:\n", 1)[1]
    block = re.split(r"\n\S", block, maxsplit=1)[0]  # up to the next top-level key
    out = {}
    for name in TUNED:
        m = re.search(rf"^  {name}:\n(?:    .*\n)*?    weight: (\S+)", block + "\n", flags=re.M)
        out[name] = float(m.group(1))
    return out


def read_metrics(run: Path) -> dict[str, float]:
    e = json.loads((run / f"eval_v1_{CHECKPOINT.removesuffix('.pt')}.json").read_text(encoding="utf-8"))["overall"]
    g = json.loads((run / f"gait_{CHECKPOINT.removesuffix('.pt')}.json").read_text(encoding="utf-8"))
    return {**{k: float(e[k]) for k in EVAL_KEYS}, **{k: float(g[k]) for k in GAIT_KEYS}}


SEED_TABLE_COLUMNS = (("fall_rate", "Falls", "{:.3f}"), ("planar_error_mps", "Planar err [m/s]", "{:.4f}"),
                      ("yaw_rate_error_radps", "Yaw err [rad/s]", "{:.4f}"), ("joint_target_rate_radps", "Joint-target rate [rad/s]", "{:.3f}"),
                      ("cost_of_transport", "CoT", "{:.3f}"), ("saturated_share", "Saturation", "pct"),
                      ("flicker_share", "Flicker", "pct"), ("swing_median_s", "Swing median [s]", "{:.4f}"))


def _fmt(fmt: str, x: float) -> str:
    return f"{100 * x:.2f}%" if fmt == "pct" else fmt.format(x)


def seed_stats(per_seed: dict[int, dict]) -> dict[str, tuple[float, float, float, float]]:
    """metric -> (mean, sample SD, min, max) over the seeds."""
    out = {}
    for key, _, _ in SEED_TABLE_COLUMNS:
        v = [per_seed[s][key] for s in sorted(per_seed)]
        out[key] = (statistics.mean(v), statistics.stdev(v), min(v), max(v))
    return out


def seed_table(per_seed: dict[int, dict]) -> str:
    seeds = sorted(per_seed)
    lines = [f"**Seeds {'/'.join(map(str, seeds))}, mean ± sample SD [min–max]** (scoreboard v1 overall + gait diagnostics, "
             f"`{CHECKPOINT}`, staleness and delay on):", "",
             "| Seed | " + " | ".join(c[1] for c in SEED_TABLE_COLUMNS) + " |", "|---|" + "---|" * len(SEED_TABLE_COLUMNS)]
    for s in seeds:
        lines.append(f"| {s} | " + " | ".join(_fmt(fmt, per_seed[s][key]) for key, _, fmt in SEED_TABLE_COLUMNS) + " |")
    st = seed_stats(per_seed)
    lines.append("| **mean ± SD [min–max]** | " + " | ".join(
        f"{_fmt(fmt, st[key][0])} ± {_fmt(fmt, st[key][1])} [{_fmt(fmt, st[key][2])}–{_fmt(fmt, st[key][3])}]"
        for key, _, fmt in SEED_TABLE_COLUMNS) + " |")
    return "\n".join(lines)


def seed_summary(per_seed: dict[int, dict]) -> str:
    """One line for the index row (as EXP-010's)."""
    st = seed_stats(per_seed)
    ms = lambda key, fmt: f"{_fmt(fmt, st[key][0])} ± {_fmt(fmt, st[key][1])}"
    falls = f"falls {st['fall_rate'][0]:.3f} ± {st['fall_rate'][1]:.3f}" if st["fall_rate"][3] > 0 else "falls 0.000 all"
    return (f"Seeds {'/'.join(map(str, sorted(per_seed)))} (mean ± SD): planar {ms('planar_error_mps', '{:.4f}')} · "
            f"yaw {ms('yaw_rate_error_radps', '{:.4f}')} · smooth {ms('joint_target_rate_radps', '{:.3f}')} · "
            f"CoT {ms('cost_of_transport', '{:.3f}')}; flicker {ms('flicker_share', 'pct')} · saturation {ms('saturated_share', 'pct')}; {falls}")


def seed_line(seed: int, cmd: str, run_name: str, state: str) -> str:
    return (f"- **Seed {seed}** ({state}): `{cmd}`. Run folder `~/dev/ironbark_runs/logs/rsl_rl/{EXPERIMENT_NAME}/*_{run_name}`, "
            f"console log `~/dev/ironbark_runs/{run_name}.log`.")


def set_seed_line(text: str, seed: int, line: str) -> str:
    """Add or replace this seed's line in the entry's Seed replicates block (made before Results on first use)."""
    if REPLICATE_HEADING not in text:
        old = "\n" + RESULTS_HEADING
        if text.count(old) != 1:
            raise ValueError("no Results heading")
        block = (f"\n{REPLICATE_HEADING}\n\nBrian (2026-11-08): \"{REPLICATE_REQUEST}\" Same weights, task and scoring "
                 f"as seed {SEED}; one run at a time.\n\n{line}\n")
        return text.replace(old, block + old, 1)
    lines = text.split("\n")
    h = lines.index(REPLICATE_HEADING)
    end = next(i for i in range(h + 1, len(lines)) if lines[i].startswith("## "))
    mine = [i for i in range(h, end) if lines[i].startswith(f"- **Seed {seed}** (")]
    if mine:
        lines[mine[0]] = line
    else:
        seeds = [i for i in range(h, end) if lines[i].startswith("- **Seed ")]
        lines.insert(seeds[-1] + 1, line)
    return "\n".join(lines)


def add_seed_table(text: str, table: str) -> str:
    """The mean ± SD table goes after the block's seed lines."""
    lines = text.split("\n")
    h = lines.index(REPLICATE_HEADING)
    end = next(i for i in range(h + 1, len(lines)) if lines[i].startswith("## "))
    last = max(i for i in range(h, end) if lines[i].startswith("- **Seed "))
    lines[last + 1:last + 1] = ["", *table.split("\n")]
    return "\n".join(lines)


def add_to_status(text: str, extra: str) -> str:
    m = re.search(r"^\*\*Status:\*\* (.*?) · \*\*Parent:\*\*", text, flags=re.M)
    if not m:
        raise ValueError("no Status line")
    status = m.group(1)
    tail = "; verdict pending (Brian)"
    status = (status.removesuffix(tail) + f"; {extra}" + tail) if status.endswith(tail) else f"{status}; {extra}"
    return set_status(text, status)


def fill_index_seeds(index: str, exp_id: str, text: str) -> str:
    old = "Verdict pending (Brian) |"
    return _edit_row(index, exp_id, old, f"{text}. {old}")


# ---------- study ----------

def make_sampler(n_startup_trials: int = N_STARTUP_TRIALS, seed: int = SAMPLER_SEED):
    import optuna

    return optuna.samplers.GPSampler(seed=seed, n_startup_trials=n_startup_trials,
                                     constraints_func=lambda t: t.user_attrs["constraints"])


def load_study(storage: str = STORAGE, parent_metrics: dict | None = None):
    """Create on first use: record the start weights and add EXP-010 (seed 42) as a known, already-trained point."""
    import optuna
    from optuna.trial import create_trial

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(study_name=STUDY_NAME, storage=storage, direction="minimize",
                                sampler=make_sampler(), load_if_exists=True)
    if "start_weights" not in study.user_attrs:
        start = config_weights()
        study.set_user_attr("start_weights", start)
        m = parent_metrics if parent_metrics is not None else read_metrics(RUNS_DIR / "logs/rsl_rl" / EXPERIMENT_NAME / PARENT_RUN)
        c = list(constraint_values(m))
        study.add_trial(create_trial(
            params={"feet_air_time": start["feet_air_time"], "action_rate_scale": 1.0, "torques_scale": 1.0},
            distributions=distributions(), value=m["flicker_share"],
            user_attrs={"exp": PARENT, "weights": {k: start[k] for k in TUNED}, "metrics": m, "constraints": c,
                        "note": "known point: trained before the search, not retrained"},
            system_attrs={"constraints": tuple(c)},  # add_trial skips the sampler's after_trial, which would store these
        ))
    return study


def carried_over(trials: list[dict], stage: int = 2) -> list[dict]:
    """Earlier trials inside this stage's action_rate range (the ones at the old 4x ceiling): known points, not retrained."""
    lo, hi = STAGES[stage].action_rate_scale_range
    return [r for r in trials if r["exp"] != PARENT and lo * (1 - 1e-6) <= r["params"]["action_rate_scale"] <= hi * (1 + 1e-6)]


def load_stage2(stage1, storage: str | None):
    """Stage 2's study. Created on first use with the stage-1 trials at the 4x ceiling as known points;
    the GP picks after those plus Stage.random_trials random ones."""
    import optuna
    from optuna.trial import create_trial

    stage = STAGES[2]
    study = optuna.create_study(study_name=stage.study_name, storage=storage, direction="minimize", load_if_exists=True)
    if "start_weights" not in study.user_attrs:
        study.set_user_attr("start_weights", stage1.user_attrs["start_weights"])
        study.set_user_attr("parent_guard", stage1.user_attrs.get("parent_guard"))
        lo, hi = stage.action_rate_scale_range
        known = carried_over(rows(stage1))
        for r in known:
            params = {**r["params"], "action_rate_scale": min(max(r["params"]["action_rate_scale"], lo), hi)}
            attrs = {k: v for k, v in r.items() if k not in ("number", "params")}
            study.add_trial(create_trial(
                params=params, distributions=distributions(2), value=r["metrics"]["flicker_share"],
                user_attrs={**attrs, "note": f"known point: stage-1 trial {r['number']}, not retrained"},
                system_attrs={"constraints": tuple(r["constraints"])},
            ))
        study.set_user_attr("known_points", [r["exp"] for r in known])
    study.sampler = make_sampler(len(study.user_attrs["known_points"]) + stage.random_trials, stage.sampler_seed)
    return study


def existing_stage2(stage1):
    path = STUDY_DIR / (STAGES[2].study_name + ".db")
    return load_stage2(stage1, storage_url(2)) if path.exists() else None


def rows(study) -> list[dict]:
    from optuna.trial import TrialState

    return [{"number": t.number, "params": dict(t.params), **t.user_attrs} for t in study.trials if t.state == TrialState.COMPLETE]


def all_rows(study, stage2=None) -> list[dict]:
    """Every scored trial once, labeled by stage (stage 2's copies of stage-1 trials left out)."""
    out = [{**r, "label": "known point" if r["exp"] == PARENT else trial_label(1, r["number"])} for r in rows(study)]
    if stage2 is not None:
        known = set(stage2.user_attrs.get("known_points", []))
        out += [{**r, "label": trial_label(2, r["number"])} for r in rows(stage2) if r["exp"] not in known]
    return out


def other_trials(study) -> list[dict]:
    from optuna.trial import TrialState

    return [{"number": t.number, "state": t.state.name, **t.user_attrs} for t in study.trials if t.state != TrialState.COMPLETE]


def search_doc(study, now: str, replicates: dict | None = None, stage2=None) -> str:
    start = study.user_attrs["start_weights"]
    s2 = STAGES[2]
    known2 = ", ".join(stage2.user_attrs.get("known_points", [])) if stage2 is not None else "not created yet"
    lines = [
        "# Search: three reward weights under EXP-010's latency (Optuna)",
        "",
        "Generated by `tools/reward_search.py` (rewritten after every trial; the per-trial results are append-only in each experiment's file).",
        "",
        "## Brian's spec (2026-11-08, verbatim)",
        "",
        *[("> " + line) if line else ">" for line in SPEC.split("\n")],
        "",
        "## Brian's change: stage 2 (2026-11-08, verbatim)",
        "",
        f"> {SPEC_2}",
        "",
        "## Setup",
        "",
        f"- Task `{TASK}` ({PARENT}'s conditions: 40 ms command delay, 130 ms round-robin joint readback, actor joint velocity dropped), "
        f"seed {SEED}, {ITERATIONS} iterations, {ENVS} envs. Scored like {PARENT}: scoreboard v1 + `gait_check`, conditions on, eval seed 0.",
        f"- Search space: feet_air_time {FEET_AIR_TIME_RANGE[0]}–{FEET_AIR_TIME_RANGE[1]}; action_rate "
        f"{ACTION_RATE_SCALE_RANGE[0]}–{ACTION_RATE_SCALE_RANGE[1]}x its start weight {_num(start['action_rate'])} "
        f"({_num(start['action_rate'] * ACTION_RATE_SCALE_RANGE[0])} to {_num(start['action_rate'] * ACTION_RATE_SCALE_RANGE[1])}); torques "
        f"{TORQUES_SCALE_RANGE[0]}–{TORQUES_SCALE_RANGE[1]}x its start weight {_num(start['torques'])} "
        f"({_num(start['torques'] * TORQUES_SCALE_RANGE[0])} to {_num(start['torques'] * TORQUES_SCALE_RANGE[1])}). "
        "Every other weight stays as `reward_config.py` had it at the search's start (checked before every trial). "
        "The weights go in as command-line overrides; `reward_config.py` isn't edited.",
        f"- **Stage 2** (Brian, 2026-11-08): action_rate {s2.action_rate_scale_range[0]:g}–{s2.action_rate_scale_range[1]:g}x "
        f"({_num(start['action_rate'] * s2.action_rate_scale_range[0])} to {_num(start['action_rate'] * s2.action_rate_scale_range[1])}); "
        "the other two ranges, the constraints, the objective, the ranking and the guard are unchanged. "
        f"Claude's defaults, for Brian to change: a new study (`{s2.study_name}`; one study's ranges can't change); "
        f"the stage-1 trials at the 4x ceiling go in as known points, not retrained ({known2}); then {s2.random_trials} random "
        f"trials in the new range, then the GP; same sampler and log scale, sampler seed {s2.sampler_seed} "
        f"(seed {SAMPLER_SEED} would repeat stage 1's random draws of the other two weights). Stage-2 trials are labeled \"stage-2 trial N\" "
        "(Optuna's numbering in the new study, the known points first).",
        f"- Constraints (unrounded): servo saturation <= {SATURATION_MAX:.1%} (`gait_check`) and planar error <= {PLANAR_ERROR_MAX_MPS} m/s "
        "(scoreboard v1 overall). Objective: minimize flicker (`gait_check` share of touchdowns after swings < 0.02 s).",
        "- Ranking (Brian): trials that pass both constraints first, lower flicker first; then trials that fail, by how far they miss "
        "(Brian, 2026-11-08): each constraint's overshoot as a fraction of its limit, summed (Claude's reading; the Miss column), "
        "smaller first, flicker breaking a tie.",
        f"- {PARENT} (seed 42, the start weights) is in the study as a known point: trained before the search, not retrained.",
        f"- Reward guard (Brian, 2026-11-08): before each trial trains, `tools/reward_check.py` runs with the trial's weights: standing still "
        f"(zero command, zero action) and {PARENT}'s policy on the command grid (\"walking\"). A negative standing or walking per-step total "
        f"is flagged here, in the trial's entry and in the index; the trial trains anyway. {PARENT}'s row shows the guard at the start weights.",
        "- **Claude's defaults (Brian approved, 2026-11-08):** "
        f"sampler Optuna GPSampler (Gaussian-process Bayesian optimization, constraint-aware), sampler seed {SAMPLER_SEED}; "
        f"the first {N_STARTUP_TRIALS} trials ({PARENT} included) are random, the GP picks after that; "
        f"{'log' if LOG_SCALE else 'linear'} scale on all three ranges.",
        f"- Studies: `~/dev/ironbark_runs/optuna/{STUDY_NAME}.db` (stage 1), `{s2.study_name}.db` (stage 2). "
        "Between trials the driver waits while `optuna/PAUSE` exists and exits if `optuna/STOP` exists.",
        "",
        f"## Ranked trials ({now})",
        "",
        "| Rank | Exp | feet_air_time | action_rate (x start) | torques (x start) | Constraints | Miss | Saturation | Planar err [m/s] | Flicker "
        "| Falls | Yaw err [rad/s] | Joint-target rate [rad/s] | CoT | Swing median [s] | Guard: standing / walking per step |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    trials = all_rows(study, stage2)
    for rank, r in enumerate(ranked(trials), 1):
        w, m = r["weights"], r["metrics"]
        g = study.user_attrs.get("parent_guard") if r["exp"] == PARENT else r.get("guard")
        exp = f"[{r['exp']}]({_entry_name(r['exp'])}) ({r['label']})"
        lines.append(
            f"| {rank} | {exp} | {_num(w['feet_air_time'])} | {_num(w['action_rate'])} ({w['action_rate'] / start['action_rate']:.2f}x) "
            f"| {_num(w['torques'])} ({w['torques'] / start['torques']:.2f}x) | {constraints_cell(m)} | {constraint_miss(m):.1%} "
            f"| {m['saturated_share']:.2%} | {m['planar_error_mps']:.4f} | {m['flicker_share']:.1%} | {m['fall_rate']:.3f} "
            f"| {m['yaw_rate_error_radps']:.3f} | {m['joint_target_rate_radps']:.2f} | {m['cost_of_transport']:.2f} | {m['swing_median_s']:.3f} "
            f"| {guard_short(g)} |")
    others = [(1, o) for o in other_trials(study)] + ([(2, o) for o in other_trials(stage2)] if stage2 is not None else [])
    if others:
        lines += ["", "Trials without scores:", ""]
        lines += [f"- {trial_label(s, o['number'])} ({o.get('exp', 'no entry')}): {o['state'].lower()}"
                  + (f", {o['reason']}" if o.get("reason") else "") for s, o in others]
    lines += replicate_section(trials, replicates or {})
    return "\n".join(lines) + "\n"


def replicate_section(trials: list[dict], replicates: dict) -> list[str]:
    """Brian's picks with their other seeds: mean ± sample SD over every seed scored so far (seed 42 included)."""
    by_exp = {r["exp"]: r for r in trials}
    done = [(exp, reps) for exp, reps in replicates.items() if exp in by_exp and reps]
    if not done:
        return []
    keys = [c for c in SEED_TABLE_COLUMNS if c[0] != "fall_rate"] + [SEED_TABLE_COLUMNS[0]]
    lines = ["", "## Seed replicates (Brian's picks)", "", f"> {REPLICATE_REQUEST}", "",
             "Mean ± sample SD over the seeds scored so far (per-seed rows and ranges are in each entry).", "",
             "| Exp | Seeds | " + " | ".join(c[1] for c in keys) + " |", "|---|---|" + "---|" * len(keys)]
    for exp, reps in done:
        per_seed = {SEED: by_exp[exp]["metrics"], **{int(s): m for s, m in reps.items()}}
        st = seed_stats(per_seed)
        lines.append(f"| [{exp}]({_entry_name(exp)}) | {'/'.join(map(str, sorted(per_seed)))} | "
                     + " | ".join(f"{_fmt(fmt, st[key][0])} ± {_fmt(fmt, st[key][1])}" for key, _, fmt in keys) + " |")
    return lines


def _entry_name(exp_id: str) -> str:
    hits = sorted(EXPERIMENTS.glob(f"{exp_id}-*.md"))
    return hits[0].name if hits else f"{exp_id}.md"


# ---------- side effects ----------

def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=check)


def commit(paths: list[Path], message: str) -> None:
    rel = [p.relative_to(REPO).as_posix() for p in paths]
    for attempt in range(5):  # another session's git command may hold the index lock for a moment
        try:
            git("add", "--", *rel)
            if not git("diff", "--cached", "--quiet", "--", *rel, check=False).returncode:
                return  # nothing changed
            git("commit", "-q", "-m", message + TRAILER, "--", *rel)
            break
        except subprocess.CalledProcessError as e:
            if attempt == 4:
                raise
            print(f"git retry: {e.stderr.strip()}", flush=True)
            time.sleep(10)
    push = git("push", "-q", check=False)
    if push.returncode:
        print(f"git push failed (will retry with the next commit): {push.stderr.strip()}", flush=True)


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")  # the repo is LF-only


def create_entry(stage: int, number: int, weights: dict[str, float], start: dict[str, float]) -> tuple[str, Path]:
    label = trial_label(stage, number)
    title = (f"search {number if stage == 1 else f's{stage}-{number}'}: feet_air_time {weights['feet_air_time']:.2f}, action_rate "
             f"{weights['action_rate'] / start['action_rate']:.2f}x, torques {weights['torques'] / start['torques']:.2f}x")
    out = subprocess.run([PY, "tools/new_experiment.py", title, "--parent", PARENT, "--task", TASK,
                          "--experiment-name", EXPERIMENT_NAME, "--seed", str(SEED), "--iterations", str(ITERATIONS),
                          "--envs", str(ENVS)], cwd=REPO, capture_output=True, text=True, check=True).stdout
    path = REPO / re.search(r"created (\S+\.md)", out).group(1)
    exp_id = path.name[:7]
    cmd = "python " + " ".join(train_args(exp_id, weights))
    write(path, fill_entry(path.read_text(encoding="utf-8"), label, weights, start, cmd))
    write(INDEX, fill_index_change(INDEX.read_text(encoding="utf-8"), exp_id, label, weights, start))
    return exp_id, path


def train(run_name: str, weights: dict[str, float], seed: int = SEED) -> tuple[Path, int]:
    log = RUNS_DIR / f"{run_name}.log"
    t0 = time.time()
    with log.open("w", encoding="utf-8") as f:
        rc = subprocess.run([PY, *train_args(run_name, weights, seed)], cwd=REPO, stdout=f, stderr=subprocess.STDOUT).returncode
    minutes = round((time.time() - t0) / 60)
    runs = sorted((RUNS_DIR / "logs/rsl_rl" / EXPERIMENT_NAME).glob(f"*_{run_name}"))
    text = log.read_text(encoding="utf-8", errors="replace")
    if rc or "Traceback" in text or not runs or not (runs[-1] / CHECKPOINT).exists():
        raise TrialFailed(f"training: exit {rc}, traceback {'Traceback' in text}, run {runs[-1] if runs else None} (log {log})")
    run = runs[-1]
    trained = saved_weights((run / "params" / "env.yaml").read_text(encoding="utf-8"))
    if any(abs(trained[k] - weights[k]) > 1e-9 * max(1.0, abs(weights[k])) for k in TUNED):
        raise TrialFailed(f"run trained with {trained}, asked for {weights}")
    return run, minutes


def score(exp_id: str, run: Path, log_name: str | None = None) -> dict[str, float]:
    """Score a run and append the results to exp_id's entry."""
    ck = str(run / CHECKPOINT)
    for tool, args in (("eval", [TASK, "--checkpoint", ck]), ("gait_check", [TASK, "--checkpoint", ck]), ("term_curves", [str(run)])):
        log = RUNS_DIR / f"{log_name or exp_id}.{tool}.log"
        with log.open("w", encoding="utf-8") as f:
            rc = subprocess.run([PY, f"tools/{tool}.py", *args, "--exp", exp_id], cwd=REPO, stdout=f, stderr=subprocess.STDOUT).returncode
        if rc:
            raise TrialFailed(f"{tool}: exit {rc} (log {log})")
    return read_metrics(run)


def guard(name: str, weights: dict[str, float]) -> dict:
    """tools/reward_check.py with these weights; its exit code 1 only means flagged."""
    out, log = RUNS_DIR / f"{name}.guard.json", RUNS_DIR / f"{name}.guard.log"
    out.unlink(missing_ok=True)
    args = [PY, "tools/reward_check.py", TASK, "--checkpoint", str(PARENT_CHECKPOINT), "--json", str(out)]
    for k in TUNED:
        args += ["--weight", f"{k}={weights[k]:.6g}"]
    with log.open("w", encoding="utf-8") as f:
        rc = subprocess.run(args, cwd=REPO, stdout=f, stderr=subprocess.STDOUT).returncode
    if rc not in (0, 1) or not out.exists():
        raise TrialFailed(f"guard: exit {rc} (log {log})")
    return json.loads(out.read_text(encoding="utf-8"))


def wait_while_paused() -> None:
    if PAUSE_FILE.exists():
        print(f"PAUSED {datetime.datetime.now():%F %T}", flush=True)
        while PAUSE_FILE.exists() and not STOP_FILE.exists():
            time.sleep(30)  # PC-side wall clock is fine (the no-wall-clock rule is Pi-side)
        print(f"RESUMED {datetime.datetime.now():%F %T}", flush=True)


def load_replicates() -> dict:
    return json.loads(REPLICATES.read_text(encoding="utf-8")) if REPLICATES.exists() else {}


def refresh_doc(study, stage2=None) -> None:
    write(SEARCH_DOC, search_doc(study, f"{datetime.datetime.now():%Y-%m-%d %H:%M}", load_replicates(), stage2))


def run_loop(stage: int = LATEST_STAGE) -> int:
    from optuna.trial import TrialState

    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    study1 = load_study()
    stage2 = load_stage2(study1, storage_url(2)) if stage == 2 else existing_stage2(study1)
    study = study1 if stage == 1 else stage2
    start = study.user_attrs["start_weights"]
    for t in study.trials:  # a trial left RUNNING by a killed driver: close it so the sampler ignores it
        if t.state == TrialState.RUNNING:
            study.tell(t.number, state=TrialState.FAIL)
            print(f"closed interrupted trial {t.number} ({t.user_attrs.get('exp')})", flush=True)
    if "parent_guard" not in study.user_attrs:  # the guard at the start weights, for comparison
        g = guard(f"{PARENT}-search-start", {k: start[k] for k in TUNED})
        study.set_user_attr("parent_guard", g)
        print(f"GUARD {PARENT} {guard_short(g)}", flush=True)
    refresh_doc(study1, stage2)
    commit([SEARCH_DOC], f"Search page: stage {stage} (Optuna over feet_air_time, action_rate, torques under EXP-010's latency)")
    while True:
        wait_while_paused()
        if STOP_FILE.exists():
            print(f"STOPPED {datetime.datetime.now():%F %T}", flush=True)
            return 0
        now_weights = config_weights()
        if now_weights != start:
            print(f"FAIL reward_config.py changed since the search started: {now_weights} vs {start}", flush=True)
            return 1
        trial = study.ask(distributions(stage))
        label = trial_label(stage, trial.number)
        weights = trial_weights(trial.params, start)
        trial.set_user_attr("weights", weights)
        exp_id, path = create_entry(stage, trial.number, weights, start)
        trial.set_user_attr("exp", exp_id)
        try:
            g = guard(exp_id, weights)
            trial.set_user_attr("guard", g)
            write(path, add_guard_line(path.read_text(encoding="utf-8"), guard_line(g)))
            print(f"GUARD {exp_id} {guard_short(g)}", flush=True)
            commit([path, INDEX], f"Add {exp_id} entry (search {label}: {change_text(weights, start)})"
                                  + (f"; guard FLAG: {', '.join(guard_flags(g))}" if guard_flags(g) else ""))
            print(f"START {exp_id} {label} {weights} {datetime.datetime.now():%F %T}", flush=True)
            run, minutes = train(exp_id, weights)
            print(f"TRAINED {exp_id} {minutes} min {run.name}", flush=True)
            m = score(exp_id, run)
        except TrialFailed as e:
            trial.set_user_attr("reason", str(e))
            study.tell(trial, state=TrialState.FAIL)
            write(path, set_status(path.read_text(encoding="utf-8"), f"search {label} (Optuna); failed: {e}"))
            refresh_doc(study1, stage2)
            commit([path, INDEX, SEARCH_DOC], f"{exp_id}: search {label} failed")
            print(f"FAIL {exp_id} {e}", flush=True)
            return 1
        trial.set_user_attr("metrics", m)
        trial.set_user_attr("constraints", list(constraint_values(m)))
        trial.set_user_attr("run", run.name)
        trial.set_user_attr("minutes", minutes)
        study.tell(trial, m["flicker_share"])
        flagged = f"; guard FLAG ({', '.join(guard_flags(g))} total negative)" if guard_flags(g) else ""
        status = (f"search {label} (Optuna); trained {datetime.date.today()} (seed {SEED}, {ITERATIONS} iterations, "
                  f"{minutes} min, no crash), scored with the staleness and delay on; {constraints_text(m)}{flagged}; verdict pending (Brian)")
        write(path, set_status(path.read_text(encoding="utf-8"), status))
        write(INDEX, fill_index_verdict(INDEX.read_text(encoding="utf-8"), exp_id,
                                        f"{summary_text(m)}; {constraints_text(m)}{flagged}. Verdict pending (Brian)"))
        refresh_doc(study1, stage2)
        commit([path, INDEX, SEARCH_DOC], f"Score {exp_id} (search {label}): flicker {m['flicker_share']:.1%}, "
                                          f"saturation {m['saturated_share']:.2%}, planar {m['planar_error_mps']:.3f}; {constraints_text(m)}")
        print(f"SCORED {exp_id} flicker {m['flicker_share']:.4f} sat {m['saturated_share']:.4f} planar {m['planar_error_mps']:.4f} "
              f"{constraints_text(m)} {datetime.datetime.now():%F %T}", flush=True)


def replicate_loop(exp_ids: list[str], seeds: list[int]) -> int:
    """Brian's picks, re-trained with other seeds one at a time (same weights, task and scoring); resumable."""
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    study = load_study()
    stage2 = existing_stage2(study)
    by_exp = {r["exp"]: r for r in all_rows(study, stage2)}
    missing = [e for e in exp_ids if e not in by_exp or e == PARENT]
    if missing or not seeds or SEED in seeds:
        print(f"FAIL not scored search trials: {missing}; seeds {seeds} (seed {SEED} is the search's own)", flush=True)
        return 1
    for exp in exp_ids:
        weights, path = by_exp[exp]["weights"], EXPERIMENTS / _entry_name(exp)
        for seed in seeds:
            if str(seed) in load_replicates().get(exp, {}):
                continue  # done before a restart
            wait_while_paused()
            if STOP_FILE.exists():
                print(f"STOPPED {datetime.datetime.now():%F %T}", flush=True)
                return 0
            name, today = f"{exp}-s{seed}", datetime.date.today()
            cmd = "python " + " ".join(train_args(name, weights, seed))
            write(path, set_seed_line(path.read_text(encoding="utf-8"), seed, seed_line(seed, cmd, name, f"training {today}")))
            commit([path], f"{exp}: seed {seed} training (Brian's pick for seeds {'/'.join(map(str, seeds))})")
            print(f"START {name} {weights} {datetime.datetime.now():%F %T}", flush=True)
            try:
                run, minutes = train(name, weights, seed)
                print(f"TRAINED {name} {minutes} min {run.name}", flush=True)
                m = score(exp, run, name)
            except TrialFailed as e:
                write(path, set_seed_line(path.read_text(encoding="utf-8"), seed, seed_line(seed, cmd, name, f"failed {today}: {e}")))
                commit([path], f"{name}: seed replicate failed")
                print(f"FAIL {name} {e}", flush=True)
                return 1
            reps = load_replicates()
            reps.setdefault(exp, {})[str(seed)] = {**m, "run": run.name, "minutes": minutes}
            write(REPLICATES, json.dumps(reps, indent=1))
            text = set_seed_line(path.read_text(encoding="utf-8"), seed,
                                 seed_line(seed, cmd, name, f"trained and scored {today}, {minutes} min, no crash"))
            if all(str(s) in reps[exp] for s in seeds):
                per_seed = {SEED: by_exp[exp]["metrics"], **{int(s): v for s, v in reps[exp].items()}}
                text = add_seed_table(text, seed_table(per_seed))
                text = add_to_status(text, f"seeds {'/'.join(map(str, seeds))} trained and scored {today} (Brian's pick)")
                write(INDEX, fill_index_seeds(INDEX.read_text(encoding="utf-8"), exp, seed_summary(per_seed)))
            write(path, text)
            refresh_doc(study, stage2)
            commit([path, INDEX, SEARCH_DOC], f"Score {name} (seed replicate, Brian's pick): flicker {m['flicker_share']:.1%}, "
                                              f"saturation {m['saturated_share']:.2%}, planar {m['planar_error_mps']:.3f}")
            print(f"SCORED {name} flicker {m['flicker_share']:.4f} sat {m['saturated_share']:.4f} planar {m['planar_error_mps']:.4f} "
                  f"{datetime.datetime.now():%F %T}", flush=True)
    print(f"ALL DONE {datetime.datetime.now():%F %T}", flush=True)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=("run", "table", "replicate"))
    p.add_argument("exps", nargs="*", help="replicate: the search trials to re-run, e.g. EXP-017 EXP-018 EXP-015")
    p.add_argument("--seeds", type=int, nargs="+", default=[43, 44], help="replicate: the other seeds")
    p.add_argument("--stage", type=int, choices=sorted(STAGES), default=LATEST_STAGE, help="run: which stage's study")
    args = p.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if args.mode == "table":
        STUDY_DIR.mkdir(parents=True, exist_ok=True)
        study = load_study()
        refresh_doc(study, existing_stage2(study))
        print(f"wrote {SEARCH_DOC.relative_to(REPO)}")
        return
    if args.mode == "replicate":
        sys.exit(replicate_loop(args.exps, args.seeds))
    sys.exit(run_loop(args.stage))


if __name__ == "__main__":
    main()
