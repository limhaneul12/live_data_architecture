"""Command-line interface for the independent event generator."""

from __future__ import annotations

import argparse
import secrets
import signal
import sys
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from types import FrameType

from event_generator.generator import EventGenerator, EventGeneratorConfig
from event_generator.models import EventType
from event_generator.serialization import event_to_json_line
from event_generator.sinks import RedisStreamEventSink, StdoutEventSink
from event_generator.traffic_profile import (
    PhaseRates,
    TrafficProfile,
    TrafficProfileConfig,
)


@dataclass(slots=True)
class ShutdownFlag:
    """Mutable signal flag shared with the CLI event loop."""

    requested: bool = False


def build_parser() -> argparse.ArgumentParser:
    """Build the event generator CLI argument parser.

    Args:
        None.

    Returns:
        Configured event generator argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="event_generator",
        description="Generate commerce web-service events as stdout JSON Lines.",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-events", type=positive_int, default=None)
    parser.add_argument("--producer-id", default="producer_local")
    parser.add_argument(
        "--start-time", type=parse_utc_datetime, default="2026-04-24T00:00:00Z"
    )
    parser.add_argument("--slow-rate", type=positive_int, default=1)
    parser.add_argument("--normal-rate", type=positive_int, default=5)
    parser.add_argument("--burst-rate", type=positive_int, default=20)
    parser.add_argument("--min-phase-seconds", type=positive_int, default=10)
    parser.add_argument("--max-phase-seconds", type=positive_int, default=30)
    parser.add_argument("--sink", choices=("stdout", "redis"), default="stdout")
    parser.add_argument(
        "--no-sleep",
        action="store_true",
        help="Skip real sleeping while keeping deterministic phase/rate calculation.",
    )
    return parser


def positive_int(value: str) -> int:
    """Parse a CLI value that must be a positive integer.

    Args:
        value: Raw CLI argument value.

    Returns:
        Parsed positive integer.

    Raises:
        argparse.ArgumentTypeError: If the parsed integer is smaller than 1.
    """
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError(  # noqa: TRY003
            "value must be greater than or equal to 1",
        )
    return parsed


def parse_utc_datetime(value: str) -> datetime:
    """Parse an ISO-8601 datetime and normalize it to UTC.

    Args:
        value: Raw ISO-8601 CLI argument value.

    Returns:
        Timezone-aware UTC datetime.

    Raises:
        argparse.ArgumentTypeError: If the value is invalid or timezone-naive.
    """
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(  # noqa: TRY003
            "value must be an ISO-8601 datetime",
        ) from exc

    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(  # noqa: TRY003
            "value must include timezone information",
        )
    return parsed.astimezone(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the event generator CLI.

    Args:
        argv: Optional argument list. When omitted, argparse reads process argv.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        seed = args.seed if args.seed is not None else secrets.randbits(64)
        rates = PhaseRates(
            slow=args.slow_rate,
            normal=args.normal_rate,
            burst=args.burst_rate,
        )
        traffic_config = TrafficProfileConfig(
            rates=rates,
            min_phase_seconds=args.min_phase_seconds,
            max_phase_seconds=args.max_phase_seconds,
        )
    except ValueError as exc:
        parser.error(str(exc))

    shutdown_flag = ShutdownFlag()
    install_signal_handlers(shutdown_flag=shutdown_flag)

    generator = EventGenerator(
        config=EventGeneratorConfig(
            seed=seed,
            producer_id=args.producer_id,
            start_time=args.start_time,
        ),
        traffic_profile=TrafficProfile(seed=seed + 1, config=traffic_config),
    )
    sink = build_event_sink(args)

    event_counts: Counter[str] = Counter()
    emitted = 0
    print(
        "event_generator started "
        f"seed={seed} max_events={args.max_events} sink={args.sink} "
        f"no_sleep={args.no_sleep}",
        file=sys.stderr,
    )

    try:
        for event in generator.iter_events(max_events=args.max_events):
            if shutdown_flag.requested:
                break

            sink.emit(event_to_json_line(event))
            emitted += 1
            event_counts[event.event_type.value] += 1

            if args.max_events is not None and emitted >= args.max_events:
                break
            if not args.no_sleep:
                time.sleep(generator.seconds_until_next_event(event.traffic_phase))
    finally:
        sink.close()

    print_summary(emitted=emitted, event_counts=event_counts)
    return 0


def build_event_sink(
    args: argparse.Namespace,
) -> StdoutEventSink | RedisStreamEventSink:
    """Build the configured output sink for generated events.

    Args:
        args: Parsed CLI arguments containing the requested sink name.

    Returns:
        Stdout or Redis Stream event sink.
    """
    if args.sink == "redis":
        return RedisStreamEventSink.from_environment()
    return StdoutEventSink()


def install_signal_handlers(*, shutdown_flag: ShutdownFlag) -> None:
    """Install SIGINT/SIGTERM handlers that request graceful shutdown.

    Args:
        shutdown_flag: Mutable flag toggled by SIGINT/SIGTERM handlers.

    Returns:
        None.
    """

    def request_shutdown(signum: int, _frame: FrameType | None) -> None:
        """Record that a termination signal requested graceful shutdown.

        Args:
            signum: POSIX signal number.
            _frame: Current interpreter frame supplied by signal handling.

        Returns:
            None.
        """
        shutdown_flag.requested = True
        signal_name = signal.Signals(signum).name
        print(f"shutdown requested by {signal_name}", file=sys.stderr)

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)


def print_summary(*, emitted: int, event_counts: Counter[str]) -> None:
    """Print a compact generation summary to stderr.

    Args:
        emitted: Number of events emitted before shutdown.
        event_counts: Counts grouped by event type.

    Returns:
        None.
    """
    ordered_counts = {
        event_type.value: event_counts.get(event_type.value, 0)
        for event_type in EventType
    }
    print(
        f"event_generator stopped emitted={emitted} counts={ordered_counts}",
        file=sys.stderr,
    )
