"""Transparent always-on-top overlay for AimFixer using AppKit (macOS)."""

from __future__ import annotations

from enum import Enum, auto

import objc
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSColor,
    NSFont,
    NSMakeRect,
    NSScreen,
    NSTextField,
    NSTextAlignmentCenter,
    NSWindow,
    NSWindowStyleMaskBorderless,
)
from Foundation import NSObject

from config import (
    OVERLAY_BG_ALPHA,
    OVERLAY_CORNER_RADIUS,
    OVERLAY_HEIGHT,
    OVERLAY_STATUS_FONT_SIZE,
    OVERLAY_TITLE_FONT_SIZE,
    OVERLAY_TOP_OFFSET,
    OVERLAY_WIDTH,
)

# Window level above screensavers / status bars (level 25)
NSStatusWindowLevel = 25

# Collection behavior flags
NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
NSWindowCollectionBehaviorFullScreenAuxiliary = 1 << 8

TITLE_HEIGHT = 36
STATUS_HEIGHT = 32


class OverlayState(Enum):
    WAITING = auto()
    RECORDING = auto()
    ANALYZING = auto()
    HIDDEN = auto()


_STATE_TEXT = {
    OverlayState.WAITING: "Press F6 to start recording",
    OverlayState.RECORDING: "🔴 Recording…  Press F6 to stop",
    OverlayState.ANALYZING: "Recording stopped. Analyzing…",
}


def _make_label(frame, font_size, weight=0.0, color=None):
    """Create a centered, non-editable text label."""
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_("")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(NSTextAlignmentCenter)
    label.setTextColor_(color or NSColor.whiteColor())
    label.setFont_(NSFont.systemFontOfSize_weight_(font_size, weight))
    return label


class OverlayController(NSObject):
    """Manages a transparent, click-through overlay window."""

    def init(self):
        self = objc.super(OverlayController, self).init()
        if self is None:
            return None

        self._app = NSApplication.sharedApplication()
        self._app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory

        screen = NSScreen.mainScreen().frame()
        x = (screen.size.width - OVERLAY_WIDTH) / 2
        y = screen.size.height - OVERLAY_TOP_OFFSET - OVERLAY_HEIGHT

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, OVERLAY_WIDTH, OVERLAY_HEIGHT),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(NSStatusWindowLevel)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setIgnoresMouseEvents_(True)
        self._window.setHasShadow_(False)
        self._window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        # Background view with rounded corners
        content = self._window.contentView()
        content.setWantsLayer_(True)
        layer = content.layer()
        layer.setCornerRadius_(OVERLAY_CORNER_RADIUS)
        layer.setMasksToBounds_(True)
        layer.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.08, 0.08, 0.08, OVERLAY_BG_ALPHA
            ).CGColor()
        )

        # Green color for text
        green = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.3, 0.9, 0.4, 1.0)

        # Title label (top half): "🎯 AimFixer"
        self._title = _make_label(
            NSMakeRect(0, STATUS_HEIGHT - 4, OVERLAY_WIDTH, TITLE_HEIGHT),
            OVERLAY_TITLE_FONT_SIZE,
            weight=0.5,  # semibold
            color=green,
        )
        self._title.setStringValue_("\U0001F3AF AimFixer")
        content.addSubview_(self._title)

        # Status label (bottom half): state-dependent text
        self._status = _make_label(
            NSMakeRect(0, 4, OVERLAY_WIDTH, STATUS_HEIGHT),
            OVERLAY_STATUS_FONT_SIZE,
            color=green,
        )
        content.addSubview_(self._status)

        self._pending_state = OverlayState.HIDDEN
        return self

    @objc.python_method
    def set_state(self, state: OverlayState):
        """Thread-safe state update. Can be called from any thread."""
        self._pending_state = state
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "applyState", None, False
        )

    def applyState(self):
        """Called on main thread to update the window."""
        state = self._pending_state
        if state == OverlayState.HIDDEN:
            self._window.orderOut_(None)
            return

        text = _STATE_TEXT.get(state, "")
        self._status.setStringValue_(text)
        self._window.orderFrontRegardless()

    def run(self):
        """Start the NSApp run loop. Blocks until stop() is called."""
        self._app.run()

    def stop(self):
        """Stop the NSApp run loop (safe to call from any thread)."""
        self._window.orderOut_(None)
        self._app.stop_(None)
        # Post a dummy event to unblock the run loop so it actually exits
        from AppKit import NSEvent, NSApplicationDefined, NSMakePoint

        event = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            NSApplicationDefined,
            NSMakePoint(0, 0),
            0, 0.0, 0, None, 0, 0, 0,
        )
        self._app.postEvent_atStart_(event, True)

    @objc.python_method
    def schedule(self, fn):
        """Schedule a no-arg callable on the main thread."""
        self._scheduled_fn = fn
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "runScheduled", None, False
        )

    def runScheduled(self):
        if hasattr(self, "_scheduled_fn") and self._scheduled_fn:
            fn = self._scheduled_fn
            self._scheduled_fn = None
            fn()
