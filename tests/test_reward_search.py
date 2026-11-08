"""tools/reward_search.py: Brian's ranges, constraints and ranking, the entry edits, and the study (CPU only)."""

import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from string import Template

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reward_search", REPO / "tools" / "reward_search.py")
rs = importlib.util.module_from_spec(spec)
sys.modules["reward_search"] = rs
spec.loader.exec_module(rs)

START = {"feet_air_time": 3.0, "action_rate": -0.08, "torques": -0.125}


def metrics(sat=0.008, planar=0.034, flicker=0.15):
    return {"fall_rate": 0.0, "planar_error_mps": planar, "yaw_rate_error_radps": 0.12, "joint_target_rate_radps": 3.0,
            "cost_of_transport": 1.7, "saturated_share": sat, "flicker_share": flicker, "swing_median_s": 0.18}


def test_start_weights_are_reward_config_now():
    from ironbark_rl.brian import reward_config

    assert rs.config_weights() == reward_config.WEIGHTS
    assert {k: reward_config.WEIGHTS[k] for k in START} == START  # the values the ranges below were checked against


def test_weights_span_brians_ranges():
    low = rs.trial_weights({"feet_air_time": 1.0, "action_rate_scale": 0.5, "torques_scale": 0.5}, START)
    high = rs.trial_weights({"feet_air_time": 7.5, "action_rate_scale": 4.0, "torques_scale": 2.0}, START)
    assert low == {"feet_air_time": 1.0, "action_rate": -0.04, "torques": -0.0625}
    assert high == {"feet_air_time": 7.5, "action_rate": -0.32, "torques": -0.25}
    d = rs.distributions()
    assert (d["feet_air_time"].low, d["feet_air_time"].high) == (1.0, 7.5)
    assert (d["action_rate_scale"].low, d["action_rate_scale"].high) == (0.5, 4.0)
    assert (d["torques_scale"].low, d["torques_scale"].high) == (0.5, 2.0)


def test_override_args_reach_the_env_cfg():
    """The driver's command-line overrides set exactly the three weights in the config training uses."""
    with contextlib.redirect_stdout(io.StringIO()):
        import ironbark_rl.tasks  # noqa: F401
        import mjlab
        import mjlab.tasks  # noqa: F401
        import src.tasks  # noqa: F401
        import tyro
        tspec = importlib.util.spec_from_file_location("luwu_train", Path(src.tasks.__file__).parents[2] / "scripts" / "train.py")
        train = importlib.util.module_from_spec(tspec)
        sys.modules["luwu_train"] = train
        tspec.loader.exec_module(train)
        weights = {"feet_air_time": 4.21738, "action_rate": -0.151234, "torques": -0.0911}
        default = train.TrainConfig.from_task(rs.TASK)
        cfg = tyro.cli(train.TrainConfig, args=rs.override_args(weights), default=train.TrainConfig.from_task(rs.TASK),
                       config=mjlab.TYRO_FLAGS)
    for name, term in cfg.env.rewards.items():
        assert term.weight == weights.get(name, default.env.rewards[name].weight)


def test_constraints_are_inclusive():
    assert rs.failed_constraints(metrics(sat=0.009, planar=0.035)) == []
    assert rs.failed_constraints(metrics(sat=0.0091, planar=0.035)) == ["saturation"]
    assert rs.failed_constraints(metrics(sat=0.009, planar=0.0351)) == ["planar"]


def test_failing_trials_rank_below_every_passing_one_by_how_far_they_miss():
    rows = [{"exp": "A", "metrics": metrics(flicker=0.20)},
            {"exp": "B", "metrics": metrics(flicker=0.05, sat=0.018)},  # lowest flicker; saturation 100% over its limit
            {"exp": "C", "metrics": metrics(flicker=0.12)},
            {"exp": "D", "metrics": metrics(flicker=0.30, planar=0.0385)},  # worst flicker; planar only 10% over
            {"exp": "E", "metrics": metrics(flicker=0.25, sat=0.0099, planar=0.0385)}]  # 10% + 10% over
    assert [r["exp"] for r in rs.ranked(rows)] == ["C", "A", "D", "E", "B"]


def test_miss_is_the_overshoots_summed_as_fractions_of_their_limits():
    assert rs.constraint_miss(metrics(sat=0.009, planar=0.035)) == 0.0
    assert rs.overshoots(metrics(sat=0.0099, planar=0.0385)) == pytest.approx({"saturation": 0.1, "planar": 0.1})
    assert rs.constraint_miss(metrics(sat=0.0099, planar=0.0385)) == pytest.approx(0.2)
    assert rs.constraints_cell(metrics(sat=0.0099, planar=0.0300)) == "fail: saturation +10.0%"
    assert rs.constraints_text(metrics(sat=0.0099, planar=0.0385)) == "constraints fail (saturation +10.0%, planar +10.0% over the limit)"
    assert rs.constraints_text(metrics()) == "constraints pass"


def template_entry(exp_id="EXP-099"):
    return Template((REPO / "docs/experiments/TEMPLATE.md").read_text(encoding="utf-8")).substitute(
        exp_id=exp_id, title="search 3: x", parent=rs.PARENT, date="2026-11-08", commit="abc1234", task=rs.TASK,
        seed=42, iterations=1500, envs=4096, train_cmd="python tools/run.py train X", run_glob="~/runs/*_EXP-099")


