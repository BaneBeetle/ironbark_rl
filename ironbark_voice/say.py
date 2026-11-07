"""Dev CLI: list devices, check the ElevenLabs account, and speak lines on the PC speakers.

Run from the worktree root with the voice venv:
  .venv\\Scripts\\python -m ironbark_voice.say devices
  .venv\\Scripts\\python -m ironbark_voice.say account
  .venv\\Scripts\\python -m ironbark_voice.say compare "Yo, found you, bro!"
  .venv\\Scripts\\python -m ironbark_voice.say line "Yo, found you, bro!" --voice Warren
  .venv\\Scripts\\python -m ironbark_voice.say haiku target_reacquired --state "behavior=FOLLOW battery=62%" --voice Warren
  .venv\\Scripts\\python -m ironbark_voice.say summary

Speaks only through the PC's audio device. Nothing here talks to the dog.
"""

import argparse
import json
import sys
import time

from ironbark_voice import config, latency_log
from ironbark_voice.latency_log import LineTiming
from ironbark_voice.player import PcmPlayer, list_output_devices


def resolve_voice(name_or_id: str | None) -> str:
    """Accept a shortlist name ("Warren") or a raw voice_id; fall back to config.VOICE_ID."""
    value = name_or_id or config.VOICE_ID
    if not value:
        raise SystemExit("No voice picked yet: pass --voice <name or id> (shortlist: " + ", ".join(config.VOICE_SHORTLIST) + ")")
    return config.VOICE_SHORTLIST.get(value, value)


def speak(text: str, voice_id: str, event: str, source: str, event_s: float, text_ready_s: float, **haiku_usage) -> dict:
    """TTS -> speakers, then log the timing. Returns the latency record."""
    from ironbark_voice.tts import ElevenLabsTTS

    tts = ElevenLabsTTS(voice_id=voice_id)
    playback = PcmPlayer().play(tts.stream_pcm(text))  # plays while it streams
    timing = LineTiming(event=event, source=source, text=text, event_s=event_s, text_ready_s=text_ready_s,
                        playback=playback, voice_id=voice_id, tts_model=tts.model_id, **haiku_usage)
    return latency_log.append(timing)


def print_record(rec: dict) -> None:
    first = rec["event_to_first_sound_s"]
    print(f'"{rec["text"]}"  [{rec["source"]}, voice {rec["voice_id"]}]')
    print(f"  event->text {rec['event_to_text_s']:.3f} s | text->first write "
          f"{(rec['text_to_first_write_s'] or 0):.3f} s | device buffer {rec['device_latency_s']:.3f} s")
    print(f"  event->first sound {first:.3f} s (target median < {config.LATENCY_TARGET_P50_S} s)" if first is not None else "  no audio came back")


def cmd_devices(args) -> None:
    for d in list_output_devices(all_host_apis=args.all):
        mark = "  <- system default" if d["default"] else ""
        print(f"{d['host_api']:<20} {d['name']}{mark}")
    print('\nTo pick one, set config.OUTPUT_DEVICE to part of its name, e.g. "Realtek Digital Output" (None = system default).')


def cmd_account(_args) -> None:
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=config.require_env("ELEVENLABS_API_KEY"))
    sub = client.user.subscription.get()
    print(f"tier {sub.tier} | characters used {sub.character_count} of {sub.character_limit} this period")
    for name, voice_id in config.VOICE_SHORTLIST.items():
        try:
            v = client.voices.get(voice_id)
            print(f"  {name:<7} ok: {v.name} (category {v.category}, tiers {v.available_for_tiers}, labels {v.labels})")
        except Exception as e:  # report and keep going: one unusable voice shouldn't hide the others
            print(f"  {name:<7} NOT usable with this key: {type(e).__name__}: {e}")


def cmd_compare(args) -> None:
    for name, voice_id in config.VOICE_SHORTLIST.items():
        print(f"\n--- {name} ---")
        now = time.perf_counter()
        print_record(speak(args.text, voice_id, event="voice_compare", source="tts", event_s=now, text_ready_s=now))
        time.sleep(0.8)  # a short gap so the voices don't run together


def cmd_line(args) -> None:
    now = time.perf_counter()  # a typed line is "ready" the moment it's sent
    print_record(speak(args.text, resolve_voice(args.voice), event="manual", source="tts", event_s=now, text_ready_s=now))


def cmd_haiku(args) -> None:
    from ironbark_voice.brain import LineWriter

    voice_id = resolve_voice(args.voice)
    event_s = time.perf_counter()  # the trigger fires now
    result = LineWriter().write_line(args.event, args.state)
    text_ready_s = time.perf_counter()
    if not result.text:
        raise SystemExit("Haiku returned no speakable line (refusal or empty).")
    if result.over_limit:
        print(f"note: {result.words} words, over the {config.MAX_WORDS_PER_LINE}-word cap")
    print_record(speak(result.text, voice_id, event=args.event, source="haiku", event_s=event_s, text_ready_s=text_ready_s,
                       haiku_input_tokens=result.input_tokens, haiku_output_tokens=result.output_tokens))


def cmd_summary(args) -> None:
    print(json.dumps(latency_log.summarize(args.path or latency_log.default_log_path()), indent=2))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ironbark_voice.say", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("devices", help="list audio output devices")
    p.add_argument("--all", action="store_true", help="show every Windows audio API, not just the default's")
    p.set_defaults(func=cmd_devices)
    sub.add_parser("account", help="ElevenLabs tier, quota, and which shortlisted voices this key can use").set_defaults(func=cmd_account)
    p = sub.add_parser("compare", help="speak one line in each shortlisted voice")
    p.add_argument("text")
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser("line", help="speak a typed line")
    p.add_argument("text")
    p.add_argument("--voice")
    p.set_defaults(func=cmd_line)
    p = sub.add_parser("haiku", help="have Haiku write a line for an event, then speak it")
    p.add_argument("event")
    p.add_argument("--state", default="", help='e.g. "behavior=FOLLOW target=visible battery=62%%"')
    p.add_argument("--voice")
    p.set_defaults(func=cmd_haiku)
    p = sub.add_parser("summary", help="median event->first-sound from a latency log")
    p.add_argument("path", nargs="?")
    p.set_defaults(func=cmd_summary)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # device names can hold curly apostrophes
    try:
        args.func(args)
    except RuntimeError as e:  # e.g. a missing API key: show the message, not a traceback
        raise SystemExit(str(e)) from None


if __name__ == "__main__":
    main()
