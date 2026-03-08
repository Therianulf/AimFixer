from __future__ import annotations
from dataclasses import dataclass, field
from statistics import median, mean
from detector import OvershootEvent, RowingEvent
from config import (
    CORRECTION_FACTOR, MIN_EVENTS_FOR_RECOMMENDATION,
    X_WEIGHT, Y_WEIGHT, DPI_STEP,
    ROWING_CORRECTION_FACTOR, MIN_ROWING_EVENTS_FOR_RECOMMENDATION,
)


@dataclass
class AxisResult:
    axis: str
    overshoot_count: int
    flick_count: int
    median_overshoot_pct: float
    mean_overshoot_pct: float
    p75_overshoot_pct: float
    recommended_reduction_pct: float
    overshoot_percentages: list[float]


@dataclass
class RowingAxisResult:
    rowing_event_count: int
    median_chain_length: float
    median_increase_ratio: float
    mean_gap_duration_ms: float
    recommended_increase_pct: float


@dataclass
class AnalysisResult:
    session_duration: float
    total_samples: int
    x_result: AxisResult
    y_result: AxisResult
    combined_reduction_pct: float
    # Computed recommendations using user's settings
    current_dpi: int
    current_sens: float
    new_sens_combined: float
    new_dpi_combined: int
    new_sens_x: float
    new_sens_y: float
    possibly_too_low: bool
    x_rowing: RowingAxisResult | None = None
    y_rowing: RowingAxisResult | None = None
    combined_increase_pct: float = 0.0
    new_sens_increase: float = 0.0
    new_dpi_increase: int = 0


def _confidence_weight(n_events: int) -> float:
    return min(1.0, 0.5 + 0.5 * (n_events / 50))


def _sorted_percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * p / 100.0)
    idx = min(idx, len(sorted_v) - 1)
    return sorted_v[idx]


def _snap_dpi(dpi: float) -> int:
    return max(DPI_STEP, round(dpi / DPI_STEP) * DPI_STEP)


def _compute_axis(events: list[OvershootEvent], flick_count: int, axis: str) -> AxisResult:
    percentages = [e.overshoot_percentage for e in events]
    n = len(percentages)

    if n == 0:
        return AxisResult(
            axis=axis, overshoot_count=0, flick_count=flick_count,
            median_overshoot_pct=0.0, mean_overshoot_pct=0.0,
            p75_overshoot_pct=0.0, recommended_reduction_pct=0.0,
            overshoot_percentages=[],
        )

    med = median(percentages)
    avg = mean(percentages)
    p75 = _sorted_percentile(percentages, 75)
    reduction = med * CORRECTION_FACTOR * _confidence_weight(n)

    return AxisResult(
        axis=axis, overshoot_count=n, flick_count=flick_count,
        median_overshoot_pct=med, mean_overshoot_pct=avg,
        p75_overshoot_pct=p75, recommended_reduction_pct=reduction,
        overshoot_percentages=percentages,
    )


def _compute_rowing_axis(events: list[RowingEvent]) -> RowingAxisResult | None:
    if not events:
        return None
    n = len(events)
    chain_lengths = [e.chain_length for e in events]
    increase_ratios = [e.increase_ratio for e in events]
    gap_durations = [e.mean_gap_duration * 1000 for e in events]  # to ms

    med_ratio = median(increase_ratios)
    increase_pct = (med_ratio - 1.0) * 100 * ROWING_CORRECTION_FACTOR * _confidence_weight(n)

    return RowingAxisResult(
        rowing_event_count=n,
        median_chain_length=median(chain_lengths),
        median_increase_ratio=med_ratio,
        mean_gap_duration_ms=mean(gap_durations),
        recommended_increase_pct=max(0.0, increase_pct),
    )


def analyze(
    events: list[OvershootEvent],
    flick_counts: dict[str, int],
    session_duration: float,
    total_samples: int,
    current_dpi: int,
    current_sens: float,
    rowing_events: list[RowingEvent] | None = None,
) -> AnalysisResult:
    x_events = [e for e in events if e.axis == "x"]
    y_events = [e for e in events if e.axis == "y"]

    x_result = _compute_axis(x_events, flick_counts.get("x", 0), "x")
    y_result = _compute_axis(y_events, flick_counts.get("y", 0), "y")

    # Combined reduction (X weighted more heavily)
    if x_result.recommended_reduction_pct > 0 or y_result.recommended_reduction_pct > 0:
        combined = (
            x_result.recommended_reduction_pct * X_WEIGHT +
            y_result.recommended_reduction_pct * Y_WEIGHT
        ) / (X_WEIGHT + Y_WEIGHT)
    else:
        combined = 0.0

    # Rowing analysis
    if rowing_events is None:
        rowing_events = []
    x_rowing_events = [e for e in rowing_events if e.axis == "x"]
    y_rowing_events = [e for e in rowing_events if e.axis == "y"]
    x_rowing = _compute_rowing_axis(x_rowing_events)
    y_rowing = _compute_rowing_axis(y_rowing_events)

    # Combined rowing increase recommendation
    x_inc = x_rowing.recommended_increase_pct if x_rowing else 0.0
    y_inc = y_rowing.recommended_increase_pct if y_rowing else 0.0
    if x_inc > 0 or y_inc > 0:
        combined_increase = (x_inc * X_WEIGHT + y_inc * Y_WEIGHT) / (X_WEIGHT + Y_WEIGHT)
    else:
        combined_increase = 0.0

    total_rowing = len(rowing_events)
    possibly_too_low = total_rowing >= MIN_ROWING_EVENTS_FOR_RECOMMENDATION

    # Compute new settings (overshoot reduction)
    new_sens_combined = current_sens * (1 - combined / 100.0)
    new_dpi_combined = _snap_dpi(current_dpi * (1 - combined / 100.0))
    new_sens_x = current_sens * (1 - x_result.recommended_reduction_pct / 100.0)
    new_sens_y = current_sens * (1 - y_result.recommended_reduction_pct / 100.0)

    # Compute new settings (rowing increase)
    new_sens_increase = current_sens * (1 + combined_increase / 100.0)
    new_dpi_increase = _snap_dpi(current_dpi * (1 + combined_increase / 100.0))

    return AnalysisResult(
        session_duration=session_duration,
        total_samples=total_samples,
        x_result=x_result,
        y_result=y_result,
        combined_reduction_pct=combined,
        current_dpi=current_dpi,
        current_sens=current_sens,
        new_sens_combined=new_sens_combined,
        new_dpi_combined=new_dpi_combined,
        new_sens_x=new_sens_x,
        new_sens_y=new_sens_y,
        possibly_too_low=possibly_too_low,
        x_rowing=x_rowing,
        y_rowing=y_rowing,
        combined_increase_pct=combined_increase,
        new_sens_increase=new_sens_increase,
        new_dpi_increase=new_dpi_increase,
    )
