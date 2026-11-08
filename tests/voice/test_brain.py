"""Haiku line writer with a fake Anthropic client: no network, no key."""

from types import SimpleNamespace

from ironbark_voice import config
from ironbark_voice.brain import PERSONA, LineWriter, clean_line


class FakeMessages:
    def __init__(self, text, stop_reason="end_turn"):
        self.text = text
        self.stop_reason = stop_reason
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.text)],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=180, output_tokens=14),
            _request_id="req_test",
        )


def writer(text, stop_reason="end_turn"):
    client = SimpleNamespace(messages=FakeMessages(text, stop_reason))
    return LineWriter(client=client), client.messages


def test_request_is_fast_haiku_with_persona():
    w, messages = writer("There you are, bro!")
    w.write_line("target_reacquired", "behavior=FOLLOW battery=62%")
    call = messages.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["system"] == PERSONA
    assert call["thinking"] == {"type": "disabled"}
    assert call["output_config"] == {"effort": "low"}
    assert call["max_tokens"] == config.HAIKU_MAX_TOKENS
    assert "target_reacquired" in call["messages"][0]["content"]
    assert "battery=62%" in call["messages"][0]["content"]


def test_v3_is_v2_plus_style_examples():
    from ironbark_voice.brain import PERSONA_V2, PERSONA_V3, STYLE_EXAMPLES

    assert PERSONA == PERSONA_V2  # Brian picked v2 after the A/B (2026-11-07)
    assert PERSONA_V3.startswith(PERSONA_V2)
    assert all(line in PERSONA_V3 for line in STYLE_EXAMPLES)
    assert all(len(line.split()) <= config.MAX_WORDS_PER_LINE for line in STYLE_EXAMPLES)  # examples obey the cap


def test_persona_can_be_swapped_for_ab_tests():
    client = SimpleNamespace(messages=FakeMessages("Yo."))
    LineWriter(client=client, persona="TEST PERSONA").write_line("x", "")
    assert client.messages.calls[0]["system"] == "TEST PERSONA"


def test_result_is_cleaned_and_counted():
    w, _ = writer('  "There you are, bro! Thought I lost you."\n')
    result = w.write_line("target_reacquired", "")
    assert result.text == "There you are, bro! Thought I lost you."
    assert result.words == 8 and not result.over_limit
    assert (result.input_tokens, result.output_tokens, result.request_id) == (180, 14, "req_test")


def test_over_limit_is_flagged_not_cut():
    long_line = " ".join(["word"] * 13)
    result = writer(long_line)[0].write_line("x", "")
    assert result.over_limit and result.text == long_line


def test_refusal_is_never_spoken():
    result = writer("I can't help with that.", stop_reason="refusal")[0].write_line("x", "")
    assert result.text == "" and result.words == 0


def test_clean_line_examples():
    assert clean_line("“Yo!”") == "Yo!"
    assert clean_line("Battery's low,\nbro.") == "Battery's low, bro."
    assert clean_line("'Sup") == "'Sup"  # a leading apostrophe alone is not a quote pair
