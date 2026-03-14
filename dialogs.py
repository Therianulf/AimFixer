"""Cross-platform GUI dialogs for AimFixer using tkinter."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def show_startup_dialog(
    default_dpi: int = 800,
    default_sens: float = 5.0,
    default_v_sens: float = 0.0,
) -> tuple[int, float, float] | None:
    """Show a GUI dialog to collect DPI and sensitivity settings.

    Returns (dpi, h_sens, v_sens) or None if cancelled.
    """
    result = [None]

    root = tk.Tk()
    root.title("\U0001F3AF AimFixer Setup")
    root.resizable(False, False)

    # Center on screen
    root.update_idletasks()
    w, h = 340, 230
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"{w}x{h}+{x}+{y}")

    # Style
    style = ttk.Style()
    style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
    style.configure("Sub.TLabel", font=("Helvetica", 11))

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="\U0001F3AF AimFixer", style="Title.TLabel").pack(pady=(0, 5))
    ttk.Label(frame, text="Enter your mouse settings to begin",
              style="Sub.TLabel").pack(pady=(0, 12))

    # Input rows
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

    # Error label
    error_var = tk.StringVar()
    error_label = ttk.Label(frame, textvariable=error_var, foreground="red")
    error_label.pack(pady=(4, 0))

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

    # Buttons
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=(8, 0))
    ttk.Button(btn_frame, text="Start", command=on_start).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Quit", command=on_quit).pack(side="left", padx=4)

    # Enter key starts
    root.bind("<Return>", lambda e: on_start())
    root.bind("<Escape>", lambda e: on_quit())

    # Focus DPI field
    dpi_entry.focus_set()
    dpi_entry.select_range(0, "end")

    # Bring to front
    root.lift()
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))

    root.mainloop()
    return result[0]


def show_settings_change_dialog(
    current_dpi: int,
    current_h_sens: float,
    current_v_sens: float,
) -> tuple[int, float, float] | None:
    """Show a dialog to change DPI and sensitivity mid-session.

    Returns (dpi, h_sens, v_sens) or None if cancelled.
    """
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

    root.mainloop()
    return result[0]
