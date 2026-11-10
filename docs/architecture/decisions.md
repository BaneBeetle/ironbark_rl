# IronBark V3 architecture: decisions

Brian owns every decision here. Claude recommends and records. Newest decisions go at the bottom of each section with date and Brian's words.

Sections: §1 decided (the dated log); §2 Claude's defaults (C-1 to C-13 approved 2026-11-08; C-14, C-15, C-16 and C-19 approved 2026-11-09 through his advisor session; C-17 and C-18 open); §3 Brian's numbers (set 2026-11-08; the two gains wait on M-6, the mic tail on M-33); §4 design questions (D-10 to D-16 answered 2026-11-08; D-17 answered the same day through the voice session; D-18 to D-22 open); §5 the `# MEASURE:` register (what must be measured, how, and which decision it unblocks).

---

## 1. Decided

### 2026-11-08: the nine architecture questions (Brian)

Claude sent nine questions with a recommendation each; Brian: **"Go with all recs."** The recommendations, now decisions:

| # | Question | Decision | Why |
|---|---|---|---|
| D-1 | Transport | **ZMQ + JSON** for everything PC ↔ Pi: one socket table, a `hello` handshake and a startup self-test per pair, `last_cmd_seq` echoed in `state`. ROS2 only inside the Pi for Yahboom's SLAM in Phase 2, behind one bridge node | V2's failures were discipline, not transport; DDS over Wi-Fi adds discovery and clock problems that would need measuring |
| D-2 | Perception placement | **PC (3090)**, with a host-agnostic `tracks` schema so the detector can move to the Pi later. Nothing safety-critical on the Pi depends on perception | The camera → PC path is measured (20 fps, 10.9 ms one-way); a Pi detector needs the CPU (~5–10 fps, unmeasured) or new hardware |
| D-3 | Who closes the follow loop | **A deterministic PC follow controller** (proportional on pixel offset, 20 Hz) emits velocity; the VLM sets goals at ~1 Hz and gets direct velocity only as a short-TTL tool | A ≥ 1 s VLM on a continuous-motion machine is V2's overcorrection (LESSONS A6) tripled |
| D-4 | Mode arbitration | **Pi-side arbiter** owns the motors: `ESTOP > fault → IDLE_HOLD > operator > brain`. Action groups **never preempt walking**: request → zero velocity → stand → handoff; action groups only from `IDLE_HOLD` | One owner at a time; handoffs are measured, not improvised |
| D-5 | Comms loss / Pi hang | On losing the PC stream: **zero-velocity command, the policy keeps standing**; freeze (stop writing) only if the IMU is also rejected. Firmware gait is never used for locomotion, so a Pi hang leaves a held pose, not a walking dog (stand test confirms). **Kill switch = power button** | A frozen mid-stride pose may be unstable; standing is the trained behaviour |
| D-6 | Who publishes events | **The owner of a fact publishes it once**: Pi → `fell`, `battery_low`, `imu_frozen`, `mode_changed`, `estop`; owner tracker → `target_found/lost/reacquired`, `verify_result`; voice subscribes and keeps its pacing policy. T1 debounce moves into the tracker, T3/T4 onto the Pi; `is_fallen` stays the single fall definition | Two fall definitions can drift |
| D-7 | STT path | The CSK4002 is a keyword recogniser over serial. **Schema for keyword events now; `speech_text` reserved** for a raw-mic → PC STT path | Mic availability is unknown |
| D-8 | Velocity semantics | Body frame, m/s / m/s / rad/s; each command carries `ttl_ticks` and expires to zero; the Pi clamps to the trained ranges (vx −0.5…0.6, vy ±0.3, wz ±0.8). **The lidar reflex blocks only** (clamps vx), never steers | The safety layer never originates motion |
| D-9 | Versioning | `v` int per message type; `hello` compares versions and lists socket pairs; the Pi refuses mismatched types and says so in `health`. JSON until a measured need for msgpack | Fail loudly at startup, before anything is armed |

Carried in from earlier calls (deployment-notes.md, journal.md), unchanged: policy loop on the Pi; IMU sanity filter; round-to-nearest bytes; all-12-first on `adopt`; `XGO_DOG` direct (no `reset()`); never `calibration()`; no wall-clock on the Pi; dead reckoning from commanded turns, not IMU yaw; hostnames not IPs; receiver-clock ageing only; persistent journal + `get_throttled` logging; kill switch within reach; stand test of Pi-silence in both modes before deployment; voice pacing (4 s / 30 s / falls interrupt / battery queues), `FALL_TILT_DEG = 46`, `BATTERY_LOW_PCT = 20`, re-arm above 30.

Wording in the table above that the reviews later corrected (the decisions stand): D-5's "standing is the trained behaviour" is unverified (M-28; see the entry below). D-7's board is a YB-MVE02-V2.0 whose chip is unconfirmed as a CSK4002, and "mic availability is unknown" is now "the board's mic is not reachable over its USB".

### 2026-11-08: defaults, numbers and D-10 to D-16 (Brian)

Brian, verbatim:

> §2: approve all defaults C-1 to C-13.
> §3: accept all recommendations as written (standoff 1.5 m). Gains KP_YAW/KP_RANGE get set after M-6 as recommended.
> §4: D-10 (c), D-11 (b), D-12 Haiku first, D-13 as recommended, D-14 as recommended, D-15 yes, D-16 yes.

The tables in §2–§4 carry each call. Still open after this: `KP_YAW` and `KP_RANGE` (set from a step test after M-6), D-10's final answer (after the obs-parity test), and the §5 register, whose **gate** rows block deployment. A number in §3 changes only through a new dated entry here.

### 2026-11-08: the two flags (Brian)

While filling in §3 and §4, Claude flagged two things: `IMU_STALE_TICKS = 75` does not clear two freezes back to back at the 25 Hz IMU read cadence (§3.1), and D-13 as written would start a yaw sweep away from a person still in view (§4). Brian, verbatim:

> Both flags: keep IMU_STALE_TICKS = 75 (a brief pause is the safe failure); approve your D-13 reading (re-verify while visible, sweep only from LOST).

### 2026-11-08: review by the voice session (corrections; no decision here)

Brian told Claude it can ask the other sessions. The voice session checked commit `17f2c92` against its code and measurements (`docs/voice/oracle-questions.md`, `s2-voice-module.md`, `decisions.md` on `feature/voice`). What changed:

