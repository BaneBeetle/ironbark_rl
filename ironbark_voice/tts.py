"""ElevenLabs text-to-speech over the HTTP streaming endpoint.

Why HTTP and not the WebSocket: our lines are complete before we send them (a cached line
or a finished 12-word Haiku reply). ElevenLabs' latency guide says the WebSocket only pays
off when text arrives in pieces, and its buffering can add delay otherwise.
"""

import re
from collections.abc import Iterator

from ironbark_voice import config


def calm_punctuation(text: str) -> str:
    """Swap "!" for "." (Brian's call, 2026-11-07, after hearing variant B).

    Measured: with "!", 2 of 3 takes of a Tilly line spiked to ~560-600 Hz median pitch (the
    squeak Brian flagged); with ".", 0 of 3 did (docs/voice/progress.md). A laid-back bro
    doesn't need it anyway. Questions stay questions.

    Example: "Yo! Let's roll!!" -> "Yo. Let's roll."   "Where'd you go?!" -> "Where'd you go?"
    """
    text = re.sub(r"[!?]*\?[!?]*", "?", text)  # any run containing "?" is still a question
    return re.sub(r"!+", ".", text)  # what's left is pure "!": one or many become a period


class ElevenLabsTTS:
    """Turns one line of text into raw PCM chunks, streamed as ElevenLabs generates them."""

    def __init__(
        self,
        voice_id: str,
        model_id: str = config.TTS_MODEL,
        output_format: str = config.TTS_OUTPUT_FORMAT,
        client=None,  # injectable so tests never hit the network or need a key
    ):
        if client is None:
            # Imported here so tests with a fake client don't need the SDK's HTTP stack.
            from elevenlabs.client import ElevenLabs

            # Pass the key explicitly: the SDK reads ELEVENLABS_API_KEY as a default argument,
            # which Python evaluates at import time, before config.load_dotenv() may have run.
            client = ElevenLabs(api_key=config.require_env("ELEVENLABS_API_KEY"))
        self._client = client
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format
        # Filled from the response headers of the latest request. Credits come from the
        # "character-cost" header: the real charge per line, measured rather than computed
        # from a price table, and readable without the key's user_read permission.
        self.last_credits: int | None = None
        self.last_request_id: str | None = None
        self.last_text: str | None = None  # what was actually sent, after calm_punctuation

    def stream_pcm(self, text: str) -> Iterator[bytes]:
        """Yield PCM byte chunks as they arrive, so playback can start before synthesis ends.

        Example: stream_pcm("Yo, found you!") -> b"\\x01\\x00\\xfe\\xff...", b"...", ...
        (16-bit little-endian mono at config.TTS_SAMPLE_RATE_HZ; chunk sizes vary and can be
        odd, so the player re-aligns them to whole samples). After the first chunk,
        last_credits holds what this line cost.
        """
        # Every spoken line passes through here (cache build, Haiku, typed), so one rule covers all.
        self.last_text = calm_punctuation(text)
        # with_raw_response exposes the headers; the plain .stream() call hides them.
        with self._client.text_to_speech.with_raw_response.stream(
            voice_id=self.voice_id,
            text=self.last_text,
            model_id=self.model_id,
            output_format=self.output_format,  # raw PCM: no decoder between network and speaker
        ) as response:
            cost = response.headers.get("character-cost")
            self.last_credits = int(cost) if cost is not None else None
            self.last_request_id = response.headers.get("request-id")  # for support tickets
            yield from response.data

    def synthesize_pcm(self, text: str) -> bytes:
        """Whole clip in one bytes object: for pre-generating cached lines, not live speech."""
        return b"".join(self.stream_pcm(text))
