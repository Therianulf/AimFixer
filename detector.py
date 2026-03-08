from __future__ import annotations
import math
from dataclasses import dataclass
from collector import MouseSample
from config import (
    EMA_ALPHA, DEAD_ZONE_PIXELS,
    MIN_SWEEP_DURATION_S, MIN_SWEEP_PIXELS,
    MIN_FLICK_VELOCITY_PX_S,
    MIN_ROWING_GAP_S, MAX_ROWING_GAP_S,
    MIN_ROWING_SWEEPS, MIN_ROWING_SWEEP_VELOCITY,
    MIN_SWIRL_ANGLE_RAD,
    CLICK_WINDOW_BEFORE_S, CLICK_WINDOW_AFTER_S,
    CLICK_APPROACH_VELOCITY_DROP,
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
class RowingEvent:
    axis: str
    sweeps: list  # list[Sweep]
    chain_length: int
    total_displacement: float
    max_single_displacement: float
    increase_ratio: float  # total / max single
    gap_durations: list[float]
    mean_gap_duration: float
    timestamp: float


@dataclass
class ClickAimEvent:
    click_time: float
    # Approach phase (the flick toward target)
    approach_peak_velocity: float    # peak 2D speed before click (raw)
    approach_displacement: float     # total distance covered approaching
    approach_duration: float         # how long the flick took
    # Correction phase (jitter/adjustment before settling on target)
    correction_magnitude: float      # total displacement in correction window
    correction_direction_changes: int
    correction_angle_rotation: float  # radians — swirl indicator
    correction_duration: float       # time from first correction to click
    # Quality metrics
    overshoot_percentage: float      # correction / approach * 100
    is_swirl: bool                   # angle rotation > threshold


def _sign(v: float) -> int:
    if v > 0:
        return 1
    elif v < 0:
        return -1
    return 0


class OvershootDetector:
    def __init__(self, samples: list[MouseSample], click_times: list[float] | None = None):
        self._samples = samples
        self._click_times = click_times or []
        self._smoothed_dx: list[float] = []
        self._smoothed_dy: list[float] = []
        self._sweeps_x: list[Sweep] = []
        self._sweeps_y: list[Sweep] = []
        self._rowing_events: list[RowingEvent] = []
        self._click_aim_events: list[ClickAimEvent] = []

    def detect(self) -> list[ClickAimEvent]:
        if len(self._samples) < 2:
            return []
        self._filter_noise()
        self._segment_sweeps()
        self._classify_click_aims()
        self._classify_rowing()
        return self._click_aim_events

    def get_all_sweeps(self) -> dict[str, list[Sweep]]:
        return {"x": self._sweeps_x, "y": self._sweeps_y}

    def get_click_aim_events(self) -> list[ClickAimEvent]:
        return self._click_aim_events

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

    # --- Stage 2: Sweep segmentation (still needed for rowing) ---

    def _build_sweeps(self, smoothed: list[float], axis: str) -> list[Sweep]:
        sweeps: list[Sweep] = []
        if not smoothed:
            return sweeps

        sweep_start = 0
        current_sign = 0
        for i, v in enumerate(smoothed):
            s = _sign(v)
            if s != 0:
                sweep_start = i
                current_sign = s
                break
        else:
            return sweeps

        for i in range(sweep_start + 1, len(smoothed)):
            s = _sign(smoothed[i])
            time_gap = self._samples[i].timestamp - self._samples[i - 1].timestamp
            if (s != 0 and s != current_sign) or time_gap > MIN_ROWING_GAP_S:
                sweep = self._make_sweep(axis, sweep_start, i - 1, smoothed)
                if sweep:
                    sweeps.append(sweep)
                sweep_start = i
                current_sign = s

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

    # --- Stage 3: Click-centric aim analysis ---

    def _classify_click_aims(self):
        """For each click, analyze the approach and correction phases using RAW data."""
        if not self._click_times:
            return

        import bisect
        timestamps = [s.timestamp for s in self._samples]
        n = len(self._samples)

        for click_t in self._click_times:
            before_start_t = click_t - CLICK_WINDOW_BEFORE_S
            after_end_t = click_t + CLICK_WINDOW_AFTER_S

            i_start = bisect.bisect_left(timestamps, before_start_t)
            i_click = bisect.bisect_right(timestamps, click_t)
            i_end = bisect.bisect_right(timestamps, after_end_t)

            # Need at least a few samples before the click
            if i_click - i_start < 2:
                continue

            # --- Approach phase: find peak velocity using RAW data ---
            peak_velocity = 0.0
            peak_index = i_start
            speeds_before: list[tuple[int, float]] = []

            for i in range(max(i_start, 1), i_click):
                dt = self._samples[i].timestamp - self._samples[i - 1].timestamp
                if dt > 0:
                    # Use RAW dx/dy for velocity calculation
                    spd = math.hypot(
                        self._samples[i].dx / dt,
                        self._samples[i].dy / dt,
                    )
                    speeds_before.append((i, spd))
                    if spd > peak_velocity:
                        peak_velocity = spd
                        peak_index = i

            if peak_velocity < MIN_FLICK_VELOCITY_PX_S:
                # No significant flick before this click
                continue

            # Find where approach transitions to correction:
            # velocity drops below threshold of peak
            velocity_threshold = peak_velocity * CLICK_APPROACH_VELOCITY_DROP
            transition_index = i_click  # default: transition right at click

            for idx, spd in speeds_before:
                if idx > peak_index and spd <= velocity_threshold:
                    transition_index = idx
                    break

            # Approach displacement (raw, from start to transition)
            approach_disp = 0.0
            for i in range(i_start, min(transition_index, i_click)):
                approach_disp += math.hypot(
                    self._samples[i].dx,
                    self._samples[i].dy,
                )

            approach_duration = 0.0
            if i_start < len(timestamps) and transition_index < len(timestamps):
                approach_duration = timestamps[min(transition_index, i_click) - 1] - timestamps[i_start] if transition_index > i_start else 0.0

            if approach_disp < 1.0:
                continue

            # --- Correction phase: from transition to click, using RAW data ---
            correction_mag = 0.0
            dir_changes = 0
            angle_rotation = 0.0
            prev_angle = None
            correction_start_t = timestamps[transition_index] if transition_index < n else click_t

            # Also include samples after the click (post-click jitter)
            corr_range_start = transition_index
            corr_range_end = min(i_end, n)

            for i in range(corr_range_start, corr_range_end):
                # Use RAW data
                dx = self._samples[i].dx
                dy = self._samples[i].dy
                step = math.hypot(dx, dy)
                correction_mag += step

                if step > 0.5:  # ignore tiny noise
                    angle = math.atan2(dy, dx)
                    if prev_angle is not None:
                        delta = math.atan2(
                            math.sin(angle - prev_angle),
                            math.cos(angle - prev_angle),
                        )
                        angle_rotation += abs(delta)
                        if abs(delta) > math.pi / 3:  # >60° = direction change
                            dir_changes += 1
                    prev_angle = angle

            correction_duration = (timestamps[min(corr_range_end - 1, n - 1)] - correction_start_t) if corr_range_end > corr_range_start else 0.0

            # Overshoot percentage: correction / approach
            overshoot_pct = (correction_mag / approach_disp * 100.0) if approach_disp > 0 else 0.0

            is_swirl = angle_rotation > MIN_SWIRL_ANGLE_RAD

            self._click_aim_events.append(ClickAimEvent(
                click_time=click_t,
                approach_peak_velocity=peak_velocity,
                approach_displacement=approach_disp,
                approach_duration=approach_duration,
                correction_magnitude=correction_mag,
                correction_direction_changes=dir_changes,
                correction_angle_rotation=angle_rotation,
                correction_duration=correction_duration,
                overshoot_percentage=overshoot_pct,
                is_swirl=is_swirl,
            ))

    # --- Stage 4: Rowing classification ---

    def get_rowing_events(self) -> list[RowingEvent]:
        return self._rowing_events

    def _classify_rowing(self):
        self._classify_rowing_axis(self._sweeps_x)
        self._classify_rowing_axis(self._sweeps_y)

    def _classify_rowing_axis(self, sweeps: list[Sweep]):
        if len(sweeps) < MIN_ROWING_SWEEPS:
            return

        chain: list[Sweep] = [sweeps[0]]

        for i in range(1, len(sweeps)):
            prev = sweeps[i - 1]
            curr = sweeps[i]

            same_dir = _sign(prev.total_displacement) == _sign(curr.total_displacement)
            gap = curr.start_time - prev.end_time
            gap_ok = MIN_ROWING_GAP_S <= gap <= MAX_ROWING_GAP_S
            fast_enough = curr.peak_velocity >= MIN_ROWING_SWEEP_VELOCITY

            if same_dir and gap_ok and fast_enough:
                chain.append(curr)
            else:
                self._emit_rowing_event(chain)
                chain = [curr]

        self._emit_rowing_event(chain)

    def _emit_rowing_event(self, chain: list[Sweep]):
        if len(chain) < MIN_ROWING_SWEEPS:
            return

        displacements = [abs(s.total_displacement) for s in chain]
        total_disp = sum(displacements)
        max_single = max(displacements)
        gaps = []
        for i in range(1, len(chain)):
            gaps.append(chain[i].start_time - chain[i - 1].end_time)

        self._rowing_events.append(RowingEvent(
            axis=chain[0].axis,
            sweeps=chain,
            chain_length=len(chain),
            total_displacement=total_disp,
            max_single_displacement=max_single,
            increase_ratio=total_disp / max_single if max_single > 0 else 1.0,
            gap_durations=gaps,
            mean_gap_duration=sum(gaps) / len(gaps) if gaps else 0.0,
            timestamp=chain[0].start_time,
        ))
