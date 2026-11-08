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


class GatedPlayer:
    """Threaded test player: each line plays until the test opens its gate (or a stop arrives)."""

    def __init__(self):
        self.log = []  # ("start" | "done" | "cut", event text)
        self.gates = {}  # text -> threading.Event the test sets to let that line finish
        self.started = {}  # text -> threading.Event set when that line starts

    def expect(self, text):
        self.gates[text], self.started[text] = threading.Event(), threading.Event()

    def play(self, chunks, stop=None):
        text = bytes(b"".join(chunks)).decode("utf-8")  # LabelCache puts the event name in the "audio"
        self.log.append(("start", text))
        self.started.setdefault(text, threading.Event()).set()
        gate = self.gates.setdefault(text, threading.Event())
        while not gate.wait(0.01):
            if stop is not None and stop.is_set():
                self.log.append(("cut", text))
                return PlaybackTiming(0, 0, 0, 0.0, 0, interrupted=True)
        self.log.append(("done", text))
        return PlaybackTiming(0, 0, 0, 0.0, 2)


class LabelCache(FakeCache):
    def pick(self, event):
        from ironbark_voice.line_cache import CachedClip
        return CachedClip(event=event, text=event, pcm=event.encode("utf-8"))  # "audio" = the event name


def threaded_loop(tmp_path, player):
    return VoiceLoop(cache=LabelCache(), writer=None, tts=FakeTTS(), player=player, speaker=Speaker(),
                     decisions_path=tmp_path / "decisions.jsonl", latency_path=tmp_path / "latency.jsonl",
                     out=lambda *_: None)


def wait_for(cond, timeout=3.0):
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_battery_low_waits_for_the_line_then_plays_right_after(tmp_path):
    """Brian, 2026-11-07: battery_low doesn't cut off a line; it plays as soon as the line ends."""
    player = GatedPlayer()
    loop = threaded_loop(tmp_path, player)
    loop.handle(RobotState(frame=0, target_visible=True, battery_pct=80))  # found: line starts
    assert player.started.setdefault("target_found", threading.Event()).wait(2.0)
    loop.handle(RobotState(frame=1, target_visible=True, battery_pct=15))  # battery_low while talking
    assert [d["outcome"] for d in decisions(tmp_path)][-1] == "queue"
    assert ("cut", "target_found") not in player.log  # not interrupted
    player.gates["target_found"].set()  # the line ends normally...
    assert wait_for(lambda: ("start", "battery_low") in player.log)  # ...and battery plays right after,
    player.gates["battery_low"].set()  # with no 4 s cooldown in between
    loop.wait()
    assert player.log == [("start", "target_found"), ("done", "target_found"), ("start", "battery_low"), ("done", "battery_low")]


def test_fall_still_cuts_off_and_a_cut_battery_line_comes_back(tmp_path):
    """A fall interrupts even the battery line; the battery line is requeued and plays after the fall."""
    player = GatedPlayer()
    loop = threaded_loop(tmp_path, player)
    loop.handle(RobotState(frame=0, battery_pct=15, roll_deg=0.0, pitch_deg=0.0))  # battery_low starts (idle)
    assert player.started.setdefault("battery_low", threading.Event()).wait(2.0)
    loop.handle(RobotState(frame=1, battery_pct=15, roll_deg=80.0, pitch_deg=0.0))  # fell -> interrupts
    assert wait_for(lambda: ("start", "fell") in player.log)
    player.gates["fell"].set()
    assert wait_for(lambda: player.log.count(("start", "battery_low")) == 2)  # battery comes back after the fall
    player.gates["battery_low"].set()
    loop.wait()
    assert player.log == [("start", "battery_low"), ("cut", "battery_low"), ("start", "fell"), ("done", "fell"),
                          ("start", "battery_low"), ("done", "battery_low")]
    assert "requeued" in " ".join(d["reason"] for d in decisions(tmp_path))


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
