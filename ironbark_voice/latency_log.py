"""Per-line latency records, so Brian's 1.5 s median target is measured, not assumed.

One JSON line per spoken line in docs/measurements/voice_latency_<date>.jsonl. Times are
perf_counter seconds (PC side, so wall-clock timers are fine here); the record stores the
intervals, which is what the target is about.
"""

import json
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ironbark_voice import config
from ironbark_voice.player import PlaybackTiming


@dataclass(frozen=True)
class LineTiming:
    event: str  # what triggered the line, e.g. "target_reacquired"
    source: str  # "cache" (no API call) or "haiku"
    text: str
    event_s: float  # trigger fired
    text_ready_s: float  # line text known (for a cached line this equals event_s)
    playback: PlaybackTiming
    voice_id: str | None = None
    tts_model: str | None = None
    haiku_input_tokens: int | None = None
    haiku_output_tokens: int | None = None

    def record(self) -> dict:
        """Flat dict of the intervals that matter, in seconds (None where there was no sound).

        Example: event at 10.00, text at 10.42, first write at 10.71, device latency 0.18
                 -> event_to_text_s 0.42, text_to_first_write_s 0.29, event_to_first_sound_s 0.89
        """
        pb = self.playback
        return {
            "logged_at": datetime.now().isoformat(timespec="milliseconds"),  # when, for humans
            "event": self.event,
            "source": self.source,
            "text": self.text,
            "voice_id": self.voice_id,
            "tts_model": self.tts_model,
            "event_to_text_s": self.text_ready_s - self.event_s,  # Haiku time (0 for cache)
            "text_to_first_write_s": None if pb.first_write_s is None else pb.first_write_s - self.text_ready_s,  # TTS time to first audio
            "device_latency_s": pb.output_latency_s,  # the OS's buffer estimate, not measured at the speaker
            # The number Brian's target is about: first write + device buffer - trigger.
            "event_to_first_sound_s": None if pb.first_sound_s is None else pb.first_sound_s - self.event_s,
            "playback_s": pb.end_s - (pb.first_write_s if pb.first_write_s is not None else pb.start_s),
            "audio_bytes": pb.num_bytes,
            "haiku_input_tokens": self.haiku_input_tokens,
            "haiku_output_tokens": self.haiku_output_tokens,
        }


def default_log_path() -> Path:
    return config.MEASUREMENTS_DIR / f"voice_latency_{datetime.now():%Y-%m-%d}.jsonl"  # one file per day


def append(timing: LineTiming, path: Path | None = None) -> dict:
    path = Path(path) if path else default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = timing.record()
    with path.open("a", encoding="utf-8") as f:  # append: a crash mid-session keeps earlier lines
        f.write(json.dumps(rec) + "\n")
    return rec


def summarize(path: Path) -> dict:
    """Median and spread of event -> first sound, split by source, against Brian's target."""
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    out = {"target_p50_s": config.LATENCY_TARGET_P50_S}
    for source in ("cache", "haiku", "all"):
        values = sorted(
            r["event_to_first_sound_s"]
            for r in rows
            if r["event_to_first_sound_s"] is not None and (source == "all" or r["source"] == source)
        )
        if values:
            out[source] = {
                "n": len(values),
                "p50_s": statistics.median(values),
                "max_s": values[-1],
                "meets_target": statistics.median(values) < config.LATENCY_TARGET_P50_S,
            }
    return out
