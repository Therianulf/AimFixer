"""Cross-platform GUI dialogs for AimFixer.

macOS: NSAlert (AppKit) — compatible with the AppKit overlay run loop.
Windows/Linux: tkinter — no AppKit dependency needed.
"""
from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API — delegates to platform-specific implementation
# ---------------------------------------------------------------------------

def show_startup_dialog(
    default_dpi: int = 800,
    default_sens: float = 5.0,
    default_v_sens: float = 0.0,
) -> tuple[int, float, float] | None:
    """Show a GUI dialog to collect DPI and sensitivity settings.

    Returns (dpi, h_sens, v_sens) or None if cancelled.
    """
    log.debug("show_startup_dialog called (platform=%s)", sys.platform)
    if sys.platform == "darwin":
        result = _mac_startup_dialog(default_dpi, default_sens, default_v_sens)
    else:
        result = _tk_startup_dialog(default_dpi, default_sens, default_v_sens)
    log.debug("show_startup_dialog returning: %s", result)
    return result


def show_settings_change_dialog(
    current_dpi: int,
    current_h_sens: float,
    current_v_sens: float,
) -> tuple[int, float, float] | None:
    """Show a dialog to change DPI and sensitivity mid-session.

    Returns (dpi, h_sens, v_sens) or None if cancelled.
    """
    log.debug("show_settings_change_dialog called (platform=%s)", sys.platform)
    if sys.platform == "darwin":
        result = _mac_settings_dialog(current_dpi, current_h_sens, current_v_sens)
    else:
        result = _tk_settings_dialog(current_dpi, current_h_sens, current_v_sens)
    log.debug("show_settings_change_dialog returning: %s", result)
    return result


# ---------------------------------------------------------------------------
# macOS implementation (NSAlert) — shares AppKit with the overlay
# ---------------------------------------------------------------------------

def _mac_startup_dialog(default_dpi, default_sens, default_v_sens):
    from AppKit import (
        NSAlert, NSApplication, NSMakeRect, NSFont,
        NSStackView, NSTextField,
        NSUserInterfaceLayoutOrientationVertical,
    )

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # Accessory — no dock icon

    alert = NSAlert.alloc().init()
    alert.setMessageText_("\U0001f3af AimFixer Setup")
    alert.setInformativeText_(
        "Enter your mouse DPI and in-game sensitivity.\n"
        "Leave V Sensitivity blank if same as H."
    )
    alert.addButtonWithTitle_("Start")
    alert.addButtonWithTitle_("Quit")

    container = NSStackView.alloc().initWithFrame_(NSMakeRect(0, 0, 280, 100))
    container.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    container.setSpacing_(8.0)

    row_dpi, field_dpi = _mac_input_row("DPI:", default_dpi, 280)
    row_sens, field_sens = _mac_input_row("H Sensitivity:", default_sens, 280)
    v_default = "" if default_v_sens in (0.0, default_sens) else str(default_v_sens)
    row_v, field_v = _mac_input_row("V Sensitivity:", v_default, 280)

    container.addView_inGravity_(row_dpi, 1)
    container.addView_inGravity_(row_sens, 1)
    container.addView_inGravity_(row_v, 1)

    alert.setAccessoryView_(container)
    alert.window().setInitialFirstResponder_(field_dpi)

    log.debug("Running NSAlert startup dialog")
    response = alert.runModal()
    log.debug("NSAlert response: %s", response)
    if response != 1000:  # NSAlertFirstButtonReturn
        return None

    try:
        dpi = int(field_dpi.stringValue())
        h_sens = float(field_sens.stringValue())
        v_str = field_v.stringValue().strip()
        v_sens = float(v_str) if v_str else h_sens
        if dpi < 50 or dpi > 25600 or h_sens <= 0 or v_sens <= 0:
            return None
        return dpi, h_sens, v_sens
    except (ValueError, TypeError):
        return None


