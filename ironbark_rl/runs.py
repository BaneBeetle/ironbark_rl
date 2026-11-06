"""Where training runs live, and how to find their checkpoints.

Runs go to IRONBARK_RUNS (default ~/dev/ironbark_runs), outside the repo.
"""

import os
from pathlib import Path

from mjlab.tasks.registry import load_rl_cfg

RUNS_DIR = Path(os.environ.get("IRONBARK_RUNS", Path.home() / "dev" / "ironbark_runs"))


def experiment_dir(task_id: str) -> Path:
    return RUNS_DIR / "logs" / "rsl_rl" / load_rl_cfg(task_id).experiment_name


def latest_checkpoint(task_id: str) -> Path | None:
    """Highest-iteration checkpoint of the newest run that has one.

    luwu's own lookup sorts file names alphabetically, so it would pick model_900
    over model_1499.
    """
    # Run directories start with a timestamp (YYYY-MM-DD_HH-MM-SS), so names sort chronologically.
    runs = sorted((p for p in experiment_dir(task_id).glob("*") if p.is_dir()), reverse=True)
    for run in runs:
        checkpoints = list(run.glob("model_*.pt"))
        if checkpoints:
            return max(checkpoints, key=lambda p: int(p.stem.removeprefix("model_")))
    return None
