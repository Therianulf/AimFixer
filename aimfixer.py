#!/usr/bin/env python3
"""AimFixer - Mouse overshoot detection and sensitivity advisor for FPS games."""

import sys


def main():
    # Subcommand: history comparison
    if len(sys.argv) >= 2 and sys.argv[1] == "history":
        from compare import run_history_comparison
        run_history_comparison()
        return

    from app import AppController

    # Optional CLI args for power users: aimfixer.py <dpi> <sensitivity> [v_sensitivity]
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
            controller = AppController(dpi, sens, v_sens)
        except ValueError:
            print("  Usage: aimfixer.py [dpi sensitivity [v_sensitivity]]")
            return
    else:
        # No args — GUI startup dialog will prompt for settings
        controller = AppController()

    controller.run()


if __name__ == "__main__":
    main()
