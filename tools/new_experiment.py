"""Create the next experiment entry in docs/experiments/ and print its train command.

  python tools/new_experiment.py "reward v1: velocity tracking only" --parent EXP-000
  python tools/new_experiment.py "seed check" --parent EXP-001 --seed 43

Fills Setup from git and the arguments, adds a row to the index in
docs/experiments/README.md, and tags the run with the experiment ID (--agent.run-name)
so its log folder is <timestamp>_EXP-NNN. Uses only the standard library.
"""

import argparse
import datetime
import re
import subprocess
from pathlib import Path
from string import Template

REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO / "docs" / "experiments"
TEMPLATE_PATH = EXPERIMENTS_DIR / "TEMPLATE.md"
INDEX_PATH = EXPERIMENTS_DIR / "README.md"
ID_PATTERN = re.compile(r"^EXP-(\d{3})")
RUNS_LOG_ROOT = "~/dev/ironbark_runs/logs/rsl_rl"

DEFAULT_TASK = "IronBark-S2-Walk-Flat"
DEFAULT_EXPERIMENT_NAME = "ironbark_s2_walk"  # rl_cfg experiment_name for DEFAULT_TASK
DEFAULT_SEED = 42
DEFAULT_ITERATIONS = 1500
DEFAULT_ENVS = 4096


def _next_id() -> str:
    numbers = [int(m.group(1)) for p in EXPERIMENTS_DIR.glob("EXP-*.md") if (m := ID_PATTERN.match(p.name))]
    return f"EXP-{max(numbers, default=-1) + 1:03d}"


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]


def _git_commit() -> str:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    return f"{commit}-dirty" if dirty else commit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("title")
    parser.add_argument("--parent", default="none")
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT_NAME, help="rl_cfg experiment_name of the task")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--envs", type=int, default=DEFAULT_ENVS)
    args = parser.parse_args()

    exp_id = _next_id()
    path = EXPERIMENTS_DIR / f"{exp_id}-{_slug(args.title)}.md"
    train_cmd = (
        f"python tools/run.py train {args.task} --env.scene.num-envs {args.envs} "
        f"--agent.max-iterations {args.iterations} --agent.seed {args.seed} --agent.run-name {exp_id}"
    )
    fields = {
        "exp_id": exp_id,
        "title": args.title,
        "parent": args.parent,
        "date": datetime.date.today().isoformat(),
        "commit": _git_commit(),
        "task": args.task,
        "seed": args.seed,
        "iterations": args.iterations,
        "envs": args.envs,
        "train_cmd": train_cmd,
        "run_glob": f"{RUNS_LOG_ROOT}/{args.experiment_name}/*_{exp_id}",
    }
    # newline="\n": the repo is LF-only (.gitattributes); Windows would otherwise write CRLF.
    path.write_text(Template(TEMPLATE_PATH.read_text(encoding="utf-8")).substitute(fields), encoding="utf-8", newline="\n")

    row = f"| [{exp_id}]({path.name}) | {fields['date']} | {args.title} | vs. {args.parent}: _fill in_ | _pending_ |\n"
    with INDEX_PATH.open("a", encoding="utf-8", newline="\n") as index:
        index.write(row)

    print(f"created {path.relative_to(REPO)}")
    print("write the hypothesis first, then train with:")
    print(f"  {train_cmd}")


if __name__ == "__main__":
    main()
