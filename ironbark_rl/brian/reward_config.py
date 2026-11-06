"""Reward parameters for IronBark-S2-Walk-Flat-Brian. Brian edits this file.

The task reads every reward parameter from here; nothing else hardcodes one. The term
weights (one per function in rewards.py) join this file in step 3.
"""

# MEASURE: real S2 standing height of the sim's `base` frame origin, m. Brian measures it:
#   dog standing in its default pose on a flat floor, ruler from the floor to the centre of
#   each thigh (upper-leg) pivot, mean of the 4 legs, plus 0.021 m (the sim's offset from
#   the thigh pivot up to the `base` origin, S2 standing pose, 2026-11-06). For reference,
#   the sim's default pose stands at 0.123 m (thigh pivots at ~0.102 m), but that stance
#   is a Mini2S placeholder.
BASE_HEIGHT_TARGET_M: float | None = None
