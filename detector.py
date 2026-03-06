from __future__ import annotations
from dataclasses import dataclass
from collector import MouseSample
from config import (
    EMA_ALPHA, DEAD_ZONE_PIXELS,
    MIN_SWEEP_DURATION_S, MIN_SWEEP_PIXELS,
    MAX_CORRECTION_GAP_S, MAX_CORRECTION_RATIO,
    MIN_FLICK_VELOCITY_PX_S, VELOCITY_RATIO_THRESHOLD,
    MAX_CORRECTION_DURATION_S,
)


@dataclass
class Sweep:
    axis: str
    start_index: int
    end_index: int
    start_time: float
    end_time: float
    total_displacement: float
    peak_velocity: float
    mean_velocity: float

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class OvershootEvent:
    axis: str
    initial_sweep: Sweep
    correction_sweep: Sweep
    overshoot_distance: float
    overshoot_percentage: float
    timestamp: float


def _sign(v: float) -> int:
    if v > 0:
        return 1
    elif v < 0:
        return -1
    return 0


class OvershootDetector:
    def __init__(self, samples: list[MouseSample]):
        self._samples = samples
        self._smoothed_dx: list[float] = []
        self._smoothed_dy: list[float] = []
        self._sweeps_x: list[Sweep] = []
        self._sweeps_y: list[Sweep] = []
        self._events: list[OvershootEvent] = []

    def detect(self) -> list[OvershootEvent]:
        if len(self._samples) < 2:
            return []
        self._filter_noise()
        self._segment_sweeps()
        self._classify_overshoots()
        return self._events

    def get_all_sweeps(self) -> dict[str, list[Sweep]]:
        return {"x": self._sweeps_x, "y": self._sweeps_y}

    def get_flick_counts(self) -> dict[str, int]:
        """Count sweeps that qualify as flicks (above velocity threshold)."""
        x_flicks = sum(1 for s in self._sweeps_x if s.peak_velocity >= MIN_FLICK_VELOCITY_PX_S)
        y_flicks = sum(1 for s in self._sweeps_y if s.peak_velocity >= MIN_FLICK_VELOCITY_PX_S)
        return {"x": x_flicks, "y": y_flicks}

    # --- Stage 1: Noise filtering ---

    def _filter_noise(self):
        prev_dx = 0.0
        prev_dy = 0.0
        for s in self._samples:
            smoothed_x = EMA_ALPHA * s.dx + (1 - EMA_ALPHA) * prev_dx
            smoothed_y = EMA_ALPHA * s.dy + (1 - EMA_ALPHA) * prev_dy
            if abs(smoothed_x) < DEAD_ZONE_PIXELS:
                smoothed_x = 0.0
            if abs(smoothed_y) < DEAD_ZONE_PIXELS:
                smoothed_y = 0.0
            self._smoothed_dx.append(smoothed_x)
            self._smoothed_dy.append(smoothed_y)
            prev_dx = smoothed_x
            prev_dy = smoothed_y

    # --- Stage 2: Sweep segmentation ---

    def _build_sweeps(self, smoothed: list[float], axis: str) -> list[Sweep]:
        sweeps: list[Sweep] = []
        if not smoothed:
            return sweeps

        # Find first non-zero to start
        sweep_start = 0
        current_sign = 0
        for i, v in enumerate(smoothed):
            s = _sign(v)
            if s != 0:
                sweep_start = i
                current_sign = s
                break
        else:
            return sweeps  # all zeros

        for i in range(sweep_start + 1, len(smoothed)):
            s = _sign(smoothed[i])
            if s != 0 and s != current_sign:
                sweep = self._make_sweep(axis, sweep_start, i - 1, smoothed)
                if sweep:
                    sweeps.append(sweep)
                sweep_start = i
                current_sign = s

        # Final sweep
        sweep = self._make_sweep(axis, sweep_start, len(smoothed) - 1, smoothed)
        if sweep:
            sweeps.append(sweep)

        return sweeps

    def _make_sweep(self, axis: str, start: int, end: int, smoothed: list[float]) -> Sweep | None:
        samples = self._samples
        start_time = samples[start].timestamp
        end_time = samples[end].timestamp
        duration = end_time - start_time

        if duration < MIN_SWEEP_DURATION_S:
            return None

        total_disp = sum(smoothed[start:end + 1])
        if abs(total_disp) < MIN_SWEEP_PIXELS:
            return None

        # Compute velocities
        peak_vel = 0.0
        for i in range(start, end + 1):
            if i > 0:
                dt = samples[i].timestamp - samples[i - 1].timestamp
                if dt > 0:
                    vel = abs(smoothed[i]) / dt
                    peak_vel = max(peak_vel, vel)

        mean_vel = abs(total_disp) / duration if duration > 0 else 0.0

        return Sweep(
            axis=axis,
            start_index=start,
            end_index=end,
            start_time=start_time,
            end_time=end_time,
            total_displacement=total_disp,
            peak_velocity=peak_vel,
            mean_velocity=mean_vel,
        )

    def _segment_sweeps(self):
        self._sweeps_x = self._build_sweeps(self._smoothed_dx, "x")
        self._sweeps_y = self._build_sweeps(self._smoothed_dy, "y")

    # --- Stage 3: Overshoot classification ---

    def _classify_axis(self, sweeps: list[Sweep]):
        for i in range(len(sweeps) - 1):
            a = sweeps[i]
            b = sweeps[i + 1]

            # Must be a direction reversal
            if _sign(a.total_displacement) == _sign(b.total_displacement):
                continue

            # Condition 1: Time gap
            gap = b.start_time - a.end_time
            if gap > MAX_CORRECTION_GAP_S:
                continue

            # Condition 2: Magnitude ratio
            ratio = abs(b.total_displacement) / abs(a.total_displacement)
            if ratio > MAX_CORRECTION_RATIO:
                continue

            # Condition 3: Initial sweep was a flick
            if a.peak_velocity < MIN_FLICK_VELOCITY_PX_S:
                continue

            # Condition 4: Correction is slower than the flick
            if b.mean_velocity >= a.peak_velocity * VELOCITY_RATIO_THRESHOLD:
                continue

            # Condition 5: Correction is brief
            if b.duration > MAX_CORRECTION_DURATION_S:
                continue

            overshoot_dist = abs(b.total_displacement)
            overshoot_pct = (overshoot_dist / abs(a.total_displacement)) * 100.0

            self._events.append(OvershootEvent(
                axis=a.axis,
                initial_sweep=a,
                correction_sweep=b,
                overshoot_distance=overshoot_dist,
                overshoot_percentage=overshoot_pct,
                timestamp=b.start_time,
            ))

    def _classify_overshoots(self):
        self._classify_axis(self._sweeps_x)
        self._classify_axis(self._sweeps_y)
