# Voice: Brian's pieces, before they're built

Learning protocol: signatures with real example inputs and outputs first, then Brian's
design calls, then the code. Nothing below is implemented yet. Recommendations are
Claude's; the calls are Brian's.

## 1. `triggers.py`: when has something happened?

```python
detect_events(prev: RobotState | None, curr: RobotState, memory: TriggerMemory) -> list[Event]

# target drops out of view (frame 35 of follow_demo.jsonl)
prev = RobotState(frame=34, behavior="FOLLOW", target_visible=True,  action="forward",   battery_pct=80, roll_deg=0.5, pitch_deg=-0.3)
curr = RobotState(frame=35, behavior="FOLLOW", target_visible=False, action="turn_left", battery_pct=80, roll_deg=0.5, pitch_deg=-0.3)
-> []                                                  # frame 35: not yet, waiting out the debounce
-> [Event(name="target_lost", frame=37, urgent=False)] # frame 37, if TARGET_LOST_FRAMES = 3

# battery crosses the low line (frame 80)
prev.battery_pct = 80, curr.battery_pct = 19 -> [Event(name="battery_low", frame=80, urgent=True)]

# tilt past the fall line (frame 90)
curr.roll_deg = 70.0 -> [Event(name="fell", frame=90, urgent=True)]
```

`TriggerMemory` holds debounce counters and "already announced" flags, so an event fires once
per crossing and not on every frame.

**Questions**
- **T1. Lost debounce:** how many frames out of view before "lost you"? *Rec: count frames,
  not seconds (house rule). The number waits on V2's perception rate (`# MEASURE:`).
  Perception flickers, so 1 frame would make it chatter.*
- **T2. Found vs. reacquired:** one event, or two ("found you" the first time, "there you
  are" after a loss)? *Rec: two. They read differently, and both are cheap cache lines.*
- **T3. Battery low:** at what %, and when does it re-arm? *Rec: re-arm only after charging
  above a higher %, so a reading that wobbles around the line doesn't repeat the warning.
  The % where the S2 browns out is a `# MEASURE:`.*
- **T4. Fall:** reuse your `FALL_TILT_DEG` and `tilt_deg` from `brian/metrics.py`, so "fell"
  means the same thing in sim and on the dog? *Rec: yes. `tilt_deg` takes projected gravity,
  and its docstring already says the real dog builds that from IMU roll and pitch.
  `metrics.py` imports only numpy, so the voice venv can import it without touching it.*

## 2. `speech_policy.py`: should we say it now?

```python
SpeechPolicy.decide(event: Event, now_s: float) -> Decision

# last line ended at 9.1 s; COOLDOWN_S = 6.0
decide(Event("target_lost", frame=37, urgent=False), now_s=12.4) -> Decision(speak=False, reason="cooldown (3.3 s of 6.0 s)")
decide(Event("fell",        frame=90, urgent=True),  now_s=12.4) -> Decision(speak=True,  reason="urgent: skips cooldown")

is_stale(event: Event, state_when_ready: RobotState) -> bool
is_stale(Event("target_lost", ...), RobotState(..., target_visible=True)) -> True   # back in view: drop "lost you"
```

**Questions**
- ~~**P1. Cooldown length**~~ **Answered (Brian, 2026-11-07):** 4 s after cached lines, at
  least 30 s between Haiku lines, and urgent cached events (fall, battery) skip the wait. See
  `decisions.md`.
- **P2. Urgent while talking:** urgent events skip the cooldown (answered). Still open: does a
  fall also cut off a line that's playing, or wait for it to end? *Rec: cut it off. A
  2-second joke shouldn't delay "I fell".*
- **P3. Events during cooldown:** drop them, or keep the newest and say it when cooldown ends?
  *Rec: drop. Saying it later is a stale line by definition.*
- **P4. Staleness:** just "the event's condition is no longer true", or also a max age? *Rec:
  both. The condition check, plus drop anything older than the latency target.*

## 3. `line_cache.py`: instant lines with no API call

```python
LineCache.build(tts, voice_id) -> None     # pre-generates every line once; skips files that exist
LineCache.pick(event_name: str) -> CachedClip | None

pick("target_lost")   -> CachedClip(text="Whoa, lost you, bro. Hang on.", pcm=b"\x00\x01...",  # ~1.4 s of 24 kHz audio
                                    path="audio_cache/7QN34D2r3hCNwbOYIeK0/target_lost_0.pcm")
pick("scan_complete") -> None   # not cached, so this goes to Haiku
```

Cache files are keyed by voice + model + text, so changing the voice or a line regenerates only
what changed. They're gitignored (they can be rebuilt from the text).

**Draft lines v2** (Claude, 2026-11-07, for persona v2: a tiny dog with big-bro energy;
≤12 words; edit freely). They play it straight as big-bro swagger; the squeaky voice is the
punchline:

| Event | Variants |
|---|---|
| target_found | "Yo, there's my guy. Let's roll." / "Got you, bro. I'm on it." / "Big dog's locked in. Lead the way." |
| target_reacquired | "There you are, man. Had me worried for a sec." / "Back on you, bro. We good." / "Found you again. Never doubted it." |
| target_lost | "Whoa, where'd you go, bro? Hang tight." / "Lost you, man. Big dog's on the case." / "Hold up, I lost you. Looking." |
| battery_low | "Bro, I'm running on fumes. Charger soon?" / "Battery's low, man. Big dog needs a nap." / "Gonna need a charge soon, bro. No stress." |
| fell | "Oof. I'm good, bro. Little help though?" / "Yeah, I ate it. Help a bro up?" / "Took a tumble, man. Still cool. Mostly." |

**Questions**
- **C1. Variants:** how many per event, and how is one chosen? *Rec: 3, random but never the
  same one twice in a row, so it doesn't sound canned.*
- **C2. What's "novel" (goes to Haiku)?** With only the events above, every event is cached and
  Haiku never runs. *Rec: Haiku gets every event type not in the table (behavior changes,
  combinations like "low battery while following"), and V2's richer events once it lands.*
- **C3. Persona prompt:** review `PERSONA` in `ironbark_voice/brain.py`. It's your
  personality answer turned into instructions.
