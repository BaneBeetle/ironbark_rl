"""The voice loop: robot state -> triggers -> pacing -> cached line or Haiku -> staleness -> speaker.

  .venv\\Scripts\\python -m ironbark_voice.run                       # synthetic replay (dev mode)
  .venv\\Scripts\\python -m ironbark_voice.run --replay path.jsonl
  .venv\\Scripts\\python -m ironbark_voice.run --telemetry           # live Pi telemetry, read-only

Read-only on the robot: it only listens to telemetry and never sends a command, so it can't
move the dog. Plays on the PC speakers (dev mode).

Logs:
- every decision -> docs/measurements/voice_decisions_<date>.jsonl
- every spoken line -> docs/measurements/voice_latency_<date>.jsonl
"""

import argparse
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from ironbark_voice import config, latency_log
from ironbark_voice.latency_log import LineTiming
from ironbark_voice.player import split_pcm
from ironbark_voice.speech_policy import SpeechPolicy
from ironbark_voice.state import RobotState, state_summary
from ironbark_voice.triggers import Event, TriggerDetector

DEMO_REPLAY = config.REPO_ROOT / "docs" / "voice" / "replays" / "follow_demo.jsonl"


class Speaker:
    """Runs one line at a time on a background thread, so the loop keeps reading state while the
    dog talks, and an urgent event can cut the line off (P2)."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, job) -> None:
        self._stop = threading.Event()  # a fresh flag per line, so an old cut-off can't stop the new one
        self._thread = threading.Thread(target=job, args=(self._stop,), daemon=True)
        self._thread.start()

    def interrupt(self, wait_s: float = 0.3) -> None:
        """Ask the current line to stop. Playback notices within ~50 ms. A Haiku request in flight
        can't be cancelled, but its line is thrown away when it returns (it checks the flag)."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(wait_s)

    def wait(self) -> None:
        if self._thread is not None:
            self._thread.join()


class InlineSpeaker:
    """Runs each line immediately on the caller's thread: deterministic, for tests."""

    busy = False

    def start(self, job) -> None:
        job(threading.Event())

    def interrupt(self, wait_s: float = 0.0) -> None:
        pass

    def wait(self) -> None:
        pass


