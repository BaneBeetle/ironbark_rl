"""ElevenLabs TTS client with a fake SDK: no network, no key."""

from contextlib import contextmanager
from types import SimpleNamespace

from ironbark_voice import config
from ironbark_voice.tts import ElevenLabsTTS


class FakeRawTTS:
    """Stands in for client.text_to_speech.with_raw_response: records the call, returns canned chunks + headers."""

    def __init__(self, chunks, headers):
        self.chunks = chunks
        self.headers = headers
        self.calls = []

    @contextmanager
    def stream(self, **kwargs):
        self.calls.append(kwargs)
        yield SimpleNamespace(headers=self.headers, data=iter(self.chunks))


def fake_client(chunks, headers=None):
    raw = FakeRawTTS(chunks, headers if headers is not None else {"character-cost": "15", "request-id": "req1"})
    return SimpleNamespace(text_to_speech=SimpleNamespace(with_raw_response=raw)), raw


def test_stream_sends_model_format_and_voice():
    client, raw = fake_client([b"\x01\x02"])
    tts = ElevenLabsTTS(voice_id="voice123", client=client)
    assert list(tts.stream_pcm("Yo, found you!")) == [b"\x01\x02"]
    assert raw.calls[0] == {
        "voice_id": "voice123",
        "text": "Yo, found you.",  # "!" swapped before sending (calm_punctuation)
        "model_id": config.TTS_MODEL,
        "output_format": config.TTS_OUTPUT_FORMAT,
    }


def test_credits_and_request_id_come_from_headers():
    client, _ = fake_client([b"ab"])
    tts = ElevenLabsTTS(voice_id="v", client=client)
    assert tts.last_credits is None  # nothing sent yet
    list(tts.stream_pcm("hi"))
    assert (tts.last_credits, tts.last_request_id) == (15, "req1")


def test_missing_cost_header_is_none():
    client, _ = fake_client([b"ab"], headers={})
    tts = ElevenLabsTTS(voice_id="v", client=client)
    list(tts.stream_pcm("hi"))
    assert tts.last_credits is None


def test_calm_punctuation_examples():
    from ironbark_voice.tts import calm_punctuation

    assert calm_punctuation("Alright, I've got you now, let's roll!") == "Alright, I've got you now, let's roll."
    assert calm_punctuation("Yo! Let's roll!!") == "Yo. Let's roll."
    assert calm_punctuation("Where'd you go?!") == "Where'd you go?"
    assert calm_punctuation("Huh!?") == "Huh?"
    assert calm_punctuation("Big dog's locked in. Lead the way.") == "Big dog's locked in. Lead the way."


def test_exclamation_never_reaches_elevenlabs():
    client, raw = fake_client([b"ab"])
    tts = ElevenLabsTTS(voice_id="v", client=client)
    list(tts.stream_pcm("Let's roll!"))
    assert raw.calls[0]["text"] == "Let's roll." and tts.last_text == "Let's roll."


def test_synthesize_joins_chunks():
    client, _ = fake_client([b"ab", b"cd", b"e"])
    assert ElevenLabsTTS(voice_id="v", client=client).synthesize_pcm("hi") == b"abcde"
