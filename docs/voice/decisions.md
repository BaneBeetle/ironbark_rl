# IronBark voice: design decisions

Brian owns these calls; Claude writes the code. Newest at the bottom. Each entry says who
decided, when, and why (in Brian's words where he gave them).

## 2026-11-07: first round (Brian)

Answers to the five planning questions, as Brian gave them:

1. **Latency target:** "median under 1.5 s event-to-first-sound; revisit after first
   measurements." (`config.LATENCY_TARGET_P50_S`)
2. **When to speak:** "Events only to start, one shared cooldown, drop stale lines, low
   battery and falls skip the wait. Add a cache: pre-generate audio for common lines (found
   you / lost you / battery low) and replay them instantly with no API call; Haiku only for
   novel situations."
3. **Personality:** "a chill, laid-back 'bro' dog, like a supportive, honest friend. Casual
   phrasing, light slang and humor without overdoing it, encouraging, first person, ≤12
   words per line. Propose 3 premade ElevenLabs voices that fit and I'll pick."
   (`config.MAX_WORDS_PER_LINE`, `brain.PERSONA`)
4. **Where audio plays:** "Option (a): PC runs Haiku + TTS and streams audio to the Pi over
   a new ZMQ port. Dev output: use the system default for now, and list the available output
   devices so I can pick." (`config.OUTPUT_DEVICE = None`)
5. **RemBeetle:** github.com/BaneBeetle/RemBeetle, cloned to `C:\Users\lolly\dev\RemBeetle`.
   Standing rule: everything lives under `C:\Users\lolly\dev`, never OneDrive.

Also: use a fake/replay state source until the V2 repo is on this PC (Brian is pushing it
from the Mac).

Claude's recommendation that Brian accepted in (4): keys stay on the PC, one code path, and
the Pi stays a thin player.

## Context Claude found (for reference, not decisions)

- **RemBeetle reuse.** Its ElevenLabs module (`tts/elevenlabs_tts.py`) is not in git; it
  lives only on the production server (`doc/vercel-deployment.md`). The repo's audio path is
  file-based for a browser frontend, so no code fits directly. What carries over: Turbo
  v2.5 measured ~0.3 s per sentence vs ~1 s for Multilingual v2 on that server, and the
  voice settings chosen by ear for Rem (stability 0.5, similarity 0.75, style 0, speaker
  boost on). IronBark starts on ElevenLabs' defaults; changing them is Brian's call.
- **ElevenLabs (live docs, 2026-11-07).** For complete short lines, HTTP
  `/v1/text-to-speech/{voice_id}/stream` beats the WebSocket (WebSocket only helps when text
  arrives in pieces). `optimize_streaming_latency` is deprecated. Free tier: 10,000 credits
  per month; Flash costs 0.5–1 credit per character.
- **Haiku 5.5.** $0.10 / $0.50 per million tokens in/out. Thinking is on by default; the
  voice turns it off (allowed at effort ≤ high) and runs effort `low` for speed.
- **Premade voices are going away.** ElevenLabs retires default (premade) voices on
  2026-12-31, only accounts made before March 2026 have them, and the free tier can't use
  Voice Library voices through the API. So the shortlist (`config.VOICE_SHORTLIST`: Warren,
  Eddie, Caleb) is ElevenLabs' official replacements. Their style tags are unverified (that
  table needs a login); `python -m ironbark_voice.say account` checks this key can use them.
- **Telemetry.** V1 (`~/ironbark-v1/pi/motor_controller.py`) binds a PUB on :5558 and sends
  one JSON string per message, so extra subscribers like the voice don't disturb the
  follower. The V2 field names come from CLAUDE.md and need checking when V2 lands.
