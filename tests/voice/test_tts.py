"""ElevenLabs TTS client with a fake SDK: no network, no key."""

from ironbark_voice import config
from ironbark_voice.tts import ElevenLabsTTS


class FakeTTSEndpoint:
    """Stands in for client.text_to_speech: records the call, returns canned chunks."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.chunks)


class FakeElevenLabs:
    def __init__(self, chunks):
        self.text_to_speech = FakeTTSEndpoint(chunks)


def test_stream_sends_model_format_and_voice():
    client = FakeElevenLabs([b"\x01\x02"])
    tts = ElevenLabsTTS(voice_id="voice123", client=client)
    assert list(tts.stream_pcm("Yo, found you!")) == [b"\x01\x02"]
    call = client.text_to_speech.calls[0]
    assert call == {
        "voice_id": "voice123",
        "text": "Yo, found you!",
        "model_id": config.TTS_MODEL,
        "output_format": config.TTS_OUTPUT_FORMAT,
    }


def test_synthesize_joins_chunks():
    tts = ElevenLabsTTS(voice_id="v", client=FakeElevenLabs([b"ab", b"cd", b"e"]))
    assert tts.synthesize_pcm("hi") == b"abcde"
