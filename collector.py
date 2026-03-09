from __future__ import annotations
import sys
import time
import threading
from dataclasses import dataclass
from pynput import mouse, keyboard
from config import (
    START_KEY, STOP_KEY, WARP_THRESHOLD_PX,
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
        self._click_times: list[float] = []
        self._collecting = False
        self._done = threading.Event()
        self._started = threading.Event()
        self._mouse_listener: mouse.Listener | None = None
        self._key_listener: keyboard.Listener | None = None
        self._on_state_change = on_state_change
        self._on_movement_key = on_movement_key
        self._movement_held = False
        self._movement_keys_down: set = set()
        self._last_movement_warn = 0.0
        self._delta_thread: threading.Thread | None = None
        self._delta_running = False
        # Linux fallback: position-based deltas
        self._prev_x: int | None = None
        self._prev_y: int | None = None

    # --- Raw delta recording (called from platform-specific capture) ---

    def _record_delta(self, dx: int, dy: int):
        """Record a mouse delta sample from platform-specific capture."""
        if not self._collecting:
            return
        if dx == 0 and dy == 0:
            return
        if abs(dx) > WARP_THRESHOLD_PX or abs(dy) > WARP_THRESHOLD_PX:
            return
        self._samples.append(MouseSample(
            timestamp=time.perf_counter(), x=0, y=0,
            dx=float(dx), dy=float(dy),
            during_movement=self._movement_held,
        ))

    # --- Click handler (all platforms, via pynput) ---

    def _on_click(self, x, y, button, pressed):
        if not self._collecting:
            return
        if pressed and button == mouse.Button.left:
            self._click_times.append(time.perf_counter())

    # --- Linux fallback: position-based deltas via pynput on_move ---

    def _on_move_fallback(self, x: int, y: int):
        if not self._collecting:
            return
        if self._prev_x is None:
            self._prev_x = x
            self._prev_y = y
            return
        dx = x - self._prev_x
        dy = y - self._prev_y
        self._prev_x = x
        self._prev_y = y
        self._record_delta(dx, dy)

    # --- Platform-specific delta capture ---

    def _start_delta_capture(self):
        self._delta_running = True
        if sys.platform == 'darwin':
            self._delta_thread = threading.Thread(
                target=self._delta_macos, daemon=True)
            self._delta_thread.start()
        elif sys.platform == 'win32':
            self._delta_thread = threading.Thread(
                target=self._delta_windows, daemon=True)
            self._delta_thread.start()
        # Linux: uses _on_move_fallback via pynput, no separate thread

    def _stop_delta_capture(self):
        self._delta_running = False
        if sys.platform == 'darwin' and hasattr(self, '_quartz_loop'):
            import Quartz
            Quartz.CFRunLoopStop(self._quartz_loop)
        elif sys.platform == 'win32' and hasattr(self, '_raw_hwnd'):
            import ctypes
            ctypes.windll.user32.PostMessageW(self._raw_hwnd, 0x0012, 0, 0)  # WM_QUIT

    def _delta_macos(self):
        """macOS: Quartz CGEvent tap for true mouse deltas."""
        import Quartz

        def callback(proxy, event_type, event, refcon):
            if event_type == Quartz.kCGEventLeftMouseDown:
                if self._collecting:
                    self._click_times.append(time.perf_counter())
                return event
            dx = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGMouseEventDeltaX)
            dy = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGMouseEventDeltaY)
            self._record_delta(dx, dy)
            return event

        event_mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventMouseMoved)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDragged)
            | Quartz.CGEventMaskBit(Quartz.kCGEventRightMouseDragged)
            | Quartz.CGEventMaskBit(Quartz.kCGEventOtherMouseDragged)
        )
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            event_mask,
            callback,
            None,
        )
        if tap is None:
            print("  WARNING: Could not create event tap.")
            print("  Grant Accessibility access to your terminal.")
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        self._quartz_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(
            self._quartz_loop, source, Quartz.kCFRunLoopDefaultMode)
        Quartz.CGEventTapEnable(tap, True)

        while self._delta_running:
            Quartz.CFRunLoopRunInMode(
                Quartz.kCFRunLoopDefaultMode, 0.1, False)

    def _delta_windows(self):
        """Windows: Raw Input API for true mouse deltas."""
        import ctypes
        from ctypes import wintypes, POINTER, byref, sizeof

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Constants
        WM_INPUT = 0x00FF
        WM_QUIT = 0x0012
        RIDEV_INPUTSINK = 0x00000100
        RID_INPUT = 0x10000003
        RIM_TYPEMOUSE = 0
        MOUSE_MOVE_RELATIVE = 0x00

        class RAWINPUTHEADER(ctypes.Structure):
            _fields_ = [
                ('dwType', wintypes.DWORD),
                ('dwSize', wintypes.DWORD),
                ('hDevice', wintypes.HANDLE),
                ('wParam', wintypes.WPARAM),
            ]

        class RAWMOUSE(ctypes.Structure):
            _fields_ = [
                ('usFlags', wintypes.USHORT),
                ('_pad', wintypes.USHORT),
                ('ulButtons', wintypes.ULONG),
                ('ulRawButtons', wintypes.ULONG),
                ('lLastX', wintypes.LONG),
                ('lLastY', wintypes.LONG),
                ('ulExtraInformation', wintypes.ULONG),
            ]

        class RAWINPUT(ctypes.Structure):
            _fields_ = [
                ('header', RAWINPUTHEADER),
                ('mouse', RAWMOUSE),
            ]

        class RAWINPUTDEVICE(ctypes.Structure):
            _fields_ = [
                ('usUsagePage', wintypes.USHORT),
                ('usUsage', wintypes.USHORT),
                ('dwFlags', wintypes.DWORD),
                ('hwndTarget', wintypes.HWND),
            ]

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM,
        )

        collector = self

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                size = wintypes.UINT(sizeof(RAWINPUT))
                raw = RAWINPUT()
                ret = user32.GetRawInputData(
                    ctypes.c_void_p(lparam), RID_INPUT,
                    byref(raw), byref(size), sizeof(RAWINPUTHEADER),
                )
                if ret != ctypes.c_uint(-1).value and raw.header.dwType == RIM_TYPEMOUSE:
                    if raw.mouse.usFlags == MOUSE_MOVE_RELATIVE:
                        collector._record_delta(
                            raw.mouse.lLastX, raw.mouse.lLastY)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        # prevent garbage collection of the callback
        self._wnd_proc_ref = WNDPROC(wnd_proc)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ('style', wintypes.UINT),
                ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int),
                ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HANDLE),
                ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HANDLE),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR),
            ]

        hinstance = kernel32.GetModuleHandleW(None)
        class_name = 'AimFixerRawInput'

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wnd_proc_ref
        wc.hInstance = hinstance
        wc.lpszClassName = class_name
        user32.RegisterClassW(byref(wc))  # OK if already registered

        # Message-only window (invisible)
        user32.CreateWindowExW.restype = wintypes.HWND
        HWND_MESSAGE = ctypes.c_void_p(-3)
        hwnd = user32.CreateWindowExW(
            0, class_name, '', 0, 0, 0, 0, 0,
            HWND_MESSAGE, None, hinstance, None,
        )
        if not hwnd:
            print("  WARNING: Could not create raw input window.")
            return

        self._raw_hwnd = hwnd

        # Register for raw mouse input
        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01  # HID_USAGE_PAGE_GENERIC
        rid.usUsage = 0x02      # HID_USAGE_GENERIC_MOUSE
        rid.dwFlags = RIDEV_INPUTSINK
        rid.hwndTarget = hwnd

        if not user32.RegisterRawInputDevices(
            byref(rid), 1, sizeof(RAWINPUTDEVICE)
        ):
            print("  WARNING: Could not register for raw mouse input.")
            user32.DestroyWindow(hwnd)
            return

        # Message loop
        msg = wintypes.MSG()
        while self._delta_running:
            while user32.PeekMessageW(byref(msg), hwnd, 0, 0, 1):
                if msg.message == WM_QUIT:
                    self._delta_running = False
                    break
                user32.TranslateMessage(byref(msg))
                user32.DispatchMessageW(byref(msg))
            if self._delta_running:
                time.sleep(0.001)

        user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(class_name, hinstance)

    # --- Key handlers ---

    def _is_movement_key(self, key) -> bool:
        if key in MOVEMENT_KEYS_SPECIAL:
            return True
        if hasattr(key, 'char') and key.char and key.char.lower() in MOVEMENT_KEYS_CHAR:
            return True
        return False

    def _on_key_press(self, key):
        if key == START_KEY and not self._collecting:
            self._collecting = True
            self._prev_x = None
            self._prev_y = None
            self._samples.clear()
            self._click_times.clear()
            self._movement_keys_down.clear()
            self._movement_held = False
            self._started.set()
            if self._on_state_change:
                self._on_state_change("recording")
            else:
                print("  Recording started! Move your mouse / aim in-game.")
        elif key == STOP_KEY and self._collecting:
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

    # --- Public API ---

    def start(self):
        """Start listeners and platform-specific delta capture."""
        # Use on_move only on Linux as fallback
        # On macOS, clicks are captured via Quartz event tap instead of pynput
        on_move = self._on_move_fallback if sys.platform == 'linux' else None
        on_click = None if sys.platform == 'darwin' else self._on_click
        self._mouse_listener = mouse.Listener(
            on_move=on_move, on_click=on_click)
        self._key_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener.start()
        self._key_listener.start()

        # Start platform-specific raw delta capture (macOS / Windows)
        self._start_delta_capture()

    def wait_for_start(self):
        self._started.wait()

    def wait_for_stop(self):
        self._done.wait()

    def stop(self):
        self._stop_delta_capture()
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._key_listener:
            self._key_listener.stop()

    def get_samples(self) -> list[MouseSample]:
        return list(self._samples)

    def get_click_times(self) -> list[float]:
        return list(self._click_times)
