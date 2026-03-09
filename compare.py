"""Multi-session history comparison and aggregate recommendation."""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

import matplotlib
matplotlib.use("macosx")
import matplotlib.pyplot as plt

from config import (
    CORRECTION_FACTOR, MAX_REDUCTION_PCT,
    MIN_ANALYZED_CLICKS_FOR_HISTORY, MIN_SESSION_DURATION_FOR_HISTORY,
    GAME_DISPLAY_NAMES,
)
from analyzer import _confidence_weight, _snap_dpi
from history import load_all_sessions


@dataclass
class AggregateStats:
    session_count: int = 0
    total_analyzed_clicks: int = 0
    weighted_median_overshoot_pct: float = 0.0
    weighted_median_correction_mag: float = 0.0
    weighted_median_correction_dur_ms: float = 0.0
    weighted_median_direction_changes: float = 0.0
    weighted_median_swirl_pct: float = 0.0
    median_hit_factor: float = 0.0
    median_aim_efficiency: float = 0.0
    median_spm: float = 0.0
    rowing_total: int = 0
    # Per-session lists for trend charts
    per_session_overshoot: list[float] = field(default_factory=list)
    per_session_hit_factor: list[float] = field(default_factory=list)
    per_session_clicks: list[int] = field(default_factory=list)
    per_session_timestamps: list[str] = field(default_factory=list)


def _load_and_filter_sessions() -> tuple[list[dict], int]:
    """Load all sessions, drop those with too few analyzed clicks."""
    all_sessions = load_all_sessions()
    filtered = []
    dropped = 0
    for s in all_sessions:
        ca = s.get("click_analysis", {})
        duration = s.get("session_duration_s", 0.0)
        if (ca.get("analyzed_clicks", 0) <= MIN_ANALYZED_CLICKS_FOR_HISTORY
                or duration < MIN_SESSION_DURATION_FOR_HISTORY
                or s.get("fire_rate") is None):
            dropped += 1
        else:
            filtered.append(s)
    return filtered, dropped


def _group_by_settings(sessions: list[dict]) -> dict[tuple[str, int, float], list[dict]]:
    """Group sessions by (game, dpi, sensitivity) tuple."""
    groups: dict[tuple[str, int, float], list[dict]] = {}
    for s in sessions:
        settings = s.get("settings", {})
        game = settings.get("game", "unknown")
        key = (game, settings.get("dpi", 0), settings.get("sensitivity", 0.0))
        groups.setdefault(key, []).append(s)
    return groups


def _weighted_median(sessions: list[dict], field_path: str) -> float:
    """Compute weighted median: each session's value expanded by its click count."""
    expanded: list[float] = []
    for s in sessions:
        ca = s.get("click_analysis", {})
        clicks = ca.get("analyzed_clicks", 1)
        # Navigate field_path like "click_analysis.median_overshoot_pct"
        parts = field_path.split(".")
        val = s
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, 0.0)
            else:
                val = 0.0
                break
        if val is None:
            val = 0.0
        expanded.extend([float(val)] * clicks)
    return median(expanded) if expanded else 0.0


def _compute_aggregate(sessions: list[dict]) -> AggregateStats:
    """Compute aggregate stats for a group of sessions."""
    stats = AggregateStats()
    stats.session_count = len(sessions)
    stats.total_analyzed_clicks = sum(
        s.get("click_analysis", {}).get("analyzed_clicks", 0) for s in sessions
    )

    stats.weighted_median_overshoot_pct = _weighted_median(
        sessions, "click_analysis.median_overshoot_pct"
    )
    stats.weighted_median_correction_mag = _weighted_median(
        sessions, "click_analysis.median_correction_magnitude"
    )
    stats.weighted_median_correction_dur_ms = _weighted_median(
        sessions, "click_analysis.median_correction_duration_ms"
    )
    stats.weighted_median_direction_changes = _weighted_median(
        sessions, "click_analysis.median_direction_changes"
    )
    stats.weighted_median_swirl_pct = _weighted_median(
        sessions, "click_analysis.swirl_click_pct"
    )

    # Fire rate medians (simple median, not click-weighted)
    hit_factors = []
    aim_effs = []
    spms = []
    for s in sessions:
        fr = s.get("fire_rate")
        if fr:
            hit_factors.append(fr.get("hit_factor", 0.0))
            aim_effs.append(fr.get("aim_efficiency", 0.0))
            spms.append(fr.get("shots_per_minute", 0.0))
    stats.median_hit_factor = median(hit_factors) if hit_factors else 0.0
    stats.median_aim_efficiency = median(aim_effs) if aim_effs else 0.0
    stats.median_spm = median(spms) if spms else 0.0

    # Rowing total
    for s in sessions:
        rowing = s.get("rowing", {})
        stats.rowing_total += rowing.get("x_events", 0) + rowing.get("y_events", 0)

    # Per-session lists for charts
    for s in sessions:
        ca = s.get("click_analysis", {})
        fr = s.get("fire_rate") or {}
        stats.per_session_overshoot.append(ca.get("median_overshoot_pct", 0.0))
        stats.per_session_hit_factor.append(fr.get("hit_factor", 0.0))
        stats.per_session_clicks.append(ca.get("analyzed_clicks", 0))
        stats.per_session_timestamps.append(s.get("timestamp", ""))

    return stats


