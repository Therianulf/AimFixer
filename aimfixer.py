#!/usr/bin/env python3
"""AimFixer - Mouse overshoot detection and sensitivity advisor for FPS games."""

import sys
from collector import MouseCollector
from detector import OvershootDetector
from analyzer import analyze
from visualizer import print_summary, show_charts


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
    dpi, sens = get_user_settings()

    print()
    print(f"  Settings: {dpi} DPI / {sens} in-game sensitivity")
    print()
    print("  Press F6 to START recording.")
    print("  Press F6 again to STOP and see results.")
    print()

    # macOS accessibility check hint
    if sys.platform == "darwin":
        print("  (macOS: If nothing happens, grant Accessibility")
        print("   access to your terminal app in System Settings")
        print("   > Privacy & Security > Accessibility)")
        print()

    collector = MouseCollector()
    collector.start()
    collector.wait_for_start()
    collector.wait_for_stop()
    collector.stop()

    samples = collector.get_samples()
    if len(samples) < 100:
        print("\n  Not enough data collected. Try a longer session")
        print("  with more mouse movement.")
        return

    session_duration = samples[-1].timestamp - samples[0].timestamp

    detector = OvershootDetector(samples)
    events = detector.detect()
    flick_counts = detector.get_flick_counts()

    result = analyze(
        events=events,
        flick_counts=flick_counts,
        session_duration=session_duration,
        total_samples=len(samples),
        current_dpi=dpi,
        current_sens=sens,
    )

    print_summary(result)
    show_charts(result, events)


if __name__ == "__main__":
    main()
