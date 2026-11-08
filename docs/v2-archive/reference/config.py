# =============================================================================
# IronBark Configuration
# Shared constants for Pi sender and PC receiver.
# Import this module anywhere with: import config
#
# Network IPs are loaded from a local `.env` file (gitignored). Copy
# `.env.example` → `.env` and fill in the values for your setup.
# =============================================================================

import os
from pathlib import Path

# ---- .env loader (no python-dotenv dependency) -----------------------------
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip()
            # Strip optional surrounding quotes
            if len(_v) >= 2 and _v[0] == _v[-1] and _v[0] in ("'", '"'):
                _v = _v[1:-1]
            os.environ.setdefault(_k, _v)

# ---- Network ----------------------------------------------------------------
# Set PC_IP and PI_IP in your local .env file. Defaults to localhost so a
# missing .env fails loudly during connect rather than silently misrouting.
PC_IP    = os.environ.get("PC_IP", "127.0.0.1")    # Mac (brain)
PI_IP    = os.environ.get("PI_IP", "127.0.0.1")    # Raspberry Pi (dog)
ZMQ_PORT   = 50505              # ZeroMQ PUSH/PULL port for video stream
MJPEG_PORT = 9000               # MJPEG HTTP stream port (fallback)

# ---- Camera -----------------------------------------------------------------
CAMERA_RESOLUTION = (640, 480)
JPEG_QUALITY      = 75
TARGET_FPS        = 30

# ── OAK-D Lite (Phase A: RGB + Phase B: Depth) ──
# Phase A: RGB stream on ZMQ_PORT (50505), drop-in replacement for Toucan.
# Phase B: depth stream on ZMQ_OAKD_DEPTH_PORT (50508), used for arrival
#          detection (replaces unreliable bbox area_ratio heuristic).
# V2: the OAK-D is in a drawer (briefing §3b — 200 g of head-high payload
# on a 972 g dog was the failure class that ended V1). The S2 has ONE 2 MP
# USB camera and no depth stream at all, so both of these are False and
# arrival keys on bbox area ratio. Left in place, not deleted: the hybrid
# fallback in §3c straps the old rig back on if MS200 bring-up fails hard.
USE_OAKD               = False
USE_OAKD_DEPTH         = False           # enable depth-based arrival
ZMQ_OAKD_DEPTH_PORT    = 50508           # Pi → Mac: depth stream (PNG-16)
OAKD_DEPTH_STALE_S     = 1.0             # ignore depth older than this (seconds)
OAKD_MIN_VALID_PCT     = 30.0            # min % of bbox pixels with valid depth
                                          # to trust the reading; below = fallback

# Depth forward-cone veto: fuse depth nose-region clearance with LiDAR
# forward distance so the dog catches low floor obstacles (chair legs,
# cables) that the body-mounted LiDAR beam passes over. Disable to fall
# back to LiDAR-only forward distance.
# V2: False — there is no depth camera. The forward veto reassigns to the
# MS200's forward arc. Known residual gap, inherited from V1's rig too:
# obstacles below the lidar plane (~18 cm) stay invisible.
USE_DEPTH_FORWARD_CLEARANCE = False

# =============================================================================
# Phase 2 - Perception Stack
# =============================================================================

YOLO_MODEL          = "yolo11s.pt"
YOLO_CONF_THRESHOLD = 0.5

# VLM model. Stage 1 swap (2026-04-24): moondream→llava-llama3:8b. Trace
# data showed moondream broke under any prompt augmentation past the bare
# minimum — Plan A's memory suffix dropped success 100%→29% with structural
# task-confusion (gibberish floats, JSON arrays). llava-llama3:8b has the
# instruction-following headroom to handle longer prompts. Cost: ~3-4x
# latency (1.2s → ~3-4s per query) but EXPLORE cadence is already 0.4Hz,
# so this fits inside the existing query loop. Pre-warm in
# follower_runner.main() loads the model into Ollama RAM at startup.
VLM_MODEL = "llava-llama3:8b"
VLM_HOST  = "http://localhost:11434"

