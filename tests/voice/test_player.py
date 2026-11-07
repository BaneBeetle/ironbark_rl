"""PCM playback with a fake stream: no sound card."""

import pytest

from ironbark_voice.player import PcmPlayer, align_to_samples, resolve_output_device

DEVICES = [  # what list_output_devices() returns: default audio API only
    {"index": 7, "name": "Microsoft Sound Mapper - Output", "host_api": "MME", "default": False},
    {"index": 9, "name": "Realtek Digital Output (Realtek", "host_api": "MME", "default": False},
    {"index": 10, "name": "Headphones (Elgato Wave:3)", "host_api": "MME", "default": True},
]


def test_resolve_device_by_name_fragment():
    assert resolve_output_device("realtek digital", DEVICES) == 9  # case-insensitive fragment
    assert resolve_output_device(None, DEVICES) is None  # system default


def test_resolve_device_must_be_unambiguous():
    with pytest.raises(ValueError, match="matched: none"):
        resolve_output_device("AirPods", DEVICES)
    with pytest.raises(ValueError, match="exactly one"):
        resolve_output_device("(", DEVICES)  # matches two names


def test_align_carries_split_samples():
    # A 16-bit sample split across chunks must be re-joined, never written half.
    assert list(align_to_samples([b"\x01\x02\x03", b"\x04"])) == [b"\x01\x02", b"\x03\x04"]


def test_align_skips_empty_and_drops_trailing_half_sample():
    assert list(align_to_samples([b"", b"\x01", b"\x02\x03"])) == [b"\x01\x02"]


class FakeStream:
    """Stands in for sounddevice.RawOutputStream."""

    latency = 0.05  # seconds the fake "device" reports

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.written = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, data):
        self.written.append(data)


def test_player_writes_aligned_audio_and_times_first_sound():
    streams = []

    def factory(**kwargs):
        streams.append(FakeStream(**kwargs))
        return streams[-1]

    timing = PcmPlayer(sample_rate_hz=24_000, device=None, stream_factory=factory).play([b"\x01\x02\x03", b"\x04"])
    stream = streams[0]
    assert stream.kwargs == {"samplerate": 24_000, "channels": 1, "dtype": "int16", "device": None}
    assert stream.written == [b"\x01\x02", b"\x03\x04"]
    assert timing.num_bytes == 4
    assert timing.start_s <= timing.first_write_s <= timing.end_s
    assert timing.first_sound_s == timing.first_write_s + 0.05


def test_player_empty_clip_has_no_first_sound():
    timing = PcmPlayer(stream_factory=FakeStream).play([])
    assert timing.first_write_s is None and timing.first_sound_s is None
