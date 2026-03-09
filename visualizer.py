from __future__ import annotations
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import tkinter as tk
from analyzer import AnalysisResult, group_shot_strings
from config import MIN_EVENTS_FOR_RECOMMENDATION, STRING_GAP_THRESHOLD_S


def print_summary(result: AnalysisResult, previous_session: dict | None = None):
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

    # Fire rate / hit factor
    if result.fire_rate:
        fr = result.fire_rate
        interval_str = f"{fr.median_shot_interval_ms:.0f}ms between shots"
        active_s = int(fr.active_combat_duration_s)
        session_s = int(result.session_duration)
        print()
        print(f"  Shot strings:        {fr.string_count} strings (avg {fr.shots_per_string_avg:.0f} shots/string)")
        print(f"  Active combat:       {active_s}s of {session_s}s session")
        print(f"  Fire rate:           {fr.shots_per_minute:.0f} shots/min ({interval_str})")
        print(f"  Aim efficiency:      {fr.aim_efficiency:.2f}")
        print(f"  Hit factor:          {fr.hit_factor:.2f}")

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

    rec = result.recommendation
    enough = ca.analyzed_clicks >= MIN_EVENTS_FOR_RECOMMENDATION
    if rec is None and not enough and not result.possibly_too_low:
        print("  Not enough aim events for a reliable")
        print("  recommendation. Try a longer session with")
        print("  more flick shots.")
        print("=" * 50)
        return

    print("  RECOMMENDATION")
    print("-" * 50)

    if rec:
        if rec.action == "keep":
            print("  Your sensitivity looks well-tuned!")
            if rec.reasoning:
                print(f"  {rec.reasoning}")
        elif rec.action == "reduce":
            print(f"  Reduce in-game sensitivity by ~{rec.primary_pct:.0f}%")
            print(f"    {result.current_sens} -> {rec.new_sens:.2f}")
        elif rec.action == "increase":
            print(f"  Increase in-game sensitivity by ~{rec.primary_pct:.0f}%")
            print(f"    {result.current_sens} -> {rec.new_sens:.2f}")
        elif rec.action == "multi_step":
            print("  Two-step adjustment recommended:")
            print(f"    Step 1: Bump DPI from {result.current_dpi} to {rec.new_dpi}")
            print(f"            Try this and run the test again.")
            if rec.step2_pct > 0.5:
                print(f"    Step 2: If overshoot persists, reduce sens by ~{rec.step2_pct:.0f}%")
                print(f"            {result.current_sens} -> {rec.step2_new_sens:.2f}")

        if rec.trend_note:
            print()
            print(f"  {rec.trend_note}")
    else:
        print("  Not enough aim events for a reliable")
        print("  recommendation. Try a longer session with")
        print("  more flick shots.")

    # DPI advisory (tiered)
    if result.dpi_advisory:
        print()
        if result.dpi_advisory_level == "warning":
            print("-" * 50)
            print("  DPI WARNING")
            print("-" * 50)
        else:
            print("  TIP:")
        print(f"  {result.dpi_advisory}")
        print(f"  Suggested DPI: {result.suggested_dpi}")
        if result.dpi_advisory_level == "warning":
            print()
            print("  Adjust DPI once in your mouse software,")
            print("  then re-calibrate your in-game sensitivity.")

    # Session comparison
    if previous_session:
        _print_comparison(result, previous_session)

    print("=" * 50)


def _delta_str(old: float, new: float, lower_is_good: bool = False) -> str:
    if old == 0:
        return ""
    pct = (new - old) / abs(old) * 100.0
    if pct > 0:
        arrow = "v" if lower_is_good else "^"
    elif pct < 0:
        arrow = "^" if lower_is_good else "v"
    else:
        return "  (no change)"
    return f"  ({arrow} {abs(pct):.0f}%)"


def _print_comparison(result: AnalysisResult, prev: dict):
    prev_settings = prev.get("settings", {})
    prev_dpi = prev_settings.get("dpi", "?")
    prev_sens = prev_settings.get("sensitivity", "?")

    prev_ca = prev.get("click_analysis", {})
    prev_overshoot = prev_ca.get("median_overshoot_pct", 0.0)

    prev_fr = prev.get("fire_rate") or {}
    prev_hit_factor = prev_fr.get("hit_factor", 0.0)
    prev_spm = prev_fr.get("shots_per_minute", 0.0)

    ca = result.click_analysis
    cur_overshoot = ca.median_overshoot_pct
    cur_hit_factor = result.fire_rate.hit_factor if result.fire_rate else 0.0
    cur_spm = result.fire_rate.shots_per_minute if result.fire_rate else 0.0

    print()
    print(f"  vs Previous ({prev_dpi} DPI / {prev_sens} sens):")
    print(f"    Overshoot:    {prev_overshoot:.1f}% -> {cur_overshoot:.1f}%"
          f"{_delta_str(prev_overshoot, cur_overshoot, lower_is_good=True)}")
    if prev_hit_factor or cur_hit_factor:
        print(f"    Hit factor:   {prev_hit_factor:.2f} -> {cur_hit_factor:.2f}"
              f"{_delta_str(prev_hit_factor, cur_hit_factor)}")
    if prev_spm or cur_spm:
        print(f"    Fire rate:    {prev_spm:.0f} -> {cur_spm:.0f} spm"
              f"{_delta_str(prev_spm, cur_spm)}")


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


