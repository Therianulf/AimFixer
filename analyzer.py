from __future__ import annotations
from dataclasses import dataclass
from statistics import median, mean
from detector import ClickAimEvent, RowingEvent
from config import (
    CORRECTION_FACTOR, MAX_REDUCTION_PCT, MIN_EVENTS_FOR_RECOMMENDATION,
    X_WEIGHT, Y_WEIGHT, DPI_STEP,
    ROWING_CORRECTION_FACTOR, MIN_ROWING_EVENTS_FOR_RECOMMENDATION,
    DPI_SWEET_SPOT_LOW, DPI_SWEET_SPOT_HIGH, DPI_HARD_LOW, DPI_HARD_HIGH,
)


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
    # Multi-step fields
    step2_action: str = ""
    step2_pct: float = 0.0
    step2_new_sens: float = 0.0
    step2_new_dpi: int = 0
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


def _confidence_weight(n_events: int) -> float:
    return min(1.0, 0.5 + 0.5 * (n_events / 50))


def _snap_dpi(dpi: float) -> int:
    return max(DPI_STEP, round(dpi / DPI_STEP) * DPI_STEP)


def _compute_dpi_advisory(current_dpi: int) -> tuple[str | None, int | None, str]:
    if current_dpi < DPI_HARD_LOW:
        return (
            f"Your DPI ({current_dpi}) is very low. Pixel skipping is likely."
            f" Strongly consider raising to {DPI_SWEET_SPOT_LOW}.",
            _snap_dpi(DPI_SWEET_SPOT_LOW),
            "warning",
        )
    elif current_dpi < DPI_SWEET_SPOT_LOW:
        return (
            f"Your DPI ({current_dpi}) is a bit low."
            f" Consider raising to {DPI_SWEET_SPOT_LOW} for smoother tracking.",
            _snap_dpi(DPI_SWEET_SPOT_LOW),
            "info",
        )
    elif current_dpi > DPI_HARD_HIGH:
        return (
            f"Your DPI ({current_dpi}) is very high."
            f" Sensor smoothing may reduce precision."
            f" Consider lowering to {DPI_SWEET_SPOT_HIGH}.",
            _snap_dpi(DPI_SWEET_SPOT_HIGH),
            "warning",
        )
    elif current_dpi > DPI_SWEET_SPOT_HIGH:
        return (
            f"Your DPI ({current_dpi}) is above the ideal"
            f" {DPI_SWEET_SPOT_LOW}-{DPI_SWEET_SPOT_HIGH} range."
            f" This is usually fine on modern sensors,"
            f" but consider lowering to {DPI_SWEET_SPOT_HIGH}.",
            _snap_dpi(DPI_SWEET_SPOT_HIGH),
            "info",
        )
    return None, None, "none"


def _compute_click_analysis(
    click_aim_events: list[ClickAimEvent],
    total_clicks: int,
) -> ClickAnalysisResult:
    n = len(click_aim_events)
    if n == 0:
        return ClickAnalysisResult(
            total_clicks=total_clicks,
            analyzed_clicks=0,
            swirl_click_count=0,
            swirl_click_pct=0.0,
            median_overshoot_pct=0.0,
            mean_overshoot_pct=0.0,
            median_correction_magnitude=0.0,
            median_correction_duration_ms=0.0,
            median_direction_changes=0.0,
            recommended_reduction_pct=0.0,
            overshoot_percentages=[],
        )

    pcts = [e.overshoot_percentage for e in click_aim_events]
    corr_mags = [e.correction_magnitude for e in click_aim_events]
    corr_durs = [e.correction_duration * 1000 for e in click_aim_events]  # to ms
    dir_changes = [e.correction_direction_changes for e in click_aim_events]
    swirl_count = sum(1 for e in click_aim_events if e.is_swirl)
    swirl_pct = swirl_count / n * 100.0

    med_pct = median(pcts)
    reduction = min(
        med_pct * CORRECTION_FACTOR * _confidence_weight(n),
        MAX_REDUCTION_PCT,
    )

    return ClickAnalysisResult(
        total_clicks=total_clicks,
        analyzed_clicks=n,
        swirl_click_count=swirl_count,
        swirl_click_pct=swirl_pct,
        median_overshoot_pct=med_pct,
        mean_overshoot_pct=mean(pcts),
        median_correction_magnitude=median(corr_mags),
        median_correction_duration_ms=median(corr_durs),
        median_direction_changes=median(dir_changes),
        recommended_reduction_pct=reduction,
        overshoot_percentages=pcts,
    )


