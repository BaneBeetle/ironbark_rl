"""ironbark_rl/assets/s2_joint_map.py: Brian's verified xgolib id <-> sim joint map (2026-11-07 `map` run)."""

import contextlib
import importlib.util
import io
from pathlib import Path

from ironbark_rl.assets.s2_joint_map import SIM_JOINT_TO_XGO_ID, XGO_ID_TO_SIM_JOINT
from ironbark_rl.brian import latency_config


def sim_joint_names():
    with contextlib.redirect_stdout(io.StringIO()):
        from ironbark_rl.assets.s2 import get_s2_spec

        model = get_s2_spec().compile()
    return {model.joint(i).name for i in range(model.njnt)} - {"floating_base"}


def test_every_sim_leg_joint_has_exactly_one_xgolib_id():
    assert set(XGO_ID_TO_SIM_JOINT.values()) == sim_joint_names()
    assert len(SIM_JOINT_TO_XGO_ID) == len(XGO_ID_TO_SIM_JOINT) == 12


def test_brians_answers_leg_major_fl_fr_br_bl_and_calf_thigh_hip():
    for xgo_id, name in XGO_ID_TO_SIM_JOINT.items():
        leg, part, _ = name.split("_")
        assert ("fl", "fr", "br", "bl")[xgo_id // 10 - 1] == leg
        assert ("calf", "thigh", "hip")[xgo_id % 10 - 1] == part


def test_probe_commands_the_same_ids():
    spec = importlib.util.spec_from_file_location("probe", Path(__file__).resolve().parents[1] / "pi" / "joint_control_probe.py")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    assert probe.LEG_IDS == sorted(XGO_ID_TO_SIM_JOINT)


def test_poll_slots_follow_id_order():
    slots = {name: latency_config.readback_slot(name) for name in SIM_JOINT_TO_XGO_ID}
    assert sorted(slots.values()) == list(range(12))
    assert slots["fl_calf_joint"] == 0 and slots["fr_thigh_joint"] == 4 and slots["bl_hip_joint"] == 11