# ── V2 target-lock (replaces the ArcFace + OSNet identity stack) ──
# V2 follows *any* human: the pipeline latches one ByteTrack ID instead of
# recognizing a specific person. Recognition returns later as one more
# scorer feeding TARGET_SCORE, not as a separate gate.
# See docs/phase1-briefing.md §5.
#
#   score = area_norm x (1 - TARGET_CENTER_WEIGHT x |cx - W/2| / (W/2))
#
# Area-primary because bbox area is a proximity proxy: the person who
# walked up to the dog is the person to follow. The centering term only
# breaks ties toward whom the dog already faces (post-SEARCH aim is
# arbitrary, so most-centered alone would be an artifact).
TARGET_CENTER_WEIGHT   = 0.3    # 0 = pure area, 1 = frame edge scores zero
TARGET_ACQUIRE_FRAMES  = 3      # consecutive frames as argmax before latching.
                                # Filters a passerby crossing the frame edge;
                                # ~300 ms at the 10 Hz perception cadence.
TARGET_HOLDOVER_FRAMES = 15     # latched ID may go missing this many frames
                                # before release (carried from V1's
                                # _owner_holdover — ByteTrack re-association
                                # usually recovers inside it).
FOLLOW_COAST_S         = 1.5    # FOLLOW replays its last action this long
                                # through detector dropouts. MUST NOT exceed
                                # TARGET_HOLDOVER_FRAMES / perception Hz
                                # (15 fr / 10 Hz = 1.5 s): the coast bridges
                                # dropouts WHILE the latch persists; once the
                                # latch releases there is no target intent
                                # left to coast on (bring-up report Q4 — the
                                # old 2.0 s left a 0.5 s blind-coast window).

# ── Diagnostics ──────────────────────────────────────────────────
# Print per-detection target scores + latch state every frame (V2
# successor to V1's DEBUG_FUSION_SCORES). Use when calibrating
# TARGET_CENTER_WEIGHT / TARGET_ACQUIRE_FRAMES against real
# two-people-in-frame footage. Set False for normal operation (one
# line per detection per frame is noisy).
DEBUG_TARGET_SCORES  = False

# Per-iteration log of depth_fwd vs lidar_fwd at every depth-veto check
# point in _explore and _follow. Used to discriminate two hypotheses for
# the depth bias issue (project_depth_camera_bias.md):
#   A. Sensor calibration bias — depth reads consistently closer than
#      reality across the full distance range.
#   B. Geometric self-occlusion — depth ROI samples the dog's own body
#      at the current head pitch (suspected cause: bottom-40% y_frac at
#      EXPLORE_HEAD_PITCH=-35° walks the ROI onto the chest/legs).
# Hypothesis B presents as low-variance constant readings independent
# of environment. Hypothesis A presents as linear offset across varied
# wall distances. Vary head pitch across short traces (-35°, -15°, 0°)
# to isolate. Default OFF — flip True for measurement traces only.
# Disabled 2026-04-26: depth-cal track hasn't started; flag was left
# True from instrumentation. Stdout pressure compounds with other flags.
DEBUG_DEPTH_CAL      = False

# Per-iteration log of the gyro-integrated yaw value coming back from the
# Pi via telemetry. Used for the Strategic-VLM v2 verification traces:
# stationary 30s drift test + deliberate 180° rotation test (sign convention
# + unit verification before the Mac-side rotation correction lands).
# See project_vlm_strategic_design.md → "Strategic VLM v2 SDK pivot."
# Default ON for the verification phase; flip OFF after v2 lands.
# Disabled 2026-04-26: v2 is closed (perceive-act architecture made
# rotation-correction unnecessary). Stdout pressure compounds with
# other flags. Re-enable only for specific gyro diagnostic traces.
DEBUG_IMU_TRACE      = False

