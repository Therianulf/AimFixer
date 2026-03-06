from dataclasses import dataclass
from statistics import median, mean
from detector import OvershootEvent
from config import (
    CORRECTION_FACTOR, MIN_EVENTS_FOR_RECOMMENDATION,
    X_WEIGHT, Y_WEIGHT, DPI_STEP,
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


def analyze(
    events: list[OvershootEvent],
    flick_counts: dict[str, int],
    session_duration: float,
    total_samples: int,
    current_dpi: int,
    current_sens: float,
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

    # Check if sensitivity might be too low
    total_flicks = flick_counts.get("x", 0) + flick_counts.get("y", 0)
    total_overshoots = x_result.overshoot_count + y_result.overshoot_count
    possibly_too_low = (
        total_flicks >= 20 and
        (total_overshoots / total_flicks if total_flicks > 0 else 0) < 0.05
    )

    # Compute new settings
    new_sens_combined = current_sens * (1 - combined / 100.0)
    new_dpi_combined = _snap_dpi(current_dpi * (1 - combined / 100.0))
    new_sens_x = current_sens * (1 - x_result.recommended_reduction_pct / 100.0)
    new_sens_y = current_sens * (1 - y_result.recommended_reduction_pct / 100.0)

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
    )
