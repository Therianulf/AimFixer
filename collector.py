from __future__ import annotations
import time
import threading
from dataclasses import dataclass, field
from pynput import mouse, keyboard
from config import (
    TOGGLE_KEY, WARP_THRESHOLD_PX,
    MOVEMENT_KEYS_SPECIAL, MOVEMENT_KEYS_CHAR, MOVEMENT_DEBOUNCE_S,
)


@dataclass
class MouseSample:
    timestamp: float
    x: int
    y: int
    dx: float
    dy: float
    during_movement: bool = False


class MouseCollector:
    def __init__(self, on_state_change=None, on_movement_key=None):
        self._samples: list[MouseSample] = []
        self._collecting = False
        self._done = threading.Event()
        self._started = threading.Event()
        self._prev_x: int | None = None
        self._prev_y: int | None = None
        self._mouse_listener: mouse.Listener | None = None
        self._key_listener: keyboard.Listener | None = None
        self._on_state_change = on_state_change
        self._on_movement_key = on_movement_key
        self._movement_held = False
        self._movement_keys_down: set = set()
        self._last_movement_warn = 0.0

    def _on_move(self, x: int, y: int):
        if not self._collecting:
            return

        now = time.perf_counter()

        if self._prev_x is None:
            self._prev_x = x
            self._prev_y = y
            return

        dx = x - self._prev_x
        dy = y - self._prev_y
        self._prev_x = x
        self._prev_y = y

        # Discard cursor warp events (GeForce Now relative mouse mode)
        if abs(dx) > WARP_THRESHOLD_PX or abs(dy) > WARP_THRESHOLD_PX:
            return

        self._samples.append(MouseSample(
            timestamp=now, x=x, y=y, dx=dx, dy=dy,
            during_movement=self._movement_held,
        ))

    def _is_movement_key(self, key) -> bool:
        if key in MOVEMENT_KEYS_SPECIAL:
            return True
        if hasattr(key, 'char') and key.char and key.char.lower() in MOVEMENT_KEYS_CHAR:
            return True
        return False

    def _on_key_press(self, key):
        if key == TOGGLE_KEY:
            if not self._collecting:
                self._collecting = True
                self._prev_x = None
                self._prev_y = None
                self._samples.clear()
                self._movement_keys_down.clear()
                self._movement_held = False
                self._started.set()
                if self._on_state_change:
                    self._on_state_change("recording")
                else:
                    print("  Recording started! Move your mouse / aim in-game.")
            else:
                self._collecting = False
                self._done.set()
                if self._on_state_change:
                    self._on_state_change("stopped")
                else:
                    print("  Recording stopped.")

        if self._collecting and self._is_movement_key(key):
            self._movement_keys_down.add(str(key))
            self._movement_held = True
            if self._on_movement_key:
                now = time.perf_counter()
                if now - self._last_movement_warn > MOVEMENT_DEBOUNCE_S:
                    self._last_movement_warn = now
                    self._on_movement_key()

    def _on_key_release(self, key):
        if self._is_movement_key(key):
            self._movement_keys_down.discard(str(key))
            if not self._movement_keys_down:
                self._movement_held = False

    def start(self):
        """Start listeners and wait for the full collect cycle (F6 start, F6 stop)."""
        self._mouse_listener = mouse.Listener(on_move=self._on_move)
        self._key_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener.start()
        self._key_listener.start()

    def wait_for_start(self):
        self._started.wait()

    def wait_for_stop(self):
        self._done.wait()

    def stop(self):
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._key_listener:
            self._key_listener.stop()

    def get_samples(self) -> list[MouseSample]:
        return list(self._samples)