# Pi motor controller per-iteration trace: commanded vs executing action,
# gait buffer depth, queued segment summary, head mode. Enable to diagnose
# gait-buffer accumulation, action-transition discontinuities (the "single
# servo snaps fast" jerk), or commanded/executing divergence after a no-
# flush transition. Pi-side stdout — capture by tee'ing motor_controller
# output, NOT in the Mac follower log.
# Default convention is OFF; was left True from earlier diagnostic tracks
# (gait-stability, buffer-saturation). Disabled 2026-04-26 as Step 1 of
# the freeze-isolation plan — eliminates 10Hz stdout from Pi to rule out
# I/O-blocking-through-tee as a cascade contributor. Re-enable only for
# specific diagnostic tracks.
DEBUG_MOTOR_TRACE    = False

# =============================================================================
# Phase 3 - Follow-Me Behavior
# =============================================================================

CMD_PORT = 5556

FRAME_CENTER_X     = 320
BODY_TURN_STEP_COUNT = 4      # gait cycles per turn (was 8; halved 2026-04-27 to cut direction-change latency from ~800ms to ~400ms — buffer depth, not dedup, was the responsiveness floor). V2: no gait queue exists, motor_controller tolerates-and-ignores step_count.
FORWARD_STEP_COUNT = 4        # gait cycles per forward (was 8; halved 2026-04-27 alongside BODY_TURN_STEP_COUNT for owner-tracking responsiveness). V2: tolerated-ignored, see above.

# ── V2 FOLLOW tuning — DogZilla S2 wide-angle USB camera ──────────
# Everything in this block is carried from V1 UNVERIFIED. The numbers were
# tuned against the OAK-D Lite's FOV on a PiDog; the S2 ships a 2 MP
# wide-angle USB cam whose FOV Yahboom does not publish, so the same
# person at the same distance lands a different bbox area and a different
# pixel offset. Replaces V1's BODY_TURN_THRESHOLD / STEERING_DEAD_ZONE /
# TARGET_AREA_RATIO / MIN_AREA_RATIO, none of which the follower read.
#
# MEASURE: with pi/cam_sender.py streaming from the dog, run
#   python pc/bbox_calibrate.py
# and walk the 1–4 m range. It prints area_ratio + off_x per detection.
# Set V2_ARRIVAL_AREA_RATIO to the ratio seen at the desired stopping
# distance, and re-derive the band edges from the ratios at those ranges.

# Body-turn deadband ladder: how far off-centre (px) the target may sit
# before the body turns instead of walking forward. Looser when the target
# is far (small bbox) — a pixel is worth more angle out there and walking
# forward re-centres on its own; tighter as the bbox grows.
V2_TURN_BANDS = (
    # (area_ratio upper bound, turn threshold in px)
    (0.08, 220),
    (0.15, 160),
    (0.30, 100),
    (float("inf"), 60),
)
# MEASURE: pixel offset tolerated before the arrival re-centre turn fires.
V2_ARRIVAL_RECENTER_PX = 80
# MEASURE: bbox area ratio that counts as "arrived". There is no depth
# sensor on the S2 (briefing §3b), so this is the ONLY arrival signal —
# the per-mode arrival_ratio / arrival_cm values in BEHAVIOR_MODES are
# dormant while VLM_SITUATION_ENABLED is False, and are just as unverified.
V2_ARRIVAL_AREA_RATIO = 0.55
# Arrival greeting bark. Identity-free (a greeting on arrival, not "I know
# you"), so it survives the identity deletion — but no speaker path is
# wired on the S2 yet (motor_controller tolerates-and-ignores `bark`), so
# it stays off and the plumbing simply sits there.
V2_ARRIVAL_BARK_ENABLED = False

# Action hysteresis: a new wanted_action must persist for this many
# consecutive perception frames before the follower commits to it. At
# ~10 Hz that's ~300 ms at 3 frames. Prevents the costmap from flapping
# turn_right ↔ forward each frame — every flap sends a STOP that flushes
# the Pi's gait buffer, so flap = zero net rotation.
ACTION_COMMIT_FRAMES = 3

