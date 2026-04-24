"""Seeded traffic phase generation for the event producer."""

from __future__ import annotations

import random
from dataclasses import dataclass

from event_generator.models import TrafficPhase

_PHASES: tuple[TrafficPhase, ...] = (
    TrafficPhase.NORMAL,
    TrafficPhase.SLOW,
    TrafficPhase.BURST,
)
_PHASE_WEIGHTS: tuple[int, ...] = (60, 25, 15)


@dataclass(frozen=True, slots=True, kw_only=True)
class PhaseRates:
    """Events-per-second limits for each traffic phase."""

    slow: int = 1
    normal: int = 5
    burst: int = 20

    def __post_init__(self) -> None:
        """Validate all configured phase rates."""
        for name, rate in (
            ("slow", self.slow),
            ("normal", self.normal),
            ("burst", self.burst),
        ):
            if rate < 1:
                raise ValueError(  # noqa: TRY003
                    f"{name} rate must be greater than or equal to 1",
                )

    def for_phase(self, phase: TrafficPhase) -> int:
        """Return the configured events-per-second rate for a phase.

        Args:
            phase: Traffic phase to look up.

        Returns:
            Events-per-second rate for the phase.
        """
        match phase:
            case TrafficPhase.SLOW:
                return self.slow
            case TrafficPhase.NORMAL:
                return self.normal
            case TrafficPhase.BURST:
                return self.burst


@dataclass(frozen=True, slots=True, kw_only=True)
class TrafficProfileConfig:
    """Configuration for seeded slow/normal/burst phase simulation."""

    rates: PhaseRates
    min_phase_seconds: int = 10
    max_phase_seconds: int = 30

    def __post_init__(self) -> None:
        """Validate phase duration bounds."""
        if self.min_phase_seconds < 1:
            raise ValueError(  # noqa: TRY003
                "min phase seconds must be greater than or equal to 1",
            )
        if self.max_phase_seconds < 1:
            raise ValueError(  # noqa: TRY003
                "max phase seconds must be greater than or equal to 1",
            )
        if self.min_phase_seconds > self.max_phase_seconds:
            raise ValueError(  # noqa: TRY003
                "min phase seconds must be less than or equal to max",
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class PhaseWindow:
    """Concrete traffic phase window selected from the profile."""

    phase: TrafficPhase
    duration_seconds: int
    event_capacity: int


class TrafficProfile:
    """Produce deterministic traffic phases and per-phase event delays."""

    def __init__(self, *, seed: int, config: TrafficProfileConfig) -> None:
        """Create a profile using a dedicated seeded random generator.

        Args:
            seed: Seed for deterministic traffic phase selection.
            config: Traffic phase duration and rate configuration.
        """
        self._rng = random.Random(seed)  # noqa: S311
        self._config = config
        self._current_window: PhaseWindow | None = None
        self._remaining_events_in_window = 0

    def next_phase(self) -> TrafficPhase:
        """Return the phase for the next event, rotating windows as needed.

        Args:
            None.

        Returns:
            Traffic phase to apply to the next generated event.
        """
        if self._remaining_events_in_window <= 0:
            self._current_window = self._choose_window()
            self._remaining_events_in_window = self._current_window.event_capacity

        self._remaining_events_in_window -= 1
        if self._current_window is None:
            raise RuntimeError(  # noqa: TRY003
                "traffic phase window was not initialized",
            )
        return self._current_window.phase

    def seconds_between_events(self, phase: TrafficPhase) -> float:
        """Return sleep seconds needed to honor the phase rate limit.

        Args:
            phase: Traffic phase whose rate should be enforced.

        Returns:
            Seconds between consecutive events for the phase.
        """
        return 1.0 / self._config.rates.for_phase(phase)

    def rate_for_phase(self, phase: TrafficPhase) -> int:
        """Return the configured rate for a phase.

        Args:
            phase: Traffic phase to look up.

        Returns:
            Events-per-second rate for the phase.
        """
        return self._config.rates.for_phase(phase)

    def _choose_window(self) -> PhaseWindow:
        phase = self._rng.choices(_PHASES, weights=_PHASE_WEIGHTS, k=1)[0]
        duration_seconds = self._rng.randint(
            self._config.min_phase_seconds,
            self._config.max_phase_seconds,
        )
        event_capacity = duration_seconds * self._config.rates.for_phase(phase)
        return PhaseWindow(
            phase=phase,
            duration_seconds=duration_seconds,
            event_capacity=event_capacity,
        )
