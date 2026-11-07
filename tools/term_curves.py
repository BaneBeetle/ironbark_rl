"""Per-term reward curves and episode endings from a run's TensorBoard log, as markdown.

  python tools/term_curves.py <run folder> [--exp EXP-004]

Reads only Episode_Metrics/reward/* (the per-step contribution of each of Brian's terms, logged by
ironbark_rl.reward_audit), Train/mean_episode_length and Episode_Termination/*. Luwu's reward terms
are never read. Each value is the mean over the iterations within +-WINDOW of the column's iteration.
Endings: each cause's share of all episode endings near the last iteration.
CPU only (reads the event file), so it's safe to run during training.
--exp appends a dated block to that experiment's Results (append-only).
"""

import argparse
import datetime
import sys
from pathlib import Path

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO / "docs" / "experiments"
RESULTS_ANCHOR = "## What I saw"
ITERATIONS = (0, 100, 400, 1499)
WINDOW = 10
REWARD_PREFIX = "Episode_Metrics/reward/"
EPISODE_LENGTH = "Train/mean_episode_length"
TERMINATION_PREFIX = "Episode_Termination/"


def _fmt(v: float) -> str:
    """Fixed 5 decimals, but scientific for tiny nonzero values, so they never print as 0."""
    return f"{v:+.1e}" if v != 0 and abs(v) < 5e-5 else f"{v:+.5f}"


def _mean_near(ea: EventAccumulator, tag: str, iteration: int) -> float:
    values = [e.value for e in ea.Scalars(tag) if abs(e.step - iteration) <= WINDOW]
    return sum(values) / len(values) if values else float("nan")


def curves(run_dir: Path) -> str:
    ea = EventAccumulator(str(run_dir), size_guidance={"scalars": 0})
    ea.Reload()
    tags = ea.Tags()["scalars"]
    last = max(e.step for e in ea.Scalars(EPISODE_LENGTH))
    columns = [i for i in ITERATIONS if i < last] + [last]
    header = "| | " + " | ".join(f"iter {i}" for i in columns) + " |\n|---|" + "---|" * len(columns) + "\n"
    rows = []
    reward_tags = sorted((t for t in tags if t.startswith(REWARD_PREFIX)), key=lambda t: -abs(_mean_near(ea, t, last)))
    for tag in reward_tags:  # biggest contribution at the end first
        rows.append(f"| {tag.removeprefix(REWARD_PREFIX)} | " + " | ".join(_fmt(_mean_near(ea, tag, i)) for i in columns) + " |")
    rows.append(f"| episode length (steps) | " + " | ".join(f"{_mean_near(ea, EPISODE_LENGTH, i):.0f}" for i in columns) + " |")
    endings = {t.removeprefix(TERMINATION_PREFIX): _mean_near(ea, t, last) for t in tags if t.startswith(TERMINATION_PREFIX)}
    total = sum(endings.values()) or 1.0
    ending_text = ", ".join(f"{name} {100 * v / total:.1f}%" for name, v in sorted(endings.items()))
    return (header + "\n".join(rows) + f"\n\nEpisode endings near iteration {last}: {ending_text}.")


def append_to_experiment(exp_id: str, run_dir: Path, text: str) -> Path:
    matches = sorted(EXPERIMENTS_DIR.glob(f"{exp_id}-*.md"))
    if len(matches) != 1:
        sys.exit(f"expected one file for {exp_id}, found {[m.name for m in matches]}")
    path = matches[0]
    doc = path.read_bytes().decode("utf-8")
    block = (f"**{datetime.date.today().isoformat()}, training curves (TensorBoard).** Run `{run_dir.name}`. Reward rows: each "
             f"term's per-step contribution (weight × value × dt), mean over ±{WINDOW} iterations.\n\n{text}\n\n")
    if RESULTS_ANCHOR not in doc:
        sys.exit(f"{path.name} has no '{RESULTS_ANCHOR}' heading to insert above")
    path.write_bytes(doc.replace(RESULTS_ANCHOR, block + RESULTS_ANCHOR, 1).encode("utf-8"))
    return path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--exp", default=None)
    args = p.parse_args()
    text = curves(args.run_dir)
    print(text)
    if args.exp:
        print("appended to", append_to_experiment(args.exp, args.run_dir, text))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
