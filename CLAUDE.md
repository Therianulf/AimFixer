# CLAUDE.md - AimFixer

## Project Overview

AimFixer is a Python-based mouse overshoot detection and sensitivity advisor for FPS games. It records real-time mouse input, detects overshoot patterns using biomechanical heuristics, and recommends optimal sensitivity/DPI adjustments.

## Tech Stack

- **Language:** Python 3.9+
- **Input Capture:** pynput (mouse + keyboard listeners)
- **Visualization:** matplotlib
- **Platform:** macOS (requires accessibility permissions), also supports Linux/Windows

## Project Structure

```
aimfixer.py    - Main entry point, orchestrates the pipeline
collector.py   - MouseCollector: records mouse movement via F6 hotkey toggle
detector.py    - OvershootDetector: 3-stage detection (EMA filter → sweep segmentation → overshoot classification)
analyzer.py    - Statistical analysis + sensitivity reduction recommendations
visualizer.py  - Terminal summary + 6-panel matplotlib charts
compare.py     - Multi-session history comparison and aggregate recommendations
history.py     - Session persistence (save/load JSON summaries + JSONL events)
config.py      - All tunable constants (thresholds, weights, hotkey)
pyproject.toml - Project metadata and dependencies
```

## How to Run

```bash
# Use the project venv
source .venv/bin/activate

# Install dependencies (if needed)
pip install pynput matplotlib

# Run (interactive — prompts for DPI + sensitivity)
python aimfixer.py

# Run with CLI args
python aimfixer.py <dpi> <sensitivity>

# Multi-session history comparison
python aimfixer.py history
```

## Architecture / Data Flow

```
User Input (DPI + Sensitivity)
    ↓
MouseCollector → Raw samples (timestamp, x, y, dx, dy)
    ↓
OvershootDetector → EMA smoothing → Sweep segmentation → Overshoot events
    ↓
Analyzer → Statistics (median, mean, p75) + sensitivity recommendation
    ↓
Visualizer → Text summary + charts (histograms, scatter, time series)
```

## Key Algorithm Details

- **Overshoot = fast flick followed by a small, slow correction in the opposite direction**
- Click-centric analysis: detects approach flick + correction jitter around each click
- Sensitivity recommendation uses median overshoot × 0.15 correction factor × confidence weight
- X-axis weighted 1.5×, Y-axis weighted 1.0× (horizontal aim matters more in FPS)
- Warp detection filters out cursor jumps >100px (cloud gaming compatibility)
- Rowing detection identifies mouse-lift-and-replace patterns (sensitivity too low)
- Shot string segmentation groups clicks into combat engagements for fire rate analysis
- Hit factor = (shots_per_minute / 60) × aim_efficiency — composite performance metric

## History Comparison (`python aimfixer.py history`)

- Aggregates stats across all saved sessions in `sessions/`
- Filters out unreliable sessions: ≤30 analyzed clicks, <30s duration, or missing fire rate data
- Groups sessions by (DPI, sensitivity) settings
- Uses click-weighted medians (heavier sessions contribute proportionally more)
- Recommendation targets the most recent settings group, no trend dampening (aggregate already smooths variance)
- 2-panel trend chart: overshoot % and hit factor over sessions

## Development Notes

- No tests currently exist
- All config constants live in `config.py` — change thresholds there
- F5 starts recording, F6 stops recording (defined via `START_KEY`/`STOP_KEY` in config.py)
- DPI recommendations snap to nearest 50 (`DPI_STEP`)
- Confidence weighting scales down recommendations when sample count is low
- Sessions are saved as JSON summaries + JSONL event logs in `sessions/`
- Unified recommendation system resolves overshoot vs rowing conflicts with trend dampening

## Code Navigation Preferences

- **Prefer LSP tools first** for navigating and understanding code (goToDefinition, findReferences, documentSymbol, hover, etc.). LSP provides accurate, type-aware results.
- **Fall back to Grep/Glob** if the LSP server is unavailable, still starting, or returns an error.
- Navigation priority: LSP → Grep → Glob → Agent (Explore)
