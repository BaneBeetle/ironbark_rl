"""Compare two persona versions on the same events, same model and same settings.

  .venv\\Scripts\\python -m ironbark_voice.persona_ab v2 v3 --wav-dir samples/persona_ab

Only the system prompt differs between the two sides, so differences in the lines come from
the persona (plus Haiku's own randomness: one line per event is a small sample). Results go to
docs/voice/persona_ab/<date>_<a>_vs_<b>.jsonl. With --wav-dir, each side's lines are rendered
into one WAV (no playback) so the two can be heard back to back.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from ironbark_voice import config
from ironbark_voice.brain import PERSONAS, STYLE_EXAMPLES, LineWriter

# Novel situations only (none is in the cache table), so this is exactly the traffic Haiku will
# get. Fixed, so every persona version is judged on the same inputs.
EVAL_EVENTS = (
    ("robot_started", "behavior=IDLE action=stop battery=95%"),
    ("follow_started", "behavior=FOLLOW target=visible action=forward battery=62%"),
    ("target_lost_long", "behavior=FOLLOW target=not visible action=turn_right battery=58%"),
    ("battery_low_while_following", "behavior=FOLLOW target=visible action=forward battery=18%"),
    ("follow_ended", "behavior=IDLE target=visible action=stop battery=47%"),
)
GAP_BETWEEN_LINES_S = 0.6  # silence between lines in the rendered WAV, so they don't run together

OUT_DIR = config.REPO_ROOT / "docs" / "voice" / "persona_ab"


def run(versions: list[str], writer_factory=LineWriter) -> list[dict]:
    """One line per (event, version). Calls alternate between versions so any API slowdown hits both."""
    writers = {v: writer_factory(persona=PERSONAS[v]) for v in versions}
    rows = []
    for event, state in EVAL_EVENTS:
        for version in versions:
            r = writers[version].write_line(event, state)
            rows.append({
                "persona": version,
                "event": event,
                "state": state,
                "text": r.text,
                "words": r.words,
                "over_limit": r.over_limit,
                # A copied style example would sound canned next to the cached line it came from.
                "reused_example": r.text in STYLE_EXAMPLES,
                "latency_s": round(r.latency_s, 3),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
            })
    return rows


def render(rows: list[dict], versions: list[str], wav_dir: Path) -> dict[str, int]:
    """One WAV per version with its lines back to back. Returns credits spent per version."""
    from ironbark_voice.player import write_wav
    from ironbark_voice.tts import ElevenLabsTTS

    tts = ElevenLabsTTS(voice_id=config.VOICE_ID)
    gap = b"\x00" * int(GAP_BETWEEN_LINES_S * config.TTS_SAMPLE_RATE_HZ) * config.TTS_SAMPLE_WIDTH_BYTES
    credits = {}
    for version in versions:
        clips, spent = [], 0
        for row in rows:
            if row["persona"] == version and row["text"]:
                clips.append(tts.synthesize_pcm(row["text"]))
                spent += tts.last_credits or 0
        write_wav(Path(wav_dir) / f"persona_{version}.wav", gap.join(clips))
        credits[version] = spent
    return credits


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ironbark_voice.persona_ab")
    parser.add_argument("a", choices=sorted(PERSONAS))
    parser.add_argument("b", choices=sorted(PERSONAS))
    parser.add_argument("--wav-dir", help="also render each version's lines to <dir>/persona_<v>.wav")
    args = parser.parse_args(argv)
    versions = [args.a, args.b]

    rows = run(versions)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{datetime.now():%Y-%m-%d_%H%M}_{args.a}_vs_{args.b}.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    for event, _ in EVAL_EVENTS:
        print(f"\n{event}")
        for r in (r for r in rows if r["event"] == event):
            flags = " [OVER CAP]" * r["over_limit"] + " [COPIED EXAMPLE]" * r["reused_example"]
            print(f"  {r['persona']}: {r['text']}  ({r['words']} words, {r['latency_s']:.2f} s){flags}")
    print(f"\nsaved {out.relative_to(config.REPO_ROOT)}")
    if args.wav_dir:
        print(f"rendered to {args.wav_dir}, credits {render(rows, versions, Path(args.wav_dir))}")


if __name__ == "__main__":
    main()