def test_entry_records_the_weights_and_command():
    w = {"feet_air_time": 4.21738, "action_rate": -0.151234, "torques": -0.0911}
    cmd = "python " + " ".join(rs.train_args("EXP-099", w))
    text = rs.fill_entry(template_entry(), 3, w, START, cmd)
    assert "**Status:** search trial 3 (Optuna), training · **Parent:** EXP-010" in text
    assert "feet_air_time 3 -> 4.217; action_rate -0.08 -> -0.1512 (1.89x); torques -0.125 -> -0.0911 (0.73x)" in text
    assert f"- Train: `{cmd}`" in text and "--env.rewards.torques.weight -0.0911" in cmd
    text = rs.set_status(text, "done")
    assert "**Status:** done · **Parent:** EXP-010" in text


def test_index_row_edits_touch_only_that_row():
    index = ("| [EXP-098](x.md) | d | t | vs. EXP-010: _fill in_ | _pending_ |\n"
             "| [EXP-099](y.md) | d | t | vs. EXP-010: _fill in_ | _pending_ |\n")
    w = {"feet_air_time": 2.0, "action_rate": -0.16, "torques": -0.125}
    out = rs.fill_index_change(index, "EXP-099", 4, w, START)
    assert out.split("\n")[0] == index.split("\n")[0]
    assert out.split("\n")[1].endswith("| vs. EXP-010: search trial 4: feet_air_time 3 -> 2; action_rate -0.08 -> -0.16 (2.00x); "
                                       "torques -0.125 -> -0.125 (1.00x) | _pending_ |")
    out = rs.fill_index_verdict(out, "EXP-099", "scored")
    assert out.split("\n")[1].endswith("(1.00x) | scored |")
    with pytest.raises(ValueError):
        rs.fill_index_verdict(out, "EXP-099", "again")  # no _pending_ left on that row


def test_saved_weights_reads_the_rewards_block():
    yaml = ("scene: {}\nrewards:\n  action_rate:\n    func: x\n    params: {}\n    weight: -0.16\n"
            "  feet_air_time:\n    func: y\n    params:\n      a: 1\n    weight: 4.2\n  torques:\n    func: z\n    params: {}\n"
            "    weight: -0.0911\nmetrics:\n  reward/torques:\n    weight: 9\n")
    assert rs.saved_weights(yaml) == {"feet_air_time": 4.2, "action_rate": -0.16, "torques": -0.0911}
    real = rs.RUNS_DIR / "logs/rsl_rl" / rs.EXPERIMENT_NAME / rs.PARENT_RUN / "params" / "env.yaml"
    if real.exists():
        assert rs.saved_weights(real.read_text(encoding="utf-8")) == START  # EXP-010 trained with the start weights


def test_study_starts_from_exp010_and_the_gp_takes_over():
    from optuna.trial import TrialState

    study = rs.load_study(storage=None, parent_metrics=metrics(sat=0.00805, planar=0.0383, flicker=0.1506))
    assert len(study.trials) == 1 and study.trials[0].user_attrs["exp"] == "EXP-010"
    assert study.trials[0].system_attrs["constraints"] == pytest.approx((0.00805 - 0.009, 0.0383 - 0.035))
    start = study.user_attrs["start_weights"]
    for k in range(rs.N_STARTUP_TRIALS + 2):  # past the random start, so the GP picks at least twice
        trial = study.ask(rs.distributions())
        w = rs.trial_weights(trial.params, start)
        assert 1.0 <= w["feet_air_time"] <= 7.5 and -0.32 <= w["action_rate"] <= -0.04 and -0.25 <= w["torques"] <= -0.0625
        m = metrics(sat=0.004 * w["feet_air_time"] / (w["torques"] / -0.125), planar=0.030 + 0.01 * (w["action_rate"] / -0.32),
                    flicker=0.3 / w["feet_air_time"])
        trial.set_user_attr("exp", f"EXP-{100 + k}")
        trial.set_user_attr("weights", w)
        trial.set_user_attr("metrics", m)
        trial.set_user_attr("constraints", list(rs.constraint_values(m)))
        study.tell(trial, m["flicker_share"])
    assert all(t.state == TrialState.COMPLETE and "constraints" in t.system_attrs for t in study.trials)
    doc = rs.search_doc(study, "now")
    table = [line for line in doc.split("\n") if line.startswith("| ") and line[2].isdigit()]
    assert len(table) == len(study.trials)
    passed = [("| pass |" in line) for line in table]
    assert passed == sorted(passed, reverse=True)  # every pass above every fail


def guard_result(standing=0.03, walking=0.4, negative_command=None):
    by_command = [{"command": [0.2, 0.0, 0.0], "total": 0.5}]
    if negative_command is not None:
        by_command.append({"command": [0.0, 0.0, 0.5], "total": negative_command})
    return {"standing_total": standing, "walking_total": walking, "walking_by_command": by_command}


def test_guard_flags_negative_standing_or_walking_totals_only():
    assert rs.guard_flags(guard_result()) == []
    assert rs.guard_flags(guard_result(standing=-0.001)) == ["standing"]
    assert rs.guard_flags(guard_result(standing=-0.1, walking=-0.2)) == ["standing", "walking"]
    assert rs.guard_flags(guard_result(negative_command=-0.3)) == []  # one command below 0 is reported, not flagged
    assert "negative commands (vx, vy, wz): (+0.0, +0.0, +0.5) -0.3000. OK" in rs.guard_text(guard_result(negative_command=-0.3))
    assert "**FLAG: walking total negative**; trained anyway" in rs.guard_text(guard_result(walking=-0.01))
    assert rs.guard_short(guard_result(standing=-0.01)) == "-0.0100 / +0.4000 **FLAG: standing**"


def test_guard_line_goes_in_setup_before_the_run_folder():
    text = rs.add_guard_line(template_entry(), rs.guard_line(guard_result()))
    lines = text.split("\n")
    i = next(k for k, line in enumerate(lines) if line.startswith("- Guard: "))
    assert lines[i + 1].startswith("- Run folder:") and lines[i - 1].startswith("- Train:")
