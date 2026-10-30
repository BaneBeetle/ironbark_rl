"""DogZilla S2 robot model for mjlab, derived from Luwu's XGO Mini2S MJCF.

Why derive instead of converting Yahboom's URDF: the S2's leg kinematics match the
Mini2S to within 1 mm, and the Mini2S MJCF already has the physics that Yahboom's
RViz-only URDF lacks (servo actuators, joint limits, foot contacts, IMU site,
self-consistent masses). See docs/s2-model-sources.md.

Changes applied to the Mini2S, in order:
  1. Remove its arm (the S2 has none).
  2. Add the S2 payload the Mini2S lacks (lidar, camera) as mass-only bodies, placed
     relative to the hips using Yahboom's URDF.
  3. Rescale the trunk so the whole robot weighs S2_TOTAL_MASS_KG.

Still the Mini2S's, pending Phase 1 measurements: joint limits, stance, and the servo
model (kp 1.15 N*m/rad, torque limit +-0.43 N*m, set in the Mini2S XML `servo` class).
"""

from dataclasses import dataclass

import mujoco
import numpy as np

from mjlab.entity import EntityCfg
from src.assets.robots.mini2s.mini2s_constants import (
    MINI2S_ARTICULATION,
    MINI2S_WALK_COLLISION,
    get_spec as get_mini2s_spec,
)

# MEASURE: reported online as ~972 g (2026-10-30, source not recorded, unverified).
# Weigh the dog (bathroom-scale difference or a luggage scale) and replace.
S2_TOTAL_MASS_KG = 0.972

MINI2S_ARM_ROOT_BODY = "arm_base"
FLOATING_BASE_BODY = "base"
# The Mini2S trunk. Mass we can't attribute to a known part (Pi 5, battery, frame
# differences) goes here, with the trunk's existing COM and inertia shape.
TRUNK_BODY = "base_model"
HIP_BODIES = ("fl_hip", "fr_hip", "bl_hip", "br_hip")

# Hip joint origins from Yahboom's yahboom_xgo_rviz.xacro (base_link frame, metres).
# Only used to place the payload relative to the hips. Both that frame and the
# Mini2S floating-base frame are x-forward, y-left, z-up.
YAHBOOM_HIP_JOINT_ORIGINS = np.array([
    (0.09332, 0.022407, 0.01454),    # lf_hip_joint
    (0.09332, -0.022517, 0.01454),   # rf_hip_joint
    (-0.05668, 0.022407, 0.01454),   # lh_hip_joint
    (-0.05668, -0.022517, 0.01454),  # rh_hip_joint
])


@dataclass(frozen=True)
class Payload:
    """A rigid part bolted to the S2 trunk that the Mini2S model doesn't have."""

    name: str
    link_origin: tuple[float, float, float]  # Yahboom URDF joint origin, base_link frame
    com: tuple[float, float, float]  # centre of mass in the link frame
    mass_kg: float
    diag_inertia: tuple[float, float, float]


# MEASURE: masses and inertias are Yahboom URDF values. The URDF copies laser_link's
# inertial onto imu_link, so treat them as unverified. Weigh the MS200 and the camera.
S2_PAYLOAD = (
    Payload(
        name="lidar",
        link_origin=(-0.016732, 4.4164e-05, 0.10335),
        com=(3.78567e-05, -1.19937e-04, -2.27984e-02),
        mass_kg=0.0141157,
        diag_inertia=(2.42578e-06, 2.37021e-06, 4.25931e-06),
    ),
    Payload(
        name="camera",
        link_origin=(0.075751, 0.0, 0.059653),
        com=(-1.41668e-02, -4.70244e-05, -1.17154e-04),
        mass_kg=0.00465716,
        diag_inertia=(3.06225e-07, 3.69724e-07, 3.81830e-07),
    ),
)

# Visual marker radius for payload sites (not physical; group 2 = visual).
PAYLOAD_MARKER_RADIUS_M = 0.008


def _hip_center_in_base(spec: mujoco.MjSpec) -> np.ndarray:
    """Mean hip-joint position in the floating-base frame at the model's zero pose."""
    model = spec.compile()
    data = mujoco.MjData(model)
    mujoco.mj_kinematics(model, data)
    # At qpos0 the free joint has identity orientation, so world offsets are base-frame.
    base = data.xpos[model.body(FLOATING_BASE_BODY).id]
    hips = np.array([data.xpos[model.body(name).id] for name in HIP_BODIES])
    return hips.mean(axis=0) - base


def _add_payload(spec: mujoco.MjSpec) -> None:
    hip_center = _hip_center_in_base(spec)
    yahboom_hip_center = YAHBOOM_HIP_JOINT_ORIGINS.mean(axis=0)
    base = spec.body(FLOATING_BASE_BODY)
    for part in S2_PAYLOAD:
        pos = np.asarray(part.link_origin) - yahboom_hip_center + hip_center
        body = base.add_body(
            name=part.name,
            pos=pos,
            ipos=part.com,
            mass=part.mass_kg,
            inertia=part.diag_inertia,
            explicitinertial=True,
        )
        body.add_site(name=f"{part.name}_site", size=[PAYLOAD_MARKER_RADIUS_M, 0, 0], group=2)


def _rescale_trunk(spec: mujoco.MjSpec, total_mass_kg: float) -> None:
    trunk = spec.body(TRUNK_BODY)
    rest_kg = float(spec.compile().body_mass.sum()) - trunk.mass
    trunk_kg = total_mass_kg - rest_kg
    if trunk_kg <= 0:
        raise ValueError(f"total mass {total_mass_kg} kg is less than the legs + payload ({rest_kg:.4f} kg)")
    # Same mass distribution, more of it: inertia scales linearly with mass.
    trunk.inertia = np.asarray(trunk.inertia) * (trunk_kg / trunk.mass)
    trunk.mass = trunk_kg


def get_s2_spec() -> mujoco.MjSpec:
    spec = get_mini2s_spec()
    spec.delete(spec.body(MINI2S_ARM_ROOT_BODY))  # also drops the arm's three actuators
    _add_payload(spec)
    _rescale_trunk(spec, S2_TOTAL_MASS_KG)
    return spec


# MEASURE: S2 stance. These are the Mini2S defaults (thigh 1.0 rad, calf 0, hip 0).
# Replace with read_motor() angles of the real dog standing, once the zero-pose
# offset between xgolib angles and these joints is known.
S2_INIT_STATE = EntityCfg.InitialStateCfg(
    pos=(0.0, 0.0, 0.20),
    joint_pos={
        r"^(fl|fr|bl|br)_thigh_joint$": 1.0,
        r"^(fl|fr|bl|br)_calf_joint$": 0.0,
        r"^(fl|fr|bl|br)_hip_joint$": 0.0,
    },
    joint_vel={".*": 0.0},
)


def get_s2_walk_robot_cfg() -> EntityCfg:
    """S2 for walking tasks: only the calf feet touch the ground (Mini2S walk setup)."""
    return EntityCfg(
        init_state=S2_INIT_STATE,
        collisions=(MINI2S_WALK_COLLISION,),
        spec_fn=get_s2_spec,
        articulation=MINI2S_ARTICULATION,
    )
