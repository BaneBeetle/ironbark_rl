# S2 sim model: sources and how far to trust them

Goal for Phase 2A step 1: an MJCF of the DogZilla S2 for mjlab. This note records what exists and what each source is good for. The files live outside the repo, in `~/dev/` (not committed: third-party, and large).

## Sources

| Source | Where | Contents |
|---|---|---|
| Yahboom URDF | Yahboom Drive → `2.Code/For_RPi5/Pi5docker code.rar` → `yahboomcar_ws/install/yahboom_description/share/yahboom_description/` | `urdf/yahboom_xgo_rviz.xacro` + per-link STL meshes (`meshes/XGO/`) |
| Yahboom CAD | Yahboom Drive → `6.3D_Model_File/DOGZILLA S2.STEP` (63 MB) | Full S2 assembly |
| Luwu Mini2S MJCF | [LuwuDynamics/luwu_mjlab](https://github.com/LuwuDynamics/luwu_mjlab) `src/assets/robots/mini2s/xmls/mini2s.xml` | MJCF used by Luwu's RL env, incl. a 3-joint arm |

Yahboom Drive root (linked from [YahboomTechnology/DOGZILLA](https://github.com/YahboomTechnology/DOGZILLA)): https://drive.google.com/drive/folders/13RYtBkce3EF5qFy8eSqtLbtFiruhWlqm

## Leg kinematics: S2 URDF matches the Mini2S

Read from both files on 2026-10-30:

| | S2 (Yahboom URDF) | Mini2S (Luwu MJCF) |
|---|---|---|
| Front↔rear hip axis spacing | 0.1500 m | 0.1500 m |
| Hip lateral offset | ±0.0224 / 0.0225 m | ±0.0225 m |
| Hip → thigh joint offset | (18.3, 49.3) mm | (18.5, 49.6 / 48.8) mm |
| Thigh length (thigh → calf joint) | 59.9 mm | 59.9 mm |
| Joint axes | hip about x, thigh/calf about y | same |

Together with the firmware string (`M-4.0.1-Y`, XGO Mini family) and the xgolib `xgomini` joint limits being close to the Mini2S MJCF ranges, this says the S2's legs **are** an XGO Mini2 leg set. The Mini2S MJCF kinematics can be reused. Mass and actuators can't.

## What the Yahboom URDF can't be trusted for

It's an RViz-only export:
- **Total mass 0.619 kg.** That's light for an S2 with a Pi 5, battery, camera and lidar.
- **Hip masses are asymmetric:** left 19.6 g, right 9.8 g (Mini2S uses 19.6 g for all four).
- **`imu_link` inertial is a copy of `laser_link`'s.**
- **All joint limits are ±π placeholders**, with effort 25 and velocity 1.5.
- **No foot link**, so calf length isn't in the URDF; get it from the lower-leg STL or the STEP.

## Plan for the S2 MJCF

1. Start from the Mini2S MJCF (kinematics match, and it's already tuned for mjlab), and remove the arm.
2. Add the S2's top-side payload (Pi 5, lidar, camera) as fixed bodies. Placement comes from the Yahboom URDF (`laser_Joint`, `camera_Joint`).
3. Scale masses to measured values. `# MEASURE:` total mass on a kitchen scale; one leg's mass if it can be removed.
4. Joint limits from xgolib `MOTOR_LIMIT` (see [phase1-xgolib-api.md](phase1-xgolib-api.md)), mapped to the MJCF zero pose. `# MEASURE:` the zero-pose offset per joint (command 0° and photograph against the MJCF default pose).
5. Actuator gains, torque limit and delay from Phase 1 step responses. `# MEASURE:` replaces the Mini2S `kp=1.15, forcerange ±0.43` placeholders.
