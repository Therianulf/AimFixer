"""Configuration loader — reads config.ini and exposes module-level constants."""
from __future__ import annotations

import configparser
from pathlib import Path

from pynput import keyboard

# ---------------------------------------------------------------------------
# Load INI
# ---------------------------------------------------------------------------
_ini = configparser.ConfigParser()
_ini.read(Path(__file__).resolve().parent / "config.ini")


def _float(section: str, key: str) -> float:
    return _ini.getfloat(section, key)


def _int(section: str, key: str) -> int:
    return _ini.getint(section, key)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
EMA_ALPHA = _float("filtering", "ema_alpha")
DEAD_ZONE_PIXELS = _float("filtering", "dead_zone_pixels")

# ---------------------------------------------------------------------------
# Sweep segmentation
# ---------------------------------------------------------------------------
MIN_SWEEP_DURATION_S = _float("sweep", "min_sweep_duration_s")
MIN_SWEEP_PIXELS = _float("sweep", "min_sweep_pixels")

# ---------------------------------------------------------------------------
# Click-centric flick detection
# ---------------------------------------------------------------------------
MIN_FLICK_VELOCITY_PX_S = _float("click_detection", "min_flick_velocity_px_s")
CLICK_WINDOW_BEFORE_S = _float("click_detection", "click_window_before_s")
CLICK_APPROACH_VELOCITY_DROP = _float("click_detection", "click_approach_velocity_drop")

# ---------------------------------------------------------------------------
# Sensitivity recommendation
# ---------------------------------------------------------------------------
CORRECTION_FACTOR = _float("recommendation", "correction_factor")
MAX_REDUCTION_PCT = _float("recommendation", "max_reduction_pct")
MIN_EVENTS_FOR_RECOMMENDATION = _int("recommendation", "min_events_for_recommendation")
X_WEIGHT = _float("recommendation", "x_weight")
Y_WEIGHT = _float("recommendation", "y_weight")

# ---------------------------------------------------------------------------
# Cursor warp detection
# ---------------------------------------------------------------------------
WARP_THRESHOLD_PX = _int("warp", "warp_threshold_px")

# ---------------------------------------------------------------------------
# Hotkeys
# ---------------------------------------------------------------------------
START_KEY = getattr(keyboard.Key, _ini.get("hotkeys", "start_key"))
STOP_KEY = getattr(keyboard.Key, _ini.get("hotkeys", "stop_key"))
GAME_CYCLE_KEY = getattr(keyboard.Key, _ini.get("hotkeys", "game_cycle_key"))

# ---------------------------------------------------------------------------
# Game tagging
# ---------------------------------------------------------------------------
GAME_LIST = [g.strip() for g in _ini.get("games", "game_list").split(",")]

GAME_SPLIT_SENS = {
    key: _ini.getboolean("game_split_sens", key)
    for key in _ini.options("game_split_sens")
}

GAME_DISPLAY_NAMES = dict(_ini.items("game_display_names"))

GAME_SENS_DECIMALS: dict[str, int] = {
    key: _ini.getint("game_sens_decimals", key)
    for key in _ini.options("game_sens_decimals")
}

# ---------------------------------------------------------------------------
# Rowing detection
# ---------------------------------------------------------------------------
MIN_ROWING_GAP_S = _float("rowing", "min_rowing_gap_s")
MAX_ROWING_GAP_S = _float("rowing", "max_rowing_gap_s")
MIN_ROWING_SWEEPS = _int("rowing", "min_rowing_sweeps")
MIN_ROWING_SWEEP_VELOCITY = _float("rowing", "min_rowing_sweep_velocity")
MIN_ROWING_SWEEP_DISPLACEMENT = _float("rowing", "min_rowing_sweep_displacement")
ROWING_CV_THRESHOLD = _float("rowing", "rowing_cv_threshold")
MAX_ROWING_DISPLACEMENT_RATIO = _float("rowing", "max_rowing_displacement_ratio")
ROWING_CORRECTION_FACTOR = _float("rowing", "rowing_correction_factor")
MIN_ROWING_EVENTS_FOR_RECOMMENDATION = _int("rowing", "min_rowing_events_for_recommendation")

# ---------------------------------------------------------------------------
# Swirl detection
# ---------------------------------------------------------------------------
MIN_SWIRL_ANGLE_RAD = _float("swirl", "min_swirl_angle_rad")

# ---------------------------------------------------------------------------
# Movement key warning
# ---------------------------------------------------------------------------
MOVEMENT_KEYS_SPECIAL = {
    getattr(keyboard.Key, k.strip())
    for k in _ini.get("movement", "movement_keys_special").split(",")
}
MOVEMENT_KEYS_CHAR = set(_ini.get("movement", "movement_keys_char").replace(" ", "").split(","))
MOVEMENT_DEBOUNCE_S = _float("movement", "movement_debounce_s")

# ---------------------------------------------------------------------------
# Shot string segmentation
# ---------------------------------------------------------------------------
STRING_GAP_THRESHOLD_S = _float("shot_strings", "string_gap_threshold_s")

# ---------------------------------------------------------------------------
# History comparison
# ---------------------------------------------------------------------------
MIN_ANALYZED_CLICKS_FOR_HISTORY = _int("history", "min_analyzed_clicks_for_history")
MIN_SESSION_DURATION_FOR_HISTORY = _float("history", "min_session_duration_for_history")

# ---------------------------------------------------------------------------
# DPI snapping / advisory
# ---------------------------------------------------------------------------
DPI_STEP = _int("dpi", "dpi_step")
DPI_SWEET_SPOT_LOW = _int("dpi", "dpi_sweet_spot_low")
DPI_SWEET_SPOT_HIGH = _int("dpi", "dpi_sweet_spot_high")
DPI_HARD_LOW = _int("dpi", "dpi_hard_low")
DPI_HARD_HIGH = _int("dpi", "dpi_hard_high")

# ---------------------------------------------------------------------------
# Overlay appearance
# ---------------------------------------------------------------------------
OVERLAY_WIDTH = _int("overlay", "overlay_width")
OVERLAY_HEIGHT_WAITING = _int("overlay", "overlay_height_waiting")
OVERLAY_HEIGHT_COMPACT = _int("overlay", "overlay_height_compact")
OVERLAY_TOP_OFFSET = _int("overlay", "overlay_top_offset")
OVERLAY_RIGHT_OFFSET = _int("overlay", "overlay_right_offset")
OVERLAY_BG_ALPHA = _float("overlay", "overlay_bg_alpha")
OVERLAY_TITLE_FONT_SIZE = _float("overlay", "overlay_title_font_size")
OVERLAY_STATUS_FONT_SIZE = _float("overlay", "overlay_status_font_size")
OVERLAY_INSTRUCTIONS_FONT_SIZE = _float("overlay", "overlay_instructions_font_size")
OVERLAY_CORNER_RADIUS = _float("overlay", "overlay_corner_radius")
OVERLAY_WARNING_FLASH_S = _float("overlay", "overlay_warning_flash_s")


# ---------------------------------------------------------------------------
# Per-game sensitivity helpers
# ---------------------------------------------------------------------------
def format_sens(value: float, game: str = "unknown") -> str:
    """Format a sensitivity value with the correct decimal places for a game."""
    decimals = GAME_SENS_DECIMALS.get(game, 2)
    return f"{value:.{decimals}f}"


def snap_sens(value: float, game: str = "unknown") -> float:
    """Round a sensitivity value to the correct precision for a game."""
    decimals = GAME_SENS_DECIMALS.get(game, 2)
    return round(value, decimals)
