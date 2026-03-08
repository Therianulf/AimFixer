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
visualizer.py  - Terminal summary + 4-panel matplotlib charts
config.py      - All tunable constants (thresholds, weights, hotkey)
pyproject.toml - Project metadata and dependencies
```

## How to Run

```bash
# Use the project venv
source .venv/bin/activate

# Install dependencies (if needed)
pip install pynput matplotlib

# Run
python aimfixer.py
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
- Detection uses 6 criteria: direction reversal, timing gap (<50ms), magnitude ratio (<50%), flick velocity (≥800 px/s), velocity drop, correction duration (<300ms)
- Sensitivity recommendation uses median overshoot × 0.60 correction factor × confidence weight
- X-axis weighted 1.5×, Y-axis weighted 1.0× (horizontal aim matters more in FPS)
- Warp detection filters out cursor jumps >100px (cloud gaming compatibility)

## Development Notes

- No tests currently exist
- All config constants live in `config.py` — change thresholds there
- The F6 hotkey is defined via `TOGGLE_KEY` in config.py
- DPI recommendations snap to nearest 50 (`DPI_STEP`)
- Confidence weighting scales down recommendations when sample count is low
