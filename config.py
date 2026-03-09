from pynput import keyboard

# Noise filtering — light touch to preserve fast movements
EMA_ALPHA = 0.08
DEAD_ZONE_PIXELS = 0.3

# Sweep segmentation — catch shorter movements
MIN_SWEEP_DURATION_S = 0.010
MIN_SWEEP_PIXELS = 1.5

# Click-centric flick detection
MIN_FLICK_VELOCITY_PX_S = 100.0

# Sensitivity recommendation
CORRECTION_FACTOR = 0.15            # Recalibrated for path-length-based overshoot (50-200% range)
MAX_REDUCTION_PCT = 30.0            # Never recommend more than 30% reduction in one step
MIN_EVENTS_FOR_RECOMMENDATION = 10
X_WEIGHT = 1.5
Y_WEIGHT = 1.0

# Cursor warp detection (GeForce Now relative mouse mode)
WARP_THRESHOLD_PX = 100

# Hotkeys
START_KEY = keyboard.Key.f5
STOP_KEY = keyboard.Key.f6
GAME_CYCLE_KEY = keyboard.Key.f7

# Game tagging
GAME_LIST = ["apex_legends", "r6_siege", "rust", "arc_raiders", "deadlock"]

# Per-game split horizontal/vertical sensitivity (informational — doesn't gate the feature)
GAME_SPLIT_SENS = {
    "apex_legends": False,
    "r6_siege": True,
    "rust": False,
    "arc_raiders": False,
    "deadlock": False,
}
GAME_DISPLAY_NAMES = {
    "apex_legends": "Apex Legends",
    "r6_siege": "R6 Siege",
    "rust": "Rust",
    "arc_raiders": "Arc Raiders",
    "deadlock": "Deadlock",
}

# Rowing detection
MIN_ROWING_GAP_S = 0.050           # Min gap to count as mouse lift (50ms = realistic lift minimum)
MAX_ROWING_GAP_S = 0.500           # Max gap before it's a deliberate pause (500ms)
MIN_ROWING_SWEEPS = 3              # Min consecutive same-dir sweeps for rowing
MIN_ROWING_SWEEP_VELOCITY = 450.0  # Normal corrections are 100-300 px/s; only flag real rowing
MIN_ROWING_SWEEP_DISPLACEMENT = 25.0  # 10px is micro-adjustment noise; rowing covers real distance
ROWING_CV_THRESHOLD = 0.5            # Coefficient of variation — was 1.0 (too lenient)
MAX_ROWING_DISPLACEMENT_RATIO = 4.0  # Reject chains with wildly inconsistent stroke sizes
ROWING_CORRECTION_FACTOR = 0.50    # Conservative increase recommendation
MIN_ROWING_EVENTS_FOR_RECOMMENDATION = 8

# Click-proximity analysis
CLICK_WINDOW_BEFORE_S = 0.500       # Look 500ms before click for the flick
CLICK_WINDOW_AFTER_S = 0.300        # Look 300ms after click for correction jitter

# Swirl detection (2D overshoot) — net rotation, not accumulated jitter
MIN_SWIRL_ANGLE_RAD = 1.5708         # ~90° net rotation = true spiral around target

# Click-centric velocity threshold for approach/correction transition
CLICK_APPROACH_VELOCITY_DROP = 0.30  # Correction starts when velocity drops to 30% of peak

# Movement key warning
MOVEMENT_KEYS_SPECIAL = {keyboard.Key.up, keyboard.Key.down, keyboard.Key.left, keyboard.Key.right}
MOVEMENT_KEYS_CHAR = {'w', 'a', 's', 'd'}
MOVEMENT_DEBOUNCE_S = 0.5
OVERLAY_WARNING_FLASH_S = 2.0

# Shot string segmentation
STRING_GAP_THRESHOLD_S = 2.0  # Max gap between shots in a combat string

# History comparison
MIN_ANALYZED_CLICKS_FOR_HISTORY = 30
MIN_SESSION_DURATION_FOR_HISTORY = 30.0  # seconds

# DPI snapping
DPI_STEP = 50

# DPI advisory ranges
DPI_SWEET_SPOT_LOW = 800
DPI_SWEET_SPOT_HIGH = 1600
DPI_HARD_LOW = 400       # Below this: strong warning (pixel skipping)
DPI_HARD_HIGH = 3200     # Above this: strong warning (sensor smoothing)

# Overlay appearance
OVERLAY_WIDTH = 360
OVERLAY_HEIGHT_WAITING = 220
OVERLAY_HEIGHT_COMPACT = 80
OVERLAY_HEIGHT = OVERLAY_HEIGHT_COMPACT
OVERLAY_TOP_OFFSET = 40
OVERLAY_RIGHT_OFFSET = 20
OVERLAY_BG_ALPHA = 0.80
OVERLAY_TITLE_FONT_SIZE = 18.0
OVERLAY_STATUS_FONT_SIZE = 14.0
OVERLAY_INSTRUCTIONS_FONT_SIZE = 12.0
OVERLAY_CORNER_RADIUS = 12.0
