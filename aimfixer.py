#!/usr/bin/env python3
"""AimFixer - Mouse overshoot detection and sensitivity advisor for FPS games."""

import sys
import threading

from collector import MouseCollector
from detector import OvershootDetector
from analyzer import analyze
from visualizer import print_summary, show_charts
from overlay import OverlayController, OverlayState


def get_user_settings() -> tuple[int, float]:
    print()
    print("=" * 50)
    print("  AimFixer - Sensitivity Advisor")
    print("=" * 50)
    print()

    while True:
        try:
            dpi = int(input("  Enter your current mouse DPI (e.g. 800): "))
            if dpi < 50 or dpi > 25600:
                print("  Please enter a DPI between 50 and 25600.")
                continue
            break
        except ValueError:
            print("  Please enter a valid number.")

    while True:
        try:
            sens = float(input("  Enter your in-game sensitivity (e.g. 5.0): "))
            if sens <= 0:
                print("  Sensitivity must be positive.")
                continue
            break
        except ValueError:
            print("  Please enter a valid number.")

    return dpi, sens


def main():
    # Accept optional CLI args: aimfixer.py <dpi> <sensitivity>
    if len(sys.argv) == 3:
        try:
            dpi = int(sys.argv[1])
            sens = float(sys.argv[2])
            if dpi < 50 or dpi > 25600:
                print("  DPI must be between 50 and 25600.")
                return
            if sens <= 0:
                print("  Sensitivity must be positive.")
                return
        except ValueError:
            print("  Usage: aimfixer.py <dpi> <sensitivity>")
            return
    else:
        dpi, sens = get_user_settings()

    print()
    print(f"  Settings: {dpi} DPI / {sens} in-game sensitivity")
    print()

    # macOS accessibility check hint (shown once in terminal before overlay starts)
    if sys.platform == "darwin":
        print("  (macOS: If nothing happens, grant Accessibility")
        print("   access to your terminal app in System Settings")
        print("   > Privacy & Security > Accessibility)")
        print()

    # Create the overlay
    overlay = OverlayController.alloc().init()

    # State change callback for the collector (called from pynput thread)
    def on_state_change(state: str):
        if state == "recording":
            overlay.set_state(OverlayState.RECORDING)
        elif state == "stopped":
            overlay.set_state(OverlayState.ANALYZING)

    def on_movement_key():
        overlay.flash_warning("Don't move! Stand still while recording")

    collector = MouseCollector(
        on_state_change=on_state_change,
        on_movement_key=on_movement_key,
    )

    # Store pending chart data for after the overlay exits
    pending = {}

    def worker():
        """Background thread: waits for recording, runs analysis, stops overlay."""
        collector.wait_for_start()
        collector.wait_for_stop()
        collector.stop()

        samples = collector.get_samples()
        if len(samples) < 100:
            print("\n  Not enough data collected. Try a longer session")
            print("  with more mouse movement.")
            overlay.schedule(overlay.stop)
            return

        session_duration = samples[-1].timestamp - samples[0].timestamp

        movement_sample_count = sum(1 for s in samples if s.during_movement)

        detector = OvershootDetector(samples)
        events = detector.detect()
        flick_counts = detector.get_flick_counts()
        rowing_events = detector.get_rowing_events()
        swirl_events = detector.get_swirl_events()

        result = analyze(
            events=events,
            flick_counts=flick_counts,
            session_duration=session_duration,
            total_samples=len(samples),
            current_dpi=dpi,
            current_sens=sens,
            rowing_events=rowing_events,
            swirl_events=swirl_events,
            movement_sample_count=movement_sample_count,
        )

        print_summary(result)

        # Stash chart data and stop overlay; main thread will show charts after
        pending["result"] = result
        pending["events"] = events
        pending["rowing_events"] = rowing_events
        pending["swirl_events"] = swirl_events
        overlay.schedule(overlay.stop)

    # Start collector listeners + background worker thread
    collector.start()
    overlay.set_state(OverlayState.WAITING)

    threading.Thread(target=worker, daemon=True).start()

    # Main thread runs the overlay event loop (blocks until overlay.stop())
    overlay.run()

    # After overlay exits, show matplotlib charts on the main thread
    if "result" in pending:
        show_charts(
            pending["result"], pending["events"],
            pending.get("rowing_events", []),
            pending.get("swirl_events", []),
        )


if __name__ == "__main__":
    main()
