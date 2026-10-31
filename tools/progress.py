"""Score every saved checkpoint of a training run on the scoreboard, and chart the improvement.

  python tools/progress.py IronBark-S2-Walk-Flat --run-dir <run folder> --label "EXP-000 (Luwu reward)"
  python tools/progress.py --chart <run>/progress_v1.json [<other run>/progress_v1.json ...]

Uses 8 dogs per command (tools/eval.py uses 32) so a 16-checkpoint sweep takes minutes;
official numbers for an experiment still come from tools/eval.py. Writes
<run folder>/progress_<scoreboard>.json, and the chart to docs/figures/.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIGURES_DIR = REPO / "docs" / "figures"
PROGRESS_EPISODES_PER_COMMAND = 8

# Reference palette (dataviz skill), validated light-mode: slot 1 blue, slot 2 orange, ...
SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")
SURFACE, TEXT_PRIMARY, TEXT_SECONDARY, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e7e6e2"
PANELS = (("fall_rate", "Fall rate", "fraction of dogs that fell"),
          ("planar_error_mps", "Speed-tracking error", "m/s, lower is better"))


def sweep(task: str, run_dir: Path, label: str) -> Path:
    from ironbark_rl.evaluation import checkpoint_iteration, evaluate_many

    checkpoints = sorted(run_dir.glob("model_*.pt"), key=checkpoint_iteration)
    if not checkpoints:
        sys.exit(f"no checkpoints in {run_dir}")
    print(f"scoring {len(checkpoints)} checkpoints of {run_dir.name}")
    results = evaluate_many(task, checkpoints, episodes_per_command=PROGRESS_EPISODES_PER_COMMAND)
    points = [{"iteration": r["iteration"], **r["overall"]} for r in results]
    for p in points:
        print(f"  iter {p['iteration']:5d}  falls {p['fall_rate']:.3f}  planar err {p['planar_error_mps']:.3f} m/s")
    out = run_dir / f"progress_{results[0]['scoreboard_version']}.json"
    out.write_text(json.dumps({
        "label": label, "task": task, "run_dir": str(run_dir), "scoreboard_version": results[0]["scoreboard_version"],
        "episodes_per_command": PROGRESS_EPISODES_PER_COMMAND, "points": points,
    }, indent=2), encoding="utf-8")
    print(f"saved {out}")
    return out


def chart(progress_files: list[Path], out: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in progress_files]
    fig, axes = plt.subplots(1, len(PANELS), figsize=(11, 3.8), dpi=150, facecolor=SURFACE)
    for ax, (key, title, unit) in zip(axes, PANELS):
        ax.set_facecolor(SURFACE)
        for color, run in zip(SERIES_COLORS, runs):
            its = [p["iteration"] for p in run["points"]]
            vals = [p[key] for p in run["points"]]
            ax.plot(its, vals, color=color, linewidth=2, marker="o", markersize=5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, label=run["label"], solid_capstyle="round")
            if len(runs) > 1:  # direct label at the line's end, in text ink
                ax.annotate(run["label"], (its[-1], vals[-1]), xytext=(6, 0), textcoords="offset points",
                            va="center", fontsize=8, color=TEXT_SECONDARY)
        ax.set_title(f"{title}  ({unit})", loc="left", fontsize=10, color=TEXT_PRIMARY)
        ax.set_xlabel("training iteration", fontsize=9, color=TEXT_SECONDARY)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
    if len(runs) == 1:
        fig.suptitle(f"{runs[0]['label']}: scoreboard {runs[0]['scoreboard_version']} over training", x=0.01, ha="left",
                     fontsize=11, color=TEXT_PRIMARY)
    else:
        axes[0].legend(frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY)
        fig.suptitle(f"Scoreboard {runs[0]['scoreboard_version']} over training", x=0.01, ha="left", fontsize=11, color=TEXT_PRIMARY)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=SURFACE)
    print(f"saved {out}")
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task", nargs="?")
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--label", default="")
    p.add_argument("--chart", type=Path, nargs="+", help="progress JSON files to chart together")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    if args.chart:
        chart(args.chart, args.out or FIGURES_DIR / "progress.png")
        return
    if not (args.task and args.run_dir):
        sys.exit("give a task and --run-dir to sweep, or --chart files to chart")
    progress_file = sweep(args.task, args.run_dir, args.label or args.run_dir.name)
    slug = "".join(c if c.isalnum() else "-" for c in (args.label or args.run_dir.name)).strip("-")
    chart([progress_file], args.out or FIGURES_DIR / f"{slug}_progress.png")


if __name__ == "__main__":
    main()