class VoiceLoop:
    def __init__(self, cache, writer, tts, player, detector=None, policy=None, speaker=None,
                 clock=time.perf_counter, decisions_path: Path | None = None, latency_path: Path | None = None, out=print):
        self.cache, self.writer, self.tts, self.player = cache, writer, tts, player
        self.detector = detector or TriggerDetector(clock=clock)
        self.policy = policy or SpeechPolicy()
        self.speaker = speaker or Speaker()
        self.clock = clock
        self.decisions_path = decisions_path
        self.latency_path = latency_path
        self.out = out
        self.state: RobotState | None = None  # latest state; staleness and Haiku read it
        self._play_lock = threading.Lock()  # one sound at a time, even while a cut-off line winds down

    # --- main thread ---------------------------------------------------------------------------
    def handle(self, state: RobotState) -> None:
        self.state = state
        events = self.detector.update(state)
        # Same-frame order: urgent first, then cached, then Haiku. After the first is spoken,
        # the rest find the dog busy and are dropped (P3).
        events.sort(key=lambda e: (not e.urgent, not self.cache.has(e.name)))
        for event in events:
            self._on_event(event)

    def _on_event(self, event: Event) -> None:
        source = "cache" if self.cache.has(event.name) else "haiku"  # C2
        decision = self.policy.decide(event, source, self.clock(), self.speaker.busy)
        self._log_decision(event, source, "speak" if decision.speak else "drop", decision.reason)
        if not decision.speak:
            return
        if decision.interrupt:
            self.speaker.interrupt()
        self.speaker.start(lambda stop: self._speak(event, source, stop))

    def wait(self) -> None:
        self.speaker.wait()

    # --- speaker thread ------------------------------------------------------------------------
    def _speak(self, event: Event, source: str, stop: threading.Event) -> None:
        try:
            usage = {}
            if source == "cache":
                clip = self.cache.pick(event.name)
                text, chunks = clip.text, split_pcm(clip.pcm)  # short pieces so a cut-off is quick
            else:
                result = self.writer.write_line(event.name, state_summary(self.state))
                if not result.text:
                    self._log_decision(event, source, "skip", "Haiku returned nothing speakable")
                    return
                text, chunks = result.text, None  # streamed from ElevenLabs below
                usage = {"haiku_input_tokens": result.input_tokens, "haiku_output_tokens": result.output_tokens}
            text_ready = self.clock()
            if stop.is_set():
                self._log_decision(event, source, "skip", "cut off before it started")
                return
            stale = self.policy.stale_reason(event, self.state, text_ready)  # P4, checked once, here
            if stale:
                self._log_decision(event, source, "stale", stale)
                return
            with self._play_lock:  # waits (~50 ms) for a cut-off line to go quiet
                if stop.is_set():
                    self._log_decision(event, source, "skip", "cut off before it started")
                    return
                if chunks is None:
                    chunks = self.tts.stream_pcm(text)
                playback = self.player.play(chunks, stop=stop)
            self.policy.line_finished(source, self.clock())  # the 4 s / 30 s gaps start now
            spoken = text if source == "cache" else (self.tts.last_text or text)
            rec = latency_log.append(LineTiming(
                event=event.name, source=source, text=spoken, event_s=event.time_s, text_ready_s=text_ready,
                playback=playback, voice_id=getattr(self.tts, "voice_id", None), tts_model=getattr(self.tts, "model_id", None),
                tts_credits=self.tts.last_credits if source == "haiku" else 0, **usage), self.latency_path)
            first = rec["event_to_first_sound_s"]
            cut = " (cut off)" if playback.interrupted else ""
            self.out(f"    said{cut}: \"{spoken}\" [{source}] first sound {first:.2f} s after the event" if first is not None
                     else f"    said nothing{cut} [{source}]")
        except Exception as e:  # a failed line must never stop the loop
            self._log_decision(event, source, "error", f"{type(e).__name__}: {e}")

    def _log_decision(self, event: Event, source: str, outcome: str, reason: str) -> None:
        self.out(f"[frame {event.frame:>4}] {event.name:<18} {source:<5} {outcome:<5} {reason}")
        if self.decisions_path is not None:
            self.decisions_path.parent.mkdir(parents=True, exist_ok=True)
            with self.decisions_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"logged_at": datetime.now().isoformat(timespec="milliseconds"), "frame": event.frame,
                                    "event": event.name, "urgent": event.urgent, "source": source,
                                    "outcome": outcome, "reason": reason}) + "\n")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ironbark_voice.run", description="IronBark voice loop (PC speakers).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--replay", type=Path, help=f"JSONL scenario (default: {DEMO_REPLAY.relative_to(config.REPO_ROOT)})")
    group.add_argument("--telemetry", action="store_true", help="listen to the Pi's telemetry (read-only)")
    args = parser.parse_args(argv)

    from ironbark_voice.brain import LineWriter
    from ironbark_voice.line_cache import LineCache
    from ironbark_voice.player import PcmPlayer
    from ironbark_voice.state import ReplaySource, TelemetrySource
    from ironbark_voice.tts import ElevenLabsTTS

    # Setup happens before any event, so imports and connections never count as line latency.
    tts = ElevenLabsTTS(voice_id=config.VOICE_ID)
    cache = LineCache()
    print(f"cache: {cache.build(tts)}")  # first run spends ~120 credits; later runs spend nothing
    day = f"{datetime.now():%Y-%m-%d}"
    loop = VoiceLoop(cache=cache, writer=LineWriter(), tts=tts, player=PcmPlayer(),
                     decisions_path=config.MEASUREMENTS_DIR / f"voice_decisions_{day}.jsonl",
                     latency_path=config.MEASUREMENTS_DIR / f"voice_latency_{day}.jsonl")
    source = TelemetrySource() if args.telemetry else ReplaySource(args.replay or DEMO_REPLAY)
    print("listening to Pi telemetry (read-only); Ctrl+C to stop" if args.telemetry else f"replaying {args.replay or DEMO_REPLAY.name}")
    try:
        for state in source.states():
            loop.handle(state)
    except KeyboardInterrupt:
        pass
    finally:
        if args.telemetry:
            source.stop()
        loop.wait()  # let the last line finish


if __name__ == "__main__":
    main()
