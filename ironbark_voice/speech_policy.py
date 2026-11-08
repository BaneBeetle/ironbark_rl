"""Should the dog say it now? Pacing (P1-P4 in docs/voice/decisions.md): Brian's design, Claude's code.

Runs on the PC, so it measures seconds with a clock; nothing here goes to the Pi.
"""

from dataclasses import dataclass

from ironbark_voice import config
from ironbark_voice.state import RobotState
from ironbark_voice.triggers import Event, still_true


@dataclass(frozen=True)
class Decision:
    speak: bool
    interrupt: bool  # cut off the line that's playing first
    reason: str  # human-readable, printed and logged so drops can be audited


class SpeechPolicy:
    def __init__(self):
        # Both gaps count from when the previous line FINISHED (Brian confirmed, 2026-11-07).
        self.last_line_end_s: float | None = None  # any line, cached or Haiku
        self.last_haiku_end_s: float | None = None  # Haiku lines only

    def decide(self, event: Event, source: str, now_s: float, busy: bool) -> Decision:
        """source is "cache" or "haiku"; busy means a line is being prepared or played.

        Examples (last line ended at 9.1 s, nothing playing):
          decide(target_lost, "cache", now_s=12.4) -> Decision(False, False, "cooldown: 3.3 s of 4.0 s")
          decide(fell, "cache", now_s=12.4)        -> Decision(True, False, "urgent: skips the cooldown")
        """
        if event.urgent:
            # P2 + Brian's pacing: urgent events skip the cooldown and cut off a playing line.
            # (P2 named the fall; battery_low interrupts too, else a warning that fires mid-line
            # would be dropped by P3 and not repeat until the battery is back above 30 %.)
            return Decision(True, busy, "urgent: cuts off the current line" if busy else "urgent: skips the cooldown")
        if busy:
            return Decision(False, False, "busy: already talking (dropped, P3)")
        if self.last_line_end_s is not None:
            quiet = now_s - self.last_line_end_s
            if quiet < config.CACHED_LINE_COOLDOWN_S:  # the 4 s quiet follows every line
                return Decision(False, False, f"cooldown: {quiet:.1f} s of {config.CACHED_LINE_COOLDOWN_S:.1f} s (dropped, P3)")
        if source == "haiku" and self.last_haiku_end_s is not None:
            since = now_s - self.last_haiku_end_s
            if since < config.HAIKU_LINE_MIN_SPACING_S:  # at most one Haiku line per 30 s
                return Decision(False, False, f"haiku spacing: {since:.1f} s of {config.HAIKU_LINE_MIN_SPACING_S:.0f} s (dropped, P3)")
        return Decision(True, False, "ok")

    def stale_reason(self, event: Event, state: RobotState, now_s: float) -> str | None:
        """P4: a line is stale if its event is no longer true, or it's older than the latency target.

        Checked once, when the line is ready to play. Returns why it's stale, or None if it's fresh.
        Example: target_lost detected at 10.0 s, Haiku text ready at 11.7 s -> "too old: 1.70 s > 1.5 s"
        """
        age = now_s - event.time_s
        if age > config.LATENCY_TARGET_P50_S:
            return f"too old: {age:.2f} s > {config.LATENCY_TARGET_P50_S} s"
        if not still_true(event, state):
            return "event no longer true"
        return None

    def line_finished(self, source: str, now_s: float) -> None:
        """Call when a line stops playing, whether it finished or was cut off: the gaps start here."""
        self.last_line_end_s = now_s
        if source == "haiku":
            self.last_haiku_end_s = now_s
