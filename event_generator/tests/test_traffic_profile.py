import pytest
from event_generator.models import TrafficPhase
from event_generator.traffic_profile import (
    PhaseRates,
    TrafficProfile,
    TrafficProfileConfig,
)


def test_same_seed_generates_same_phase_sequence() -> None:
    config = TrafficProfileConfig(rates=PhaseRates())
    first = TrafficProfile(seed=20260425, config=config)
    second = TrafficProfile(seed=20260425, config=config)

    first_phases = [first.next_phase() for _ in range(100)]
    second_phases = [second.next_phase() for _ in range(100)]

    assert first_phases == second_phases


def test_phase_rates_match_configuration() -> None:
    rates = PhaseRates(slow=2, normal=7, burst=30)

    assert rates.for_phase(TrafficPhase.SLOW) == 2
    assert rates.for_phase(TrafficPhase.NORMAL) == 7
    assert rates.for_phase(TrafficPhase.BURST) == 30


def test_invalid_phase_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match="slow rate"):
        PhaseRates(slow=0)


def test_invalid_phase_bounds_are_rejected() -> None:
    with pytest.raises(ValueError, match="min phase seconds"):
        TrafficProfileConfig(rates=PhaseRates(), min_phase_seconds=0)

    with pytest.raises(ValueError, match="less than or equal"):
        TrafficProfileConfig(
            rates=PhaseRates(),
            min_phase_seconds=30,
            max_phase_seconds=10,
        )
