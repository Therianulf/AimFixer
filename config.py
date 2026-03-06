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

# DPI snapping
DPI_STEP = 50