# (Ultrasonic removed — LiDAR costmap handles all obstacle avoidance)

# ── Phase 7: RPLidar C1 (360° obstacle avoidance) ─────────────────
# Replaces the ultrasonic head-sweep scan with continuous 360° LiDAR.
# The LiDAR is body-mounted and head-independent — no more blind spots.
ZMQ_LIDAR_PORT            = 50507           # Pi → Mac: LiDAR scan stream
USE_LIDAR                 = True            # enable LiDAR obstacle avoidance
LIDAR_STALE_S             = 1.0             # ignore scans older than this (seconds)

# Arc definitions (degrees, clockwise: 0=forward, 90=right, 180=behind, 270=left)
LIDAR_FORWARD_ARC_HALF    = 30              # forward = 330° to 30° (60° wide)
LIDAR_OBSTACLE_CM         = 50              # forward stopping-distance threshold — reaction time + gait travel before collision
LIDAR_FWD_DANGER_CM       = 19              # forward hard-stop (imminent) — head sticks forward of the LiDAR mount, so 19cm reading ≈ head near wall
LIDAR_SIDE_FIT_CM         = 25              # left/right physical-fit threshold for cornered check — "can I pass between these walls?" PiDog body ~12-15cm wide; 25cm = 7-8cm half-width + ~15cm clearance margin + ~3cm LiDAR mount offset. Started at 25 (oracle 2026-04-25): cost of too-aggressive (scrape walls) > cost of too-conservative (one extra trace cycle to tune down). See project_plan_a_explore_memory.md for the threshold-overload diagnosis.
LIDAR_SIDE_DANGER_CM      = 15              # left/right hard-stop (currently unused — placeholder for future side-imminent check parallel to LIDAR_FWD_DANGER_CM)

# ── Costmap (2D occupancy grid from LiDAR) ────────────────────────
# Replaces the arc-based obstacle checks with a continuous gradient.
# Set USE_COSTMAP=False to fall back to the arc-based veto logic.
USE_COSTMAP               = True
COSTMAP_GRID_SIZE         = 120            # cells per side (120×120)
COSTMAP_CELL_CM           = 5              # cm per cell → 6m×6m grid
COSTMAP_INFLATE_CM        = 25             # inflate radius: dog body ~20cm + margin
COSTMAP_DECAY_FACTOR      = 0.85           # per-scan decay — obstacles persist ~5 scans through beam skips
COSTMAP_MIN_CLEAR_CM      = 70             # min clear run to accept a heading — full body-length

# Legacy ultrasonic (kept as fallback if LiDAR unavailable)

# ── 3-phase maneuver (Mac-side obstacle avoidance) ────────────────
MANEUVER_CLEARING_DURATION_S = 3.5   # seconds to walk forward past obstacle edge
MANEUVER_MAX_RETRIES         = 2     # max clearing re-turns before aborting
NAV_FRAME_MAX_AGE_S          = 2.0   # discard ribbon cam frame older than this

BARK_HEAD_PITCH     = 35        # Look all the way up during arrival bark

SEARCH_TIMEOUT_S   = 5.0
EXPLORE_TIMEOUT_S  = 30.0

# EXPLORE is Phase 3 work and is NOT part of FOLLOW bring-up. Its
# perceive-act EXECUTING gate still waits on the Pi's gait buffer_depth,
# which V2 telemetry deliberately does not send — a velocity-setpoint
# machine has no gait buffer to drain (smoke Q1). With this False a SEARCH
# timeout falls back to IDLE instead of EXPLORE, and the IDLE-boredom
# EXPLORE kick is suppressed too. Flip it only after that gate has been
# moved onto yaw/frame predicates.
EXPLORE_ENABLED    = False

HEAD_DEFAULT_PITCH = 0  # was 15 — lowered to compensate for OAK-D mount height