def _compute_rowing_axis(events: list[RowingEvent]) -> RowingAxisResult | None:
    if not events:
        return None
    n = len(events)
    chain_lengths = [e.chain_length for e in events]
    increase_ratios = [e.increase_ratio for e in events]
    gap_durations = [e.mean_gap_duration * 1000 for e in events]

    med_ratio = median(increase_ratios)
    increase_pct = (med_ratio - 1.0) * 100 * ROWING_CORRECTION_FACTOR * _confidence_weight(n)

    return RowingAxisResult(
        rowing_event_count=n,
        median_chain_length=median(chain_lengths),
        median_increase_ratio=med_ratio,
        mean_gap_duration_ms=mean(gap_durations),
        recommended_increase_pct=max(0.0, increase_pct),
    )


def _compute_fire_rate(
    click_times: list[float],
    session_duration: float,
    median_overshoot_pct: float,
) -> FireRateResult | None:
    if len(click_times) < 2 or session_duration <= 0:
        return None

    sorted_times = sorted(click_times)
    intervals = [
        (sorted_times[i] - sorted_times[i - 1]) * 1000  # ms
        for i in range(1, len(sorted_times))
    ]

    total_shots = len(sorted_times)
    shots_per_minute = total_shots / session_duration * 60.0
    aim_efficiency = max(0.0, min(1.0, 1.0 - median_overshoot_pct / 200.0))
    hit_factor = (shots_per_minute / 60.0) * aim_efficiency

    return FireRateResult(
        total_shots=total_shots,
        shots_per_minute=shots_per_minute,
        median_shot_interval_ms=median(intervals),
        mean_shot_interval_ms=mean(intervals),
        aim_efficiency=aim_efficiency,
        hit_factor=hit_factor,
    )


def _build_trend(
    current_result_fire_rate: FireRateResult | None,
    current_overshoot_pct: float,
    previous_session: dict | None,
    current_dpi: int,
    current_sens: float,
) -> TrendData | None:
    if previous_session is None:
        return None

    prev_fr = previous_session.get("fire_rate") or {}
    prev_hit_factor = prev_fr.get("hit_factor", 0.0)
    curr_hit_factor = current_result_fire_rate.hit_factor if current_result_fire_rate else 0.0

    prev_ca = previous_session.get("click_analysis", {})
    prev_overshoot = prev_ca.get("median_overshoot_pct", 0.0)

    prev_settings = previous_session.get("settings", {})
    prev_dpi = prev_settings.get("dpi", 0)
    prev_sens = prev_settings.get("sensitivity", 0.0)
    settings_changed = (prev_dpi != current_dpi or prev_sens != current_sens)

    if prev_hit_factor > 0:
        hit_factor_change = (curr_hit_factor - prev_hit_factor) / prev_hit_factor * 100.0
    else:
        hit_factor_change = 0.0

    return TrendData(
        prev_hit_factor=prev_hit_factor,
        curr_hit_factor=curr_hit_factor,
        hit_factor_change_pct=hit_factor_change,
        prev_overshoot_pct=prev_overshoot,
        curr_overshoot_pct=current_overshoot_pct,
        settings_changed=settings_changed,
    )


def _apply_trend_dampening(raw_pct: float, trend: TrendData | None) -> float:
    if trend is None:
        return raw_pct
    change = trend.hit_factor_change_pct
    if change > 10.0:
        return raw_pct * 0.15
    elif change > 5.0:
        return raw_pct * 0.50
    return raw_pct


