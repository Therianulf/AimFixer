"""Transparent always-on-top overlay for AimFixer using tkinter (Windows/Linux)."""

from __future__ import annotations

import tkinter as tk

from config import (
    OVERLAY_BG_ALPHA,
    OVERLAY_HEIGHT_WAITING,
    OVERLAY_HEIGHT_COMPACT,
    OVERLAY_INSTRUCTIONS_FONT_SIZE,
    OVERLAY_STATUS_FONT_SIZE,
    OVERLAY_TITLE_FONT_SIZE,
    OVERLAY_RIGHT_OFFSET,
    OVERLAY_TOP_OFFSET,
    OVERLAY_WARNING_FLASH_S,
    OVERLAY_WIDTH,
)
from models import OverlayState

_INSTRUCTIONS_TEXT = (
    "Tips:\n"
    "\u2022 Stand still \u2014 avoid moving your character\n"
    "\u2022 Use a single-shot weapon\n"
    "\u2022 Flick quickly between targets\n"
    "\u2022 Only fire when you're on target\n"
    "\u2022 Pick targets at varying distances\n"
    "\n"
    "\u2022 F7: Game  \u2022 F8: Quit  \u2022 F9: Settings"
)

_DONE_TEXT = (
    "Session complete!\n\n"
    "\u2022 F5: New session\n"
    "\u2022 F8: Quit and show charts\n"
    "\u2022 F9: Change settings"
)

_DARK_BG = "#141414"
_RED_BG = "#991010"
_GREEN_FG = "#4de669"
_GRAY_FG = "#b3b3b3"
_WHITE_FG = "#ffffff"

_STATE_TEXT = {
    OverlayState.WAITING: "Press F5 to start recording",
    OverlayState.RECORDING: "\U0001f534 Recording\u2026  Press F6 to stop",
    OverlayState.ANALYZING: "Recording stopped. Analyzing\u2026",
    OverlayState.DONE: "\u2705 Done!  Press F5 for new session",
}

_DEFAULT_WAITING_FMT = "{game}  |  Press F5 to start"

# Warning flash duration in milliseconds
_WARNING_FLASH_MS = int(OVERLAY_WARNING_FLASH_S * 1000)