# ── Timing ──────────────────────────────────────────────────────────
CMD_INTERVAL        = 0.1       # seconds between Mac→Pi commands. Buffer-saturation fix C (=0.2) was empirically rejected 2026-04-25 — produced WORSE behavior + consistent dog crashes (likely empty-buffer tip-overs between commands; doubled decision latency for safety responses). Reverted. See project_plan_a_explore_memory.md → Buffer saturation 2026-04-25 for the full failure analysis.
# Mac-side action dedup heartbeat — emit at least once per this interval
# even if dedup would skip (Pi presence beacon, bounds "Pi thinks Mac is
# dead" failure mode). Math (oracle-derived): 1000ms × 8 frames/cmd =
# 8 frames/sec queued, drain ~7/sec → buffer stays at ~10-20 frames
# during sustained same-action. Lag <2s, well under "real-time."
# See project_vlm_strategic_design.md → Strategic VLM v2 final.
CMD_DEDUP_HEARTBEAT_S = 1.0
FOLLOW_GAIT_PAUSE_S = 0.05     # pause between follow-me gaits (was 0.2)

# ── Arrival behavior — bbox area ratio thresholds ───────────────────
# The dog uses bbox size as a distance proxy: big bbox = close, small = far.
# Same concept drones use — no ultrasonic needed, camera-based.
#
# CALIBRATION: Run follower.py and watch the "[FOLLOW] area=X.XXX" log.
#   Stand at "arrived" distance (~3 feet) → note the ratio → set ARRIVED
ARRIVAL_ARRIVED_RATIO = 0.55    # bbox > 55% → arrived! (~1.5 feet instead of ~3 feet)

# =============================================================================
# Phase 4 - VLA (Vision-Language-Action) Integration
# =============================================================================

VLM_ACTION_CONFIDENCE_THRESHOLD = 0.5   # Min confidence to act on VLM action
VLM_TURN_STEP_COUNT = 4                 # step_count for VLM turns (more decisive)
VLM_TURN_SPEED = 90                     # Speed for VLM turns (slightly < max)
VLM_ACTION_TIMEOUT_S = 8.0              # Expire stale VLM action after this long

# =============================================================================
# Remote Control (Teleoperation)
# =============================================================================

REMOTE_CMD_PORT   = 5557        # Mac→Pi: WASD commands
REMOTE_TELEM_PORT = 5558        # Pi→Mac: telemetry (distance, battery, state)
DANGER_DISTANCE   = 15          # cm — ultrasonic auto-stop threshold

# =============================================================================
# Phase 6 — Situation-Aware Behavior + Semantic Exploration
# =============================================================================

# ── Part A: Situation-Aware Behavior ──────────────────────────────
# VLM reads the scene every few seconds and sets a behavior mode that
# modifies how the dog follows: speed, arrival distance, bark, idle pose.
#
# V2: DEFERRED, not deleted (docs/phase1-briefing.md §6.2). The behavior
# modes existed to modulate courtship of a *known owner* — GENTLE near a
# sitting owner, PLAYFUL for an active one. With any-human following there
# is nothing for mode discrimination to key off, so llava's 5.5 GB RAM and
# ~9 s pre-warm buy nothing. While False: no VLMReasoner is constructed, no
# worker thread starts, no query is queued, and Ollama is NOT a runtime
# dependency. Behavior stays pinned at BEHAVIOR_DEFAULT_MODE. The
# _consume_situation plumbing on both sides stays in place dormant, so
# re-enabling is this one flag — a value-for-cost deferral, not a
# capability retreat.
VLM_SITUATION_ENABLED    = False
VLM_SITUATION_INTERVAL_S = 2.5      # seconds between situation queries
VLM_SITUATION_TIMEOUT_S  = 8.0      # discard stale mode after this

