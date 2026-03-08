# AimFixer

A mouse overshoot detection and sensitivity advisor for FPS games. AimFixer monitors your real-time mouse movements during gameplay, identifies overshoot patterns in your aim, and provides data-driven recommendations to optimize your mouse sensitivity and DPI settings.

## How It Works

1. **Record** — Press F6 to start/stop recording your mouse movements during gameplay
2. **Detect** — AimFixer analyzes your input to find overshoot patterns (when you flick past a target and correct back)
3. **Recommend** — Get a tailored sensitivity/DPI adjustment based on your actual aim behavior
4. **Visualize** — View detailed charts breaking down your overshoots by axis, velocity, and over time

### The Science

AimFixer uses a 3-stage detection pipeline:

- **Noise Filtering** — Exponential moving average smoothing removes sensor jitter and micro-tremor
- **Sweep Segmentation** — Continuous movements are broken into directional sweeps with velocity and displacement tracking
- **Overshoot Classification** — Consecutive sweeps are matched against biomechanical heuristics: a fast intentional flick followed by a small, slow correction in the opposite direction is flagged as an overshoot

The algorithm distinguishes deliberate aim adjustments from involuntary overshoots using timing, velocity ratios, magnitude ratios, and direction reversals.

## Installation

**Requirements:** Python 3.9+

```bash
pip install pynput matplotlib
```

On **macOS**, you'll need to grant accessibility permissions to your terminal app (System Settings → Privacy & Security → Accessibility).

## Usage

```bash
python aimfixer.py
```

You'll be prompted to enter your current DPI and in-game sensitivity. Then:

- Press **F6** to start recording
- Play your game normally — flick, track, aim as you usually do
- Press **F6** again to stop

AimFixer will display:

- **Overshoot statistics** — count, median/mean/p75 overshoot percentages per axis
- **Sensitivity recommendation** — three options:
  - **Option A:** Adjust in-game sensitivity only
  - **Option B:** Adjust DPI only
  - **Option C:** Per-axis adjustments (if your game supports it)
- **4-panel chart** — X/Y overshoot histograms, flick velocity vs. overshoot scatter plot, and overshoot trend over time (reveals fatigue)

## Configuration

All tunable parameters live in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `TOGGLE_KEY` | F6 | Hotkey to start/stop recording |
| `EMA_ALPHA` | 0.3 | Smoothing factor (higher = less smoothing) |
| `MIN_FLICK_VELOCITY_PX_S` | 800.0 | Minimum velocity to count as a deliberate flick |
| `MAX_CORRECTION_GAP_S` | 0.050 | Max time gap between flick and correction (seconds) |
| `MAX_CORRECTION_RATIO` | 0.50 | Correction must be ≤50% of flick distance |
| `CORRECTION_FACTOR` | 0.60 | How aggressively to recommend sensitivity changes |
| `DPI_STEP` | 50 | DPI rounding granularity |

## Tips for Best Results

- Record at least **30–60 seconds** of active aim (flicking between targets)
- Do multiple sessions to get consistent recommendations
- If AimFixer detects very few overshoots, your sensitivity may actually be too *low* — it'll tell you
- Focus on natural gameplay; don't deliberately overshoot or aim carefully

## License

MIT
