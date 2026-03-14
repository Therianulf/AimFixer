"""Shared dataclass definitions for AimFixer analysis results."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class OverlayState(Enum):
    WAITING = auto()
    RECORDING = auto()
    ANALYZING = auto()
    DONE = auto()
    HIDDEN = auto()


@dataclass
class ClickAnalysisResult:
    total_clicks: int
    analyzed_clicks: int              # clicks with a detected flick
    swirl_click_count: int            # clicks with angle_rotation > threshold
    swirl_click_pct: float
    median_overshoot_pct: float
    mean_overshoot_pct: float
    median_correction_magnitude: float
    median_correction_duration_ms: float
    median_direction_changes: float
    recommended_reduction_pct: float
    overshoot_percentages: list[float]


@dataclass
class FireRateResult:
    total_shots: int
    shots_per_minute: float
    median_shot_interval_ms: float
    mean_shot_interval_ms: float
    aim_efficiency: float          # 0-1, higher = less overshoot
    hit_factor: float              # (shots_per_minute / 60) * aim_efficiency
    string_count: int = 0
    active_combat_duration_s: float = 0.0
    shots_per_string_avg: float = 0.0


@dataclass
class RowingAxisResult:
    rowing_event_count: int
    median_chain_length: float
    median_increase_ratio: float
    mean_gap_duration_ms: float
    recommended_increase_pct: float


@dataclass
class TrendData:
    prev_hit_factor: float
    curr_hit_factor: float
    hit_factor_change_pct: float
    prev_overshoot_pct: float
    curr_overshoot_pct: float
    settings_changed: bool


@dataclass
class UnifiedRecommendation:
    action: str  # "reduce" | "increase" | "keep" | "multi_step"
    primary_pct: float = 0.0
    new_sens: float = 0.0
    new_dpi: int = 0
    reasoning: str = ""
    new_v_sens: float = 0.0
    # Multi-step fields
    step2_action: str = ""
    step2_pct: float = 0.0
    step2_new_sens: float = 0.0
    step2_new_dpi: int = 0
    step2_new_v_sens: float = 0.0
    # Trend context
    trend_note: str = ""


@dataclass
class AnalysisResult:
    session_duration: float
    total_samples: int
    current_dpi: int
    current_sens: float
    click_analysis: ClickAnalysisResult
    # Overshoot recommendations (raw, kept for charts/history)
    combined_reduction_pct: float
    new_sens_combined: float
    new_dpi_combined: int
    # Rowing
    possibly_too_low: bool
    x_rowing: RowingAxisResult | None = None
    y_rowing: RowingAxisResult | None = None
    combined_increase_pct: float = 0.0
    new_sens_increase: float = 0.0
    new_dpi_increase: int = 0
    # Fire rate / hit factor
    fire_rate: FireRateResult | None = None
    # Contamination
    movement_contamination_pct: float = 0.0
    # DPI advisory
    dpi_advisory: str | None = None
    suggested_dpi: int | None = None
    dpi_advisory_level: str = "none"
    # Unified recommendation
    recommendation: UnifiedRecommendation | None = None
    trend: TrendData | None = None
    # Vertical sensitivity
    current_v_sens: float = 0.0
    new_v_sens_combined: float = 0.0
    new_v_sens_increase: float = 0.0
    # Game tagging
    current_game: str = "unknown"
