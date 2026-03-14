#!/usr/bin/env python3
"""Minimal repro: does NSAlert.runModal() cause SIGTRAP with Quartz CGEventTap?"""

import sys
import threading
import time

def test_event_tap():
    """Create a Quartz CGEventTap on a background thread."""
    import Quartz

    def callback(proxy, event_type, event, refcon):
        return event

    event_mask = Quartz.CGEventMaskBit(Quartz.kCGEventMouseMoved)
    print("  Creating CGEventTap...")
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionListenOnly,
        event_mask,
        callback,
        None,
    )
    if tap is None:
        print("  FAILED: Could not create event tap (accessibility?)")
        return
    print("  CGEventTap created successfully!")

    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    loop = Quartz.CFRunLoopGetCurrent()
    Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopDefaultMode)
    Quartz.CGEventTapEnable(tap, True)
    print("  Event tap enabled, run loop running for 1s...")
    Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 1.0, False)
    print("  Done!")


def test_pynput_keyboard():
    """Start a pynput keyboard listener."""
    from pynput import keyboard
    print("  Starting pynput keyboard listener...")
    listener = keyboard.Listener(on_press=lambda k: None)
    listener.start()
    print("  Keyboard listener started!")
    time.sleep(0.5)
    listener.stop()
    print("  Keyboard listener stopped!")


def test_pynput_mouse():
    """Start a pynput mouse listener."""
    from pynput import mouse
    print("  Starting pynput mouse listener...")
    listener = mouse.Listener(on_move=lambda x, y: None)
    listener.start()
    print("  Mouse listener started!")
    time.sleep(0.5)
    listener.stop()
    print("  Mouse listener stopped!")


def show_nsalert():
    """Show a simple NSAlert dialog."""
    from AppKit import NSAlert, NSApplication
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)

    alert = NSAlert.alloc().init()
    alert.setMessageText_("Test Dialog")
    alert.setInformativeText_("Click OK to continue")
    alert.addButtonWithTitle_("OK")
    print("  Showing NSAlert...")
    alert.runModal()
    print("  NSAlert dismissed!")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "tap_only":
        print("\n=== Test: CGEventTap only (no dialog) ===")
        t = threading.Thread(target=test_event_tap, daemon=True)
        t.start()
        t.join(timeout=5)

    elif mode == "pynput_only":
        print("\n=== Test: pynput only (no dialog) ===")
        test_pynput_keyboard()
        test_pynput_mouse()

    elif mode == "dialog_then_tap":
        print("\n=== Test: NSAlert → CGEventTap ===")
        show_nsalert()
        print("  Starting CGEventTap thread after dialog...")
        t = threading.Thread(target=test_event_tap, daemon=True)
        t.start()
        t.join(timeout=5)

    elif mode == "dialog_then_pynput":
        print("\n=== Test: NSAlert → pynput listeners ===")
        show_nsalert()
        print("  Starting pynput after dialog...")
        test_pynput_keyboard()
        test_pynput_mouse()

    elif mode == "dialog_then_all":
        print("\n=== Test: NSAlert → pynput + CGEventTap ===")
        show_nsalert()
        print("  Starting pynput listeners...")
        test_pynput_keyboard()
        test_pynput_mouse()
        print("  Starting CGEventTap thread...")
        t = threading.Thread(target=test_event_tap, daemon=True)
        t.start()
        t.join(timeout=5)

    elif mode == "all":
        print("Usage: python test_quartz.py <mode>")
        print("Modes:")
        print("  tap_only          - CGEventTap only (no dialog)")
        print("  pynput_only       - pynput only (no dialog)")
        print("  dialog_then_tap   - NSAlert → CGEventTap")
        print("  dialog_then_pynput - NSAlert → pynput")
        print("  dialog_then_all   - NSAlert → pynput + CGEventTap")

    print("\n=== All tests passed! ===")
