from __future__ import annotations
import math
from dataclasses import dataclass
from collector import MouseSample
from config import (
    EMA_ALPHA, DEAD_ZONE_PIXELS,
    MIN_SWEEP_DURATION_S, MIN_SWEEP_PIXELS,
    MAX_CORRECTION_GAP_S, MAX_CORRECTION_RATIO,
    MIN_FLICK_VELOCITY_PX_S, VELOCITY_RATIO_THRESHOLD,
    MAX_CORRECTION_DURATION_S,
    MIN_ROWING_GAP_S, MAX_ROWING_GAP_S,
    MIN_ROWING_SWEEPS, MIN_ROWING_SWEEP_VELOCITY,
    MIN_SWIRL_ANGLE_RAD, MAX_SWIRL_CORRECTION_S,
    SWIRL_DOT_THRESHOLD,
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
class OvershootEvent:
    axis: str
    initial_sweep: Sweep
    correction_sweep: Sweep
    overshoot_distance: float
    overshoot_percentage: float
    timestamp: float


@dataclass
class SwirlEvent:
    flick_start_index: int
    flick_end_index: int
    flick_start_time: float
    flick_end_time: float
    flick_displacement_x: float
    flick_displacement_y: float
    flick_magnitude: float
    flick_peak_velocity: float
    flick_direction: float  # radians
    correction_start_index: int
    correction_end_index: int
    correction_start_time: float
    correction_end_time: float
    correction_displacement_x: float
    correction_displacement_y: float
    correction_magnitude: float
    overshoot_percentage: float
    total_angle_rotation: float  # radians
    peak_correction_velocity: float
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
        self._rowing_events: list[RowingEvent] = []
        self._swirl_events: list[SwirlEvent] = []

    def detect(self) -> list[OvershootEvent]:
        if len(self._samples) < 2:
            return []
        self._filter_noise()
        self._segment_sweeps()
        self._classify_overshoots()
        self._classify_swirls()
        self._merge_events()
        self._classify_rowing()
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
            time_gap = self._samples[i].timestamp - self._samples[i - 1].timestamp
            if (s != 0 and s != current_sign) or time_gap > MIN_ROWING_GAP_S:
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

    # --- Stage 4: Swirl (2D overshoot) detection ---

    def get_swirl_events(self) -> list[SwirlEvent]:
        return self._swirl_events

    def _compute_2d_velocities(self) -> tuple[list[float], list[float], list[float], list[float]]:
        """Compute per-sample 2D velocity vectors. Returns (vx, vy, speed, angle)."""
        n = len(self._samples)
        vx = [0.0] * n
        vy = [0.0] * n
        speed = [0.0] * n
        angle = [0.0] * n

        for i in range(1, n):
            dt = self._samples[i].timestamp - self._samples[i - 1].timestamp
            if dt <= 0:
                continue
            vx[i] = self._smoothed_dx[i] / dt
            vy[i] = self._smoothed_dy[i] / dt
            speed[i] = math.hypot(vx[i], vy[i])
            angle[i] = math.atan2(vy[i], vx[i])

        return vx, vy, speed, angle

    def _find_flick_segments(self, speed: list[float]) -> list[tuple[int, int]]:
        """Find contiguous runs where 2D speed >= flick threshold."""
        segments = []
        in_flick = False
        start = 0

        for i in range(1, len(speed)):
            if speed[i] >= MIN_FLICK_VELOCITY_PX_S:
                if not in_flick:
                    start = i
                    in_flick = True
            else:
                if in_flick:
                    segments.append((start, i - 1))
                    in_flick = False

        if in_flick:
            segments.append((start, len(speed) - 1))

        return segments

    def _check_swirl_correction(
        self, flick_start: int, flick_end: int,
        vx: list[float], vy: list[float], speed: list[float], angle: list[float],
    ) -> SwirlEvent | None:
        """Check if a swirl correction follows the given flick."""
        samples = self._samples
        n = len(samples)

        # Compute flick properties
        flick_dx = sum(self._smoothed_dx[flick_start:flick_end + 1])
        flick_dy = sum(self._smoothed_dy[flick_start:flick_end + 1])
        flick_mag = math.hypot(flick_dx, flick_dy)
        if flick_mag < MIN_SWEEP_PIXELS:
            return None
        flick_dir = math.atan2(flick_dy, flick_dx)
        flick_peak_vel = max(speed[flick_start:flick_end + 1])

        # Scan for correction starting right after flick
        corr_start = flick_end + 1
        if corr_start >= n:
            return None

        flick_end_time = samples[flick_end].timestamp
        max_corr_end_time = flick_end_time + MAX_SWIRL_CORRECTION_S

        # Find correction end (within time window, while speed is below flick)
        corr_end = corr_start
        cumulative_angle = 0.0
        corr_dx = 0.0
        corr_dy = 0.0
        peak_corr_vel = 0.0
        total_corr_speed = 0.0
        corr_count = 0

        for i in range(corr_start, n):
            if samples[i].timestamp > max_corr_end_time:
                break

            corr_end = i
            corr_dx += self._smoothed_dx[i]
            corr_dy += self._smoothed_dy[i]
            peak_corr_vel = max(peak_corr_vel, speed[i])
            total_corr_speed += speed[i]
            corr_count += 1

            # Track angle rotation
            if i > corr_start and speed[i] > DEAD_ZONE_PIXELS and speed[i - 1] > DEAD_ZONE_PIXELS:
                delta = angle[i] - angle[i - 1]
                # Wrap to [-pi, pi]
                delta = math.atan2(math.sin(delta), math.cos(delta))
                cumulative_angle += abs(delta)

        if corr_count < 2:
            return None

        corr_mag = math.hypot(corr_dx, corr_dy)
        if corr_mag < MIN_SWEEP_PIXELS:
            return None

        # Check swirl conditions:
        # 1. Angle rotation threshold (correction arc curves)
        if cumulative_angle < MIN_SWIRL_ANGLE_RAD:
            return None

        # 2. Velocity decay (correction is slower than flick)
        mean_corr_vel = total_corr_speed / corr_count
        if mean_corr_vel >= flick_peak_vel * VELOCITY_RATIO_THRESHOLD:
            return None

        # 3. Correction opposes flick direction (dot product)
        # Normalize and compute dot product
        dot = (corr_dx * flick_dx + corr_dy * flick_dy) / (corr_mag * flick_mag)
        if dot > SWIRL_DOT_THRESHOLD:
            return None

        # 4. Magnitude ratio
        ratio = corr_mag / flick_mag
        if ratio > MAX_CORRECTION_RATIO:
            return None

        overshoot_pct = ratio * 100.0

        return SwirlEvent(
            flick_start_index=flick_start,
            flick_end_index=flick_end,
            flick_start_time=samples[flick_start].timestamp,
            flick_end_time=samples[flick_end].timestamp,
            flick_displacement_x=flick_dx,
            flick_displacement_y=flick_dy,
            flick_magnitude=flick_mag,
            flick_peak_velocity=flick_peak_vel,
            flick_direction=flick_dir,
            correction_start_index=corr_start,
            correction_end_index=corr_end,
            correction_start_time=samples[corr_start].timestamp,
            correction_end_time=samples[corr_end].timestamp,
            correction_displacement_x=corr_dx,
            correction_displacement_y=corr_dy,
            correction_magnitude=corr_mag,
            overshoot_percentage=overshoot_pct,
            total_angle_rotation=cumulative_angle,
            peak_correction_velocity=peak_corr_vel,
            timestamp=samples[corr_start].timestamp,
        )

    def _classify_swirls(self):
        """Main swirl detection: find 2D flick+correction arcs."""
        vx, vy, speed, angle = self._compute_2d_velocities()
        flick_segments = self._find_flick_segments(speed)

        for start, end in flick_segments:
            event = self._check_swirl_correction(start, end, vx, vy, speed, angle)
            if event:
                self._swirl_events.append(event)

    def _merge_events(self):
        """Remove per-axis OvershootEvents that overlap with SwirlEvents."""
        if not self._swirl_events:
            return

        merged = []
        for oe in self._events:
            overlaps = False
            for se in self._swirl_events:
                # Check if correction windows overlap
                oe_start = oe.correction_sweep.start_time
                oe_end = oe.correction_sweep.end_time
                if oe_start <= se.correction_end_time and oe_end >= se.correction_start_time:
                    overlaps = True
                    break
            if not overlaps:
                merged.append(oe)
        self._events = merged

    # --- Stage 5: Rowing classification ---

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