def _compute_aggregate_recommendation(
    stats: AggregateStats,
    dpi: int,
    sens: float,
) -> dict:
    """Compute recommendation from aggregate stats. No trend dampening."""
    overshoot = stats.weighted_median_overshoot_pct
    total_clicks = stats.total_analyzed_clicks

    raw_reduction = min(
        overshoot * CORRECTION_FACTOR * _confidence_weight(total_clicks),
        MAX_REDUCTION_PCT,
    )

    rowing_significant = stats.rowing_total >= 8
    has_overshoot = raw_reduction > 0.5

    if has_overshoot and rowing_significant:
        # Mixed signal — recommend reduce (overshoot usually more actionable)
        new_sens = sens * (1 - raw_reduction / 100.0)
        return {
            "action": "mixed",
            "reduction_pct": raw_reduction,
            "new_sens": new_sens,
            "new_dpi": _snap_dpi(dpi * (1 - raw_reduction / 100.0)),
            "note": "Both overshoot and rowing detected across sessions.",
        }
    elif has_overshoot:
        new_sens = sens * (1 - raw_reduction / 100.0)
        return {
            "action": "reduce",
            "reduction_pct": raw_reduction,
            "new_sens": new_sens,
            "new_dpi": _snap_dpi(dpi * (1 - raw_reduction / 100.0)),
            "note": "",
        }
    elif rowing_significant:
        return {
            "action": "increase",
            "reduction_pct": 0.0,
            "new_sens": sens,
            "new_dpi": dpi,
            "note": "Rowing detected — sensitivity may be too low.",
        }
    else:
        return {
            "action": "keep",
            "reduction_pct": 0.0,
            "new_sens": sens,
            "new_dpi": dpi,
            "note": "Your settings look well-tuned across sessions.",
        }


def _print_history_report(
    filtered: list[dict],
    dropped_count: int,
    groups: dict[tuple[str, int, float], list[dict]],
    aggregates: dict[tuple[str, int, float], AggregateStats],
    most_recent_key: tuple[str, int, float],
):
    total_loaded = len(filtered) + dropped_count
    print()
    print("=" * 50)
    print("  AimFixer Session History")
    print("=" * 50)
    print(f"  Sessions loaded:    {total_loaded}")
    if dropped_count > 0:
        print(f"  Sessions dropped:   {dropped_count} (<={MIN_ANALYZED_CLICKS_FOR_HISTORY} clicks or <{MIN_SESSION_DURATION_FOR_HISTORY:.0f}s)")
    print()

    for key, sessions in groups.items():
        game, dpi, sens = key
        game_display = GAME_DISPLAY_NAMES.get(game, game.replace("_", " ").title())
        stats = aggregates[key]
        print("-" * 50)
        print(f"  {game_display} @ {dpi} DPI / {sens} sens  ({stats.session_count} sessions, {stats.total_analyzed_clicks} clicks)")
        print("-" * 50)
        print(f"  Median overshoot:      {stats.weighted_median_overshoot_pct:.1f}%")
        print(f"  Median correction:     {stats.weighted_median_correction_mag:.1f}px over {stats.weighted_median_correction_dur_ms:.0f}ms")
        print(f"  Swirl rate:            {stats.weighted_median_swirl_pct:.1f}%")
        if stats.median_hit_factor > 0:
            print(f"  Median hit factor:     {stats.median_hit_factor:.2f}")
        if stats.median_spm > 0:
            print(f"  Median fire rate:      {stats.median_spm:.0f} spm")
        if stats.rowing_total > 0:
            print(f"  Rowing events:         {stats.rowing_total}")
        print()
        print("  Session breakdown:")
        for s in sessions:
            ts = s.get("timestamp", "?")
            # Show just the date portion
            date_str = ts[:10] if len(ts) >= 10 else ts
            ca = s.get("click_analysis", {})
            clicks = ca.get("analyzed_clicks", 0)
            overshoot = ca.get("median_overshoot_pct", 0.0)
            fr = s.get("fire_rate") or {}
            hf = fr.get("hit_factor", 0.0)
            hf_str = f"  HF {hf:.2f}" if hf > 0 else ""
            print(f"    {date_str}  {clicks:>3} clicks  {overshoot:>5.1f}% overshoot{hf_str}")
        print()

    # Recommendation for most recent group
    game, dpi, sens = most_recent_key
    game_display = GAME_DISPLAY_NAMES.get(game, game.replace("_", " ").title())
    stats = aggregates[most_recent_key]
    rec = _compute_aggregate_recommendation(stats, dpi, sens)

    print("-" * 50)
    print(f"  RECOMMENDATION ({game_display} @ {dpi} DPI / {sens} sens)")
    print("-" * 50)
    print(f"  Based on {stats.total_analyzed_clicks} clicks across {stats.session_count} sessions:")

    if rec["action"] == "reduce":
        print(f"  Reduce in-game sensitivity by ~{rec['reduction_pct']:.0f}%")
        print(f"    {sens} -> {rec['new_sens']:.2f}")
    elif rec["action"] == "increase":
        print(f"  {rec['note']}")
    elif rec["action"] == "mixed":
        print(f"  Reduce in-game sensitivity by ~{rec['reduction_pct']:.0f}%")
        print(f"    {sens} -> {rec['new_sens']:.2f}")
        print(f"  Note: {rec['note']}")
    elif rec["action"] == "keep":
        print(f"  {rec['note']}")

    print("=" * 50)


