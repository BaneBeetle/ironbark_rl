"""S2 model sanity checks. CPU only: compiles the MJCF, no simulation."""

import mujoco
import numpy as np
import pytest

from ironbark_rl.assets import s2


@pytest.fixture(scope="module")
def model() -> mujoco.MjModel:
    return s2.get_s2_spec().compile()


@pytest.fixture(scope="module")
def data(model) -> mujoco.MjData:
    data = mujoco.MjData(model)
    mujoco.mj_kinematics(model, data)
    return data


def _base_frame_pos(model, data, body: str) -> np.ndarray:
    return data.xpos[model.body(body).id] - data.xpos[model.body(s2.FLOATING_BASE_BODY).id]


def test_arm_removed(model):
    joints = [model.joint(i).name for i in range(model.njnt)]
    assert not any(name.startswith("arm_") for name in joints)
    assert model.nu == 12


def test_free_base_plus_twelve_leg_joints(model):
    assert model.njnt == 13
    assert model.jnt_type[0] == mujoco.mjtJoint.mjJNT_FREE


def test_total_mass_matches_working_value(model):
    assert model.body_mass.sum() == pytest.approx(s2.S2_TOTAL_MASS_KG, abs=1e-6)


def test_base_frame_is_x_forward_y_left(model, data):
    front_left = _base_frame_pos(model, data, "fl_hip")
    assert front_left[0] > 0 and front_left[1] > 0


def test_payload_keeps_yahboom_offset_from_hip_center(model, data):
    hip_center = np.mean([_base_frame_pos(model, data, h) for h in s2.HIP_BODIES], axis=0)
    yahboom_hip_center = s2.YAHBOOM_HIP_JOINT_ORIGINS.mean(axis=0)
    for part in s2.S2_PAYLOAD:
        got = _base_frame_pos(model, data, part.name) - hip_center
        want = np.asarray(part.link_origin) - yahboom_hip_center
        np.testing.assert_allclose(got, want, atol=1e-9)


def test_lidar_above_hips_and_behind_camera(model, data):
    lidar = _base_frame_pos(model, data, "lidar")
    camera = _base_frame_pos(model, data, "camera")
    hip_heights = [_base_frame_pos(model, data, h)[2] for h in s2.HIP_BODIES]
    assert lidar[2] > max(hip_heights)
    assert camera[0] > lidar[0]
