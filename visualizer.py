import matplotlib.pyplot as plt
from analyzer import AnalysisResult
from config import MIN_EVENTS_FOR_RECOMMENDATION, MIN_ROWING_EVENTS_FOR_RECOMMENDATION


def print_summary(result: AnalysisResult):
    duration_m = int(result.session_duration // 60)
    duration_s = int(result.session_duration % 60)

    ca = result.click_analysis

    print("\n" + "=" * 50)
    print("  AimFixer Results")
    print("=" * 50)
    print(f"  Session duration:    {duration_m}m {duration_s}s")
    print(f"  Samples collected:   {result.total_samples:,}")
    print(f"  Current settings:    {result.current_dpi} DPI / {result.current_sens} in-game sens")

    # Click-centric stats
    print()
    print(f"  Shots fired:         {ca.total_clicks}")
    print(f"  Shots analyzed:      {ca.analyzed_clicks}")
    if ca.analyzed_clicks > 0:
        print(f"  Swirl corrections:   {ca.swirl_click_count} ({ca.swirl_click_pct:.0f}% of shots)")
        print(f"  Median overshoot:    {ca.median_overshoot_pct:.1f}%")
        print(f"  Mean overshoot:      {ca.mean_overshoot_pct:.1f}%")
        print(f"  Median correction:   {ca.median_correction_magnitude:.1f}px over {ca.median_correction_duration_ms:.0f}ms")
        print(f"  Median dir changes:  {ca.median_direction_changes:.0f} per shot")

    # Rowing stats
    _print_rowing(result)

    # Movement contamination warning
    if result.movement_contamination_pct > 0:
        print()
        if result.movement_contamination_pct > 20:
            print(f"  WARNING: {result.movement_contamination_pct:.1f}% of samples were")
            print("  collected during character movement.")
            print("  Results may be unreliable. Re-record")
            print("  while standing still for best results.")
        else:
            print(f"  Note: {result.movement_contamination_pct:.1f}% of samples were")
            print("  collected during character movement.")

    print()
    print("-" * 50)

    enough = ca.analyzed_clicks >= MIN_EVENTS_FOR_RECOMMENDATION
    if not enough and not result.possibly_too_low:
        print("  Not enough aim events for a reliable")
        print("  recommendation. Try a longer session with")
        print("  more flick shots.")
        print("=" * 50)
        return

    print("  RECOMMENDATION")
    print("-" * 50)

    if result.possibly_too_low and result.combined_increase_pct > 0.5:
        print(f"  Sensitivity too LOW - rowing detected!")
        print(f"  Increase overall sensitivity by ~{result.combined_increase_pct:.0f}%")
        print()
        print(f"  Option A - Adjust in-game sens only:")
        print(f"    {result.current_sens} -> {result.new_sens_increase:.2f}")
        print()
        print(f"  Option B - Adjust DPI only:")
        print(f"    {result.current_dpi} -> {result.new_dpi_increase}")
        print()
    elif result.possibly_too_low:
        print("  NOTE: Rowing detected. Your sensitivity might")
        print("  be too LOW. Consider increasing by 5-10%.")
        print()

    if result.combined_reduction_pct > 0.5:
        print(f"  Reduce overall sensitivity by ~{result.combined_reduction_pct:.0f}%")
        print()
        print(f"  Option A - Adjust in-game sens only:")
        print(f"    {result.current_sens} -> {result.new_sens_combined:.2f}")
        print()
        print(f"  Option B - Adjust DPI only:")
        print(f"    {result.current_dpi} -> {result.new_dpi_combined}")
    elif not result.possibly_too_low:
        print("  Your sensitivity looks well-tuned!")
        print("  No significant overshoot detected.")

    print("=" * 50)


def _print_rowing(result: AnalysisResult):
    x_r = result.x_rowing
    y_r = result.y_rowing
    total = (x_r.rowing_event_count if x_r else 0) + (y_r.rowing_event_count if y_r else 0)
    if total == 0:
        return

    print()
    print(f"  Rowing (mouse-lift) Events:")
    if x_r and x_r.rowing_event_count > 0:
        print(f"    X-axis: {x_r.rowing_event_count} events, "
              f"median chain: {x_r.median_chain_length:.0f} sweeps, "
              f"avg gap: {x_r.mean_gap_duration_ms:.0f}ms")
    if y_r and y_r.rowing_event_count > 0:
        print(f"    Y-axis: {y_r.rowing_event_count} events, "
              f"median chain: {y_r.median_chain_length:.0f} sweeps, "
              f"avg gap: {y_r.mean_gap_duration_ms:.0f}ms")


def show_charts(result: AnalysisResult, click_aim_events, rowing_events=None):
    if rowing_events is None:
        rowing_events = []

    ca = result.click_analysis

    fig, axes = plt.subplots(3, 2, figsize=(12, 14))
    fig.suptitle("AimFixer Analysis", fontsize=14, fontweight="bold")

    # Panel 1: Click overshoot % histogram
    ax = axes[0][0]
    pcts = ca.overshoot_percentages
    if pcts:
        ax.hist(pcts, bins=20, color="#4a90d9", edgecolor="white", alpha=0.85)
        ax.axvline(ca.median_overshoot_pct, color="red",
                   linestyle="--", label=f"Median: {ca.median_overshoot_pct:.1f}%")
        ax.legend()
    ax.set_title("Overshoot % per Shot")
    ax.set_xlabel("Overshoot %")
    ax.set_ylabel("Count")

    # Panel 2: Correction magnitude per shot (colored by swirl vs clean)
    ax = axes[0][1]
    if click_aim_events:
        mags = [e.correction_magnitude for e in click_aim_events]
        colors = ["#9b59b6" if e.is_swirl else "#2ecc71" for e in click_aim_events]
        ax.bar(range(len(mags)), mags, color=colors, alpha=0.85)
        # Legend
        ax.bar([], [], color="#9b59b6", label="Swirl")
        ax.bar([], [], color="#2ecc71", label="Clean")
        ax.legend()
    ax.set_title("Correction Magnitude per Shot")
    ax.set_xlabel("Shot #")
    ax.set_ylabel("Correction (px)")

    # Panel 3: Correction duration vs overshoot % scatter
    ax = axes[1][0]
    if click_aim_events:
        durations = [e.correction_duration * 1000 for e in click_aim_events]
        overshoots = [e.overshoot_percentage for e in click_aim_events]
        colors = ["#9b59b6" if e.is_swirl else "#2ecc71" for e in click_aim_events]
        ax.scatter(durations, overshoots, c=colors, alpha=0.6, s=30)
        ax.scatter([], [], c="#9b59b6", label="Swirl")
        ax.scatter([], [], c="#2ecc71", label="Clean")
        ax.legend()
    ax.set_title("Correction Duration vs Overshoot")
    ax.set_xlabel("Correction Duration (ms)")
    ax.set_ylabel("Overshoot %")

    # Panel 4: Direction changes per shot histogram
    ax = axes[1][1]
    if click_aim_events:
        dir_changes = [e.correction_direction_changes for e in click_aim_events]
        max_dc = max(dir_changes) if dir_changes else 0
        bins = range(0, max(max_dc + 2, 3))
        ax.hist(dir_changes, bins=bins, color="#e8913a", edgecolor="white", alpha=0.85, align="left")
    ax.set_title("Direction Changes per Shot")
    ax.set_xlabel("Direction Changes")
    ax.set_ylabel("Count")

    # Panel 5: Rowing chain length histogram
    ax = axes[2][0]
    if rowing_events:
        chain_lengths = [e.chain_length for e in rowing_events]
        colors = ["#4a90d9" if e.axis == "x" else "#e8913a" for e in rowing_events]
        ax.bar(range(len(chain_lengths)), chain_lengths, color=colors, alpha=0.85)
        ax.axhline(y=2, color="gray", linestyle="--", alpha=0.5, label="Min threshold")
        ax.scatter([], [], c="#4a90d9", label="Horizontal")
        ax.scatter([], [], c="#e8913a", label="Vertical")
        ax.legend()
    ax.set_title("Rowing Chain Lengths")
    ax.set_xlabel("Event #")
    ax.set_ylabel("Sweeps in chain")

    # Panel 6: Rowing events over time
    ax = axes[2][1]
    if rowing_events:
        t0 = rowing_events[0].timestamp
        times = [(e.timestamp - t0) for e in rowing_events]
        ratios = [e.increase_ratio for e in rowing_events]
        colors = ["#4a90d9" if e.axis == "x" else "#e8913a" for e in rowing_events]
        ax.scatter(times, ratios, c=colors, alpha=0.6, s=30)
        ax.scatter([], [], c="#4a90d9", label="Horizontal")
        ax.scatter([], [], c="#e8913a", label="Vertical")
        ax.legend()
    ax.set_title("Rowing Events Over Time")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Increase ratio (total/max)")

    plt.tight_layout()
    plt.show()
