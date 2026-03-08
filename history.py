"""Session persistence — saves JSON summary + JSONL events per run."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from analyzer import AnalysisResult
from detector import ClickAimEvent, RowingEvent


def _sessions_dir() -> Path:
    d = Path(__file__).resolve().parent / "sessions"
    d.mkdir(exist_ok=True)
    return d


def _timestamp_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def save_session(
    result: AnalysisResult,
    click_aim_events: list[ClickAimEvent],
    rowing_events: list[RowingEvent],
    click_times: list[float],
) -> Path:
    prefix = _timestamp_prefix()
    sessions = _sessions_dir()

    # Determine session start for relative timestamps
    t0 = click_times[0] if click_times else 0.0

    # --- Summary JSON ---
    ca = result.click_analysis
    summary = {
        "timestamp": prefix,
        "session_duration_s": round(result.session_duration, 2),
        "total_samples": result.total_samples,
        "settings": {
            "dpi": result.current_dpi,
            "sensitivity": result.current_sens,
        },
        "click_analysis": {
            "total_clicks": ca.total_clicks,
            "analyzed_clicks": ca.analyzed_clicks,
            "swirl_click_count": ca.swirl_click_count,
            "swirl_click_pct": round(ca.swirl_click_pct, 1),
            "median_overshoot_pct": round(ca.median_overshoot_pct, 1),
            "mean_overshoot_pct": round(ca.mean_overshoot_pct, 1),
            "median_correction_magnitude": round(ca.median_correction_magnitude, 1),
            "median_correction_duration_ms": round(ca.median_correction_duration_ms, 1),
            "median_direction_changes": round(ca.median_direction_changes, 1),
        },
        "fire_rate": None,
        "rowing": {
            "x_events": result.x_rowing.rowing_event_count if result.x_rowing else 0,
            "y_events": result.y_rowing.rowing_event_count if result.y_rowing else 0,
            "possibly_too_low": result.possibly_too_low,
        },
        "recommendations": {
            "reduction_pct": round(result.combined_reduction_pct, 1),
            "new_sens": round(result.new_sens_combined, 2),
            "new_dpi": result.new_dpi_combined,
            "increase_pct": round(result.combined_increase_pct, 1),
            "dpi_advisory": result.dpi_advisory,
            "suggested_dpi": result.suggested_dpi,
        },
    }

    if result.fire_rate:
        fr = result.fire_rate
        summary["fire_rate"] = {
            "total_shots": fr.total_shots,
            "shots_per_minute": round(fr.shots_per_minute, 1),
            "median_shot_interval_ms": round(fr.median_shot_interval_ms, 1),
            "mean_shot_interval_ms": round(fr.mean_shot_interval_ms, 1),
            "aim_efficiency": round(fr.aim_efficiency, 3),
            "hit_factor": round(fr.hit_factor, 3),
        }

    summary_path = sessions / f"{prefix}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    # --- Events JSONL ---
    events_path = sessions / f"{prefix}_events.jsonl"
    with events_path.open("w") as f:
        for e in click_aim_events:
            line = {
                "type": "click_aim",
                "click_time": round(e.click_time - t0, 4),
                "approach_peak_velocity": round(e.approach_peak_velocity, 1),
                "approach_displacement": round(e.approach_displacement, 1),
                "approach_duration": round(e.approach_duration, 4),
                "correction_magnitude": round(e.correction_magnitude, 1),
                "correction_direction_changes": e.correction_direction_changes,
                "correction_angle_rotation": round(e.correction_angle_rotation, 3),
                "correction_duration": round(e.correction_duration, 4),
                "overshoot_percentage": round(e.overshoot_percentage, 1),
                "is_swirl": e.is_swirl,
            }
            f.write(json.dumps(line) + "\n")

        for e in rowing_events:
            line = {
                "type": "rowing",
                "axis": e.axis,
                "chain_length": e.chain_length,
                "total_displacement": round(e.total_displacement, 1),
                "max_single_displacement": round(e.max_single_displacement, 1),
                "increase_ratio": round(e.increase_ratio, 2),
                "gap_durations": [round(g, 4) for g in e.gap_durations],
                "mean_gap_duration": round(e.mean_gap_duration, 4),
                "timestamp": round(e.timestamp - t0, 4),
            }
            f.write(json.dumps(line) + "\n")

    return summary_path


def load_previous_session() -> dict | None:
    sessions = _sessions_dir()
    summaries = sorted(sessions.glob("*_summary.json"))
    # Need at least 2 (current + previous)
    if len(summaries) < 2:
        return None
    # Second-to-last is the previous session
    prev_path = summaries[-2]
    try:
        return json.loads(prev_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
