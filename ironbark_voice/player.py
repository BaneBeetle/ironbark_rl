"""Play raw PCM on the PC's speakers as it streams in, and time when sound starts.

Dev mode only: later the same PCM goes to the Pi over ZMQ (Brian's option (a)).
"""

import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from ironbark_voice import config


def align_to_samples(chunks: Iterable[bytes], sample_width: int = config.TTS_SAMPLE_WIDTH_BYTES) -> Iterator[bytes]:
    """Re-cut network chunks so every chunk holds whole samples.

    HTTP chunks can split a 16-bit sample across two chunks; writing half a sample would
    shift every later sample by one byte and turn the audio into noise.

    Example: [b"\\x01\\x02\\x03", b"\\x04"] -> b"\\x01\\x02", b"\\x03\\x04"
    """
    carry = b""  # bytes of an incomplete sample left over from the previous chunk
    for chunk in chunks:
        data = carry + chunk
        whole = len(data) - (len(data) % sample_width)  # largest prefix of whole samples
        carry = data[whole:]
        if whole:
            yield data[:whole]
    # A trailing partial sample is dropped on purpose: it is half a sample of a finished clip.


@dataclass(frozen=True)
class PlaybackTiming:
    """Perf-counter timestamps (seconds) for one clip."""

    start_s: float  # play() called
    first_write_s: float | None  # first audio handed to the device; None if the clip was empty
    end_s: float  # playback finished (closing the stream waits for its buffer to drain)
    output_latency_s: float  # device buffer the OS reports: sound leaves the speaker this much after a write
    num_bytes: int

    @property
    def first_sound_s(self) -> float | None:
        """Best estimate of when the speaker actually starts: first write + device latency."""
        if self.first_write_s is None:
            return None
        return self.first_write_s + self.output_latency_s


def list_output_devices() -> list[dict]:
    """Every device that can play sound, with the system default flagged."""
    import sounddevice as sd

    host_apis = sd.query_hostapis()
    default_out = sd.default.device[1]  # (input, output) pair; we want output
    devices = []
    for index, dev in enumerate(sd.query_devices()):
        if dev["max_output_channels"] > 0:  # skip microphones
            devices.append(
                {
                    "index": index,  # what config.OUTPUT_DEVICE takes
                    "name": dev["name"],
                    "host_api": host_apis[dev["hostapi"]]["name"],
                    "default": index == default_out,
                }
            )
    return devices


class PcmPlayer:
    """Plays 16-bit mono PCM chunks through one output device, blocking until done."""

    def __init__(self, sample_rate_hz: int = config.TTS_SAMPLE_RATE_HZ, device=config.OUTPUT_DEVICE, stream_factory=None):
        if stream_factory is None:
            import sounddevice as sd

            stream_factory = sd.RawOutputStream  # raw bytes in, no numpy conversion per chunk
        self._stream_factory = stream_factory  # injectable so tests run without a sound card
        self.sample_rate_hz = sample_rate_hz
        self.device = device  # None = system default (Brian, 2026-11-07)

    def play(self, chunks: Iterable[bytes]) -> PlaybackTiming:
        start = time.perf_counter()
        first_write = None
        num_bytes = 0
        stream = self._stream_factory(samplerate=self.sample_rate_hz, channels=1, dtype="int16", device=self.device)
        with stream:  # opens and starts the device; closing waits for the buffer to drain
            for chunk in align_to_samples(chunks):
                if first_write is None:
                    first_write = time.perf_counter()  # the latency harness's "first sound" anchor
                stream.write(chunk)  # blocks while the device buffer is full, so this paces itself
                num_bytes += len(chunk)
            output_latency = float(stream.latency)  # read before close; the OS's own buffer estimate
        return PlaybackTiming(
            start_s=start,
            first_write_s=first_write,
            end_s=time.perf_counter(),
            output_latency_s=output_latency,
            num_bytes=num_bytes,
        )
