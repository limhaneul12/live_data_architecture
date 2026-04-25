from __future__ import annotations

import json
import os
import subprocess
import sys
import time


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    return subprocess.run(
        [sys.executable, "-m", "event_generator", *args],
        check=False,
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_cli_emits_exact_max_events_to_stdout() -> None:
    result = run_generator("--max-events", "10", "--seed", "20260424", "--no-sleep")

    lines = result.stdout.splitlines()

    assert result.returncode == 0
    assert len(lines) == 10
    assert "event_generator started" not in result.stdout
    assert "event_generator stopped" in result.stderr
    assert all(str(json.loads(line)["event_id"]).startswith("evt_") for line in lines)


def test_cli_is_reproducible_with_same_seed() -> None:
    args = ("--max-events", "20", "--seed", "20260424", "--no-sleep")

    first = run_generator(*args)
    second = run_generator(*args)

    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == second.stdout


def test_cli_rejects_invalid_positive_integer_options() -> None:
    result = run_generator("--max-events", "0")

    assert result.returncode != 0
    assert "value must be greater than or equal to 1" in result.stderr


def test_cli_rejects_invalid_phase_bounds() -> None:
    result = run_generator(
        "--min-phase-seconds",
        "30",
        "--max-phase-seconds",
        "10",
    )

    assert result.returncode != 0
    assert "min phase seconds must be less than or equal to max" in result.stderr


def test_cli_applies_custom_start_time_date_to_first_event() -> None:
    result = run_generator(
        "--max-events",
        "1",
        "--seed",
        "20260424",
        "--start-time",
        "2026-05-01T12:30:00Z",
        "--no-sleep",
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert str(payload["occurred_at"]).startswith("2026-05-01T")


def test_cli_exits_cleanly_when_sigterm_requests_shutdown() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "event_generator",
            "--seed",
            "20260424",
            "--slow-rate",
            "20",
            "--normal-rate",
            "20",
            "--burst-rate",
            "20",
        ],
        cwd=os.getcwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(0.25)
    process.terminate()
    stdout, stderr = process.communicate(timeout=5)

    assert process.returncode == 0
    assert "shutdown requested by SIGTERM" in stderr
    assert "event_generator stopped" in stderr
    assert stdout.splitlines()
    assert all(
        str(json.loads(line)["event_id"]).startswith("evt_")
        for line in stdout.splitlines()
    )
