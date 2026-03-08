from pynput import keyboard

# Noise filtering
EMA_ALPHA = 0.3
DEAD_ZONE_PIXELS = 0.5

# Sweep segmentation
MIN_SWEEP_DURATION_S = 0.020
MIN_SWEEP_PIXELS = 3.0

# Overshoot classification
MAX_CORRECTION_GAP_S = 0.050
MAX_CORRECTION_RATIO = 0.50
MIN_FLICK_VELOCITY_PX_S = 800.0
VELOCITY_RATIO_THRESHOLD = 0.70
MAX_CORRECTION_DURATION_S = 0.300

# Sensitivity recommendation
CORRECTION_FACTOR = 0.60
MIN_EVENTS_FOR_RECOMMENDATION = 10
X_WEIGHT = 1.5
Y_WEIGHT = 1.0

# Cursor warp detection (GeForce Now relative mouse mode)
WARP_THRESHOLD_PX = 100

# Hotkey
TOGGLE_KEY = keyboard.Key.f6

# Rowing detection
MIN_ROWING_GAP_S = 0.030           # Min gap to count as mouse lift (30ms)
MAX_ROWING_GAP_S = 0.500           # Max gap before it's a deliberate pause (500ms)
MIN_ROWING_SWEEPS = 2              # Min consecutive same-dir sweeps for rowing
MIN_ROWING_SWEEP_VELOCITY = 400.0  # Lower than flick threshold since rowing sweeps decelerate at pad edge
ROWING_CORRECTION_FACTOR = 0.50    # Conservative increase recommendation
MIN_ROWING_EVENTS_FOR_RECOMMENDATION = 5

# Swirl detection (2D overshoot)
MIN_SWIRL_ANGLE_RAD = 0.785          # pi/4 = 45° minimum correction arc rotation
MAX_SWIRL_CORRECTION_S = 0.400       # Slightly longer than 1D (arcs take more time)
SWIRL_DOT_THRESHOLD = -0.3           # Correction must point somewhat opposite to flick
SWIRL_WEIGHT = 2.0                   # Swirls weighted higher in combined recommendation

# Movement key warning
MOVEMENT_KEYS_SPECIAL = {keyboard.Key.up, keyboard.Key.down, keyboard.Key.left, keyboard.Key.right}
MOVEMENT_KEYS_CHAR = {'w', 'a', 's', 'd'}
MOVEMENT_DEBOUNCE_S = 0.5
OVERLAY_WARNING_FLASH_S = 2.0

# DPI snapping
DPI_STEP = 50

# Overlay appearance
OVERLAY_WIDTH = 360
OVERLAY_HEIGHT_WAITING = 220
OVERLAY_HEIGHT_COMPACT = 80
OVERLAY_HEIGHT = OVERLAY_HEIGHT_COMPACT
OVERLAY_TOP_OFFSET = 80
OVERLAY_BG_ALPHA = 0.80
OVERLAY_TITLE_FONT_SIZE = 18.0
OVERLAY_STATUS_FONT_SIZE = 14.0
OVERLAY_INSTRUCTIONS_FONT_SIZE = 12.0
OVERLAY_CORNER_RADIUS = 12.0
