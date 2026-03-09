# AimFixer

A mouse overshoot detection and sensitivity advisor for FPS games. AimFixer monitors your real-time mouse movements during gameplay, identifies overshoot patterns in your aim, and provides data-driven recommendations to optimize your mouse sensitivity and DPI settings.

## How It Works

1. **Record** — Press F5 to start and F6 to stop recording your mouse movements during gameplay
2. **Detect** — AimFixer analyzes your input to find overshoot patterns (when you flick past a target and correct back)
3. **Recommend** — Get a tailored sensitivity/DPI adjustment based on your actual aim behavior
4. **Visualize** — View detailed charts breaking down your overshoots, corrections, and fire rate
5. **Compare** — Aggregate stats across multiple sessions for stable, reliable recommendations

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

### Single Session

```bash
python aimfixer.py
# or with CLI args:
python aimfixer.py 1600 1.73
```

You'll be prompted to enter your current DPI and in-game sensitivity. Then:

- Press **F5** to start recording
- Play your game normally — flick, track, aim as you usually do
- Press **F6** to stop

AimFixer will display:

- **Click-centric overshoot statistics** — median/mean overshoot %, correction magnitude, swirl detection
- **Fire rate analysis** — shots per minute, shot strings, aim efficiency, hit factor
- **Rowing detection** — identifies mouse-lift-and-replace patterns (sensitivity too low)
- **Unified recommendation** — reduce, increase, or keep sensitivity based on all signals
- **6-panel chart** — overshoot histograms, correction per shot, duration vs overshoot scatter, direction changes, and shot interval analysis

### Multi-Session History

```bash
python aimfixer.py history
```

Aggregates all saved sessions for a more stable recommendation:

- Groups sessions by DPI/sensitivity settings
- Filters out unreliable sessions (≤30 clicks, <30s duration, missing fire rate)
- Uses click-weighted medians so longer sessions contribute more
- Shows per-session breakdown and trend charts for overshoot and hit factor

## Configuration

All tunable parameters live in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `START_KEY` | F5 | Hotkey to start recording |
| `STOP_KEY` | F6 | Hotkey to stop recording |
| `EMA_ALPHA` | 0.08 | Smoothing factor (higher = less smoothing) |
| `MIN_FLICK_VELOCITY_PX_S` | 100.0 | Minimum velocity to count as a deliberate flick |
| `CORRECTION_FACTOR` | 0.15 | How aggressively to recommend sensitivity changes |
| `MAX_REDUCTION_PCT` | 30.0 | Maximum recommended reduction per step |
| `DPI_STEP` | 50 | DPI rounding granularity |
| `MIN_ANALYZED_CLICKS_FOR_HISTORY` | 30 | Minimum clicks for a session to count in history |
| `MIN_SESSION_DURATION_FOR_HISTORY` | 30.0 | Minimum session duration (seconds) for history |

## Tips for Best Results

- Record at least **30–60 seconds** of active aim (flicking between targets)
- Do multiple sessions to get consistent recommendations
- If AimFixer detects very few overshoots, your sensitivity may actually be too *low* — it'll tell you
- Focus on natural gameplay; don't deliberately overshoot or aim carefully

## License

MIT