- **Corrected to match what Brian had already decided.** T3 re-arms "above 30%" (the docs said ≥ 30). D-6's `verify_result` is published as `owner_verified` / `owner_rejected`. failure-modes §10 no longer claims a cached-line fallback: cached events never call an API, and a failed Haiku line is logged and dropped. architecture §4.5 no longer calls STT a Phase 2 item: the PC-side loop (mic → Scribe → Haiku → Tilly) is built.
- **Measured facts taken in.** The dog has no microphone the Pi can reach. (The review also said "no speaker". Brian disputed that the same day, and it is unverified either way until M-13: see the last entry in this section. It was an inference from a silent report and from the speaker's plug going into the voice board, a YB-MVE02-V2.0 seen on USB as CH340 serial only.) The board's wake word works and sends `$B000#` at 115200 baud. D-7's "keyword events first" stands; its "mic availability is unknown" is now "not reachable through the board's USB".
- **Gaps fixed in `interfaces.md`**, as defaults C-14 to C-19 in §2 (awaiting Brian).
- **New questions for Brian:** D-17 to D-22 in §4. Five of them are the voice session's logged Oracle questions.

### 2026-11-08: after the joint-control session's review (Brian)

The joint-control session checked the same commit against the Phase 1 logs and the training configs. Brian, verbatim:

> To the Oracle (via the RL agent's review): before I merge, update the docs: (1) release stance is unmeasured; M-8 must cover the no-reset() case. (2) IMU freezes are scoring-only today; plan to train with them in the domain-randomization phase. (3) "policy stands" is unverified: add an eval of walk→stop transitions and plan more stand commands in training. (4) tick budget is 17–19 ms per the review; battery reads get their own tick, confirmed by M-2. (5) Decision: a monotonic clock is allowed on the Pi for loop pacing ONLY; decisions still use tick/frame counts. (6) Flag M-4 as the first hardware session, since a new default pose means retraining every policy.

| # | Where it landed |
|---|---|
| 1 | architecture §3.2 (`release` blocked until measured), C-5 amended, M-8 extended, failure-modes §15 |
| 2 | architecture §3.3 and §5.2, failure-modes §4, interfaces §9. The plan is a training experiment in the domain-randomization phase (Phase 2A week 5); its design is Brian's when it is written up |
| 3 | architecture §3.3, failure-modes §1, new gate row M-28 (walk → stop eval). More stand commands in training (`rel_standing_envs` is 0 today): the amount is Brian's, as its own experiment |
| 4 | architecture §3.1 and §5.3, C-2 amended, `BATTERY_EVERY_TICKS` in §3.1, M-2 rewritten |
| 5 | architecture §1 rule 4 and §3.1, interfaces §9. `CLAUDE.md`'s hard rule ("No wall-clock logic in Pi-side code") carries the exception on `main` since `aea73cb` |
| 6 | M-4 marked first in §5, interfaces §9, architecture §6 |

Also from that review, corrected without needing a call: `adopt` waits ≥ 8 ticks (the cycle measured 126–144 ms), is not atomic, and is what `BOOT` → `IDLE_HOLD` runs; the IMU at 25 Hz is coarser, not finer, than its live refresh; vendor calls no probe has logged (`action(id)`, `unload_allmotor` / `load_allmotor`, stationary `attitude`) are blocked until one has; the adapter sets `motor_speed` itself; the ONNX holds its own normaliser; `default_joint_pos` is still the Mini2S placeholder; M-11 reworded; new register rows M-24 to M-28. Checked and confirmed by the same review: the measured serial components, the adapter's construction and rounding, and the 35-float layout against EXP-025's exported model.

### 2026-11-08: Brian: the dog's speaker played Tilly (the Pi playback path is unverified until M-13)

Brian, verbatim:

> Correction for D-17: the dog's speaker DID play Tilly's voice in my test, so a playback path from the Pi exists. Identify it: run `aplay -l` on the Pi (M-13) to find the audio device, and record how that test was played. Also check whether a mic on the same device is reachable with `arecord -l`.

**The candidate device.** Card 2, `sndrpihifiberry` [`snd_rpi_hifiberry_dac`], device 0 ("HifiBerry DAC HiFi pcm5102a-hifi-0"): the Pi's I2S DAC from the `hifiberry-dac` overlay, and the only device any Tilly clip was ever sent to on the Pi. Cards 0 and 1 are the two HDMI outputs. Source: the voice session's saved `aplay -l` output (`samples/pi_audio/inventory.txt` and `inventory_usb_connected.txt` in its worktree; 2026-11-08, 19:14 and 20:04 EST). **Not re-run live:** the Pi was off the network when Claude tried at 22:15 EST (no ping, SSH or mDNS at 192.168.68.56).

**How the test was played** (the voice session's record: four plays in two rounds, 2026-11-08 at 19:33 and 19:34 EST):

- Clip: `samples/1_target_found.wav`, 24 kHz mono S16_LE, 1.86 s ("Yo, there's my guy. Let's roll."), copied to the Pi's `/tmp` with `scp` and deleted after each round.
- Commands: round 1, `aplay -q -D plughw:2,0 /tmp/tilly_quiet.wav` twice, 1 s apart. Round 2, `tilly_quiet.wav` then `tilly_mid.wav`, 2 s apart. All four exited 0.
- Volume: software gain written into the file only, 30 % (`tilly_quiet`) and 60 % (`tilly_mid`). No `amixer` or `pactl` command was run, no mixer value was read, and 100 % was never tried. `plughw:2,0` bypasses the default route in `/etc/asound.conf` (softvol into dmix), so that route was never exercised.
- State: before the voice board's USB port was cabled. Whether the voice board had power is not recorded.
- What Brian said at the time: after round 1, "try one more time?"; after round 2, "cant hear it. Ill take the dog down and check this". The voice session logged that as "no audible sound". What he says now is the quote above. Which of the four plays he heard is not on record.

**A mic on the same device: no.** The PCM5102A is a playback-only DAC, and `arecord -l` listed no capture hardware at all, before and after the voice board's USB was cabled (the only PulseAudio source is the monitor of the output). The voice board's own mic works for its wake word but does not reach the Pi.

**The record does not settle it** (added later the same day, from the voice session). Brian told the voice session when he heard it: after he reassembled the dog and plugged in the USB-C ("Now I head tilly's voice"). The last Tilly clip sent to the Pi was at 19:34 EST, before that cabling, and he reported it then as "cant hear it". The only speech logged after the cabling is the voice board's own reply to "Hello Yahboom" at about 20:07 EST, through its own speaker, which he described then as "something like Hi Im Here". So either a Pi playback happened that no session logged, or what he heard was the board's reply. He is the witness; the docs take neither side.

**What this changes.** Both claims are now marked unverified: "no speaker the Pi can reach" (the voice review's inference) and "the speaker plays from the Pi" (not matched by any logged play). `AUDIO_DEVICE = plughw:2,0` is a candidate, `# MEASURE:` until M-13 passes. D-17 keeps both the speaker and the mic. M-13 is one audible re-run with the board cabled and powered, which is a real change from the silent plays (those ran before cabling, board power unknown).

### 2026-11-08: M-13 first results: still silent, and card 2 looks like a V1 leftover

**Live listing** (Claude, read-only over SSH, 22:21 EST, Pi up 2 minutes, voice board on USB):

- `aplay -l`: card 0 `vc4hdmi0`, card 1 `vc4hdmi1`, card 2 `sndrpihifiberry` [`snd_rpi_hifiberry_dac`], device 0 "HifiBerry DAC HiFi pcm5102a-hifi-0". Same as the saved listings.
- `arecord -l`: no capture hardware. PulseAudio's only source is the monitor of the output.

**Re-run with the board cabled** (voice session, with Brian): the 60 % clip (`tilly_mid.wav`) to `plughw:2,0`, four plays in two rounds, all exit 0, CH340 and `/dev/ttyUSB0` present. Brian after round 1: "Can u do it one more time"; after round 2: **"Silence..."**. Not run: 30 %, 100 %, the board's USB unplugged. Whether the board's amplifier was on is unknown. At uptime 0 minutes the first attempt failed twice with `audio open error: Device or resource busy`; seconds later nothing held the device and it opened.

**Where card 2 comes from** (read on the Pi the same minute):

- `/etc/asound.conf`, dated 2025-10-18, is SunFounder's Robot HAT speaker setup: `pcm.speaker` → `hw:sndrpihifiberry`, a dmix, a softvol whose control is named "robot-hat speaker Playback Volume", and `pcm.robothat`. `amixer -c 2` shows that one control and nothing else.
- `robot_hat 2.3.5`, `pidog 1.3.9` and `vilib` are installed on this OS; `~/robot-hat` and `~/vilib` exist.
- `/boot/firmware/config.txt` loads `dtoverlay=hifiberry-dac`; GPIO 18–21 are in their I2S function.

**Reading (Claude's, an inference):** card 2 is the audio setup of V1's PiDog (its Robot HAT carried an I2S amplifier), still on this OS install. The `hifiberry-dac` overlay registers a card whether or not a DAC is wired, because the PCM5102A has no control bus to probe; so `aplay` exiting 0 says nothing about sound. On the S2 nothing is known to be wired to GPIO 18, 19 and 21. That fits eight plays and no sound, and it is LESSONS B1 again: machinery that rode along from V1. The speaker that does make sound on this dog is the voice board's, answering its wake word.

Brian then asked the voice session to "play the other one that I heard". No such file exists; the only audio logged from the dog is the board's own reply. He has not said in those words that this is what he heard.

**Status.** No working playback path from the Pi is known. `AUDIO_DEVICE` stays unset. D-17 keeps the speaker and the mic. New: M-29 (what audio path the S2 is meant to have), and the player must retry when the device is busy at boot.

### 2026-11-08: Brian picks a USB sound card for the dog's mic and speaker (relayed by the voice session)

Brian, to the voice session, about an Amazon listing ("USB Sound Card with 8Ω 5W Speaker for Raspberry Pi/Jetson Nano", brand Wonrabai; its photo shows a Waveshare USB TO AUDIO card):

> Imma just use this

Relayed by the voice session, not said to this one. The card is not on the dog yet, and nobody has confirmed it is ordered.

**Vendor claims, none measured** (Waveshare's wiki and product page, through the voice session): USB 2.0, driver-free on Linux, SSS1629A5 codec, onboard mic, 8 to 48 kHz including 16 and 24 kHz, PH2.0 speaker port, 2.6 W per channel into 4 Ω. No echo cancellation is documented.

**What this changes.**

- **D-17 is answered:** the mic and the speaker are both on this card, on the Pi. Claude's rec was to learn the S2's own audio path first (M-29) and to prefer a device with echo cancellation. Without echo cancellation the mic stays shut while the dog talks (half-duplex, which the voice loop already is).
- **`AUDIO_DEVICE` stays unset**, `# MEASURE:` until the card is on the Pi. It is set by card name, never by card number (numbers can shift) and never as `default`: this Pi's `/etc/asound.conf` sends the default route to the dead card 2.
- **M-13 now targets this card.** The card-2 plays no longer matter to the design, and M-29 no longer blocks a purchase.
- **D-20 is live:** there will be a mic on the Pi, so the dog-mic → PC stream needs Brian's call. Its options are rewritten for that (the old (c) was "decide with D-17").
- **New measures:** USB current at speech volume (M-30: the card shares the Pi's USB budget with the camera, and a brownout is a Pi hang); the added mass (M-31: the sim has none of it); loop timing beside a Pi-side wake word (M-32).

**The voice board: not decided.** Brian has not said it leaves. The voice session's report (`reports/DOGZILLA S2 voice board removal.md`, untracked in the main checkout) recommends unplugging it and keeping it until two checks pass: tracing its 4-pin cable, and scoring a software wake word against the chip with 50 Hz loop timing logged. So C-18's `voice_module_reader` becomes optional, and `keyword` now names what was heard and carries its `source` (interfaces §6), which makes chip versus software a one-variable swap. From the report, for M-14 and M-29: the board matches Yahboom's documented CSK4002 module (their documents are for the V1.0 board; this one is V2.0 and its chip marking is unread), `$B000#` is the documented wake event, the Program micro-USB is documented only for firmware updates, and how Yahboom's own S2 LLM feature gets audio is still unknown.

### 2026-11-08: Brian: mute the dog's mic whenever Tilly is speaking (relayed by the voice session)

Brian, to the voice session:

> I was thinking about muting the mic whenever tilly voice is speaking

The voice session told him this matches its existing mic gate and points to D-20 (a). His reply: "Update IronBark V3 architecture design". He has not named a D-20 option, so the mute is recorded as his direction and the letter stays open.

**The rule.** The dog's mic is deaf while the voice speaks and for a short tail after. It holds whichever way D-20 goes. It has two halves, and either one alone stops the dog answering its own voice:

- **PC (built on `feature/voice`, `mic_blocked`):** mic audio is ignored from the moment a line job starts (per the voice session, that includes Haiku's thinking time) until the line ends plus `MIC_GATE_TAIL_S`. The PC knows a line is coming before the Pi does.
- **Pi (design, nothing built):** the mic stream is shut from the first PCM write to the device until the device buffer has drained, plus a tail of `MIC_GATE_TAIL_CHUNKS` mic chunks. Chunks, because Pi-side code uses no wall clock.

**The tail is unmeasured.** The voice's `MIC_GATE_TAIL_S = 0.3` is a starting guess made on the PC. How long the dog's mic hears its own speaker after a line is `# MEASURE:` on the new card (M-33). Both tails are Brian's to set from that (§3.4).

**Trade-off, as the voice session put it to Brian:** nobody can talk over her, and anything said during a line is lost. Lines run about 2 to 3 s.

### 2026-11-09: Brian: never command all joints to 0°; solve the zero offsets from safe poses (relayed by the joint-control session)

M-4's method said "command 0° per joint vs the MJCF default pose". Brian dropped that. His words, relayed by the joint-control session and recorded on `main` in `docs/deployment-notes.md` (`294d4e9`, `2b99d6c`):

> Skip the all-joints-at-0° pose; it may be unsafe and exceeds the probe's ±15° rule. Solve zero offsets from safe poses instead: the boot pose (firmware 0/48/14, I'll photo it), plus the +10° held direction-test poses, compared against sim renders at the matching angles.

On which number is the firmware angle, through his advisor session:

> go whatever the actual agent that's in charge of actually manipulating it has access to the code, because they actually have it.

So the firmware angle is the joint readback logged at each photo, and 0/48/14 is not a source. The Phase 1 runs with no `reset()` (`passive`, `map`) read hip −0.6 on all legs, thigh 39.4 / 40.0 / 46.9 / 45.6 and calf 19.3 / 19.3 / 19.8 / 20.3 (fl / fr / br / bl).

**What this changes.** M-4's method in §5. M-4 is still the first hardware session and still a gate. Two tools it needs are not built (the joint-control session is building both): a hold in the probe's `map`, which today wiggles and returns and goes −10° when a joint has no room above, and a sim render at given joint angles.

### 2026-11-09: Brian approves C-14, C-15, C-16 and C-19 (relayed by his advisor session)

The advisor session briefed Brian on the four motion-related defaults as they read at branch head `08407b9`, then asked: "Approve C-14, C-15, C-16 and C-19 and have me relay that to the Oracle?" Brian:

> Approve all 4

Approved: only S1–S3 block arming (C-14); one writer on the command socket, the `gateway` (C-15); `seq` per topic with a level for every paired event (C-16); PC-origin events published by their owner on the PC bus (C-19).

**Still open:** C-17, C-18 and D-18 to D-22, all voice. Brian has parked voice to work on motion: "the whole voice interaction thing is like a nice little feature rather than a necessary need". This is not approval to merge the PR; that stays his.

---

## 2. Claude's defaults (approved by Brian, 2026-11-08)

Plumbing choices made while writing the docs. None is a `brian/` design decision, but each changes how things are built, so they were listed for a veto. Brian: "approve all defaults C-1 to C-13."

| # | Default | Why | Where |
|---|---|---|---|
| C-1 | **The Pi binds every socket; the PC connects to `PI_HOST`.** PUB/SUB roles are unchanged (the PC's command PUB *connects* to the Pi's SUB bind) | The Pi needs no PC address (fixes LESSONS C4 and the 2026-09-30 address-drift step); no inbound Windows firewall rule; one config value on the PC | interfaces §2 |
| C-2 | **Alternate `read_imu()` and `read_motor()` on even/odd ticks** so each 20 ms tick fits. Amended 2026-11-08 (Brian, after the review): the budget is 17–19 ms inferred / 18.0 ms measured, not 14 / 18; battery reads get their own tick; a monotonic clock paces the loop | A 47.6 Hz loop is a 5 % rate error against the 50 Hz training; joint readback at 25 Hz loses little (105–130 ms refresh). The IMU at 25 Hz is coarser than its live refresh | architecture §3.1; see D-10, M-2 |
| C-3 | **`CONFLATE=1` on the PC's camera and lidar PULL sockets** | V2 saw a 3.87 s-stale frame burst on connect | interfaces §2 |
| C-4 | **Camera, lidar and audio are separate Pi processes**, reporting to the runtime over `ipc://`; the runtime publishes one consolidated `health` | Keeps JPEG encoding and serial parsing out of the 50 Hz process; one place for the operator to look | architecture §2 |
| C-5 | **The `release` handoff pre-positions the joints at the pose `stop()` returns them to**, then calls `stop()`. Amended 2026-11-08 (Brian, after the review): that pose is unmeasured. The approved text read it at boot, and the logs contradict that (boot pose vs post-`stop()` pose: 7–8° at the calves, 4–5° at the thighs, and that `stop()` followed a `reset()`). `release` is blocked until M-8 | Keeps the snap on `stop()` small instead of the ~8° jumps Phase 1 saw | architecture §3.2 |
| C-6 | **Action groups are an allow-list file** (`name`, xgolib `id`, `budget_ticks`, `min_battery_pct`); the brain sees names only | The ids are vendor numbers nobody has verified; a budget in ticks bounds every firmware action | interfaces §7 |
| C-7 | **`ESTOP` holds, then unloads after `FALL_UNLOAD_TICKS` when fallen**; never unloads while upright | Unloading upright drops the dog; servos fighting the floor after a fall overheat (V1's death) | architecture §3.2 |
| C-8 | **`REST` = lie-down action group then `unload_allmotor()`**, requested by the brain or operator, never automatic | It is a firmware motion, so it goes through the arbiter like any action | architecture §3.2 |
| C-9 | **Rescan is a yaw sweep under the policy**; a pitch scan is a stationary `ACTION` used only when the yaw sweep failed | `attitude()` is a firmware call; no handoff is needed for the common case | architecture §4.2; see D-11 |
| C-10 | **`speech_started` echoes the PC's `t_ms`** so the voice latency is measured as a round trip on the PC clock | No cross-host arithmetic | interfaces §6 |
| C-11 | **Camera message format kept from V2** (`<qI` + JPEG) | It is measured and works; the stats move to `health` | interfaces §8 |
| C-12 | **Owner photos live outside the repo** (`OWNER_PHOTOS_DIR`) | Privacy; they are not code | interfaces §10 |
| C-13 | **Unknown fields are rejected, not tolerated** | LESSONS B1: V2 carried nine dead fields | interfaces §1 |

### Added 2026-11-08 after the reviews (C-14, C-15, C-16, C-19 approved 2026-11-09; C-17, C-18 open)

| # | Default | Why | Where | Brian |
|---|---|---|---|---|
| C-14 | **Only S1–S3 block arming.** A camera, lidar or audio self-test failure raises a degraded notice and blocks only the behaviour that needs that stream | The first draft let a dead speaker block arming, against failure-modes §10 ("no effect on motion") | interfaces §3 | **approved** 2026-11-09 ("Approve all 4", relayed by his advisor session; §1) |
| C-15 | **One writer on the command socket: a `gateway` in the HUD process.** The follow controller and the brain publish `cmd_request` on the PC bus; the gateway adds `deadman` and forwards, and sends zero velocity while disarmed | With several writers `last_cmd_seq` means nothing; disarming becomes one choke point on the PC | interfaces §12 | **approved** 2026-11-09 ("Approve all 4", relayed by his advisor session; §1) |
| C-16 | **`seq` counts per topic, and every paired event has a level** in a periodic message from its owner (`state.active`, `owner.state`, `goal`) | An event-only subscriber saw constant gaps; a `battery_low` lost in a link blip would never fire again, breaking "never dropped" | interfaces §1, §4; failure-modes §14 | **approved** 2026-11-09 ("Approve all 4", relayed by his advisor session; §1) |
| C-17 | **Audio stream rules.** Sender: `IMMEDIATE=1`, bounded high-water mark, non-blocking send, drop the line if it would block. Player: receives on its own thread; `stop` discards queued PCM and drops the device buffer. A zero-length `final` chunk is allowed; "ended" means final received and drained | Otherwise a link drop replays up to ~50 s of old speech, and a `stop` queues behind a 3 s clip | interfaces §8 | open (voice is parked, §1) |
| C-18 | **A `voice_module_reader` process on the Pi owns the voice board's serial port** and publishes `keyword` through the runtime. Amended 2026-11-08 (the board's future is undecided, §1): the reader is optional and runs only while the board is plugged in; `keyword` names what was heard and carries its `source`, so a software wake word can publish the same event | Voice session's question 4: no process owned it. Source-independent, so chip versus software is a one-variable swap | architecture §2, interfaces §6 | open (voice is parked, §1) |
| C-19 | **PC-origin events are published by their owner on the PC bus** (tracker `:5571`, brain `:5572`, topic `event`); subscribers merge them with the Pi's. The HUD can publish the goal, so supervised FOLLOW runs with no brain | The first draft gave these events no socket, so `target_*` could not reach the voice | interfaces §12 | **approved** 2026-11-09 ("Approve all 4", relayed by his advisor session; §1) |

---

## 3. Brian's numbers (set 2026-11-08)

Each constant: what it controls, the measured context, Claude's recommendation with a one-line reason, and Brian's call. Brian: "accept all recommendations as written (standoff 1.5 m). Gains KP_YAW/KP_RANGE get set after M-6 as recommended." Constraints between constants are written where they bind (LESSONS B4).

### 3.1 Pi safety layer

| Constant | Controls | Context | Rec | Brian (2026-11-08) |
|---|---|---|---|---|
| `VELOCITY_TTL_TICKS` (default sent by the PC) | how long one velocity command stays valid | commands at 20 Hz = 2.5 ticks apart | 15 (300 ms; tolerates 5 missed messages) | **15** |
| `CMD_LOST_TICKS` | when `cmd_stream_lost` fires | must be > TTL | 50 (1 s) | **50** |
| `CMD_DEAD_TICKS` | when the arbiter drops to `IDLE_HOLD` | must be > `CMD_LOST_TICKS` | 250 (5 s) | **250** |
| `REQUIRE_DEADMAN` | whether nonzero velocity needs `deadman=true` | supervised sessions first | `true` until the first unsupervised session is a deliberate decision | **`true`** (changes only under D-14) |
| `IMU_FREEZE_READS` | identical blocks before `frozen` | live refresh 4–8 ms; reads 40 ms apart under C-2 | 3 (120 ms; unambiguous) | **3** |
| `GYRO_MAX_DPS` | reject threshold | outliers measured 1514–1623 °/s; real gait rates `# MEASURE:` (M-5) | 1000 | **1000** |
| `IMU_STALE_TICKS` | frozen/rejected → velocity zero | longest measured freeze 1004 ms = 50 ticks; must exceed it | 75 (1.5 s) | **75**, confirmed after the flag below |
| `IMU_DEAD_TICKS` | → `IDLE_HOLD` | > `IMU_STALE_TICKS` | 150 (3 s) | **150** |
| `FALL_UNLOAD_TICKS` | hold → unload after a fall | servo heat vs a chance to recover | 100 (2 s) | **100** |
| `JOINT_MARGIN_DEG` | inside `MOTOR_LIMIT` | the probe used 3° | 3 | **3** |
| `JOINT_STEP_MAX_DEG` | max target change per tick | servo spec 0.1 s/60° → 12°/20 ms | 12 | **12** |
| `ADOPT_RAMP_TICKS` | measured pose → policy default pose | | 50 (1 s) | **50** |
| `STAND_TICKS` | zero-velocity settle before `release` or `IDLE_HOLD` | one gait cycle ≈ 0.4 s | 25 (0.5 s) | **25** |
| `BATTERY_CRITICAL_PCT` | velocity zero, rest requested | firmware lockout at 9 %; load sag suspected | 12 | **12** |
| `BATTERY_EVERY_TICKS` | battery read cadence | V2 used 250 (5 s); a read costs ~3 ms in a tick | 250, on an `imu` tick | **250**, on its own tick with no other read (changed 2026-11-08 after the review: on an IMU tick it would overrun) |

**Flag (Claude, 2026-11-08); Brian the same day: keep 75.** `IMU_STALE_TICKS = 75` clears one measured freeze (≤ 1004 ms) but not two back to back. Under C-2 the IMU is read every 40 ms, and the shortest measured live stretch between freezes is 25 ms (1 of the 40 in `latency_config.IMU_LIVE_MS`), so a read can miss it and see ~2 s of identical values; velocity would zero until the next accepted read. Expected to be rare, roughly one freeze in a hundred. Brian: "keep IMU_STALE_TICKS = 75 (a brief pause is the safe failure)." M-2 still counts how often it happens at the real cadence, as a measurement, not a reopened decision.

### 3.2 PC follow controller and owner tracker

| Constant | Controls | Context | Rec | Brian (2026-11-08) |
|---|---|---|---|---|
| `TARGET_LOST_FRAMES` | zero velocity and `target_lost`, one constant for both | voice placeholder was 3 at 5 Hz; tracker runs at 20 fps | 10 (0.5 s) | **10** |
| `STANDOFF_AREA_RATIO` | the range the dog holds | ladder: 0.159 at 1 m, 0.118 at 1.5 m, 0.099 at 2 m; 1 m is noisy (σ 40 px, clipped) | 0.118 (1.5 m); re-run the 1.5 m station first (its hit-rate dip is one sample) | **0.118 (standoff 1.5 m)**; re-run the 1.5 m ladder station first |
| `OFFSET_DEADBAND_PX` | no yaw correction inside | static noise σ 2.6–3.5 px at 2–3 m, 40 px at 1 m; motion jitter ~45 px median (uncommitted V2 log) | 30 at ≥ 1.5 m | **30** at ≥ 1.5 m |
| `KP_YAW`, `KP_RANGE` | proportional gains | dead time ≈ 150–250 ms (architecture §5.2); the real number is M-6 | set from a step test after M-6; start at half the gain that gives one overshoot | **not set: after M-6**, as recommended |
| `ACQUIRE_FRAMES` | consecutive argmax frames before lock | V2 §5: 3 | 3 | **3** |
| `CONFIDENCE_DECAY_LOCKED` | per-frame multiplier while locked and unverified | | 0.999 (half-life ~35 s at 20 fps) | **0.999** |
| `CONFIDENCE_DECAY_LOST` | per-frame multiplier while lost | | 0.97 (half-life ~1 s) | **0.97** |
| `RESCAN_CONFIDENCE` | below this → rescan | | 0.3 | **0.3** |
| `VERIFY_PERIOD_FRAMES` | periodic VLM verify while locked | VLM cost/latency | 600 (30 s) | **600** |
| `RESCAN_WZ` | sweep yaw rate | trained max 0.8 rad/s | 0.5 rad/s | **0.5 rad/s** |
| `RESCAN_MAX_ANGLE_DEG` | sweep bound each side of the dead-reckoned bearing | | 90 | **90** |
| `RESCAN_COOLDOWN_FRAMES` | between sweeps | | 100 (5 s) | **100** |
| `RESCAN_MAX_ATTEMPTS` | before the voice fallback | | 2 | **2** |
| `BRAIN_VELOCITY_TTL_MAX` | cap on a brain `set_velocity` | | 100 ticks (2 s) | **100 ticks** |
| `TELEM_STALE_S`, `FRAME_STALE_FRAMES` | PC-side link/age thresholds (PC clock allowed) | | 1.0 s; 5 frames | **1.0 s; 5 frames** |

How the tracker constants compose (arithmetic, for the builder): with a verify every 600 frames, a locked target's confidence falls to 0.999⁶⁰⁰ ≈ 0.55 between verifies and never reaches 0.3 while verifies succeed; it takes ~1200 frames (60 s) without one.

### 3.3 Lidar reflex (Phase 2)

| Constant | Controls | Context | Rec | Brian (2026-11-08) |
|---|---|---|---|---|
| `FRONT_SECTOR_DEG` | half-width of the forward sector | body 14.5 cm wide; lidar offset from the nose `# MEASURE:` (M-9) | ±30° | **±30°** |
| `STOP_DISTANCE_M` | vx → 0 at or under | | 0.25 | **0.25** |
| `TAPER_DISTANCE_M` | full vx allowed at or beyond | | 0.60 | **0.60** |
| `VX_CAP_LIDAR_DARK` | forward cap with no scan | | 0.2 m/s | **0.2 m/s** |
| `LIDAR_DARK_SCANS` | scans missing before dark | | 3 | **3** |

### 3.4 Voice (added 2026-11-08; not set)

| Constant | Controls | Context | Rec | Brian |
|---|---|---|---|---|
| `MIC_GATE_TAIL_CHUNKS` (Pi) and the voice's `MIC_GATE_TAIL_S` (PC) | how long the mic stays deaf after a line ends | the PC value is 0.3 s, a starting guess; the dog's own echo on the new card is `# MEASURE:` (M-33) | set after M-33: the measured echo plus a margin | |

---

## 4. Design questions (answered by Brian, 2026-11-08)

| # | Question | Options | Rec | Brian (2026-11-08) |
|---|---|---|---|---|
| D-10 | Should the sim's joint-readback model mirror the 40 ms read cadence of C-2? | (a) leave `JOINT_REFRESH_PERIOD_S = 0.130` as is; (b) add the 2-tick read cadence to `stale_joint_pos`; (c) decide after the parity test | (c): the parity test (week 6) shows whether the extra ≤ 40 ms of staleness moves the policy; retrain only if it does | **(c)**. The review adds the 40 ms IMU hold from C-2 to the same test; the question as asked covered joints only |
| D-11 | Pitch scan during rescan | (a) never (yaw sweep only); (b) stationary `ACTION` with `attitude('p')` after the yaw sweep fails (C-9); (c) add body pitch to the policy's command and retrain | (b) | **(b)** |
| D-12 | VLM model for owner verify | Haiku 5.5 (fast, cheap) vs a larger model | Haiku 5.5 first; promote only if M-12's held-out accuracy says so | **"Haiku first"** |
| D-13 | Verify failure policy | reject → unlock immediately, or reject → keep following at low confidence until the next verify | unlock after 2 consecutive rejects; one reject lowers confidence to `RESCAN_CONFIDENCE` | **as recommended**, with the reading Brian approved the same day ("re-verify while visible, sweep only from LOST"): after one reject with the target still in view, the tracker re-verifies on the next frame and does not sweep; the yaw sweep runs only from `LOST` |
| D-14 | Unsupervised sessions | when `REQUIRE_DEADMAN` may be false | after the stand-test gate and ≥ 3 supervised sessions with zero `ESTOP`s from the safety layer | **as recommended** |
| D-15 | Session logging | what the PC records every session | all of `state`, `health`, `event`, `tracks`, `owner`, `velocity` to JSONL + the camera stream to MJPEG, by session id; it is the dataset for Path B-style learning later and the evidence after any hang | **yes** |
| D-16 | Gamepad (roadmap, later) | `velocity` with `src: teleop` through the same arbiter | yes, nothing new on the Pi | **yes** |

### Added 2026-11-08 from the voice session's review (D-17 answered; D-18 to D-22 open)

| # | Question | Options | Rec | Brian |
|---|---|---|---|---|
| D-17 | **Audio hardware on the dog.** Speaker: no working path from the Pi is known. Eight plays to card 2 (`plughw:2,0`) made no sound, the last four with the voice board cabled (Brian: "Silence..."), and card 2 looks like V1's Robot HAT setup with nothing behind it on the S2 (§1). Brian recalls hearing Tilly from the dog; no logged play matches. Mic: none reachable, `arecord -l` lists no capture device | (a) a USB speakerphone on the Pi (mic + speaker + echo cancellation); (b) a separate USB speaker and USB mic; (c) keep both on the PC for Phase 1; (d) first learn the S2's intended audio path (M-29: Yahboom's image plays and records on the Pi somehow), then choose; (e) the voice board's own speaker, its stored phrases only | (c) now, since voice out and listening already work on the PC, and (d) before buying anything: if Yahboom's path exists on this hardware it is free. (a) if it does not, because echo cancellation in one device is what lets the mic stay open while the dog talks. Yahboom warns about the Pi's USB current limit: measure the draw before adding a USB device | **A USB sound card with its own 8 Ω 5 W speaker pair, for both the mic and the speaker** ("Imma just use this", to the voice session, relayed 2026-11-08; §1). Closest to (b), in one device, no echo cancellation documented. Not on the dog yet |
| D-18 | **Pacing of the brain's `say` / `ask_owner`** | (a) both obey the 30 s Haiku spacing; (b) both skip the gaps like replies; (c) `ask_owner` is heard like a cached line, `say` obeys the 30 s spacing | (c): `ask_owner` is the verify fallback and must be heard; free chatter stays paced | |
| D-19 | **Which events the voice speaks.** "Haiku handles any event not in the cache table" was written for 6 events; the catalogue now has about 25, and `speech_*` would loop | (a) a voice-owned speak list: cached = found / lost / reacquired / `battery_low` / `fell`, Haiku = `behavior_changed`, everything else silent; (b) the rule as written | (a). Add cached lines for `owner_verify_needed` ("that you, bro?") and `battery_critical`; `battery_critical` queues like `battery_low`; `estop` stays silent; only `fell` interrupts, as now | |
| D-20 | **Dog mic → PC** (voice questions 1 and 3). Live since D-17 put a mic on the Pi; the card documents no echo cancellation | (a) reserve a stream: Pi PUSH (binds) → PC PULL on 5561, the audio framing of S6, sent only while a gate is open (opened by a wake `keyword` or a PC `mic_ctl open`, closed by `mic_ctl close` or a tick budget); the Pi shuts the gate itself while it is playing; (b) voice-activity detection on the Pi; (c) an always-open stream, with the wake word found on the PC | (a). The gate keeps pre-wake audio off Wi-Fi, and the Pi shutting it during playback is the half-duplex rule a card without echo cancellation needs. (b) puts audio processing on the Pi beside the 50 Hz loop (M-32). Nothing is built until the card is on the Pi and M-13 passes | Direction, relayed 2026-11-08: "I was thinking about muting the mic whenever tilly voice is speaking" (§1). It fits (a). No option named yet |
| D-21 | **Can speech cause motion?** (voice question 5) Today it cannot | (a) never; (b) only to reduce it: a heard "stop" / "stay" sets goal `STAY` through the brain's path, with no safety role; "follow me" reaches the brain as input like any other; (c) speech as a command channel | (b). A spoken stop is never a safety mechanism: recognition can miss and adds ≥ 0.4 s. The HUD e-stop and the power button stay the stops. The voice process still sends no commands | |
| D-22 | **Who else learns what was said?** (voice question 7) Today it is private to the voice | (a) keep it private; (b) publish "a person is speaking" start / stop, no text, so the brain can hold its chatter; (c) also give the brain the text as `speech_text`, never logged | (b) and (c) together if D-21 is (b); transcripts are never written to committed logs, the voice's existing rule | |

Answered by the docs without a call: voice question 2 (PC → dog speaker) is S6; question 4 (who owns the voice board's port) is C-18, while the board stays plugged in; question 6 (`behavior` and `target_visible` for the voice) is the event stream plus its levels (C-16, C-19).

---

## 5. `# MEASURE:` register

Every unmeasured number the architecture depends on, with the procedure and the decision it unblocks. This list is the **stand-test gate** (LESSONS D1): nothing deploys until the rows marked **gate** are green. Brian runs everything that moves the dog.

**M-4 is the first hardware session** (Brian, 2026-11-08): the policy's default pose is still the Mini2S placeholder, and if the S2's joint zeros force a different one, every policy trained so far has to be retrained. Everything else in the gate is cheaper to learn second.

| # | Measure | How | Unblocks | Gate |
|---|---|---|---|---|
| M-1 | Board behaviour when the Pi stops sending mid-motion, joint mode and gait mode | dog on the stand; probe commands a motion then `kill -STOP`s itself; video the legs; log whether the pose holds, the gait continues, and any board-side timeout | D-5, failure-modes §2 | **gate** |
| M-2 | Composed tick time of the C-2 schedule. Done so far: both reads every tick (`imu-loop`, 21.0 ms). The alternating schedule has never run | a new probe mode (none exists): even ticks write + `read_imu()`, odd ticks write + `read_motor()`, one battery-only tick every 250, paced to 20 ms by the monotonic clock; p50/p99 per tick kind over 1500 ticks, overruns counted; try the obs/policy work between write and read; count IMU freezes that read longer than `IMU_STALE_TICKS` at this 25 Hz cadence | C-2, D-10, `IMU_STALE_TICKS`, the 17–19 ms inference | **gate** |
| M-3 | Gyro unit and bias | rotate the dog by a known angle on the stand, integrate `read_imu()` gyro z; compare °/s vs rad/s; bias at rest over 60 s | obs slot 0–2 | **gate** |
| M-4 | Joint sign and zero offset per joint vs the sim. Done: the id → joint map (`map_20261108-001412`). Open: sign and zero offset (every foot-direction prompt was skipped) | changed 2026-11-09 (Brian, §1): photo the boot pose, then each joint held at +10° with its foot direction answered (probe `map` with a hold); the readback logged at each photo is the firmware angle; compare against sim renders at the matching angles. **Never command all joints to 0°.** Not built yet: the hold, and the sim render | action mapping, obs slots 11–22, whether `default_joint_pos` survives (if not: retrain everything) | **gate, first** |
| M-5 | Real gyro and accel ranges during walking | first tethered steps, `state` log | `GYRO_MAX_DPS`, accel band | before unsupervised |
| M-6 | Command-to-motion and stop latency, external reference | high-speed video of the dog against floor marks for step velocity commands; compare against the 40 ms model | `KP_YAW`, `KP_RANGE`, §5.2 budget | before FOLLOW |
| M-7 | `K_TURN` (achieved / commanded yaw rate) | video of in-place turns at 0.2/0.4/0.8 rad/s | dead reckoning | before FOLLOW |
| M-8 | `adopt` and `release` handoffs. Logged so far: `adopt` from the boot pose only (final change ≤ 0.8°). Boot pose and post-`stop()` pose differ (calves 7–8°, thighs 4–5°), and that `stop()` followed a `reset()` | stand, **with no `reset()` that boot**: (a) where `stop()` leaves the legs after joint mode, vs the boot pose; (b) `adopt` from that stance; (c) `release` with the joints pre-positioned there: max joint jump, ramp smoothness, readback before/after | D-4, C-5, `ACTION`, `REST` | **gate** |
| M-9 | Lidar UART port, scan rate, points per scan, lidar-to-nose offset | trace the cable; `ms200_reader --dump`; tape measure | §3.3 reflex | Phase 2 |
| M-10 | xgolib `action()` ids, each group's duration and whether it ends standing | read `xgolib_dog.py` on the Pi; time each allow-listed group on the stand | C-6 allow-list | before personality |
| M-11 | Whether the board can run above 115200 baud at all | xgolib has no call that changes the firmware's baud (`__change_baud` only reopens the host side), so opening the port at 2 Mbaud tests nothing unless the board is already there. Ask Yahboom, or look for a firmware-side switch | C-2 headroom | optional |
| M-12 | Owner verify accuracy | held-out photo set: owner vs others, same room, same lighting; accuracy and latency per model | D-12, D-13 | before FOLLOW |
| M-13 | Does the dog's speaker play from the Pi, and how late? **Retargeted 2026-11-08** to the USB sound card Brian picked (D-17), which is not on the dog yet. Card 2 is closed for the design: live `aplay -l` lists it (`sndrpihifiberry`, PCM5102A), eight plays were silent (30 % and 60 % before the voice board was cabled, 60 % four times with it cabled; Brian: "Silence..."), and it traces to V1. Live `arecord -l`: no capture device. First open at boot failed once with "Device or resource busy" | with the card on the Pi: `aplay -l`, `aplay -L` and `arecord -l` for its name; one 24 kHz clip played by card name, with Brian's verdict; one short recording from its mic played back (kept out of the repo); then device latency and the `speech_started` round trip | `AUDIO_DEVICE`, voice on the Pi, D-20 | before voice on dog |
| M-14 | Voice board wiring and whether raw audio is exposed. Measured 2026-11-08 (voice session, Brian): board YB-MVE02-V2.0; its "USB connect" port is CH340 serial only, no capture device; wake word → `$B000#` at 115200. From Yahboom's documents for the V1.0 board (the voice session's report; not measured here): it matches their CSK4002 module, `$B000#` is the wake event, and the Program port is for firmware updates | still open: the chip marking; the Program port without BOOT held; where the 4-pin cable goes; the exact wake reply and how long it lasts; whether `$B000#` still fires with the board's speaker unplugged | D-7, C-18, D-20 | Phase 2 |
| M-15 | Pi-side detector rate (for a later move) | `yolo benchmark` NCNN export on the Pi 5 | D-2 revisit | optional |
| M-16 | Sustained-load battery runtime | one full session with `battery_pct` logged, policy standing and walking | session planning | before demos |
| M-17 | Wi-Fi one-way `velocity` latency | `noop` → `last_cmd_seq` round trip on the PC clock, halved | §5.2 budget | before FOLLOW |
| M-18 | YOLO + tracker time on the 3090 | PC-side timing log | §5.2 budget | before FOLLOW |
| M-19 | Camera stall recovery time | power-cycle the dog with the Pi up; time to `camera_ok` | failure-modes §6 | before FOLLOW |
| M-20 | ~~`mdp.phase` standing gate~~ resolved from source 2026-11-08: both phase values are 0 when the command norm < 0.1; otherwise sin/cos of the episode-step clock over a 0.4 s period | — | obs slots 9–10 | done |
| M-21 | `audio_ctl stop` → silence on the Pi player | play a 3 s clip, send `stop`, record the speaker; time to silence | C-17, a fall cutting a line | before voice on dog |
| M-22 | No stale speech after a link drop | drop Wi-Fi mid-line and between lines; nothing old may play on reconnect (`IMMEDIATE=1` and the bounded high-water mark are ZMQ's documented behaviour, untested here) | C-17 | before voice on dog |
| M-23 | The voice board's other `$Bxxx#` codes | Yahboom's phrase table; say only non-motion phrases, with no Yahboom program running (their samples drive the dog from speech) | `keyword` meanings, D-21 | Phase 2 |
| M-24 | `unload_allmotor()` and `load_allmotor()`. Logged: one leg only, per-leg calls; after reload two joints returned to their pre-unload angles and the third was still moving at the end of the window | stand: unload all, reload all, log every joint until it settles; then `adopt` | `REST`, the unload after a fall (C-7, C-8) | before `REST` or fall-unload is enabled |
| M-25 | Projected-gravity axes and signs | stand: tilt the dog by hand about each axis; compare gravity built from roll/pitch with the sim's convention | obs slots 3–5 | **gate** |
| M-26 | Servo response underneath the ~105 ms readback refresh | high-speed video of one leg against a protractor for a step command (Phase 1 results, "Open") | the 40 ms command-delay model, which is inferred | before trusting sim-to-real numbers |
| M-27 | Sim placeholders still carried from the Mini2S: stance and default pose, servo kp / torque limit / delay, masses | system ID (Phase 2A week 2): scale, ruler, Phase 1 logs replayed in sim | every policy's training conditions | Phase 2A week 2 |
| M-28 | Walk → zero-velocity stop | sim first: step the command from each scoreboard row to zero; falls, settle time, drift. Then on the stand, then tethered | D-5, the TTL and deadman behaviour, `release` | **gate** |
| M-29 | The audio path the S2 is meant to have. No longer blocks a purchase (D-17 is answered). Yahboom's LLM course records and plays on the Pi; this OS install has neither, and its one sound card is a V1 leftover | read Yahboom's image (sound overlay, default device, their `audio.py`) without running it; the expansion board's pinout for GPIO 18, 19, 21; the voice board's "Program" micro-USB port (with M-14); whether `dtoverlay=hifiberry-dac` and the Robot HAT `asound.conf` should come off this Pi (a config change: Brian's call; until then the default route goes to the dead card) | cleaning V1's audio leftovers off the Pi | optional |
| M-30 | USB current with the sound card at speech volume, camera running. Raspberry Pi documents a 600 mA or 1.6 A USB budget depending on the supply; which one this dog gets is unmeasured | inline USB meter on the card: idle, then speech at the planned gain, one speaker and two; `vcgencmd get_config usb_max_current_enable` and `vcgencmd get_throttled` before and after | failure-modes §10 (a brownout is a Pi hang), the speaker gain, one speaker or two | before the dog walks with voice on it |
| M-31 | Mass and mounting point of the sound card and its speakers | kitchen scale; ruler from the body origin | the MJCF mass (with M-27) and Brian's randomization ranges | with M-27 |
| M-32 | Does a wake-word model on the Pi disturb the 50 Hz loop? | M-2's probe with and without the model running on the card's mic: p50/p99 tick time and overruns (the voice report's check 8; Brian runs any motion in it) | C-18 (chip or software as the `keyword` source), D-20 | before a software wake word runs on the Pi |
| M-33 | How long the dog's mic hears its own speaker after a line ends | card and speakers mounted where they will sit: play a cached line with the mute off, record the mic, find when the level is back at the room's noise floor; repeat at the planned gain (the voice's checklist step 7) | `MIC_GATE_TAIL_CHUNKS`, `MIC_GATE_TAIL_S` | before listening on the dog |
