"""Which S2 sim joint each xgolib servo id drives. Verified on the real dog.

Brian, 2026-11-07 (Pi clock 2026-11-08 00:14), probe `map` run
docs/measurements/joint_control_map_20261108-001412.jsonl: each id was wiggled 10 deg on its own
(the readback confirmed each id moved only its own channel), and Brian named the leg and joint:
"11 was fl calf, 12 is fl thigh, 13 is fl hip, 21 is fr calf, 22 is fr thigh, 23 is fr hip, 31 is br calf,
32 is br thigh, 33 is br hip, 41 is bl calf, 42 is bl thigh, 43 is bl hip".
So xgolib legs 1-4 are fl, fr, br, bl (the vendor MJCF's order) and joints 1-3 are calf, thigh, hip.

Still open before any policy deployment:
# MEASURE: the sign and zero offset of each xgolib angle vs. its sim joint angle. The map run recorded
# no foot directions (every prompt was skipped); rerun `map` answering e.g. "fl thigh fwd", and command
# 0 deg per joint against the MJCF default pose (docs/s2-model-sources.md).
"""

XGO_ID_TO_SIM_JOINT = {
    11: "fl_calf_joint", 12: "fl_thigh_joint", 13: "fl_hip_joint",
    21: "fr_calf_joint", 22: "fr_thigh_joint", 23: "fr_hip_joint",
    31: "br_calf_joint", 32: "br_thigh_joint", 33: "br_hip_joint",
    41: "bl_calf_joint", 42: "bl_thigh_joint", 43: "bl_hip_joint",
}

SIM_JOINT_TO_XGO_ID = {name: xgo_id for xgo_id, name in XGO_ID_TO_SIM_JOINT.items()}
