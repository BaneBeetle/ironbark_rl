"""Instant lines with no API call: pre-generated audio for the common events.

Design: Brian (C1, C2). Lines: Claude's v2 drafts for persona v2 (docs/voice/next-pieces.md),
which Brian heard in samples. Code: Claude.
"""

import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

from ironbark_voice import config

# C1 (Brian): 3 variants per event. C2 (Brian): any event not in this table goes to Haiku.
CACHE_LINES: dict[str, tuple[str, ...]] = {
    "target_found": ("Yo, there's my guy. Let's roll.", "Got you, bro. I'm on it.", "Big dog's locked in. Lead the way."),
    "target_reacquired": ("There you are, man. Had me worried for a sec.", "Back on you, bro. We good.", "Found you again. Never doubted it."),
    "target_lost": ("Whoa, where'd you go, bro? Hang tight.", "Lost you, man. Big dog's on the case.", "Hold up, I lost you. Looking."),
    "battery_low": ("Bro, I'm running on fumes. Charger soon?", "Battery's low, man. Big dog needs a nap.", "Gonna need a charge soon, bro. No stress."),
    "fell": ("Oof. I'm good, bro. Little help though?", "Yeah, I ate it. Help a bro up?", "Took a tumble, man. Still cool. Mostly."),
}
CACHE_DIR = config.REPO_ROOT / "audio_cache"  # gitignored: rebuildable from the text above


@dataclass(frozen=True)
class CachedClip:
    event: str
    text: str
    pcm: bytes  # 16-bit mono at config.TTS_SAMPLE_RATE_HZ, ready to play


class LineCache:
    def __init__(self, voice_id: str = config.VOICE_ID, model_id: str = config.TTS_MODEL,
                 output_format: str = config.TTS_OUTPUT_FORMAT, root: Path = CACHE_DIR,
                 lines: dict[str, tuple[str, ...]] = CACHE_LINES, rng: random.Random | None = None):
        self.voice_id, self.model_id, self.output_format = voice_id, model_id, output_format
        self.root = Path(root)
        self.lines = lines
        self._rng = rng or random.Random()  # injectable so tests are deterministic
        self._last: dict[str, int] = {}  # event -> variant index said last time (C1: never twice in a row)
        self._pcm: dict[str, bytes] = {}  # text -> audio, loaded once so a pick never touches the disk

    def path_for(self, text: str) -> Path:
        """One file per (voice, model, format, text): change any of them and only that clip is rebuilt.

        Example: "Got you, bro. I'm on it." -> audio_cache/MkTSSXNgnBULS6ek4pon/3f1c9a0b2d4e5f61.pcm
        """
        key = f"{self.model_id}|{self.output_format}|{text}".encode("utf-8")
        return self.root / self.voice_id / f"{hashlib.sha1(key).hexdigest()[:16]}.pcm"

    def has(self, event: str) -> bool:
        return event in self.lines

    def build(self, tts) -> dict:
        """Generate any missing clips, then load them all. Returns counts and credits spent."""
        built = skipped = credits = 0
        for text in (t for variants in self.lines.values() for t in variants):
            path = self.path_for(text)
            if path.exists():
                skipped += 1  # already paid for; don't spend credits again
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(tts.synthesize_pcm(text))
                built += 1
                credits += tts.last_credits or 0
            self._pcm[text] = path.read_bytes()
        return {"built": built, "skipped": skipped, "credits": credits}

    def pick(self, event: str) -> CachedClip | None:
        """A random variant, never the one said last time for this event. None if the event isn't cached.

        Example: pick("target_lost") -> CachedClip(text="Hold up, I lost you. Looking.", pcm=b"...")
        """
        variants = self.lines.get(event)
        if not variants:
            return None
        choices = [i for i in range(len(variants)) if i != self._last.get(event)] or [0]
        i = self._rng.choice(choices)
        self._last[event] = i
        text = variants[i]
        if text not in self._pcm:
            raise RuntimeError(f"cache not built for {text!r}: call LineCache.build(tts) at startup")
        return CachedClip(event=event, text=text, pcm=self._pcm[text])
