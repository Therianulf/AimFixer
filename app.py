"""AppController — manages multi-session lifecycle with overlay + collector."""
from __future__ import annotations

import sys
import threading

from collector import MouseCollector
from dialogs import show_startup_dialog, show_settings_change_dialog
from models import OverlayState
from session import SessionRunner
from visualizer import show_charts

if sys.platform == "darwin":
    from overlay import OverlayController
else:
    from overlay_win import OverlayController


class AppController:
    """Manages the overlay, collector, and session loop."""

    def __init__(self, dpi: int = 0, h_sens: float = 0.0, v_sens: float = 0.0):
        self.dpi = dpi
        self.h_sens = h_sens
        self.v_sens = v_sens
        self._overlay: OverlayController | None = None
        self._collector: MouseCollector | None = None
        self._pending_charts: list[tuple] = []
        self._session_count = 0

    def run(self):
        """Main entry point. Blocks until quit."""
        # If no settings provided, show GUI startup dialog
        if self.dpi == 0 or self.h_sens == 0.0:
            result = show_startup_dialog()
            if result is None:
                return  # User cancelled
            self.dpi, self.h_sens, self.v_sens = result

        if sys.platform == "darwin":
            self._overlay = OverlayController.alloc().init()
        else:
            self._overlay = OverlayController()
        self._overlay.set_settings(self.dpi, self.h_sens, self.v_sens)

        self._collector = MouseCollector(
            on_state_change=self._on_state_change,
            on_movement_key=self._on_movement_key,
            on_game_change=self._on_game_change,
            on_quit=self._on_quit,
            on_settings=self._on_settings,
        )
        self._collector.start_listeners()
        self._start_session()

        # Main thread runs overlay event loop (blocks until quit)
        self._overlay.run()

        # Cleanup
        self._collector.stop_listeners()

        # Show final charts after overlay exits (on main thread)
        if self._pending_charts:
            result, events, rowing = self._pending_charts[-1]
            show_charts(result, events, rowing)

    def _start_session(self):
        """Prepare and launch a new session on a background thread."""
        self._collector.reset()
        self._overlay.set_state(OverlayState.WAITING)
        self._session_count += 1

        runner = SessionRunner(
            dpi=self.dpi,
            h_sens=self.h_sens,
            v_sens=self.v_sens,
            collector=self._collector,
            on_complete=self._on_session_complete,
            on_error=self._on_session_error,
        )
        threading.Thread(target=runner.run, daemon=True).start()

    def _on_session_complete(self, result, click_aim_events, rowing_events):
        """Called from worker thread when analysis finishes."""
        self._pending_charts.append((result, click_aim_events, rowing_events))
        self._overlay.set_state(OverlayState.DONE)
        # Auto-start next session listener (user presses F5 to record again)
        self._start_session()

    def _on_session_error(self, msg):
        """Called from worker thread on error."""
        print(f"\n  {msg}")
        self._overlay.set_state(OverlayState.DONE)
        # Allow retry
        self._start_session()

    def _on_state_change(self, state: str):
        if state == "recording":
            self._overlay.set_state(OverlayState.RECORDING)
        elif state == "stopped":
            self._overlay.set_state(OverlayState.ANALYZING)

    def _on_movement_key(self):
        self._overlay.flash_warning("Don't move! Stand still while recording")

    def _on_game_change(self, display_name: str):
        self._overlay.set_game(display_name)

    def _on_settings(self):
        """Called when user presses settings hotkey (F9)."""
        def _show():
            result = show_settings_change_dialog(
                self.dpi, self.h_sens, self.v_sens,
            )
            if result is not None:
                self._apply_settings(*result)
        self._overlay.schedule(_show)

    def _apply_settings(self, new_dpi, new_h_sens, new_v_sens):
        """Called on main thread when user applies new settings."""
        self.dpi = new_dpi
        self.h_sens = new_h_sens
        self.v_sens = new_v_sens
        self._overlay.set_settings(new_dpi, new_h_sens, new_v_sens)
        print(f"\n  Settings updated: {new_dpi} DPI / ", end="")
        if new_v_sens != new_h_sens:
            print(f"H:{new_h_sens} V:{new_v_sens} sens")
        else:
            print(f"{new_h_sens} sens")

    def _on_quit(self):
        """Called when user presses quit hotkey (F8)."""
        self._overlay.schedule(self._overlay.stop)
