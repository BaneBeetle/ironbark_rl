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

## 2026-11-07: voice and persona v2 (Brian)

- **Voice:** "use Tilly from the Voice Library, voice ID MkTSSXNgnBULS6ek4pon. I'm on the
  ElevenLabs Creator plan (not free tier), so Voice Library voices work via the API."
  (`config.VOICE_ID`). This replaces Claude's shortlist (Warren, Eddie, Caleb).
- **Persona v2, to match the voice:** "a tiny dog with big-bro energy. Chill, supportive,
  honest friend vibes, casual slang, ≤12 words, first person. The comedy is a small squeaky
  voice acting like a big laid-back bro." (`brain.PERSONA`)
  - Claude's reading, for Brian to confirm: the lines play it straight, as big-bro swagger
    that never mentions the voice, so the contrast is all in the sound. A size joke now and
    then is allowed.
- **Cooldown:** Brian asked to recompute the line budget from his real monthly credits
  (`say account`) and to shorten the cooldown if the budget allows. Claude proposes a
  number; the call is Brian's.

## 2026-11-07: budget, pacing, few-shot persona (Brian)

1. **Allowance:** "My ElevenLabs Creator allowance is 121000 credits/month (keeping the key
   restricted)." (`config.ELEVENLABS_MONTHLY_CREDITS`) The key stays without `user_read`, so
   `say account` can't read it; the number lives in config.
2. **Pacing:** "Cooldown: 4 s after cached lines; 30 s minimum between Haiku-generated lines.
   Urgent cached events (fall, battery) skip the wait." (`CACHED_LINE_COOLDOWN_S`,
   `HAIKU_LINE_MIN_SPACING_S`, `URGENT_EVENTS`). This answers P1 and part of P2.
   - Claude's assumptions, not yet confirmed: both gaps count from when the previous line
     ends, and the 4 s quiet also follows Haiku lines.
3. **Few-shot persona:** "Yes, add 2-3 cached lines to the persona prompt as few-shot style
   examples. Then generate 5 fresh Haiku lines for different events so I can compare before
   vs after." (persona v3)

**Budget, from measured cost** (Claude): ~7 credits per spoken line (0.22 credits/character,
measured from ElevenLabs' `character-cost` header).
- 121,000 / 7 ≈ 17,000 uncached lines a month.
- At the 30 s Haiku minimum, Haiku lines cost at most ~840 credits/hour, so the allowance
  covers ~144 hours a month of Haiku talking nonstop at its fastest.
- Cached lines are free after a one-time build of ~120 credits per voice.
- So credits don't bind; the pacing is a taste call.

## 2026-11-07: persona A/B verdict (Brian)

After listening to v2 vs v3 (`docs/voice/persona_ab/2026-11-07_1911_v2_vs_v3.jsonl`): "v2
better but follow started on both too high pitched. the rest good." The live persona goes back
to v2; v3 stays in `brain.PERSONAS` for later comparisons. One line per event, so this is a
first preference, not a measured result.

## 2026-11-07: no exclamation marks (Brian)

After hearing A ("!"), B ("." instead) and C ("." + stability 0.75): "B sounds the best."
Every spoken line now has "!" swapped for "." before it reaches ElevenLabs
(`tts.calm_punctuation`, at the TTS boundary so cached, Haiku and typed lines all get it).
Questions keep their "?". Tilly's voice settings stay at her defaults (C not adopted). The
measurements behind it are in `progress.md`.

## 2026-11-07: triggers, pacing and cache (Brian)

Brian's answers to `next-pieces.md`, as given:

- **T1:** "frame-count based; exact number TBD once V2's perception rate is known (placeholder
  # MEASURE:)." (`triggers.TARGET_LOST_FRAMES`)
- **T2:** "yes, separate 'found' and 'reacquired' lines."
- **T3:** "battery low at 20%, re-arms above 30%." (`BATTERY_LOW_PCT`, `BATTERY_REARM_PCT`)
- **T4:** "yes, reuse tilt_deg and FALL_TILT_DEG so 'fell' means the same thing in sim and on
  the dog." (the voice calls `ironbark_rl.brian.metrics.is_fallen` and doesn't modify it)
- **P2:** "yes, a fall cuts off a line that's playing."
- **P3:** "events during cooldown are dropped."
- **P4:** "stale = its event is no longer true, OR it's older than the 1.5 s latency target."
- **C1:** "3 variants per cached line, never the same one twice in a row."
- **C2:** "Haiku handles any event not in the cache table."
- **Pacing assumptions confirmed:** "both gaps count from when the previous line finishes;
  the 4 s quiet also follows Haiku lines."

Claude's choices while building, for Brian to veto (none of these were asked):
- **`TARGET_LOST_FRAMES = 3`** as the T1 placeholder. That's 0.6 s at the replay's 5 Hz,
  marked `# MEASURE:`.
- **Interrupts:** both urgent events (`fell` and `battery_low`) cut off a playing line, though
  P2 named only the fall. Reason: a `battery_low` that fires mid-line would otherwise be
  dropped (P3), and it won't fire again until the battery is charged above 30 %. Holding it
  until the line ends would clash with P4's 1.5 s age rule. Easy to narrow to falls only if
  Brian prefers.
- **`behavior_changed`** (e.g. IDLE → FOLLOW) is the one novel event, so Haiku has something to
  say (C2). It's taken from Claude's C2 recommendation, which Brian accepted only in general
  terms.
- **Same-frame events** are handled urgent first, then cached, then Haiku. The rest are
  dropped by P3 because the dog is already talking.
- **Staleness is checked once**, when the line is ready to play (cached: right away; Haiku:
  when its text comes back).
- **Found and reacquired fire on the first visible frame** (no debounce; T1 covered only
  "lost"). A one-frame flicker while lost would say "reacquired".
- **"fell" fires on the upright → fallen transition** and re-arms once tilt drops back under
  `FALL_TILT_DEG`. One noisy frame could trigger it.

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
