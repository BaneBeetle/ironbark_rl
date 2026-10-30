"""Run luwu_mjlab's train/play scripts with the IronBark tasks registered.

Logs and checkpoints land in IRONBARK_RUNS (default ~/dev/ironbark_runs), outside the
OneDrive-synced repo.

  python tools/run.py train IronBark-S2-Walk-Flat --env.scene.num-envs 4096
  python tools/run.py play  IronBark-S2-Walk-Flat --viewer native
  python tools/run.py play  IronBark-S2-Walk-Flat --agent zero --viewer native

`play` without --checkpoint-file loads the newest run's highest-iteration checkpoint.
(luwu's own lookup sorts names alphabetically, so it would pick model_900 over
model_1499.)
"""

import os
import runpy
import sys
from pathlib import Path

import ironbark_rl.tasks  # noqa: F401  (registers IronBark tasks)
import src  # Luwu's luwu_mjlab package

from mjlab.tasks.registry import load_rl_cfg

MODES = ("train", "play")
DUMMY_AGENTS = ("zero", "random")
RUNS_DIR = Path(os.environ.get("IRONBARK_RUNS", Path.home() / "dev" / "ironbark_runs"))


def _latest_checkpoint(task_id: str) -> Path | None:
    """Highest-iteration checkpoint of the newest run that has one."""
    experiment_dir = RUNS_DIR / "logs" / "rsl_rl" / load_rl_cfg(task_id).experiment_name
    # Run directories are timestamps (YYYY-MM-DD_HH-MM-SS), so names sort chronologically.
    for run in sorted((p for p in experiment_dir.glob("*") if p.is_dir()), reverse=True):
        checkpoints = list(run.glob("model_*.pt"))
        if checkpoints:
            return max(checkpoints, key=lambda p: int(p.stem.removeprefix("model_")))
    return None


def _wants_trained_checkpoint(args: list[str]) -> bool:
    if "--checkpoint-file" in args:
        return False
    if "--agent" in args:
        i = args.index("--agent")
        return i + 1 >= len(args) or args[i + 1] not in DUMMY_AGENTS
    return True


def main() -> None:
    # Windows pipes default to cp1252, and mjlab prints Unicode (arrows, box drawing)
    # when it builds the managers, which raises UnicodeEncodeError there.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2 or sys.argv[1] not in MODES:
        sys.exit(f"usage: python tools/run.py {{{'|'.join(MODES)}}} <task_id> [options]")
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "play" and args and _wants_trained_checkpoint(args):
        checkpoint = _latest_checkpoint(args[0])
        if checkpoint is not None:
            print(f"[run.py] playing {checkpoint}")
            args += ["--checkpoint-file", str(checkpoint)]
    script = src.SRC_PATH.parent / "scripts" / f"{mode}.py"
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(RUNS_DIR)
    sys.argv = [str(script), *args]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