def _resolve_recommendation(
    combined_reduction: float,
    combined_increase: float,
    possibly_too_low: bool,
    enough_clicks: bool,
    trend: TrendData | None,
    current_dpi: int,
    current_sens: float,
) -> UnifiedRecommendation:
    has_overshoot = enough_clicks and combined_reduction > 0.5
    has_rowing = possibly_too_low and combined_increase > 0.5

    improving = trend is not None and trend.hit_factor_change_pct > 10.0

    # Case 1: Both rowing + overshoot, but performance improving >10%
    if has_rowing and has_overshoot and improving:
        return UnifiedRecommendation(
            action="keep",
            reasoning="Both overshoot and rowing detected, but your performance is improving.",
            trend_note=(
                f"Hit factor improved {trend.hit_factor_change_pct:.0f}% "
                f"({trend.prev_hit_factor:.2f} -> {trend.curr_hit_factor:.2f}). "
                "Keep your current settings and keep practicing."
            ),
        )

    # Case 2: Both detected, not improving -> multi-step DPI-first approach
    if has_rowing and has_overshoot:
        if current_dpi < DPI_SWEET_SPOT_LOW:
            step1_dpi = _snap_dpi(DPI_SWEET_SPOT_LOW)
        elif current_dpi > DPI_SWEET_SPOT_HIGH:
            step1_dpi = _snap_dpi(DPI_SWEET_SPOT_HIGH)
        else:
            step1_dpi = _snap_dpi(current_dpi + DPI_STEP * 2)

        dampened_reduction = _apply_trend_dampening(combined_reduction, trend)
        step2_sens = current_sens * (1 - dampened_reduction / 100.0)

        note = ""
        if trend and trend.settings_changed:
            note = (f"Hit factor changed {trend.hit_factor_change_pct:+.0f}% "
                    f"since last session.")

        return UnifiedRecommendation(
            action="multi_step",
            primary_pct=0.0,
            new_sens=current_sens,
            new_dpi=step1_dpi,
            reasoning=(
                "Both overshoot and rowing detected. "
                "Try bumping your DPI first, then re-test to calibrate sensitivity."
            ),
            step2_action="reduce",
            step2_pct=dampened_reduction,
            step2_new_sens=step2_sens,
            step2_new_dpi=step1_dpi,
            trend_note=note,
        )

    # Case 3: Only rowing -> increase
    if has_rowing:
        dampened = _apply_trend_dampening(combined_increase, trend)
        new_sens = current_sens * (1 + dampened / 100.0)
        new_dpi = _snap_dpi(current_dpi * (1 + dampened / 100.0))
        note = ""
        if trend and trend.hit_factor_change_pct > 5.0:
            note = (f"Hit factor improved {trend.hit_factor_change_pct:.0f}%, "
                    f"so this recommendation is dampened.")
        return UnifiedRecommendation(
            action="increase",
            primary_pct=dampened,
            new_sens=new_sens,
            new_dpi=new_dpi,
            reasoning="Rowing detected — sensitivity appears too low.",
            trend_note=note,
        )

    # Case 4: Only overshoot -> reduce
    if has_overshoot:
        dampened = _apply_trend_dampening(combined_reduction, trend)
        new_sens = current_sens * (1 - dampened / 100.0)
        new_dpi = _snap_dpi(current_dpi * (1 - dampened / 100.0))
        note = ""
        if trend and trend.hit_factor_change_pct > 5.0:
            note = (f"Hit factor improved {trend.hit_factor_change_pct:.0f}%, "
                    f"so this recommendation is dampened.")
        return UnifiedRecommendation(
            action="reduce",
            primary_pct=dampened,
            new_sens=new_sens,
            new_dpi=new_dpi,
            reasoning="Overshoot detected on flick shots.",
            trend_note=note,
        )

    # Case 5: Neither significant
    note = ""
    if trend and trend.hit_factor_change_pct > 5.0:
        note = (f"Hit factor improved {trend.hit_factor_change_pct:.0f}% "
                f"— nice progress!")
    return UnifiedRecommendation(
        action="keep",
        reasoning="No significant overshoot or rowing detected.",
        trend_note=note,
    )


