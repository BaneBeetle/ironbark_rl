"""Persona A/B harness with a fake writer: no network."""

from ironbark_voice import persona_ab
from ironbark_voice.brain import PERSONAS, STYLE_EXAMPLES, LineResult


class FakeWriter:
    def __init__(self, persona):
        self.persona = persona

    def write_line(self, event, state):
        # v3 "copies" an example on one event, to exercise the flag.
        text = STYLE_EXAMPLES[0] if (self.persona == PERSONAS["v3"] and event == "robot_started") else f"line for {event}"
        return LineResult(text=text, words=len(text.split()), over_limit=False, latency_s=0.5,
                          input_tokens=300, output_tokens=20, request_id=None)


def test_run_interleaves_versions_on_the_same_events():
    rows = persona_ab.run(["v2", "v3"], writer_factory=FakeWriter)
    assert len(rows) == 2 * len(persona_ab.EVAL_EVENTS)
    assert [r["persona"] for r in rows[:4]] == ["v2", "v3", "v2", "v3"]  # alternating
    assert rows[0]["event"] == rows[1]["event"] == "robot_started"
    assert rows[1]["reused_example"] and not rows[0]["reused_example"]