BEHAVIOR_MODES = {
    # arrival_cm:    real depth-based arrival distance (Phase B, OAK-D depth)
    # arrival_ratio: legacy bbox-area fallback used when depth unavailable
    # speed: all modes pinned to 98 (matches STRATEGIC_GAIT_SPEED) so the
    # dog walks the same pace in FOLLOW as in EXPLORE — user-requested
    # 2026-04-27 to eliminate "slow motion" perception when SITUATION VLM
    # downgrades to CALM/GENTLE. Per-mode arrival/bark/pose still vary.
    "ACTIVE":  {"speed": 98, "arrival_cm": 90,  "arrival_ratio": 0.55, "bark_enabled": True,  "bark_volume": 80, "idle_pose": "stand"},
    "GENTLE":  {"speed": 98, "arrival_cm": 70,  "arrival_ratio": 0.45, "bark_enabled": True,  "bark_volume": 40, "idle_pose": "sit"},
    "CALM":    {"speed": 98, "arrival_cm": 60,  "arrival_ratio": 0.40, "bark_enabled": False, "bark_volume": 0,  "idle_pose": "lie"},
    "PLAYFUL": {"speed": 98, "arrival_cm": 100, "arrival_ratio": 0.60, "bark_enabled": True,  "bark_volume": 80, "idle_pose": "stand"},
    "SOCIAL":  {"speed": 98, "arrival_cm": 80,  "arrival_ratio": 0.50, "bark_enabled": False, "bark_volume": 0,  "idle_pose": "stand"},
}

BEHAVIOR_DEFAULT_MODE = "ACTIVE"

# ── Part B: Costmap+LiDAR Exploration ──────────────────────────────
# EXPLORE state is driven by costmap find-best-gap + LiDAR. Local 7B VLM
# was removed 2026-04-25 — curl-test confirmed Tier 3 fail on
# llava-llama3:8b for structured-constraint reasoning. Object-matching,
# not strategic. See project_vlm_strategic_design.md.
EXPLORE_STEP_COUNT        = 6       # steps per forward move in EXPLORE

