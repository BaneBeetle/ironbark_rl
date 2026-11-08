"""Voice settings in one place.

Values marked "Brian" are his design calls (docs/voice/decisions.md); change them only
with his say-so. Values marked "docs" come from the vendor docs on 2026-11-07.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]  # the worktree root, where .env lives

# --- Secrets -----------------------------------------------------------------------------
# load_dotenv never overrides variables already set in the shell, so a key exported by
# hand wins over the file. .env is gitignored; .env.example lists the names.
load_dotenv(REPO_ROOT / ".env")


def require_env(name: str) -> str:
    """Return an env var or fail with a message that says where to put it."""
    value = os.environ.get(name, "").strip()  # strip: a stray space in .env would 401
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to {REPO_ROOT / '.env'} (see .env.example).")
    return value


# --- Brain (Claude) ----------------------------------------------------------------------
HAIKU_MODEL = "claude-haiku-5-5"  # Brian: Haiku for novel lines
HAIKU_EFFORT = "low"  # a 12-word quip needs no deliberation; lower effort = faster reply
HAIKU_MAX_TOKENS = 100  # ~12 words is ~20 tokens; 100 leaves room without letting it ramble
MAX_WORDS_PER_LINE = 12  # Brian, 2026-11-07

# --- Voice (ElevenLabs) ------------------------------------------------------------------
# docs: Flash v2.5 is the lowest-latency model (~100 ms median model inference, network
# not included); turbo_v2_5 is deprecated in its favor.
TTS_MODEL = "eleven_flash_v2_5"
# docs: raw 16-bit little-endian mono PCM, no header, so it plays with no decoder.
# The default Windows device opens at 24 kHz (checked 2026-11-07); the OS resamples.
TTS_OUTPUT_FORMAT = "pcm_24000"
TTS_SAMPLE_RATE_HZ = 24_000  # must match TTS_OUTPUT_FORMAT
TTS_SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
# Brian, 2026-11-07: Tilly from the Voice Library (he's on the Creator plan, so library
# voices work via the API). A small squeaky voice playing a big laid-back bro is the joke.
VOICE_ID: str | None = "MkTSSXNgnBULS6ek4pon"

# --- Audio output (PC dev mode) ----------------------------------------------------------
# Brian: system default for now (None = default). To pick one, use part of its name (e.g.
# "Realtek Digital Output"), not its number: numbers shift when headphones connect.
OUTPUT_DEVICE: str | None = None

# --- Robot (read-only) -------------------------------------------------------------------
PI_HOST = "raspberrypi.local"  # memory: lolly@raspberrypi.local (192.168.68.56)
TELEMETRY_PORT = 5558  # Pi PUBs telemetry JSON here (CLAUDE.md wire protocol)

# --- Speech pacing (Brian, 2026-11-07) ------------------------------------------------------
# Wall-clock seconds are fine here: this runs on the PC, never on the Pi.
# ASSUMED, for Brian to confirm: both gaps count from when the previous line finished playing,
# and the 4 s quiet applies after any line (cached or Haiku).
CACHED_LINE_COOLDOWN_S = 4.0  # quiet after a line before the next cached line
HAIKU_LINE_MIN_SPACING_S = 30.0  # at least this long between two Haiku-generated lines
URGENT_EVENTS = frozenset({"fell", "battery_low"})  # cached, and skip the cooldown

# --- Budget ------------------------------------------------------------------------------
ELEVENLABS_MONTHLY_CREDITS = 121_000  # Brian, 2026-11-07: Creator plan (key stays restricted, so not readable via API)

# --- Latency -----------------------------------------------------------------------------
LATENCY_TARGET_P50_S = 1.5  # Brian: event -> first sound, median; revisit after measuring
MEASUREMENTS_DIR = REPO_ROOT / "docs" / "measurements"  # voice_latency_*.jsonl land here