def _show_history_charts(
    groups: dict[tuple[str, int, float], list[dict]],
    aggregates: dict[tuple[str, int, float], AggregateStats],
):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("AimFixer Session History", fontsize=14, fontweight="bold")

    # Assign colors per settings group
    colors = ["#4a90d9", "#e8913a", "#2ecc71", "#9b59b6", "#e74c3c"]
    group_keys = list(groups.keys())

    session_idx = 0
    for gi, key in enumerate(group_keys):
        game, dpi, sens = key
        game_display = GAME_DISPLAY_NAMES.get(game, game.replace("_", " ").title())
        stats = aggregates[key]
        color = colors[gi % len(colors)]
        label = f"{game_display} @ {dpi} DPI / {sens}"
        n = stats.session_count

        xs = list(range(session_idx, session_idx + n))
        # Scale dot sizes: min 30, proportional to clicks
        sizes = [max(30, c * 0.5) for c in stats.per_session_clicks]

        ax1.scatter(xs, stats.per_session_overshoot, c=color, s=sizes,
                    alpha=0.7, label=label, edgecolors="white", linewidth=0.5)
        ax2.scatter(xs, stats.per_session_hit_factor, c=color, s=sizes,
                    alpha=0.7, label=label, edgecolors="white", linewidth=0.5)

        session_idx += n

    ax1.set_title("Overshoot % Over Sessions")
    ax1.set_xlabel("Session")
    ax1.set_ylabel("Median Overshoot %")
    ax1.legend(fontsize=8)

    ax2.set_title("Hit Factor Over Sessions")
    ax2.set_xlabel("Session")
    ax2.set_ylabel("Hit Factor")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.canvas.manager.set_window_title("AimFixer History")
    plt.show()


def run_history_comparison():
    """Entry point for `python aimfixer.py history`."""
    filtered, dropped_count = _load_and_filter_sessions()

    if not filtered:
        print()
        print("=" * 50)
        print("  AimFixer Session History")
        print("=" * 50)
        total = len(load_all_sessions())
        if total == 0:
            print("  No saved sessions found.")
        else:
            print(f"  All {total} sessions had <={MIN_ANALYZED_CLICKS_FOR_HISTORY} analyzed clicks.")
        print("=" * 50)
        return

    groups = _group_by_settings(filtered)
    aggregates = {key: _compute_aggregate(sessions) for key, sessions in groups.items()}

    # Find the group containing the most recent session
    most_recent_key = None
    most_recent_ts = ""
    for key, sessions in groups.items():
        for s in sessions:
            ts = s.get("timestamp", "")
            if ts > most_recent_ts:
                most_recent_ts = ts
                most_recent_key = key

    _print_history_report(filtered, dropped_count, groups, aggregates, most_recent_key)
    _show_history_charts(groups, aggregates)
