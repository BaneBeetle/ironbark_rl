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

**Interview talking point:** split the latency budget into parts (LLM → text, TTS → first
audio byte, device buffer) and measure each one separately. Caching the common lines removes
both network hops for the lines that matter most. That's precomputation, traded against
variety, which the variants and Haiku for novel events buy back.
