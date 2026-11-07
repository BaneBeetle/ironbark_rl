"""Gait diagnostics next to the scoreboard: servo saturation and swing times (not part of metrics.py).

  python tools/gait_check.py IronBark-S2-Walk-Flat --checkpoint <run>/model_1499.pt [--exp EXP-002]

Brian's EXP-003 hypothesis names two numbers the frozen scoreboard doesn't have: servo saturation %
and swing-time p10 (contact flicker). This runs a checkpoint under scoreboard conditions (pinned
COMMAND_GRID, play config, terminations off, fixed seed, first SKIP_S seconds skipped) and reports:
- saturation: share of servo-steps whose requested (pre-clip) torque exceeds the servo cap;
- swing time at touchdown: p10 / median / p90, and the share of touchdowns after a swing shorter
  than FLICKER_SWING_S (counted as flicker);
- touchdowns per foot per second.
Reads simulator tensors only, never the task's reward. Run it only while nothing is training.
--exp appends a dated block to that experiment's Results (append-only), labeled as diagnostics.
"""

import argparse
import contextlib
import datetime
import io
import sys
from pathlib import Path

import numpy as np
import torch

from ironbark_rl import evaluation
from ironbark_rl.brian import metrics

REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO / "docs" / "experiments"
RESULTS_ANCHOR = "## What I saw"
SKIP_S = 1.0  # the drop from the spawn height and the first steps aren't walking
# Flicker cutoff (Brian, 2026-11-07): one 0.02 s policy step. A swing that short is faster than
# the policy can deliberately control, so it can't be a real step.
FLICKER_SWING_S = 0.02
FEET_SENSOR = "feet_ground_contact"


def diagnose(task: str, checkpoint: Path, episodes_per_command: int, seconds: float, seed: int) -> dict:
    grid = np.asarray(metrics.COMMAND_GRID, dtype=float)  # (C, 3)
    commands = np.repeat(grid, episodes_per_command, axis=0)  # (C * E, 3)
    with contextlib.redirect_stdout(io.StringIO()):  # mjlab's startup tables, the network printout
        env, _ = evaluation.make_pinned_command_env(task, commands, seed)
        policy = evaluation.load_policy(task, env, checkpoint)
    base = env.unwrapped
    robot, sim, feet = base.scene["robot"], base.sim, base.scene[FEET_SENSOR]
    ids = robot.indexing.ctrl_ids
    lo, hi = (torch.as_tensor(x, dtype=torch.float32, device=base.device) for x in sim.mj_model.actuator_ctrlrange[ids.cpu()].T)
    cap = float(sim.mj_model.actuator_forcerange[ids.cpu(), 1].max())
    dt = base.step_dt
    saturated, servo_steps, swings, touchdowns, dog_steps = 0, 0, [], 0, 0
    with torch.no_grad(), contextlib.redirect_stdout(io.StringIO()):
        env.reset()
        evaluation.pin_commands(env, commands)
        obs = env.get_observations()
        for step in range(round(seconds / dt)):
            obs, *_ = env.step(policy(obs))
            if step * dt < SKIP_S:
                continue
            kp = sim.model.actuator_gainprm[:, ids, 0]  # (N, 12)
            b = sim.model.actuator_biasprm[:, ids, :3]  # (N, 12, 3)
            q, qd = robot.data.joint_pos, robot.data.joint_vel  # (N, 12)
            requested = kp * sim.data.ctrl[:, ids].clamp(lo, hi) + b[..., 0] + b[..., 1] * q + b[..., 2] * qd  # (N, 12)
            saturated += int((requested.abs() > cap).sum())
            servo_steps += requested.numel()
            first = feet.compute_first_contact(dt)  # (N, 4)
            swings.append(feet.data.last_air_time[first].cpu().numpy())
            touchdowns += int(first.sum())
            dog_steps += len(commands)
    env.close()
    swings = np.concatenate(swings) if swings else np.array([])
    return {
        "date": datetime.date.today().isoformat(), "checkpoint": str(checkpoint), "episodes_per_command": episodes_per_command,
        "seconds": seconds, "seed": seed, "servo_cap_nm": cap,
        "saturated_share": saturated / max(servo_steps, 1),
        "swing_p10_s": float(np.percentile(swings, 10)) if swings.size else float("nan"),
        "swing_median_s": float(np.median(swings)) if swings.size else float("nan"),
        "swing_p90_s": float(np.percentile(swings, 90)) if swings.size else float("nan"),
        "flicker_share": float((swings < FLICKER_SWING_S).mean()) if swings.size else float("nan"),
        "touchdowns_per_foot_per_s": touchdowns / max(dog_steps, 1) / 4 / dt,
    }


def markdown(r: dict) -> str:
    return ("| Servo saturation | Swing p10 [s] | Swing median [s] | Swing p90 [s] | Flicker touchdowns (< "
            f"{FLICKER_SWING_S:g} s) | Touchdowns / foot / s |\n|---|---|---|---|---|---|\n"
            f"| {100 * r['saturated_share']:.2f}% | {r['swing_p10_s']:.3f} | {r['swing_median_s']:.3f} | {r['swing_p90_s']:.3f} | "
            f"{100 * r['flicker_share']:.1f}% | {r['touchdowns_per_foot_per_s']:.2f} |")


def append_to_experiment(exp_id: str, r: dict, table: str) -> Path:
    matches = sorted(EXPERIMENTS_DIR.glob(f"{exp_id}-*.md"))
    if len(matches) != 1:
        sys.exit(f"expected one file for {exp_id}, found {[m.name for m in matches]}")
    path = matches[0]
    text = path.read_bytes().decode("utf-8")
    block = (f"**{r['date']}, gait diagnostics (not scoreboard).** Run `{Path(r['checkpoint']).parent.name}`, checkpoint "
             f"`{Path(r['checkpoint']).name}`, {r['episodes_per_command']} dogs × {r['seconds']:g} s per command (first {SKIP_S:g} s "
             f"skipped), seed {r['seed']}. Saturation: requested torque above the {r['servo_cap_nm']:.2f} N·m cap.\n\n{table}\n\n")
    if RESULTS_ANCHOR not in text:
        sys.exit(f"{path.name} has no '{RESULTS_ANCHOR}' heading to insert above")
    path.write_bytes(text.replace(RESULTS_ANCHOR, block + RESULTS_ANCHOR, 1).encode("utf-8"))
    return path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--exp", default=None, help="experiment ID to append the diagnostics to")
    p.add_argument("--episodes-per-command", type=int, default=evaluation.EPISODES_PER_COMMAND)
    p.add_argument("--seconds", type=float, default=evaluation.EVAL_SECONDS)
    p.add_argument("--seed", type=int, default=evaluation.EVAL_SEED)
    args = p.parse_args()
    r = diagnose(args.task, args.checkpoint, args.episodes_per_command, args.seconds, args.seed)
    table = markdown(r)
    print(table)
    if args.exp:
        print("appended to", append_to_experiment(args.exp, r, table))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
