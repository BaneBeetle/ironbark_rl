"""Run luwu_mjlab's train/play scripts with the IronBark tasks registered.

Logs and checkpoints land in IRONBARK_RUNS (default ~/dev/ironbark_runs), outside the repo.

  python tools/run.py train IronBark-S2-Walk-Flat --env.scene.num-envs 4096
  python tools/run.py play  IronBark-S2-Walk-Flat --viewer native
  python tools/run.py play  IronBark-S2-Walk-Flat --agent zero --viewer native

`play` without --checkpoint-file loads the newest run's highest-iteration checkpoint
(ironbark_rl.runs.latest_checkpoint).
"""

import os
import runpy
import sys

import ironbark_rl.tasks  # noqa: F401  (registers IronBark tasks)
import src  # Luwu's luwu_mjlab package
from ironbark_rl.runs import RUNS_DIR, latest_checkpoint

MODES = ("train", "play")
DUMMY_AGENTS = ("zero", "random")


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
        checkpoint = latest_checkpoint(args[0])
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