def _mac_settings_dialog(current_dpi, current_h_sens, current_v_sens):
    from AppKit import NSAlert, NSMakeRect, NSTextField

    alert = NSAlert.alloc().init()
    alert.setMessageText_("AimFixer Settings")
    alert.setInformativeText_(
        "Enter DPI, H Sensitivity, V Sensitivity\n"
        "(separated by spaces or commas)"
    )
    alert.addButtonWithTitle_("Apply")
    alert.addButtonWithTitle_("Cancel")

    input_field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 250, 24))
    if current_v_sens != current_h_sens:
        input_field.setStringValue_(f"{current_dpi} {current_h_sens} {current_v_sens}")
    else:
        input_field.setStringValue_(f"{current_dpi} {current_h_sens}")
    input_field.setEditable_(True)
    input_field.setSelectable_(True)
    alert.setAccessoryView_(input_field)
    alert.window().setInitialFirstResponder_(input_field)

    log.debug("Running NSAlert settings dialog")
    response = alert.runModal()
    log.debug("NSAlert response: %s", response)
    if response != 1000:
        return None

    raw = input_field.stringValue()
    parts = raw.replace(",", " ").split()
    try:
        new_dpi = int(parts[0])
        new_h_sens = float(parts[1])
        new_v_sens = float(parts[2]) if len(parts) >= 3 else new_h_sens
        if 50 <= new_dpi <= 25600 and new_h_sens > 0 and new_v_sens > 0:
            return new_dpi, new_h_sens, new_v_sens
    except (ValueError, IndexError):
        pass
    return None


def _mac_input_row(label_text, default_value, width=250):
    """Create a label + text field row for NSAlert dialogs."""
    from AppKit import NSFont, NSMakeRect, NSStackView, NSTextField

    row = NSStackView.alloc().initWithFrame_(NSMakeRect(0, 0, width, 28))
    row.setOrientation_(0)  # horizontal
    row.setSpacing_(8.0)

    label = NSTextField.labelWithString_(label_text)
    label.setFont_(NSFont.systemFontOfSize_(13.0))
    label.setFrame_(NSMakeRect(0, 0, 120, 22))

    field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, width - 128, 22))
    field.setStringValue_(str(default_value))
    field.setEditable_(True)
    field.setSelectable_(True)
    field.setFont_(NSFont.systemFontOfSize_(13.0))

    row.addView_inGravity_(label, 1)
    row.addView_inGravity_(field, 1)
    return row, field


# ---------------------------------------------------------------------------
# tkinter implementation (Windows / Linux)
# ---------------------------------------------------------------------------

def _tk_startup_dialog(default_dpi, default_sens, default_v_sens):
    import tkinter as tk
    from tkinter import ttk

    result = [None]

    root = tk.Tk()
    root.title("\U0001f3af AimFixer Setup")
    root.resizable(False, False)

    root.update_idletasks()
    w, h = 340, 230
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"{w}x{h}+{x}+{y}")

    style = ttk.Style()
    style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
    style.configure("Sub.TLabel", font=("Helvetica", 11))

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="\U0001f3af AimFixer", style="Title.TLabel").pack(pady=(0, 5))
    ttk.Label(frame, text="Enter your mouse settings to begin",
              style="Sub.TLabel").pack(pady=(0, 12))

    inputs_frame = ttk.Frame(frame)
    inputs_frame.pack(fill="x")

    ttk.Label(inputs_frame, text="DPI:").grid(row=0, column=0, sticky="w", pady=3)
    dpi_var = tk.StringVar(value=str(default_dpi))
    dpi_entry = ttk.Entry(inputs_frame, textvariable=dpi_var, width=18)
    dpi_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)

    ttk.Label(inputs_frame, text="H Sensitivity:").grid(row=1, column=0, sticky="w", pady=3)
    sens_var = tk.StringVar(value=str(default_sens))
    ttk.Entry(inputs_frame, textvariable=sens_var, width=18).grid(
        row=1, column=1, sticky="ew", padx=(8, 0), pady=3)

    v_default = "" if default_v_sens in (0.0, default_sens) else str(default_v_sens)
    ttk.Label(inputs_frame, text="V Sensitivity:").grid(row=2, column=0, sticky="w", pady=3)
    v_sens_var = tk.StringVar(value=v_default)
    ttk.Entry(inputs_frame, textvariable=v_sens_var, width=18).grid(
        row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

    ttk.Label(inputs_frame, text="(blank = same as H)",
              font=("Helvetica", 9)).grid(row=2, column=2, padx=(4, 0))

    inputs_frame.columnconfigure(1, weight=1)

    error_var = tk.StringVar()
    ttk.Label(frame, textvariable=error_var, foreground="red").pack(pady=(4, 0))

    def on_start():
        try:
            dpi = int(dpi_var.get())
            h_sens = float(sens_var.get())
            v_str = v_sens_var.get().strip()
            v_sens = float(v_str) if v_str else h_sens
            if dpi < 50 or dpi > 25600:
                error_var.set("DPI must be between 50 and 25600")
                return
            if h_sens <= 0 or v_sens <= 0:
                error_var.set("Sensitivity must be positive")
                return
            result[0] = (dpi, h_sens, v_sens)
            root.destroy()
        except ValueError:
            error_var.set("Please enter valid numbers")

    def on_quit():
        root.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=(8, 0))
    ttk.Button(btn_frame, text="Start", command=on_start).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Quit", command=on_quit).pack(side="left", padx=4)

    root.bind("<Return>", lambda e: on_start())
    root.bind("<Escape>", lambda e: on_quit())

    dpi_entry.focus_set()
    dpi_entry.select_range(0, "end")

    root.lift()
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))

    log.debug("Entering tkinter mainloop (startup)")
    root.mainloop()
    log.debug("tkinter mainloop exited, result=%s", result[0])
    return result[0]


