"""Line cache with a fake TTS and a temp folder: no network."""

import random

import pytest

from ironbark_voice import config
from ironbark_voice.line_cache import CACHE_LINES, LineCache


class FakeTTS:
    def __init__(self):
        self.calls = []
        self.last_credits = None

    def synthesize_pcm(self, text):
        self.calls.append(text)
        self.last_credits = 7
        return text.encode("utf-8")  # stand-in audio: the text's bytes


def test_cache_table_follows_c1_and_the_word_cap():
    for event, variants in CACHE_LINES.items():
        assert len(variants) == 3, event  # C1: 3 variants
        assert all(len(v.split()) <= config.MAX_WORDS_PER_LINE for v in variants)
        assert all("!" not in v for v in variants)  # no squeak spikes (Brian picked variant B)


def test_build_once_then_skip(tmp_path):
    tts = FakeTTS()
    cache = LineCache(voice_id="v", root=tmp_path, lines={"a": ("one", "two")})
    assert cache.build(tts) == {"built": 2, "skipped": 0, "credits": 14}
    assert LineCache(voice_id="v", root=tmp_path, lines={"a": ("one", "two")}).build(tts) == {"built": 0, "skipped": 2, "credits": 0}
    assert tts.calls == ["one", "two"]  # second build spent nothing


def test_changing_voice_or_text_changes_the_file(tmp_path):
    a = LineCache(voice_id="v1", root=tmp_path)
    assert a.path_for("hi") != LineCache(voice_id="v2", root=tmp_path).path_for("hi")
    assert a.path_for("hi") != a.path_for("hi.")
    assert a.path_for("hi") != LineCache(voice_id="v1", model_id="other", root=tmp_path).path_for("hi")


def test_pick_never_repeats_back_to_back(tmp_path):
    cache = LineCache(voice_id="v", root=tmp_path, lines={"a": ("x", "y", "z")}, rng=random.Random(0))
    cache.build(FakeTTS())
    picks = [cache.pick("a").text for _ in range(200)]
    assert all(p != q for p, q in zip(picks, picks[1:]))
    assert set(picks) == {"x", "y", "z"}  # all variants get used
    assert cache.pick("a").pcm in (b"x", b"y", b"z")


def test_uncached_event_goes_to_haiku(tmp_path):
    cache = LineCache(voice_id="v", root=tmp_path)
    assert not cache.has("behavior_changed") and cache.pick("behavior_changed") is None


def test_pick_before_build_fails_loudly(tmp_path):
    with pytest.raises(RuntimeError, match="cache not built"):
        LineCache(voice_id="v", root=tmp_path, lines={"a": ("x",)}).pick("a")
