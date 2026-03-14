# CLAUDE.md - AimFixer

## Project Overview

AimFixer is a Python-based mouse overshoot detection and sensitivity advisor for FPS games. It records real-time mouse input, detects overshoot patterns using biomechanical heuristics, and recommends optimal sensitivity/DPI adjustments. Supports multiple consecutive recording sessions without restarting.

## Tech Stack

- **Language:** Python 3.9+
- **Input Capture:** pynput (mouse + keyboard listeners)
- **Visualization:** matplotlib
- **Overlay:** AppKit (macOS native OSD), tkinter (Windows/Linux)
- **GUI Dialogs:** tkinter (cross-platform startup + settings dialogs)
- **Platform:** macOS (requires accessibility permissions), Windows, Linux

## Project Structure

```
aimfixer.py    - Main entry point, CLI arg parsing
app.py         - AppController: multi-session lifecycle (overlay + collector + session loop)
session.py     - SessionRunner: collect → detect → analyze → save pipeline
collector.py   - MouseCollector: records mouse movement, supports reset() for multi-session
detector.py    - OvershootDetector: 4-stage detection (EMA filter → sweep segmentation → click-aim → rowing)
analyzer.py    - Statistical analysis + sensitivity reduction recommendations
models.py      - Shared dataclass definitions (AnalysisResult, OverlayState, etc.)
dialogs.py     - Cross-platform tkinter dialogs (startup settings, mid-session settings change)
visualizer.py  - Terminal summary + 6-panel matplotlib charts
overlay.py     - macOS native OSD (AppKit NSWindow), states: WAITING/RECORDING/ANALYZING/DONE
overlay_win.py - Windows/Linux OSD (tkinter Toplevel), mirrors overlay.py API
compare.py     - Multi-session history comparison and aggregate recommendations
history.py     - Session persistence (save/load JSON summaries + JSONL events)
config.py      - Configuration loader from config.ini
config.ini     - All tunable constants (thresholds, weights, hotkeys)
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
python aimfixer.py <dpi> <h_sensitivity> <v_sensitivity>

# Multi-session history comparison
python aimfixer.py history
```

## Hotkeys

- **F5** — Start recording
- **F6** — Stop recording
- **F7** — Cycle through games (Apex Legends, R6 Siege, Rust, Arc Raiders, Deadlock)
- **F8** — Quit app and show charts
- **F9** — Change settings (DPI/sensitivity) via dialog

## Architecture / Data Flow

```
User Input (DPI + H/V Sensitivity)
    ↓
AppController (multi-session loop)
    ↓
SessionRunner → MouseCollector → Raw samples (timestamp, x, y, dx, dy)
    ↓
OvershootDetector → EMA smoothing → Sweep segmentation → Overshoot events
    ↓
Analyzer → Statistics (median, mean, p75) + sensitivity recommendation
    ↓
Visualizer → Text summary + charts (histograms, scatter, time series)
```

## Multi-Session Flow

1. User enters settings (DPI, sensitivity) at startup
2. Overlay shows WAITING state with tips and current settings
3. F5 starts recording → RECORDING state
4. F6 stops recording → ANALYZING state → analysis runs → DONE state
5. From DONE: F5 starts a new session (loop back to step 3), F8 quits
6. Each session creates independent data in `sessions/`
7. On quit, final charts display on main thread

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
- Groups sessions by (DPI, H sensitivity, V sensitivity) settings
- Uses click-weighted medians (heavier sessions contribute proportionally more)
- Recommendation targets the most recent settings group, no trend dampening (aggregate already smooths variance)
- 2-panel trend chart: overshoot % and hit factor over sessions

## Development Notes

- No tests currently exist
- All config constants live in `config.ini`, loaded by `config.py`
- Hotkeys defined in config.ini under `[hotkeys]`
- DPI recommendations snap to nearest 50 (`DPI_STEP`)
- Confidence weighting scales down recommendations when sample count is low
- Sessions are saved as JSON summaries + JSONL event logs in `sessions/`
- Unified recommendation system resolves overshoot vs rowing conflicts with trend dampening
- Per-game split H/V sensitivity support — games like R6 Siege have separate horizontal/vertical sliders
- `GAME_SPLIT_SENS` in config.py marks which games natively support split sens (informational)
- When V sens differs from H sens, recommendations show separate H/V values using the same percentage adjustment
- CLI supports `<dpi> <h_sens> <v_sens>`; no-args launches tkinter startup dialog
- Old sessions without `v_sensitivity` fall back to `sensitivity` (backward compatible)
- `OverlayState` enum lives in `models.py` (shared by both overlay modules)
- `app.py` imports overlay controller based on `sys.platform` (macOS → `overlay.py`, else → `overlay_win.py`)
- Startup and settings dialogs use `dialogs.py` (tkinter, cross-platform) — `overlay.py` no longer contains dialog code
- `overlay_win.py` mirrors `overlay.py` API: `set_state()`, `set_game()`, `flash_warning()`, `set_settings()`, `schedule()`, `run()`, `stop()`

## Code Navigation Preferences

- **Always use LSP tools first** for navigating and understanding code (goToDefinition, findReferences, documentSymbol, hover, etc.). LSP provides accurate, type-aware results.
- **Fall back to Grep/Glob** only if the LSP server is unavailable, still starting, or returns an error.
- Navigation priority: LSP → Grep → Glob → Agent (Explore)
- Use LSP whenever possible — this is a strong preference.
