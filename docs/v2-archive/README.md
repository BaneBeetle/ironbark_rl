# IronBark V2 archive

Knowledge from IronBark V2 (Mac brain + Raspberry Pi 5 on a Yahboom
DOGZILLA S2, Aug–Oct 2026), archived for V3. **This is reference
material, not code to port.** Nothing here is imported, run or deployed.

Start with the two synthesised files:

- [`MEASURED_FACTS.md`](MEASURED_FACTS.md): every measured constant and
  protocol fact, each with its source. It also lists the constants that
  were **never measured**, so they don't get mistaken for facts.
- [`LESSONS.md`](LESSONS.md): what made V2 finicky, with causes, and what
  V3 should do differently.

## Contents

| Path | What it is | Source in the V2 repo |
|---|---|---|
| `migration-notes.md` | Dated log of measured facts (smoke test, bench passes, camera, clocks, MS200) | `docs/migration-notes.md` |
| `phase1-briefing.md` | Oracle briefing: S2 command model, sensor-rig decision, target-lock design (§5) | `docs/phase1-briefing.md` |
| `bringup-report.md` | FOLLOW bring-up W1–W5 report: measured numbers, deviations, open items | `docs/bringup-report.md` |
| `handoffs/coding-handoff-follow-bringup.md` | The W1–W5 spec handed to the implementation session | `docs/coding-handoff-follow-bringup.md` |
| `measurements/smoke_*.jsonl` | Raw hardware smoke-test traces (Q1–Q8) | `docs/measurements/` |
| `measurements/ladder_20260904_204929.json` | Static perception calibration on the dog's camera, 1–4 m | `docs/measurements/` |
| `measurements/*.txt` | Mac-only verification logs: FOLLOW dry run, MS200 parser, deadman | `docs/measurements/` |
| `reference/motor_controller.py` | V2 Pi controller: wire protocol, IMU-ready latch, watchdog | `pi/motor_controller.py` |
| `reference/config.py` | Where motor_controller's `V2_*` constants actually live | `config.py` |
| `findings/2026-08-30-first-autonomous-follow.md` | First autonomous FOLLOW run: setup, what worked, what didn't | written for this archive |
| `findings/turn-overcorrection.md` | Turn overshoot diagnosis, the frozen-yaw connection, V2's unapplied tuning ladder | written for this archive |
| `findings/usb-camera-stall.md` | Camera stalls after a dog power cycle; the USB rebind fix | written for this archive |
| `findings/2026-09-30-pi-hang.md` | Pi dropped off the network mid-session; cause unknown; the watchdog gap | written for this archive |

Everything outside `findings/` comes from branch
`claude/ironbark-v2-oracle-handoff-e29f1a` at `7f44ec8`, the newest V2
commit (2026-09-04).

## Read before trusting

- **The two `reference/` files are for reading only.** `motor_controller.py`
  imports `config` and `xgolib` and expects the V2 directory layout. Its
  measured constants are in `config.py`, not in the controller itself.
- **Links inside the copied docs point at V2 paths.** `docs/measurements/…`
  in the V2 repo is `measurements/…` here.
- **Scrubbed for this public repo.** LAN addresses became `<MAC_LAN_IP>`
  and `<PI_LAN_IP>`; Tailscale addresses became `<MAC_TAILSCALE_IP>` and
  `<PI_TAILSCALE_IP>`. No `.env`, API key or token was ever in these
  files; `ANTHROPIC_API_KEY` appears only as a variable name. Everything else is verbatim, so the scrubbed files no longer match
  the V2 blobs byte-for-byte.
- **`findings/` was written after the fact from session notes, not from
  traces.** None of those sessions committed a log, so their numbers are
  observations and estimates, and each file says which.
- **Some V2 claims were later corrected.** In particular V2's "343 Hz
  read_yaw" and "−0.009 °/s drift" — see `MEASURED_FACTS.md` § IMU.