# ── Part C: Strategic VLA (hosted Anthropic API, Level 3) ──────────
# claude-haiku-4-5 fires per-goal during EXPLORE — picks a cardinal
# direction (FORWARD/LEFT/RIGHT/BACK) given the OAK-D frame + LiDAR
# clearances. NOT per-frame — fires on EXPLORE entry + STRATEGIC_GOAL_TTL_S
# expiry only. See project_vlm_strategic_design.md Level 3 for the curl-test
# validation and full architecture. Requires ANTHROPIC_API_KEY in .env.
STRATEGIC_VLM_MODEL       = "claude-haiku-4-5"
STRATEGIC_GOAL_TTL_S      = 5.0     # seconds before re-firing strategic query (was 30 — Strategic VLM v2 final 2026-04-25, plan-execute-wait architecture). Body-frame decay during cycle bounded by next cycle's fresh re-evaluation. TTL clock starts at response receipt (verified at follower.py:535), so slow API calls don't compress execution window. See project_vlm_strategic_design.md.
STRATEGIC_DAILY_CALL_CAP  = 500     # cost runaway protection — costmap-only fallback when exceeded
# 3-state clearance thresholds for the strategic prompt (BLOCKED < TIGHT < CLEAR)
STRATEGIC_BLOCKED_CM      = 50      # < this = BLOCKED (matches LIDAR_OBSTACLE_CM)
STRATEGIC_TIGHT_CM        = 150     # >= BLOCKED and < this = TIGHT; >= this = CLEAR
# Disable the entire strategic path (e.g. when offline). Falls back to
# costmap-only EXPLORE (current post-removal behavior). Default True so
# absence of API key naturally degrades — `StrategicReasoner.__init__`
# also short-circuits if ANTHROPIC_API_KEY is unset.
STRATEGIC_VLM_ENABLED     = True
# Stall fallback for v3 perceive-act loop. If PERCEIVING substate exceeds
# this without a strategic response landing, transition to EXECUTING with
# costmap-only routing (target_angle=0) for one cycle so the dog doesn't
# freeze indefinitely on API hiccups. Mac-side time — no Pi-jitter
# concern (per feedback_no_time_logic_pi.md, Pi timing is unreliable;
# Mac measuring its own outstanding API call is fine). See
# project_vlm_strategic_design.md → Strategic VLM v3 final.
STRATEGIC_PERCEIVE_TIMEOUT_S = 10.0
# v3 PERCEIVING floor — minimum time PERCEIVING must last before
# transitioning to EXECUTING, even when the strategic VLM responds faster.
# Reduces v3's cycles-per-minute rate. STRATEGIC_PERCEIVE_TIMEOUT_S=10s
# remains the ceiling (stall fallback); MIN_PERCEIVE_S is the floor.
# Tuned 2026-04-26 from 5.0 → 3.0 to reduce holding-torque cumulative
# energy per minute (servos hold pose with full torque during
# PERCEIVING; the SDK has no servo-release path). Cycle period now
# ~5s (3s perceive + 2s exec) instead of ~7s. More cycles per minute,
# but less pose-hold time per cycle. Trades some servo cooling time
# for shorter continuous holding-torque draw. Reversible — bump back
# up if cycle rate causes thermal issues.
# See project_vlm_strategic_design.md → Strategic VLM v3 final.
MIN_PERCEIVE_S = 3.0
# v3 EXECUTING substate timeout. If a cycle's gait never reports
# completion (buffer_depth==0 after observing >0), force DONE after this.
# Belt-and-suspenders for telemetry hangs / Pi freezes — without it, a
# stuck cycle would prevent any further VLM queries from firing. Real
# v3 cycles should be 1-5s of EXECUTING; 15s is generous. Tune down if
# real gait dynamics settle faster.
STRATEGIC_EXECUTE_TIMEOUT_S = 15.0
# v3 turn step_count — separate from FOLLOW's BODY_TURN_STEP_COUNT (=4
# as of 2026-04-27). v3 perceive-act cycles at the original step_count=8
# queued ~400 frames per turn (~4s of continuous high-current
# servo motion). Multiple cycles of that profile triggered Pi-side
# undervoltage on the shared servo+Pi battery rail (kernel log:
# "hwmon hwmon3: Undervoltage detected!" → freeze). step_count=4 halves
# the per-cycle continuous load (~2s of high-current per cycle, with
# ~1.5s PERCEIVING idle between) — much friendlier to the battery rail.
# See project_plan_a_explore_memory.md → Pi freeze hypothesis.
STRATEGIC_TURN_STEP_COUNT = 4
# v3 forward/turn gait speed — separate from FOLLOW's behavior_params
# (ACTIVE=98). Reverted to 98 after the speed=94 trace 2026-04-25
# still froze at approximately the same elapsed time, confirming speed
# isn't the primary undervoltage driver. Cumulative-load / battery-SOC /
# camera+LiDAR power draw are the more likely candidates. Backward
# (safety) also at 98 since slow backward tips per platform fact.
# See project_plan_a_explore_memory.md.
STRATEGIC_GAIT_SPEED = 98

# Head pitch during SEARCH/EXPLORE (negative = looking down toward the floor).
# During FOLLOW the head is pitched up to track the owner's face, which is
# terrible for navigating — searching for doorways by looking at the ceiling
# is useless. When no owner is visible, pitch the head forward-and-down so
# the VLM can actually see floor, thresholds, and low obstacles.
#
# Tilted more aggressively (was -10) since the OAK-D Lite is mounted higher
# than the old ribbon cam — needs more pitch-down to see the floor.
# Range allowed by SDK: HEAD_PITCH_MIN=-45 to HEAD_PITCH_MAX=30.
EXPLORE_HEAD_PITCH        = -35