def _get_intra_string_intervals(click_aim_events) -> list[float]:
    """Compute intra-string intervals (ms) from click aim events, excluding reload gaps."""
    if len(click_aim_events) < 2:
        return []
    sorted_clicks = sorted(e.click_time for e in click_aim_events)
    strings = group_shot_strings(sorted_clicks)
    intervals_ms: list[float] = []
    for s in strings:
        for i in range(1, len(s)):
            intervals_ms.append((s[i] - s[i - 1]) * 1000)
    return intervals_ms


def show_charts(result: AnalysisResult, click_aim_events, rowing_events=None):
    if rowing_events is None:
        rowing_events = []

    ca = result.click_analysis

    fig = Figure(figsize=(12, 14))
    axes = fig.subplots(3, 2)
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

    # Bottom row: rowing panels OR shot interval panels
    if rowing_events:
        # Panel 5: Rowing chain length histogram
        ax = axes[2][0]
        chain_lengths = [e.chain_length for e in rowing_events]
        colors = ["#4a90d9" if e.axis == "x" else "#e8913a" for e in rowing_events]
        ax.bar(range(len(chain_lengths)), chain_lengths, color=colors, alpha=0.85)
        ax.axhline(y=3, color="gray", linestyle="--", alpha=0.5, label="Min threshold")
        ax.scatter([], [], c="#4a90d9", label="Horizontal")
        ax.scatter([], [], c="#e8913a", label="Vertical")
        ax.legend()
        ax.set_title("Rowing Chain Lengths")
        ax.set_xlabel("Event #")
        ax.set_ylabel("Sweeps in chain")

        # Panel 6: Rowing events over time
        ax = axes[2][1]
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
    elif click_aim_events:
        # Use intra-string intervals only (filter out reload gaps)
        intra_intervals = _get_intra_string_intervals(click_aim_events)

        # Panel 5: Shot interval histogram (intra-string only)
        ax = axes[2][0]
        if intra_intervals:
            ax.hist(intra_intervals, bins=20, color="#27ae60", edgecolor="white", alpha=0.85)
            from statistics import median as _median
            med_interval = _median(intra_intervals)
            ax.axvline(med_interval, color="red", linestyle="--",
                       label=f"Median: {med_interval:.0f}ms")
            ax.legend()
        ax.set_title("Shot Interval Distribution (in-string)")
        ax.set_xlabel("Interval (ms)")
        ax.set_ylabel("Count")

        # Panel 6: Shot intervals over time (intra-string only)
        ax = axes[2][1]
        if intra_intervals:
            sorted_clicks = sorted(e.click_time for e in click_aim_events)
            strings = group_shot_strings(sorted_clicks)
            t0 = sorted_clicks[0]
            shot_times: list[float] = []
            interval_vals: list[float] = []
            for s in strings:
                for i in range(1, len(s)):
                    shot_times.append(s[i] - t0)
                    interval_vals.append((s[i] - s[i - 1]) * 1000)
            ax.scatter(shot_times, interval_vals, c="#27ae60", alpha=0.6, s=30)
        ax.set_title("Shot Intervals Over Time (in-string)")
        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Interval (ms)")
    else:
        axes[2][0].set_visible(False)
        axes[2][1].set_visible(False)

    fig.tight_layout()

    # Build scrollable Tkinter window
    root = tk.Tk()
    root.title("AimFixer Analysis")

    # Size window to near-fullscreen
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_h = screen_h - 80  # leave room for menubar/dock
    root.geometry(f"{screen_w}x{win_h}+0+0")

    # Outer frame with canvas + scrollbar
    outer = tk.Frame(root)
    outer.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(outer)
    scrollbar = tk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Inner frame for the figure
    inner = tk.Frame(canvas)
    canvas.create_window((0, 0), window=inner, anchor="nw")

    # Embed matplotlib figure
    fig_canvas = FigureCanvasTkAgg(fig, master=inner)
    fig_canvas.draw()
    fig_widget = fig_canvas.get_tk_widget()
    fig_widget.pack(fill=tk.BOTH, expand=True)

    # Navigation toolbar for zoom/pan/save
    toolbar = NavigationToolbar2Tk(fig_canvas, inner)
    toolbar.update()
    toolbar.pack(side=tk.BOTTOM, fill=tk.X)

    def _on_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    inner.bind("<Configure>", _on_configure)

    # Mousewheel scrolling (macOS uses MouseWheel with delta)
    def _on_mousewheel(event):
        # macOS sends event.delta in units of 120 (or raw pixels on trackpad)
        canvas.yview_scroll(int(-event.delta), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    root.mainloop()