class OverlayController:
    """Manages a transparent, always-on-top overlay window using tkinter."""

    def __init__(self):
        self._root = tk.Tk()
        self._root.withdraw()  # Hide default root window

        self._current_height = OVERLAY_HEIGHT_WAITING
        self._current_state = OverlayState.HIDDEN
        self._current_game_display = "Apex Legends"
        self._warning_after_id = None

        # Create overlay toplevel window
        self._window = tk.Toplevel(self._root)
        self._window.overrideredirect(True)  # Borderless
        self._window.attributes("-topmost", True)  # Always on top
        self._window.attributes("-alpha", OVERLAY_BG_ALPHA)
        self._window.configure(bg=_DARK_BG)

        # Position: top-right of screen
        self._window.update_idletasks()
        screen_w = self._window.winfo_screenwidth()
        x = screen_w - OVERLAY_WIDTH - OVERLAY_RIGHT_OFFSET
        y = OVERLAY_TOP_OFFSET
        self._window.geometry(f"{OVERLAY_WIDTH}x{self._current_height}+{x}+{y}")

        # Make click-through on Windows
        try:
            # Windows: WS_EX_TRANSPARENT | WS_EX_LAYERED via hwnd
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self._window.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            # WS_EX_LAYERED=0x80000, WS_EX_TRANSPARENT=0x20
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
        except Exception:
            pass  # Not on Windows, or not supported

        # Title label
        self._title = tk.Label(
            self._window,
            text="\U0001f3af AimFixer",
            font=("Helvetica", int(OVERLAY_TITLE_FONT_SIZE), "bold"),
            fg=_GREEN_FG,
            bg=_DARK_BG,
            anchor="center",
        )
        self._title.pack(fill="x", pady=(8, 0))

        # Status label
        self._status = tk.Label(
            self._window,
            text="",
            font=("Helvetica", int(OVERLAY_STATUS_FONT_SIZE)),
            fg=_GREEN_FG,
            bg=_DARK_BG,
            anchor="center",
        )
        self._status.pack(fill="x", pady=(4, 0))

        # Instructions label
        self._instructions = tk.Label(
            self._window,
            text=_INSTRUCTIONS_TEXT,
            font=("Helvetica", int(OVERLAY_INSTRUCTIONS_FONT_SIZE)),
            fg=_GRAY_FG,
            bg=_DARK_BG,
            anchor="nw",
            justify="left",
        )
        self._instructions.pack(fill="both", expand=True, padx=20, pady=(8, 8))

        # Start hidden
        self._window.withdraw()

    def _reposition(self):
        """Reposition window after height change."""
        screen_w = self._window.winfo_screenwidth()
        x = screen_w - OVERLAY_WIDTH - OVERLAY_RIGHT_OFFSET
        y = OVERLAY_TOP_OFFSET
        self._window.geometry(f"{OVERLAY_WIDTH}x{self._current_height}+{x}+{y}")

    def set_state(self, state: OverlayState):
        """Thread-safe state update. Can be called from any thread."""
        self._root.after(0, self._apply_state, state)

    def _apply_state(self, state: OverlayState):
        """Called on main thread to update the window."""
        self._current_state = state

        if state == OverlayState.HIDDEN:
            self._window.withdraw()
            return

        if state in (OverlayState.WAITING, OverlayState.DONE):
            self._current_height = OVERLAY_HEIGHT_WAITING
            self._instructions.pack(fill="both", expand=True, padx=20, pady=(8, 8))
            if state == OverlayState.DONE:
                self._instructions.configure(text=_DONE_TEXT)
            else:
                self._instructions.configure(text=_INSTRUCTIONS_TEXT)
        else:
            self._current_height = OVERLAY_HEIGHT_COMPACT
            self._instructions.pack_forget()

        self._reposition()

        # Restore normal background
        self._window.configure(bg=_DARK_BG)
        self._title.configure(bg=_DARK_BG)
        self._status.configure(bg=_DARK_BG, fg=_GREEN_FG)
        self._instructions.configure(bg=_DARK_BG)

        if state == OverlayState.WAITING:
            text = _DEFAULT_WAITING_FMT.format(game=self._current_game_display)
        else:
            text = _STATE_TEXT.get(state, "")
        self._status.configure(text=text)

        self._window.deiconify()
        self._window.lift()

    def set_game(self, name: str):
        """Thread-safe: update the displayed game name while in WAITING state."""
        self._current_game_display = name
        if self._current_state == OverlayState.WAITING:
            self._root.after(0, self._apply_game)

    def _apply_game(self):
        text = _DEFAULT_WAITING_FMT.format(game=self._current_game_display)
        self._status.configure(text=text)

    def set_settings(self, dpi: int, h_sens: float, v_sens: float):
        """Thread-safe: update the settings display in the title."""
        if v_sens != h_sens:
            settings = f"{dpi} DPI / H:{h_sens} V:{v_sens}"
        else:
            settings = f"{dpi} DPI / {h_sens} sens"
        self._root.after(0, self._apply_settings, settings)

    def _apply_settings(self, settings: str):
        self._title.configure(text=f"\U0001f3af AimFixer  \u2022  {settings}")

    def flash_warning(self, message: str):
        """Thread-safe: trigger a red flash with warning text."""
        self._root.after(0, self._apply_warning, message)

    def _apply_warning(self, message: str):
        # Change background to red
        self._window.configure(bg=_RED_BG)
        self._title.configure(bg=_RED_BG)
        self._status.configure(bg=_RED_BG, fg=_WHITE_FG, text=message)
        self._instructions.configure(bg=_RED_BG)

        # Cancel any existing revert timer
        if self._warning_after_id is not None:
            self._root.after_cancel(self._warning_after_id)

        self._warning_after_id = self._root.after(
            _WARNING_FLASH_MS, self._revert_warning
        )

    def _revert_warning(self):
        self._warning_after_id = None
        if self._current_state != OverlayState.RECORDING:
            return
        self._window.configure(bg=_DARK_BG)
        self._title.configure(bg=_DARK_BG)
        self._status.configure(
            bg=_DARK_BG, fg=_GREEN_FG,
            text=_STATE_TEXT[OverlayState.RECORDING],
        )
        self._instructions.configure(bg=_DARK_BG)

    def schedule(self, fn):
        """Schedule a no-arg callable on the main thread."""
        self._root.after(0, fn)

    def run(self):
        """Start the tkinter main loop. Blocks until stop() is called."""
        self._root.mainloop()

    def stop(self):
        """Stop the tkinter main loop (safe to call from any thread)."""
        self._root.after(0, self._root.quit)