# ── Dual-camera setup (ribbon cam for navigation) ─────────────────
# The PiDog ships with a ribbon camera on the nose (forward-facing, level
# with the floor). We use it as a dedicated "navigation eye" during
# SEARCH/EXPLORE so the VLM reasons about doorways and obstacles instead
# of whatever angle the webcam's head servo happens to be at.
#
# Wire-up:
#   - Pi runs TWO pi_sender processes: webcam → ZMQ_PORT, ribbon → ZMQ_NAV_PORT
#   - Mac follower.py binds both ports, pulls from each, passes nav frame
#     to pipeline.process_frame(frame, nav_frame=...)
#   - If the ribbon cam stream is unavailable, process_frame silently
#     falls back to the webcam for explore queries — no failure mode.
ZMQ_NAV_PORT              = 50506   # ribbon camera stream (nose, forward)
USE_RIBBON_CAM            = False   # OAK-D Lite handles both owner + nav now;
                                     # head tilts down (EXPLORE_HEAD_PITCH) for floor view

# ── V2: DogZilla S2 motor controller (pi/motor_controller.py) ─────────
# All values below are grounded in the 2026-08-28/29 smoke-test passes
# (docs/measurements/smoke_*.jsonl). The S2 is a velocity-setpoint
# machine: movement calls are non-blocking and continuous until stop().
V2_MOTION_PORT      = "/dev/ttyAMA0"  # ESP32 motion MCU, 115200 (needs dtparam=uart0=on)
V2_FORWARD_STEP_MAX = 14   # forward()/back() step at speed=100; SDK range [0,25].
                           # 25 is "relatively fast" per Yahboom — start moderate.
V2_TURN_RATE_DPS    = 40   # turnleft/turnright step ≈ °/s (measured 39.2 at 40).
                           # Fixed rate for FOLLOW centering; speed field doesn't scale it (v0).
V2_STRAFE_STEP      = 10   # left()/right() step; SDK range [0,18]. No Mac vocab yet.
V2_ATTITUDE_PITCH_LIMIT = 15  # attitude('p') clamp; SDK range [-15,15]. Q7: composes with gait.
V2_LOOP_HZ          = 50   # controller loop; reads are ~3ms so this is comfortable
V2_TELEM_EVERY_TICKS = 5   # publish telemetry at LOOP_HZ/5 = 10 Hz
V2_BATTERY_EVERY_TICKS = 250  # battery read cadence (~5s); percent sags under load
# ── V2: Oradar MS200 lidar (pi/ms200_reader.py) ──────────────────────
# MEASURE: the MS200 is wired to a Pi UART, but which one is unknown until
# the cable is traced and the matching overlay is added to
# /boot/firmware/config.txt. On this vanilla-trixie Pi only /dev/ttyAMA0
# (motion MCU, created by dtparam=uart0=on) and /dev/ttyAMA10 (the Pi 5
# debug connector) exist today — there is no lidar port yet. Yahboom's own
# factory image exposes it as ttyAMA1, so ttyAMA1/ttyAMA2 are the leading
# candidates. Set this once `ms200_reader.py --dump` returns real bytes.
# ── V2: deadman (hold-to-arm) for supervised sessions ────────────────
# Teleop approximates true key-held arming: tap F to arm, and ANY
# recognised key refreshes the arm. Release everything and the arm lapses
# after this long, so walking away from the keyboard stops the dog.
# Must comfortably exceed the terminal's initial key-repeat delay
# (~0.25-0.5 s on macOS) or holding W would disarm mid-stride.
V2_DEADMAN_LAPSE_S  = 1.0

V2_LIDAR_PORT       = "/dev/ttyAMA2"
V2_LIDAR_BAUD       = 230400  # fixed by the MS200 (Oradar SDK: 8N1 @ 230400)

V2_CMD_WATCHDOG_TICKS  = 75   # loop ticks without any Mac command before auto-stop
                              # (count predicate, not wall-clock, per V1 discipline;
                              # 75 ticks at 50 Hz ≈ 1.5s of Mac silence)