def analyze(
    click_aim_events: list[ClickAimEvent],
    total_clicks: int,
    session_duration: float,
    total_samples: int,
    current_dpi: int,
    current_sens: float,
    rowing_events: list[RowingEvent] | None = None,
    movement_sample_count: int = 0,
    click_times: list[float] | None = None,
    previous_session: dict | None = None,
) -> AnalysisResult:
    # Click-centric analysis
    click_analysis = _compute_click_analysis(click_aim_events, total_clicks)

    combined_reduction = click_analysis.recommended_reduction_pct

    # Movement contamination
    contamination = (movement_sample_count / total_samples * 100.0) if total_samples > 0 else 0.0

    # Rowing analysis
    if rowing_events is None:
        rowing_events = []
    x_rowing_events = [e for e in rowing_events if e.axis == "x"]
    y_rowing_events = [e for e in rowing_events if e.axis == "y"]
    x_rowing = _compute_rowing_axis(x_rowing_events)
    y_rowing = _compute_rowing_axis(y_rowing_events)

    x_inc = x_rowing.recommended_increase_pct if x_rowing else 0.0
    y_inc = y_rowing.recommended_increase_pct if y_rowing else 0.0
    if x_inc > 0 or y_inc > 0:
        combined_increase = (x_inc * X_WEIGHT + y_inc * Y_WEIGHT) / (X_WEIGHT + Y_WEIGHT)
    else:
        combined_increase = 0.0

    total_rowing = len(rowing_events)
    possibly_too_low = total_rowing >= MIN_ROWING_EVENTS_FOR_RECOMMENDATION

    # Compute new settings (overshoot reduction — raw, for history)
    new_sens_combined = current_sens * (1 - combined_reduction / 100.0)
    new_dpi_combined = _snap_dpi(current_dpi * (1 - combined_reduction / 100.0))

    # Compute new settings (rowing increase — raw, for history)
    new_sens_increase = current_sens * (1 + combined_increase / 100.0)
    new_dpi_increase = _snap_dpi(current_dpi * (1 + combined_increase / 100.0))

    # Fire rate / hit factor
    fire_rate = None
    if click_times:
        fire_rate = _compute_fire_rate(
            click_times, session_duration, click_analysis.median_overshoot_pct,
        )

    # DPI advisory
    dpi_advisory, suggested_dpi, dpi_level = _compute_dpi_advisory(current_dpi)

    # Build trend data from previous session
    trend = _build_trend(
        fire_rate, click_analysis.median_overshoot_pct,
        previous_session, current_dpi, current_sens,
    )

    # Resolve unified recommendation
    enough_clicks = click_analysis.analyzed_clicks >= MIN_EVENTS_FOR_RECOMMENDATION
    recommendation = _resolve_recommendation(
        combined_reduction, combined_increase, possibly_too_low,
        enough_clicks, trend, current_dpi, current_sens,
    )

    return AnalysisResult(
        session_duration=session_duration,
        total_samples=total_samples,
        current_dpi=current_dpi,
        current_sens=current_sens,
        click_analysis=click_analysis,
        combined_reduction_pct=combined_reduction,
        new_sens_combined=new_sens_combined,
        new_dpi_combined=new_dpi_combined,
        possibly_too_low=possibly_too_low,
        fire_rate=fire_rate,
        x_rowing=x_rowing,
        y_rowing=y_rowing,
        combined_increase_pct=combined_increase,
        new_sens_increase=new_sens_increase,
        new_dpi_increase=new_dpi_increase,
        movement_contamination_pct=contamination,
        dpi_advisory=dpi_advisory,
        suggested_dpi=suggested_dpi,
        dpi_advisory_level=dpi_level,
        recommendation=recommendation,
        trend=trend,
    )
