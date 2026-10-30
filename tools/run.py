"""Run luwu_mjlab's train/play scripts with the IronBark tasks registered.

Logs and checkpoints land in IRONBARK_RUNS (default ~/dev/ironbark_runs), outside the
OneDrive-synced repo.

  python tools/run.py train IronBark-S2-Walk-Flat --env.scene.num-envs 4096
  python tools/run.py play  IronBark-S2-Walk-Flat --viewer native
  python tools/run.py play  IronBark-S2-Walk-Flat --agent zero --viewer native
"""

import os
import runpy
import sys
from pathlib import Path

import ironbark_rl.tasks  # noqa: F401  (registers IronBark tasks)
import src  # Luwu's luwu_mjlab package

MODES = ("train", "play")
RUNS_DIR = Path(os.environ.get("IRONBARK_RUNS", Path.home() / "dev" / "ironbark_runs"))


def main() -> None:
    # Windows pipes default to cp1252, and mjlab prints Unicode (arrows, box drawing)
    # when it builds the managers, which raises UnicodeEncodeError there.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2 or sys.argv[1] not in MODES:
        sys.exit(f"usage: python tools/run.py {{{'|'.join(MODES)}}} <task_id> [options]")
    script = src.SRC_PATH.parent / "scripts" / f"{sys.argv[1]}.py"
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(RUNS_DIR)
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
