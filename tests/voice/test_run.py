"""Voice loop end to end with fakes: real triggers and pacing, fake audio/LLM, a hand-driven clock."""

import json
import threading

from ironbark_voice.brain import LineResult
from ironbark_voice.player import PlaybackTiming
from ironbark_voice.run import InlineSpeaker, Speaker, VoiceLoop
from ironbark_voice.state import RobotState


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeCache:
    lines = {"target_found": ("Yo.",), "target_lost": ("Lost you.",), "fell": ("Oof.",), "battery_low": ("Low.",),
             "target_reacquired": ("Back.",)}

    def has(self, event):
        return event in self.lines

    def pick(self, event):
        from ironbark_voice.line_cache import CachedClip
        return CachedClip(event=event, text=self.lines[event][0], pcm=b"\x00\x00" * 100)


class FakeWriter:
    def __init__(self, clock, delay_s=0.5, text="New vibe, bro."):
        self.clock, self.delay_s, self.text, self.calls = clock, delay_s, text, []

    def write_line(self, event, summary):
        self.calls.append((event, summary))
        self.clock.t += self.delay_s  # Haiku takes time
        return LineResult(text=self.text, words=3, over_limit=False, latency_s=self.delay_s, input_tokens=300, output_tokens=8, request_id=None)


class FakeTTS:
    voice_id, model_id, last_credits, last_text = "v", "m", 7, None

    def stream_pcm(self, text):
        self.last_text = text
        return iter([b"\x00\x00" * 100])


class FakePlayer:
    def __init__(self, clock, line_s=2.0):
        self.clock, self.line_s, self.played = clock, line_s, []

    def play(self, chunks, stop=None):
        start = self.clock.t
        data = b"".join(chunks)
        self.clock.t += self.line_s  # the line takes this long to play
        self.played.append(data)
        return PlaybackTiming(start_s=start, first_write_s=start + 0.05, end_s=self.clock.t, output_latency_s=0.18, num_bytes=len(data))


def make_loop(tmp_path, clock, writer_delay=0.5):
    writer = FakeWriter(clock, delay_s=writer_delay)
    player = FakePlayer(clock)
    lines = []
    loop = VoiceLoop(cache=FakeCache(), writer=writer, tts=FakeTTS(), player=player, speaker=InlineSpeaker(),
                     clock=clock, decisions_path=tmp_path / "decisions.jsonl", latency_path=tmp_path / "latency.jsonl",
                     out=lines.append)
    return loop, writer, player, lines


def decisions(tmp_path):
    return [json.loads(l) for l in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]


def test_cached_line_then_cooldown_drop_then_spoken(tmp_path):
    clock = Clock()
    loop, _, player, _ = make_loop(tmp_path, clock)
    loop.handle(RobotState(frame=0, target_visible=True))  # found -> spoken, line ends at t=2.0
    for f in range(1, 4):  # lost after 3 frames, at t=3.0 -> only 1 s of quiet -> dropped
        clock.t = 2.0 + f / 3
        loop.handle(RobotState(frame=f, target_visible=False))
    clock.t = 7.0
    loop.handle(RobotState(frame=4, target_visible=True))  # reacquired, 5 s after the last line -> spoken
    got = [(d["event"], d["outcome"]) for d in decisions(tmp_path)]
    assert got == [("target_found", "speak"), ("target_lost", "drop"), ("target_reacquired", "speak")]
    assert len(player.played) == 2


def test_haiku_handles_uncached_events_with_state_summary(tmp_path):
    clock = Clock()
    loop, writer, player, _ = make_loop(tmp_path, clock)
    loop.handle(RobotState(frame=0, behavior="IDLE", battery_pct=80))
    loop.handle(RobotState(frame=1, behavior="FOLLOW", battery_pct=80))
    assert writer.calls == [("behavior_changed", "behavior=FOLLOW battery=80%")]
    rec = json.loads((tmp_path / "latency.jsonl").read_text(encoding="utf-8"))
    assert rec["source"] == "haiku" and rec["text"] == "New vibe, bro." and rec["tts_credits"] == 7


def test_slow_haiku_line_is_dropped_as_stale(tmp_path):
    clock = Clock()
    loop, _, player, _ = make_loop(tmp_path, clock, writer_delay=2.0)  # older than 1.5 s when ready
    loop.handle(RobotState(frame=0, behavior="IDLE"))
    loop.handle(RobotState(frame=1, behavior="FOLLOW"))
    assert decisions(tmp_path)[-1]["outcome"] == "stale" and player.played == []


def test_same_frame_urgent_goes_first(tmp_path):
    clock = Clock()
    loop, _, player, _ = make_loop(tmp_path, clock)
    loop.handle(RobotState(frame=0, target_visible=True, battery_pct=15))  # found + battery_low on one frame
    assert [d["event"] for d in decisions(tmp_path)][0] == "battery_low"


def test_real_speaker_cuts_a_line_off_for_a_fall(tmp_path):
    """Threaded: a long cached line is playing when a fall arrives; the fall interrupts it."""
    played, started = [], threading.Event()

    class SlowPlayer:
        def play(self, chunks, stop=None):
            n = 0
            for _ in chunks:
                started.set()
                if stop is not None and stop.wait(0.01):
                    played.append(("cut", n))
                    return PlaybackTiming(0, 0, 0, 0.0, n, interrupted=True)
                n += 1
            played.append(("done", n))
            return PlaybackTiming(0, 0, 0, 0.0, n)

    class LongCache(FakeCache):
        def pick(self, event):
            from ironbark_voice.line_cache import CachedClip
            return CachedClip(event=event, text=event, pcm=b"\x00\x00" * 24_000 * 10)  # 10 s line

    loop = VoiceLoop(cache=LongCache(), writer=None, tts=FakeTTS(), player=SlowPlayer(), speaker=Speaker(),
                     latency_path=tmp_path / "latency.jsonl", out=lambda *_: None)
    loop.handle(RobotState(frame=0, target_visible=True, roll_deg=0.0, pitch_deg=0.0))  # found: long line starts
    assert started.wait(2.0)
    loop.handle(RobotState(frame=1, target_visible=True, roll_deg=80.0, pitch_deg=0.0))  # fell -> interrupt
    loop.wait()
    assert played[0][0] == "cut" and played[1][0] in ("cut", "done") and len(played) == 2
