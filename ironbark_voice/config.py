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
VOICE_ID: str | None = None  # Brian picks from the shortlist; None until then

# --- Audio output (PC dev mode) ----------------------------------------------------------
OUTPUT_DEVICE: int | str | None = None  # Brian: system default for now (None = default)

# --- Robot (read-only) -------------------------------------------------------------------
PI_HOST = "raspberrypi.local"  # memory: lolly@raspberrypi.local (192.168.68.56)
TELEMETRY_PORT = 5558  # Pi PUBs telemetry JSON here (CLAUDE.md wire protocol)

# --- Latency -----------------------------------------------------------------------------
LATENCY_TARGET_P50_S = 1.5  # Brian: event -> first sound, median; revisit after measuring
MEASUREMENTS_DIR = REPO_ROOT / "docs" / "measurements"  # voice_latency_*.jsonl land here
