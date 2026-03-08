import matplotlib.pyplot as plt
from analyzer import AnalysisResult
from config import MIN_EVENTS_FOR_RECOMMENDATION, MIN_ROWING_EVENTS_FOR_RECOMMENDATION


def print_summary(result: AnalysisResult):
    duration_m = int(result.session_duration // 60)
    duration_s = int(result.session_duration % 60)

    print("\n" + "=" * 50)
    print("  AimFixer Results")
    print("=" * 50)
    print(f"  Session duration:    {duration_m}m {duration_s}s")
    print(f"  Samples collected:   {result.total_samples:,}")
    print(f"  Current settings:    {result.current_dpi} DPI / {result.current_sens} in-game sens")

    total_flicks = result.x_result.flick_count + result.y_result.flick_count
    total_overshoots = result.x_result.overshoot_count + result.y_result.overshoot_count
    if total_flicks > 0:
        pct = total_overshoots / total_flicks * 100
        print(f"  Flicks detected:     {total_flicks}")
        print(f"  Overshoots detected: {total_overshoots} ({pct:.1f}% of flicks)")
    else:
        print("  Flicks detected:     0")

    _print_axis(result.x_result, "X-Axis (Horizontal)")
    _print_axis(result.y_result, "Y-Axis (Vertical)")

    # Swirl stats
    _print_swirl(result)

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

    enough = (result.x_result.overshoot_count + result.y_result.overshoot_count) >= MIN_EVENTS_FOR_RECOMMENDATION
    if not enough and not result.possibly_too_low:
        print("  Not enough overshoot events for a reliable")
        print("  recommendation. Try a longer session.")
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
        print()
        print(f"  Per-axis (if your game supports separate X/Y):")
        print(f"    X sens: {result.current_sens} -> {result.new_sens_x:.2f}")
        print(f"    Y sens: {result.current_sens} -> {result.new_sens_y:.2f}")
    elif not result.possibly_too_low:
        print("  Your sensitivity looks well-tuned!")
        print("  No significant overshoot detected.")

    print("=" * 50)


def _print_axis(axis, label: str):
    print()
    print(f"  {label}:")
    if axis.flick_count == 0:
        print("    No flicks detected")
        return
    overshoot_rate = axis.overshoot_count / axis.flick_count * 100 if axis.flick_count else 0
    print(f"    Overshoots: {axis.overshoot_count} of {axis.flick_count} flicks ({overshoot_rate:.1f}%)")
    if axis.overshoot_count > 0:
        print(f"    Median overshoot:  {axis.median_overshoot_pct:.1f}%")
        print(f"    Mean overshoot:    {axis.mean_overshoot_pct:.1f}%")
        print(f"    75th percentile:   {axis.p75_overshoot_pct:.1f}%")


def _print_swirl(result: AnalysisResult):
    sr = result.swirl_result
    if not sr or sr.swirl_count == 0:
        return
    print()
    print(f"  2D Swirl (Circular Correction) Events:")
    print(f"    Swirls detected:   {sr.swirl_count}")
    print(f"    Median overshoot:  {sr.median_overshoot_pct:.1f}%")
    print(f"    Mean overshoot:    {sr.mean_overshoot_pct:.1f}%")
    print(f"    Median rotation:   {sr.median_angle_rotation_deg:.1f} degrees")


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


def show_charts(result: AnalysisResult, events, rowing_events=None, swirl_events=None):
    if rowing_events is None:
        rowing_events = []
    if swirl_events is None:
        swirl_events = []
    fig, axes = plt.subplots(4, 2, figsize=(12, 16))
    fig.suptitle("AimFixer Analysis", fontsize=14, fontweight="bold")

    x_pcts = result.x_result.overshoot_percentages
    y_pcts = result.y_result.overshoot_percentages

    # Top-left: X-axis overshoot histogram
    ax = axes[0][0]
    if x_pcts:
        ax.hist(x_pcts, bins=20, color="#4a90d9", edgecolor="white", alpha=0.85)
        ax.axvline(result.x_result.median_overshoot_pct, color="red",
                    linestyle="--", label=f"Median: {result.x_result.median_overshoot_pct:.1f}%")
        ax.legend()
    ax.set_title("X-Axis (Horizontal) Overshoot")
    ax.set_xlabel("Overshoot %")
    ax.set_ylabel("Count")

    # Top-right: Y-axis overshoot histogram
    ax = axes[0][1]
    if y_pcts:
        ax.hist(y_pcts, bins=20, color="#e8913a", edgecolor="white", alpha=0.85)
        ax.axvline(result.y_result.median_overshoot_pct, color="red",
                    linestyle="--", label=f"Median: {result.y_result.median_overshoot_pct:.1f}%")
        ax.legend()
    ax.set_title("Y-Axis (Vertical) Overshoot")
    ax.set_xlabel("Overshoot %")
    ax.set_ylabel("Count")

    # Bottom-left: Velocity vs overshoot scatter
    ax = axes[1][0]
    if events:
        velocities = [e.initial_sweep.peak_velocity for e in events]
        overshoots = [e.overshoot_percentage for e in events]
        colors = ["#4a90d9" if e.axis == "x" else "#e8913a" for e in events]
        ax.scatter(velocities, overshoots, c=colors, alpha=0.6, s=30)
        # Legend
        ax.scatter([], [], c="#4a90d9", label="Horizontal")
        ax.scatter([], [], c="#e8913a", label="Vertical")
        ax.legend()
    ax.set_title("Flick Speed vs Overshoot")
    ax.set_xlabel("Peak Velocity (px/s)")
    ax.set_ylabel("Overshoot %")

    # Bottom-right: Overshoot over time
    ax = axes[1][1]
    if events:
        t0 = events[0].timestamp
        times = [(e.timestamp - t0) for e in events]
        pcts = [e.overshoot_percentage for e in events]
        colors = ["#4a90d9" if e.axis == "x" else "#e8913a" for e in events]
        ax.scatter(times, pcts, c=colors, alpha=0.6, s=30)
        # Rolling average line
        if len(pcts) >= 5:
            window = 5
            rolling = []
            rolling_t = []
            for i in range(len(pcts) - window + 1):
                rolling.append(sum(pcts[i:i + window]) / window)
                rolling_t.append(times[i + window - 1])
            ax.plot(rolling_t, rolling, color="red", linewidth=2, alpha=0.7, label="Rolling avg (5)")
            ax.legend()
    ax.set_title("Overshoot Over Time (fatigue?)")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Overshoot %")

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

    # Panel 7: Swirl overshoot histogram
    ax = axes[3][0]
    swirl_pcts = result.swirl_result.overshoot_percentages if result.swirl_result else []
    if swirl_pcts:
        ax.hist(swirl_pcts, bins=20, color="#9b59b6", edgecolor="white", alpha=0.85)
        ax.axvline(result.swirl_result.median_overshoot_pct, color="red",
                    linestyle="--", label=f"Median: {result.swirl_result.median_overshoot_pct:.1f}%")
        ax.legend()
    ax.set_title("2D Swirl Overshoot Distribution")
    ax.set_xlabel("Overshoot %")
    ax.set_ylabel("Count")

    # Panel 8: Swirl correction arcs (2D scatter of correction vectors)
    ax = axes[3][1]
    if swirl_events:
        corr_dx = [e.correction_displacement_x for e in swirl_events]
        corr_dy = [e.correction_displacement_y for e in swirl_events]
        colors = [e.overshoot_percentage for e in swirl_events]
        sc = ax.scatter(corr_dx, corr_dy, c=colors, cmap="plasma", alpha=0.7, s=40)
        ax.axhline(0, color="gray", linewidth=0.5, alpha=0.5)
        ax.axvline(0, color="gray", linewidth=0.5, alpha=0.5)
        fig.colorbar(sc, ax=ax, label="Overshoot %")
    ax.set_title("Swirl Correction Vectors")
    ax.set_xlabel("Correction dx (pixels)")
    ax.set_ylabel("Correction dy (pixels)")
    ax.set_aspect("equal", adjustable="datalim")

    plt.tight_layout()
    plt.show()
