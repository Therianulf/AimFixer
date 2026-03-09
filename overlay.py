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
    NSTextAlignmentLeft,
    NSTimer,
    NSWindow,
    NSWindowStyleMaskBorderless,
)
from Foundation import NSObject

from config import (
    OVERLAY_BG_ALPHA,
    OVERLAY_CORNER_RADIUS,
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

# Window level above screensavers / status bars (level 25)
NSStatusWindowLevel = 25

# Collection behavior flags
NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
NSWindowCollectionBehaviorFullScreenAuxiliary = 1 << 8

TITLE_HEIGHT = 36
STATUS_HEIGHT = 32

_INSTRUCTIONS_TEXT = (
    "Tips:\n"
    "\u2022 Stand still \u2014 avoid moving your character\n"
    "\u2022 Use a single-shot weapon\n"
    "\u2022 Flick quickly between targets\n"
    "\u2022 Only fire when you're on target\n"
    "\u2022 Pick targets at varying distances\n"
    "\n"
    "\u2022 F7: Change game"
)

_DARK_BG = (0.08, 0.08, 0.08)
_RED_BG = (0.6, 0.05, 0.05)


class OverlayState(Enum):
    WAITING = auto()
    RECORDING = auto()
    ANALYZING = auto()
    HIDDEN = auto()


_STATE_TEXT = {
    OverlayState.WAITING: "Press F5 to start recording",
    OverlayState.RECORDING: "\U0001F534 Recording\u2026  Press F6 to stop",
    OverlayState.ANALYZING: "Recording stopped. Analyzing\u2026",
}

_DEFAULT_WAITING_FMT = "{game}  |  Press F5 to start"


def _make_label(frame, font_size, weight=0.0, color=None, alignment=NSTextAlignmentCenter):
    """Create a non-editable text label."""
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_("")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(alignment)
    label.setTextColor_(color or NSColor.whiteColor())
    label.setFont_(NSFont.systemFontOfSize_weight_(font_size, weight))
    return label


def _bg_color(r, g, b):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, OVERLAY_BG_ALPHA).CGColor()


class OverlayController(NSObject):
    """Manages a transparent, click-through overlay window."""

    def init(self):
        self = objc.super(OverlayController, self).init()
        if self is None:
            return None

        self._app = NSApplication.sharedApplication()
        self._app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory

        self._current_height = OVERLAY_HEIGHT_WAITING
        screen = NSScreen.mainScreen().frame()
        x = screen.size.width - OVERLAY_WIDTH - OVERLAY_RIGHT_OFFSET
        y = screen.size.height - OVERLAY_TOP_OFFSET - self._current_height

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, OVERLAY_WIDTH, self._current_height),
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
        layer.setBackgroundColor_(_bg_color(*_DARK_BG))

        # Green color for text
        green = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.3, 0.9, 0.4, 1.0)
        gray = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.7, 0.7, 1.0)

        # Title label: "🎯 AimFixer"
        self._title = _make_label(
            NSMakeRect(0, self._current_height - TITLE_HEIGHT - 4, OVERLAY_WIDTH, TITLE_HEIGHT),
            OVERLAY_TITLE_FONT_SIZE,
            weight=0.5,
            color=green,
        )
        self._title.setStringValue_("\U0001F3AF AimFixer")
        content.addSubview_(self._title)

        # Status label: state-dependent text
        self._status = _make_label(
            NSMakeRect(0, self._current_height - TITLE_HEIGHT - STATUS_HEIGHT, OVERLAY_WIDTH, STATUS_HEIGHT),
            OVERLAY_STATUS_FONT_SIZE,
            color=green,
        )
        content.addSubview_(self._status)

        # Instructions label (visible only in WAITING state)
        instructions_top = self._current_height - TITLE_HEIGHT - STATUS_HEIGHT - 8
        self._instructions = _make_label(
            NSMakeRect(20, 8, OVERLAY_WIDTH - 40, instructions_top - 8),
            OVERLAY_INSTRUCTIONS_FONT_SIZE,
            color=gray,
            alignment=NSTextAlignmentLeft,
        )
        self._instructions.setMaximumNumberOfLines_(0)
        self._instructions.setStringValue_(_INSTRUCTIONS_TEXT)
        content.addSubview_(self._instructions)

        self._pending_state = OverlayState.HIDDEN
        self._warning_timer = None
        self._green = green
        self._current_game_display = "Apex Legends"
        return self

    @objc.python_method
    def _resize_window(self, new_height):
        """Resize keeping top edge anchored."""
        if new_height == self._current_height:
            return
        screen = NSScreen.mainScreen().frame()
        frame = self._window.frame()
        new_y = screen.size.height - OVERLAY_TOP_OFFSET - new_height
        self._window.setFrame_display_animate_(
            NSMakeRect(frame.origin.x, new_y, OVERLAY_WIDTH, new_height),
            True, True,
        )
        self._current_height = new_height
        # Reposition labels relative to new height
        self._title.setFrame_(
            NSMakeRect(0, new_height - TITLE_HEIGHT - 4, OVERLAY_WIDTH, TITLE_HEIGHT)
        )
        self._status.setFrame_(
            NSMakeRect(0, new_height - TITLE_HEIGHT - STATUS_HEIGHT, OVERLAY_WIDTH, STATUS_HEIGHT)
        )

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

        if state == OverlayState.WAITING:
            self._resize_window(OVERLAY_HEIGHT_WAITING)
            self._instructions.setHidden_(False)
        else:
            self._resize_window(OVERLAY_HEIGHT_COMPACT)
            self._instructions.setHidden_(True)

        # Restore normal background (in case a warning was active)
        self._window.contentView().layer().setBackgroundColor_(_bg_color(*_DARK_BG))
        self._status.setTextColor_(self._green)

        if state == OverlayState.WAITING:
            text = _DEFAULT_WAITING_FMT.format(game=self._current_game_display)
        else:
            text = _STATE_TEXT.get(state, "")
        self._status.setStringValue_(text)
        self._window.orderFrontRegardless()

    @objc.python_method
    def set_game(self, name: str):
        """Thread-safe: update the displayed game name while in WAITING state."""
        self._current_game_display = name
        if self._pending_state == OverlayState.WAITING:
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "applyGame", None, False
            )

    def applyGame(self):
        """Called on main thread to update game name in status text."""
        text = _DEFAULT_WAITING_FMT.format(game=self._current_game_display)
        self._status.setStringValue_(text)

    @objc.python_method
    def flash_warning(self, message: str):
        """Thread-safe: trigger a red flash with warning text."""
        self._pending_warning = message
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "applyWarning", None, False
        )

    def applyWarning(self):
        """Called on main thread to show warning flash."""
        message = getattr(self, '_pending_warning', None)
        if not message:
            return

        # Change background to red
        self._window.contentView().layer().setBackgroundColor_(_bg_color(*_RED_BG))

        # Change status text to warning
        self._status.setStringValue_(message)
        self._status.setTextColor_(NSColor.whiteColor())

        # Cancel any existing revert timer
        if self._warning_timer:
            self._warning_timer.invalidate()

        self._warning_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            OVERLAY_WARNING_FLASH_S,
            self,
            "revertWarning",
            None,
            False,
        )

    def revertWarning(self):
        """Called by NSTimer to revert the warning flash."""
        self._warning_timer = None
        # Only revert if we're still in RECORDING state
        if self._pending_state != OverlayState.RECORDING:
            return
        self._window.contentView().layer().setBackgroundColor_(_bg_color(*_DARK_BG))
        self._status.setTextColor_(self._green)
        self._status.setStringValue_(_STATE_TEXT[OverlayState.RECORDING])

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
