"""Measure prediction limits in the local deterministic universe."""

from __future__ import annotations

import argparse
import csv
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean

from demon import next_state, validate_rule, validate_state

DEFAULT_STATE = "0000000000000001000000000000000"
DEFAULT_RULE = 30
DEFAULT_STEPS = 10
DEFAULT_RUNS = 100
DEFAULT_SEED = 42
PREDICTABILITY_THRESHOLD = 0.95
CSV_FIELDS = (
    "scenario",
    "step",
    "predictability",
    "exact_match_rate",
)


@dataclass(frozen=True)
class Scenario:
    """One experimentally controlled source of uncertainty."""

    name: str
    initial_error: float
    rule_error: float
    noise: float


SCENARIOS = (
    Scenario("perfect", 0.00, 0.00, 0.00),
    Scenario("measurement_error", 0.05, 0.00, 0.00),
    Scenario("model_error", 0.00, 0.05, 0.00),
    Scenario("intrinsic_noise", 0.00, 0.00, 0.01),
    Scenario("combined", 0.05, 0.05, 0.01),
    Scenario("improved_data", 0.01, 0.01, 0.01),
)


def validate_probability(value: float, name: str) -> None:
    """Reject invalid uncertainty parameters."""
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


def flip_state(state: str, probability: float, rng: random.Random) -> str:
    """Apply independent bit errors to a state."""
    validate_state(state)
    validate_probability(probability, "probability")
    return "".join(
        str(1 - int(cell)) if rng.random() < probability else cell for cell in state
    )


def perturb_rule(rule: int, probability: float, rng: random.Random) -> int:
    """Sample a plausible rule by independently flipping its eight table bits."""
    validate_rule(rule)
    validate_probability(probability, "probability")
    sampled = rule
    for bit in range(8):
        if rng.random() < probability:
            sampled ^= 1 << bit
    return sampled


def simulate(
    state: str,
    rule: int,
    steps: int,
    noise: float,
    rng: random.Random,
) -> list[str]:
    """Return a complete trajectory, including its initial state."""
    validate_state(state)
    validate_rule(rule)
    validate_probability(noise, "noise")
    if steps < 0:
        raise ValueError("steps must not be negative")

    trajectory = [state]
    current = state
    for _ in range(steps):
        current = next_state(current, rule)
        current = flip_state(current, noise, rng)
        trajectory.append(current)
    return trajectory


def predictability(states: Sequence[str]) -> float:
    """Return one minus normalized per-cell variance across possible states."""
    if not states:
        raise ValueError("states must not be empty")
    width = len(states[0])
    if width == 0 or any(len(state) != width for state in states):
        raise ValueError("states must have one non-empty width")
    for state in states:
        validate_state(state)

    uncertainty = fmean(
        4.0 * frequency * (1.0 - frequency)
        for frequency in (
            fmean(int(state[cell]) for state in states) for cell in range(width)
        )
    )
    return 1.0 - uncertainty


def run_experiment(
    state: str,
    rule: int,
    steps: int,
    runs: int,
    seed: int,
    scenarios: Sequence[Scenario] = SCENARIOS,
) -> list[dict[str, str | int | float]]:
    """Run all scenarios and return tidy per-step measurements."""
    validate_state(state)
    validate_rule(rule)
    if steps < 0:
        raise ValueError("steps must not be negative")
    if runs < 2:
        raise ValueError("runs must be at least 2")

    truth = simulate(state, rule, steps, 0.0, random.Random(seed))
    rows: list[dict[str, str | int | float]] = []

    for scenario_index, scenario in enumerate(scenarios):
        validate_probability(scenario.initial_error, "initial_error")
        validate_probability(scenario.rule_error, "rule_error")
        validate_probability(scenario.noise, "noise")
        rng = random.Random(seed + scenario_index)
        trajectories = []

        for _ in range(runs):
            sampled_state = flip_state(state, scenario.initial_error, rng)
            sampled_rule = perturb_rule(rule, scenario.rule_error, rng)
            trajectories.append(
                simulate(sampled_state, sampled_rule, steps, scenario.noise, rng)
            )

        for step in range(steps + 1):
            possible_states = [trajectory[step] for trajectory in trajectories]
            rows.append(
                {
                    "scenario": scenario.name,
                    "step": step,
                    "predictability": predictability(possible_states),
                    "exact_match_rate": fmean(
                        possible == truth[step] for possible in possible_states
                    ),
                }
            )

    return rows


def write_csv(
    path: Path, rows: Sequence[dict[str, str | int | float]]
) -> None:
    """Write experiment measurements as UTF-8 CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: Sequence[dict[str, str | int | float]]) -> None:
    """Print final predictability and first failed horizon for every scenario."""
    print("scenario             final_predictability  exact_match  horizon")
    names = dict.fromkeys(str(row["scenario"]) for row in rows)
    for name in names:
        selected = [row for row in rows if row["scenario"] == name]
        failed = [
            int(row["step"])
            for row in selected
            if float(row["predictability"]) < PREDICTABILITY_THRESHOLD
        ]
        horizon = str(failed[0]) if failed else "not reached"
        final = selected[-1]
        print(
            f"{name:20} "
            f"{float(final['predictability']):20.3f} "
            f"{float(final['exact_match_rate']):12.3f}  {horizon}"
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Measure how uncertainty limits a local Laplace demon."
    )
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--rule", type=int, default=DEFAULT_RULE)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=Path("results.csv"))
    return parser.parse_args(argv)


def run(argv: Sequence[str] | None = None) -> int:
    """Run the experiment CLI."""
    args = parse_args(argv)
    try:
        rows = run_experiment(args.state, args.rule, args.steps, args.runs, args.seed)
        write_csv(args.output, rows)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print_summary(rows)
    print(f"\nCSV: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
