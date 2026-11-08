"""tools/reward_check.py's weight overrides (no simulation): parsing, and the env config they change."""

import contextlib
import importlib.util
import io
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):  # mjlab prints a banner on import
    spec = importlib.util.spec_from_file_location("reward_check", REPO / "tools" / "reward_check.py")
    rc = importlib.util.module_from_spec(spec)
    sys.modules["reward_check"] = rc
    spec.loader.exec_module(rc)
    from ironbark_rl import evaluation
    from mjlab.tasks.registry import load_env_cfg

TASK = "IronBark-S2-Walk-Flat-Brian-StaleJoints"


def test_parse_weights():
    assert rc.parse_weights(["torques=-0.25", "feet_air_time=4.2"]) == {"torques": -0.25, "feet_air_time": 4.2}
    assert rc.parse_weights([]) == {}
    for bad in ("torques", "=1.0", "torques=abc"):
        with pytest.raises(ValueError):
            rc.parse_weights([bad])


def test_overrides_change_only_the_named_terms():
    with contextlib.redirect_stdout(io.StringIO()):
        base, cfg = load_env_cfg(TASK, play=True), load_env_cfg(TASK, play=True)
    evaluation.apply_reward_weights(cfg, {"torques": -0.25, "action_rate": -0.32})
    for name, term in cfg.rewards.items():
        expected = {"torques": -0.25, "action_rate": -0.32}.get(name, base.rewards[name].weight)
        assert term.weight == expected
    with pytest.raises(KeyError):
        evaluation.apply_reward_weights(cfg, {"torque": -0.25})  # a typo must not pass silently
