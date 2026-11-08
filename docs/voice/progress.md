# IronBark voice: progress

Branch `feature/voice`, worktree `C:\Users\lolly\dev\ironbark_voice`, venv `.venv` (separate
from the RL env). Voice progress lives here rather than in `docs/progress.md`, so the branch
doesn't touch RL files.

## 2026-11-07: plumbing

**Done (Claude)**
- Package `ironbark_voice/`:
  - `config` (one place for every setting; Brian's values are marked)
  - `tts` (ElevenLabs HTTP stream, Flash v2.5, raw PCM 24 kHz)
  - `player` (PC speaker, sample alignment, device by name, first-sound timing)
  - `brain` (Haiku 5.5, thinking off, effort low, Brian's persona)
  - `state` (read-only Pi telemetry SUB plus a synthetic replay)
  - `latency_log` (event → text → first sound, median vs. target)
  - `say` (dev CLI)
- 22 tests, all on fakes: no network, no keys, no sound card.
- Decisions recorded in `docs/voice/decisions.md`. The next 🧠 pieces are written up as
  signatures and questions in `docs/voice/next-pieces.md`.

**Key result:** none yet. No live latency number, because the API keys aren't in `.env`.

**Found:**
- ElevenLabs retires its premade voices on 2026-12-31, and the free tier can't use Voice
  Library voices through the API. So the voice shortlist uses ElevenLabs' official
  replacements; `say account` checks whether this key can use them.
- RemBeetle's ElevenLabs code isn't in git; it lives only on its server.

**Next**
1. Brian: put the keys in `.env`, then run `say account` and `say compare`, and pick a voice.
2. Brian answers T1–T4, P1–P4 and C1–C3 in `next-pieces.md`. Claude then builds triggers,
   the speech policy and the cache, and the replay run loop.
3. First latency measurement: cached path vs. Haiku path, against the 1.5 s median.
4. Later: stream PCM to the Pi over a new ZMQ port (option a), once V2 is on the PC.

## 2026-11-07 (evening): Tilly, persona v2, first measurements

**Done:**
- Voice set to Tilly (Brian's pick); persona v2 and the cached lines redrafted.
- Credits per line are now logged from ElevenLabs' `character-cost` response header.
- Samples go to a gitignored `samples/` folder.

**Measured** (`docs/measurements/voice_latency_2026-11-07.jsonl`; n is tiny, so these are first readings, not results):

| Path | Event → text | Text → first audio | Device buffer | **Event → first sound** |
|---|---|---|---|---|
| Line sent straight to TTS (n=2) | 0 | 0.20–0.21 s | 0.18 s | **0.38–0.40 s** |
| Haiku → TTS (n=1) | 0.81 s | 0.21 s | 0.18 s | **1.20 s** (target 1.5) |

- **Haiku alone, warm, 4 calls in one process:** 0.67–0.93 s; 306 input and ~21 output
  tokens, about $0.00004 a line.
- **ElevenLabs time to first byte, one process, 3 requests:** 0.23 s cold (TLS handshake),
  then 0.15 and 0.16 s warm.
- **Cached lines** (local audio, no network) should land near the 0.18 s device buffer.
  That's untested until the cache exists.
- **Measurement bug, found and fixed:** the first CLI run reported 1.43 s (TTS) and 6.5 s
  (Haiku). It had counted the SDK imports as latency: `import anthropic` ~3.7 s and
  `import elevenlabs.client` ~0.8 s in a fresh process. That log was set aside, not committed.
- **Cost:** 7 credits per 30–34 character line (≈0.22 credits/character; "Yo." cost 1). That
  includes any custom rate on Tilly. Building all 15 cached lines once is ~527 characters
  ≈ 120 credits.
- **Concurrency:** the TTS response reports a 10-request limit, which matches the Creator
  tier in ElevenLabs' docs.

**Blocked:** the monthly credit allowance. The ElevenLabs key is scoped and lacks `user_read`
(and `voices_read`), so `say account` can't read the balance. Brian can add "User: Read" to
the key, or read the number off the subscription page. Lines per month = allowance / 7.

**Cooldown proposal (Claude, for Brian):** 4 s of quiet after a line ends.
- Lines are ~1.9–2.3 s long (measured), so 4 s keeps the dog quieter than it talks.
- Worst case, every event is uncached and fires as soon as allowed: one line every ~6 s,
  600 lines/hour, ~4,200 credits/hour.
- Cached events are free, so real use costs far less.
- The allowance only binds if the dog chatters nonstop for allowance/4,200 hours.

**Persona v2 check:** Haiku's lines are on-voice but often plain ("Following you now, bro, I
got you"; "Got you in sight, following along, keeping pace with you"). One option, Brian's
call: add a few of the cached lines to `PERSONA` as style examples.

## 2026-11-07 (night): budget, pacing, persona v3

**Done:**
- Brian's allowance (121k credits/month) and pacing (4 s / 30 s / urgent skips) recorded in
  config and `decisions.md`.
- Persona versions kept side by side; v3 = v2 + 3 cached lines as style examples (now live).
- `persona_ab` harness: 5 fixed novel events, identical settings, JSONL + one WAV per version.

**v2 vs v3, first run** (`docs/voice/persona_ab/2026-11-07_1911_v2_vs_v3.jsonl`, one line per
event, so Haiku's randomness alone could explain any difference). Counts only; the judgment is
Brian's:
- All 10 lines ≤ 12 words. Neither version copied a style example.
- "Alright" opens 5 of 10 lines (v2: 3, v3: 2). "bro" appears in 4 of 5 v2 lines and 3 of 5
  v3 lines.
- Battery % is read out in 4 of 10 lines (as words, e.g. "forty-seven").
- Haiku latency 0.62–0.93 s per line. Rendering cost 59 (v2) / 58 (v3) credits for 5 lines.

## 2026-11-07 (late): v2 back live; the "too high-pitched" line

**Brian's verdict on the A/B:** "v2 better but follow started on both too high pitched. the
rest good." The live persona is back to v2.

**Pitch measured** with a scratch autocorrelation F0 tracker (120–700 Hz band, so values near
670 Hz may be capped; fine for comparing lines, not for absolute pitch):
- In the A/B clips, v2 follow_started had a median F0 of **571 Hz**; the other v2 lines
  were 229–393 Hz.
- The only two lines ending in "!" were the highest in their sets (571 Hz in v2, 511 Hz in v3).

**Experiment:** the same line ("Alright, I've got you now, let's roll"), 3 takes per variant,
72 credits:

| Variant | Median F0 per take | Takes > 500 Hz |
|---|---|---|
| A: as written, ends in "!" | 600, 558, 258 Hz | 2 of 3 |
| B: "!" → "." | 268, 329, 397 Hz | 0 of 3 |
| C: "." + `stability=0.75` | 338, 242, 253 Hz | 0 of 3 |

- Read: "!" makes Tilly's delivery spike into squeak on most takes. Dropping it removes the
  spikes, and stability 0.75 lowers and tightens it further.
- Caveat 1: n=3 per variant.
- Caveat 2: C sends only `stability`, so ElevenLabs may have reset Tilly's other stored
  settings for those takes. Listen for whether C still sounds like Tilly.
- WAVs are in `samples/pitch_fix/` (gitignored). Which fix to adopt is Brian's call.

## 2026-11-07 (late night): triggers, pacing and cache built; first full replay

**Done:**
- `triggers` (T1–T4, using Brian's `is_fallen`).
- `speech_policy` (4 s / 30 s / urgent interrupts / P4 staleness).
- `line_cache` (15 lines, keyed by voice + model + format + text).
- Interruptible playback.
- `run` loop (`python -m ironbark_voice.run`), which logs every decision and spoken line.
- 68 tests, including a threaded fall-interrupt test.
- Claude's unasked choices are listed in `decisions.md` for Brian to veto. The main one:
  `battery_low` interrupts too, not just falls.

**First full replay** (`follow_demo.jsonl`, real APIs, PC speakers; logs:
`docs/measurements/voice_decisions_2026-11-07.jsonl`, `voice_latency_2026-11-07.jsonl`):

| Frame | Event | Outcome |
|---|---|---|
| 10 | target_found | spoken (cache), first sound **0.21 s** after the event |
| 10 | behavior_changed | dropped: busy (P3) |
| 47 | target_lost | spoken (cache), **0.19 s** |
| 80 | target_reacquired | dropped: cooldown, 3.9 s of 4.0 s |
| 105 | battery_low | spoken (cache, urgent), then **cut off** by the fall |
| 110 | fell | spoken (cache, urgent, interrupt), **0.25 s** |
| 145 | behavior_changed | spoken (Haiku), **1.29 s**: "Battery's at nineteen percent, but I'm chill, bro. Got this." |

- Building the cache cost 116 credits, once. Cached lines cost nothing after that.
- n is small: 4 cached lines and 1 Haiku line in one run.

**Interview talking point:** split the latency budget into parts (LLM → text, TTS → first
audio byte, device buffer) and measure each one separately. Caching the common lines removes
both network hops for the lines that matter most. That's precomputation, traded against
variety, which the variants and Haiku for novel events buy back.
