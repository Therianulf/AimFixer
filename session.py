"""SessionRunner — encapsulates the collect -> detect -> analyze -> save pipeline."""
from __future__ import annotations

from collector import MouseCollector
from detector import OvershootDetector
from analyzer import analyze
from visualizer import print_summary


class SessionRunner:
    """Runs one recording session: collect -> detect -> analyze -> save."""

    def __init__(
        self,
        dpi: int,
        h_sens: float,
        v_sens: float,
        collector: MouseCollector,
        on_complete=None,
        on_error=None,
    ):
        self.dpi = dpi
        self.h_sens = h_sens
        self.v_sens = v_sens
        self._collector = collector
        self._on_complete = on_complete
        self._on_error = on_error

    def run(self):
        """Blocking call. Run on a background thread."""
        self._collector.wait_for_start()
        self._collector.wait_for_stop()

        samples = self._collector.get_samples()
        if len(samples) < 100:
            if self._on_error:
                self._on_error("Not enough data. Try a longer session.")
            return

        session_duration = samples[-1].timestamp - samples[0].timestamp
        movement_sample_count = sum(1 for s in samples if s.during_movement)
        click_times = self._collector.get_click_times()

        detector = OvershootDetector(samples, click_times)
        detector.detect()
        click_aim_events = detector.get_click_aim_events()
        rowing_events = detector.get_rowing_events()

        from history import save_session, load_previous_session
        previous_session = load_previous_session(before_current_save=True)

        current_game = self._collector.get_current_game()

        result = analyze(
            click_aim_events=click_aim_events,
            total_clicks=len(click_times),
            session_duration=session_duration,
            total_samples=len(samples),
            current_dpi=self.dpi,
            current_sens=self.h_sens,
            rowing_events=rowing_events,
            movement_sample_count=movement_sample_count,
            click_times=click_times,
            previous_session=previous_session,
            current_game=current_game,
            current_v_sens=self.v_sens,
        )

        save_session(result, click_aim_events, rowing_events, click_times,
                     game=current_game)
        print_summary(result, previous_session=previous_session)

        if self._on_complete:
            self._on_complete(result, click_aim_events, rowing_events)
