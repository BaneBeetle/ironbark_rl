"""Fall-on-purpose guard: mean per-step reward, total and per term, in fixed scenarios.

  python tools/reward_check.py IronBark-S2-Walk-Flat-Brian
  python tools/reward_check.py IronBark-S2-Walk-Flat-Brian --checkpoint <EXP-002 run>/model_1499.pt

Scenarios (scoreboard conditions: play config, pinned commands, terminations off, fixed seed):
  (a) standing still: zero command, zero action (the default pose)
  (b) only with --checkpoint: that policy on metrics.COMMAND_GRID; the task must share the
      checkpoint's observations and actions (IronBark-S2-Walk-Flat-Brian does: only the reward differs)
A negative mean total is flagged: if a typical step loses reward, ending the episode early
pays. Reports numbers only; weights are Brian's (ironbark_rl/brian/reward_config.py).
Meant for Brian's reward tasks: on the baseline task it would list Luwu's reward terms.
Run it only while nothing is training.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

from ironbark_rl import evaluation, reward_audit
from ironbark_rl.brian import metrics

STANDING_DOGS = 32


def report(title: str, means: dict[str, float]) -> None:
    print(f"\n{title}\n  {'term':22s} {'per step':>8s}  share")
    print("\n".join(reward_audit.summary_lines(means)))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task")
    p.add_argument("--checkpoint", type=Path, default=None, help="policy for scenario (b), e.g. the EXP-002 baseline")
    p.add_argument("--episodes-per-command", type=int, default=evaluation.EPISODES_PER_COMMAND)
    p.add_argument("--seconds", type=float, default=evaluation.EVAL_SECONDS)
    p.add_argument("--seed", type=int, default=evaluation.EVAL_SEED)
    args = p.parse_args()

    flagged = False

    standing = np.zeros((STANDING_DOGS, 3))
    env, _ = evaluation.make_pinned_command_env(args.task, standing, args.seed)
    zero_action = lambda obs: torch.zeros(env.unwrapped.action_space.shape, device=env.unwrapped.device)  # (N, J)
    means, _ = reward_audit.mean_contributions(env, standing, zero_action, args.seconds)
    env.close()
    report(f"{args.task} (a) standing still, zero command: {STANDING_DOGS} dogs x {args.seconds:.0f} s", means)
    flagged |= reward_audit.is_negative(means[reward_audit.TOTAL])

    if args.checkpoint is not None:
        grid = np.asarray(metrics.COMMAND_GRID, dtype=float)  # (C, 3)
        commands = np.repeat(grid, args.episodes_per_command, axis=0)  # (C * E, 3)
        env, _ = evaluation.make_pinned_command_env(args.task, commands, args.seed)
        policy = evaluation.load_policy(args.task, env, args.checkpoint)
        means, per_dog_total = reward_audit.mean_contributions(env, commands, policy, args.seconds)
        env.close()
        report(f"{args.task} (b) {args.checkpoint} on the command grid: {len(commands)} dogs x {args.seconds:.0f} s", means)
        flagged |= reward_audit.is_negative(means[reward_audit.TOTAL])
        print("\n  mean per-step total by command (vx, vy, wz):")
        for k, command in enumerate(grid):
            total = float(per_dog_total[k * args.episodes_per_command:(k + 1) * args.episodes_per_command].mean())
            mark = "  <-- NEGATIVE" if reward_audit.is_negative(total) else ""
            print(f"    ({command[0]:+.2f}, {command[1]:+.2f}, {command[2]:+.2f})  {total:+.5f}{mark}")

    print("\nFLAG: a mean per-step total is negative (see above)." if flagged else "\nOK: every mean per-step total is >= 0.")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
