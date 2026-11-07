"""Claude Haiku writes one short spoken line for a situation the cache doesn't cover.

Called only for novel situations (Brian, 2026-11-07); common lines come from the audio cache
with no API call at all.
"""

import time
from dataclasses import dataclass

from ironbark_voice import config

# Brian's personality spec (2026-11-07), turned into a system prompt. It never changes at
# runtime, so it is a stable prefix (cacheable later if it ever grows past the cache minimum).
PERSONA = f"""You are IronBark, a small robot dog, saying your thoughts out loud to the people around you.

Who you are: a chill, laid-back bro. A supportive, honest friend. Casual phrasing, a little slang and humor, never overdone. Encouraging.

How you speak:
- First person.
- One line, at most {config.MAX_WORDS_PER_LINE} words.
- Plain spoken words only: a text-to-speech voice reads it aloud. No emojis, quotes, hashtags or stage directions.
- Only talk about what the robot state shows. Don't invent people, objects or places you can't sense."""


@dataclass(frozen=True)
class LineResult:
    text: str  # cleaned line, ready for TTS; "" if Claude declined
    words: int  # word count after cleaning
    over_limit: bool  # True if Claude ignored the word cap (logged; what to do is Brian's call)
    latency_s: float  # request sent -> full reply back
    input_tokens: int
    output_tokens: int
    request_id: str | None  # for reporting a bad reply to Anthropic


def clean_line(raw: str) -> str:
    """Make a reply safe to speak: one line, no wrapping quotes, single spaces.

    Example: '  "Yo, found you, bro!"\\n' -> 'Yo, found you, bro!'
    """
    text = " ".join(raw.split())  # newlines and double spaces would read as odd pauses
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()  # models sometimes quote their own line; TTS would not say the quotes anyway
    if len(text) >= 2 and text[0] == "“" and text[-1] == "”":
        text = text[1:-1].strip()  # curly quotes come as a pair of different characters
    return text


class LineWriter:
    def __init__(self, client=None, model: str = config.HAIKU_MODEL):
        if client is None:
            import anthropic

            client = anthropic.Anthropic(
                api_key=config.require_env("ANTHROPIC_API_KEY"),
                timeout=5.0,  # seconds; a line this late is stale anyway, so fail fast
                max_retries=1,  # one retry covers a blip without doubling the wait twice
            )
        self._client = client  # injectable so tests never hit the network
        self.model = model

    def write_line(self, event: str, state_summary: str) -> LineResult:
        """One line for one event.

        Example: write_line("target_reacquired", "behavior=FOLLOW action=forward battery=62%")
                 -> LineResult(text="There you are, bro! Thought I lost you.", words=8, ...)
        """
        start = time.perf_counter()
        response = self._client.messages.create(
            model=self.model,
            max_tokens=config.HAIKU_MAX_TOKENS,
            system=PERSONA,
            # Thinking off: a 12-word quip gains nothing from it and it costs time to first token.
            # Haiku 5.5 allows "disabled" at effort high or below.
            thinking={"type": "disabled"},
            output_config={"effort": config.HAIKU_EFFORT},
            messages=[{"role": "user", "content": f"Event: {event}\nRobot state: {state_summary}\n\nSay your line."}],
        )
        latency = time.perf_counter() - start
        if response.stop_reason == "refusal":
            text = ""  # never speak a refusal message out loud; the caller skips empty lines
        else:
            text = clean_line("".join(block.text for block in response.content if block.type == "text"))
        words = len(text.split())
        return LineResult(
            text=text,
            words=words,
            over_limit=words > config.MAX_WORDS_PER_LINE,
            latency_s=latency,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            request_id=getattr(response, "_request_id", None),
        )
