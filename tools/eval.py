"""Score a checkpoint on the frozen scoreboard (ironbark_rl/brian/metrics.py).

  python tools/eval.py IronBark-S2-Walk-Flat                          # newest checkpoint
  python tools/eval.py IronBark-S2-Walk-Flat --checkpoint path/model_1499.pt --exp EXP-000

Conditions (see ironbark_rl/evaluation.py): every COMMAND_GRID command x 32 dogs x 10 s,
commands pinned, start from rest, no pushes or noise, falls judged by metrics.is_fallen,
fixed seed. Writes eval_<scoreboard>_<checkpoint>.json next to the checkpoint; --exp
appends the table (dated) to that experiment's Results section.
"""

import argparse
import json
import sys
from pathlib import Path

from ironbark_rl.evaluation import EPISODES_PER_COMMAND, EVAL_SECONDS, EVAL_SEED, evaluate, markdown_table
from ironbark_rl.runs import latest_checkpoint

REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO / "docs" / "experiments"
RESULTS_ANCHOR = "## What I saw"  # results are inserted just above this heading


def append_to_experiment(exp_id: str, result: dict, table: str) -> Path:
    matches = sorted(EXPERIMENTS_DIR.glob(f"{exp_id}-*.md"))
    if len(matches) != 1:
        sys.exit(f"expected one file for {exp_id}, found {[m.name for m in matches]}")
    path = matches[0]
    text = path.read_text(encoding="utf-8")
    block = (
        f"**{result['date']}, scoreboard {result['scoreboard_version']}.** Checkpoint "
        f"`{Path(result['checkpoint']).name}` (iteration {result['iteration']}), "
        f"{result['episodes_per_command']} dogs × {result['seconds']:g} s per command, seed {result['seed']}, "
        f"mass {result['mass_kg']:.3f} kg. Smoothness and CoT use only episodes that never fell; "
        f"CoT is NaN by design where there's no ground speed (standing, turning in place).\n\n{table}\n"
    )
    if RESULTS_ANCHOR not in text:
        sys.exit(f"{path.name} has no '{RESULTS_ANCHOR}' heading to insert above")
    path.write_text(text.replace(RESULTS_ANCHOR, block + RESULTS_ANCHOR, 1), encoding="utf-8", newline="\n")
    return path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task")
    p.add_argument("--checkpoint", type=Path, default=None, help="default: newest run's highest-iteration checkpoint")
    p.add_argument("--exp", default=None, help="experiment ID to append results to, e.g. EXP-000")
    p.add_argument("--episodes-per-command", type=int, default=EPISODES_PER_COMMAND)
    p.add_argument("--seconds", type=float, default=EVAL_SECONDS)
    p.add_argument("--seed", type=int, default=EVAL_SEED)
    args = p.parse_args()

    checkpoint = args.checkpoint or latest_checkpoint(args.task)
    if checkpoint is None:
        sys.exit(f"no checkpoint found for {args.task}")
    result = evaluate(args.task, checkpoint, args.episodes_per_command, args.seconds, args.seed)
    table = markdown_table(result)
    print(f"\n{args.task} · {Path(checkpoint).name} · scoreboard {result['scoreboard_version']}\n")
    print(table)

    out = Path(checkpoint).with_name(f"eval_{result['scoreboard_version']}_{Path(checkpoint).stem}.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"saved {out}")
    if args.exp:
        print(f"appended to {append_to_experiment(args.exp, result, table).relative_to(REPO)}")


if __name__ == "__main__":
    main()
