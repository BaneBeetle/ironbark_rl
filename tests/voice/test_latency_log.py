"""Latency records with hand-set timestamps."""

import json

import pytest

from ironbark_voice import latency_log
from ironbark_voice.latency_log import LineTiming
from ironbark_voice.player import PlaybackTiming


def timing(source, event_s, text_s, first_write_s, latency=0.18):
    pb = PlaybackTiming(start_s=text_s, first_write_s=first_write_s, end_s=(first_write_s or text_s) + 1.0,
                        output_latency_s=latency, num_bytes=48_000)
    return LineTiming(event="target_reacquired", source=source, text="There you are!",
                      event_s=event_s, text_ready_s=text_s, playback=pb)


def test_record_intervals():
    rec = timing("haiku", 10.00, 10.42, 10.71).record()
    assert rec["event_to_text_s"] == pytest.approx(0.42)
    assert rec["text_to_first_write_s"] == pytest.approx(0.29)
    assert rec["event_to_first_sound_s"] == pytest.approx(0.89)  # 0.71 + 0.18 device buffer
    assert rec["playback_s"] == pytest.approx(1.0)


def test_silent_clip_has_no_first_sound():
    rec = timing("cache", 5.0, 5.0, None).record()
    assert rec["event_to_first_sound_s"] is None and rec["text_to_first_write_s"] is None


def test_append_and_summarize(tmp_path):
    path = tmp_path / "voice_latency_test.jsonl"
    latency_log.append(timing("cache", 0.0, 0.0, 0.10), path)  # 0.28 s
    latency_log.append(timing("haiku", 0.0, 0.5, 0.80), path)  # 0.98 s
    latency_log.append(timing("haiku", 0.0, 1.2, 1.60), path)  # 1.78 s
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["source"] == "cache"
    s = latency_log.summarize(path)
    assert s["cache"]["n"] == 1 and s["cache"]["p50_s"] == pytest.approx(0.28)
    assert s["haiku"]["p50_s"] == pytest.approx((0.98 + 1.78) / 2)
    assert s["haiku"]["meets_target"] is True  # 1.38 < 1.5
    assert s["all"]["p50_s"] == pytest.approx(0.98)
