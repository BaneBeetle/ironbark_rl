# USB camera stalls after a dog power cycle

Found during the 2026-09-04 ladder session. The fix is a manual USB
rebind. V2 never automated it.

## Symptom

After the dog was power-cycled, the camera stopped delivering frames.
`/dev/video0` still existed and still opened, but reads failed with V4L2
`select()` timeouts. No frames reached the Mac.

## The device

| | |
|---|---|
| Camera | USB 2 MP wide-angle, USB ID **`05a3:9230`** (ARC International) |
| sysfs USB path at the time | **`3-1`** |
| Driver | `uvcvideo`, `/dev/video0` |

## Fix (manual, worked)

Unbind and rebind the device from the USB core. That re-enumerates it
without anyone touching the dog:

```bash
echo 3-1 | sudo tee /sys/bus/usb/drivers/usb/unbind
```

```bash
echo 3-1 | sudo tee /sys/bus/usb/drivers/usb/bind
```

`3-1` is the port the camera sat on at the time. It's a physical-port
path, not a property of the camera, so look it up before using it:

```bash
basename "$(readlink -f /sys/class/video4linux/video0/device/..)"
```

Cross-check against `lsusb -t` or `lsusb -d 05a3:9230`. The Pi user has
passwordless sudo, which is what makes this scriptable.

## Why V2's cam_sender wouldn't have recovered on its own

`../reference/` doesn't include `cam_sender.py`. From the V2 source
(`pi/cam_sender.py`, unchanged since commit `c8e55cb`):

- `stream()` gives up after **`READ_FAIL_LIMIT = 30` consecutive failed
  reads**, then the outer loop releases the capture and reopens it after
  a backoff of 1 → 15 s.
- Each failed `cap.read()` on a stalled V4L2 device blocks for OpenCV's
  `select()` timeout. That's **10 s by default**
  (`OPENCV_VIDEOIO_V4L_SELECT_TIMEOUT`, per the OpenCV 4.10 environment
  reference; the Pi runs OpenCV 4.10.0 from apt). So 30 failures take
  about **5 minutes** before the first reopen. Measure this on the Pi —
  the default wasn't confirmed there.
- **Reopening doesn't reset the device.** The stall survives
  `cap.release()` and a new `VideoCapture`. Only the rebind clears it,
  so the reopen loop would cycle forever.

## Hardening V2 identified but never wrote

1. **Fail fast.** Lower the read timeout (for example
   `OPENCV_VIDEOIO_V4L_SELECT_TIMEOUT=1`) and/or the consecutive-failure
   limit, so a stall is caught in seconds, not minutes. At 20 fps a
   healthy read takes ~19 ms (`../migration-notes.md`), so a 1 s timeout
   still leaves wide margin. Keep the limit a count, per the no-wall-clock
   rule on the Pi.
2. **Escalate to a USB reset.** After N failed reopens, unbind/rebind the
   camera's USB path (looked up at runtime, as above), then reopen.
3. **Report it.** Log every escalation and send camera health over
   telemetry, so the operator sees "camera recovering" instead of a frozen
   image.

## Open questions

- **Root cause is unknown.** Candidates are the camera's power-on sequencing
  when the S2 board powers up, USB enumeration racing the boot, or the
  hub. Whether a full Pi reboot (rather than a dog power cycle) also clears
  it was not recorded.
- **How often it happens is unknown.** It was seen after a power cycle; it
  wasn't counted across power cycles.