def _tk_settings_dialog(current_dpi, current_h_sens, current_v_sens):
    import tkinter as tk
    from tkinter import ttk

    result = [None]

    root = tk.Tk()
    root.title("AimFixer Settings")
    root.resizable(False, False)

    root.update_idletasks()
    w, h = 320, 200
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"{w}x{h}+{x}+{y}")

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Change Settings", font=("Helvetica", 14, "bold")).pack(pady=(0, 10))

    inputs_frame = ttk.Frame(frame)
    inputs_frame.pack(fill="x")

    ttk.Label(inputs_frame, text="DPI:").grid(row=0, column=0, sticky="w", pady=3)
    dpi_var = tk.StringVar(value=str(current_dpi))
    dpi_entry = ttk.Entry(inputs_frame, textvariable=dpi_var, width=18)
    dpi_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)

    ttk.Label(inputs_frame, text="H Sensitivity:").grid(row=1, column=0, sticky="w", pady=3)
    sens_var = tk.StringVar(value=str(current_h_sens))
    ttk.Entry(inputs_frame, textvariable=sens_var, width=18).grid(
        row=1, column=1, sticky="ew", padx=(8, 0), pady=3)

    v_default = str(current_v_sens) if current_v_sens != current_h_sens else ""
    ttk.Label(inputs_frame, text="V Sensitivity:").grid(row=2, column=0, sticky="w", pady=3)
    v_sens_var = tk.StringVar(value=v_default)
    ttk.Entry(inputs_frame, textvariable=v_sens_var, width=18).grid(
        row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

    inputs_frame.columnconfigure(1, weight=1)

    error_var = tk.StringVar()
    ttk.Label(frame, textvariable=error_var, foreground="red").pack(pady=(4, 0))

    def on_apply():
        try:
            dpi = int(dpi_var.get())
            h_sens = float(sens_var.get())
            v_str = v_sens_var.get().strip()
            v_sens = float(v_str) if v_str else h_sens
            if dpi < 50 or dpi > 25600:
                error_var.set("DPI must be between 50 and 25600")
                return
            if h_sens <= 0 or v_sens <= 0:
                error_var.set("Sensitivity must be positive")
                return
            result[0] = (dpi, h_sens, v_sens)
            root.destroy()
        except ValueError:
            error_var.set("Please enter valid numbers")

    def on_cancel():
        root.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=(8, 0))
    ttk.Button(btn_frame, text="Apply", command=on_apply).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=4)

    root.bind("<Return>", lambda e: on_apply())
    root.bind("<Escape>", lambda e: on_cancel())

    dpi_entry.focus_set()
    dpi_entry.select_range(0, "end")

    root.lift()
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))

    log.debug("Entering tkinter mainloop (settings)")
    root.mainloop()
    log.debug("tkinter mainloop exited, result=%s", result[0])
    return result[0]
