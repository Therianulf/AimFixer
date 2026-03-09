#!/usr/bin/env python3
"""AimFixer - Mouse overshoot detection and sensitivity advisor for FPS games."""

import sys
import threading

from collector import MouseCollector
from detector import OvershootDetector
from analyzer import analyze
from visualizer import print_summary, show_charts
from overlay import OverlayController, OverlayState


def get_user_settings() -> tuple[int, float, float]:
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

    while True:
        v_input = input("  Vertical sensitivity (Enter = same): ").strip()
        if not v_input:
            v_sens = sens
            break
        try:
            v_sens = float(v_input)
            if v_sens <= 0:
                print("  Sensitivity must be positive.")
                continue
            break
        except ValueError:
            print("  Please enter a valid number.")

    return dpi, sens, v_sens


def main():
    # Subcommand: history comparison
    if len(sys.argv) >= 2 and sys.argv[1] == "history":
        from compare import run_history_comparison
        run_history_comparison()
        return

    # Accept optional CLI args: aimfixer.py <dpi> <sensitivity> [v_sensitivity]
    if len(sys.argv) in (3, 4):
        try:
            dpi = int(sys.argv[1])
            sens = float(sys.argv[2])
            v_sens = float(sys.argv[3]) if len(sys.argv) == 4 else sens
            if dpi < 50 or dpi > 25600:
                print("  DPI must be between 50 and 25600.")
                return
            if sens <= 0 or v_sens <= 0:
                print("  Sensitivity must be positive.")
                return
        except ValueError:
            print("  Usage: aimfixer.py <dpi> <sensitivity> [v_sensitivity]")
            return
    else:
        dpi, sens, v_sens = get_user_settings()

    from config import GAME_DISPLAY_NAMES, GAME_LIST, format_sens
    print()
    if v_sens != sens:
        print(f"  Settings: {dpi} DPI / H:{format_sens(sens, GAME_LIST[0])} V:{format_sens(v_sens, GAME_LIST[0])} in-game sensitivity")
    else:
        print(f"  Settings: {dpi} DPI / {format_sens(sens, GAME_LIST[0])} in-game sensitivity")
    print(f"  Game: {GAME_DISPLAY_NAMES[GAME_LIST[0]]}")
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

    def on_game_change(display_name: str):
        overlay.set_game(display_name)

    collector = MouseCollector(
        on_state_change=on_state_change,
        on_movement_key=on_movement_key,
        on_game_change=on_game_change,
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

        click_times = collector.get_click_times()

        detector = OvershootDetector(samples, click_times)
        detector.detect()
        click_aim_events = detector.get_click_aim_events()
        rowing_events = detector.get_rowing_events()

        # Load previous session BEFORE analyze so trend data is available
        from history import save_session, load_previous_session
        previous_session = load_previous_session(before_current_save=True)

        current_game = collector.get_current_game()

        result = analyze(
            click_aim_events=click_aim_events,
            total_clicks=len(click_times),
            session_duration=session_duration,
            total_samples=len(samples),
            current_dpi=dpi,
            current_sens=sens,
            rowing_events=rowing_events,
            movement_sample_count=movement_sample_count,
            click_times=click_times,
            previous_session=previous_session,
            current_game=current_game,
            current_v_sens=v_sens,
        )

        # Save current session AFTER analyze
        save_session(result, click_aim_events, rowing_events, click_times, game=current_game)

        print_summary(result, previous_session=previous_session)

        # Stash chart data and stop overlay; main thread will show charts after
        pending["result"] = result
        pending["click_aim_events"] = click_aim_events
        pending["rowing_events"] = rowing_events
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
            pending["result"],
            pending.get("click_aim_events", []),
            pending.get("rowing_events", []),
        )


if __name__ == "__main__":
    main()
