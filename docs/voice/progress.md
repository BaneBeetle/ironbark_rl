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

**Interview talking point:** split the latency budget into parts (LLM → text, TTS → first
audio byte, device buffer) and measure each one separately. Caching the common lines removes
both network hops for the lines that matter most. That's precomputation, traded against
variety, which the variants and Haiku for novel events buy back.
