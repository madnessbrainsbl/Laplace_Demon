"""Exact predictor for a finite deterministic local universe."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence

MIN_RULE = 0
MAX_RULE = 255
VALID_CELLS = frozenset("01")
MAX_RETRODICTION_WIDTH = 16
MAX_LISTED_PASTS = 8


def validate_state(state: str) -> None:
    """Reject empty or non-binary universe states."""
    if not state:
        raise ValueError("state must not be empty")
    if not set(state) <= VALID_CELLS:
        raise ValueError("state must contain only 0 and 1")


def validate_rule(rule: int) -> None:
    """Reject values outside the elementary cellular automaton rule range."""
    if not MIN_RULE <= rule <= MAX_RULE:
        raise ValueError(f"rule must be between {MIN_RULE} and {MAX_RULE}")


def next_state(state: str, rule: int) -> str:
    """Advance a periodic one-dimensional universe by one exact step."""
    validate_state(state)
    validate_rule(rule)
    width = len(state)
    cells: list[str] = []

    for index in range(width):
        left = int(state[(index - 1) % width])
        center = int(state[index])
        right = int(state[(index + 1) % width])
        neighborhood = (left << 2) | (center << 1) | right
        cells.append(str((rule >> neighborhood) & 1))

    return "".join(cells)


def predict(state: str, rule: int, steps: int) -> str:
    """Return the exact state after steps, skipping any discovered cycle."""
    validate_state(state)
    validate_rule(rule)
    if steps < 0:
        raise ValueError("steps must not be negative")

    history: list[str] = []
    seen_at: dict[str, int] = {}
    current = state

    for step in range(steps):
        if current in seen_at:
            cycle_start = seen_at[current]
            cycle_length = step - cycle_start
            target = cycle_start + (steps - cycle_start) % cycle_length
            return history[target]
        seen_at[current] = step
        history.append(current)
        current = next_state(current, rule)

    return current


def preimages(state: str, rule: int) -> list[str]:
    """Every yesterday that leads to this today: exact enumeration."""
    validate_state(state)
    validate_rule(rule)
    width = len(state)
    if width > MAX_RETRODICTION_WIDTH:
        raise ValueError(
            f"retrodiction enumerates 2^width pasts — width must be at most"
            f" {MAX_RETRODICTION_WIDTH}"
        )
    return [
        candidate
        for value in range(1 << width)
        if next_state(candidate := f"{value:0{width}b}", rule) == state
    ]


def retrodiction_report(state: str, rule: int) -> str:
    """Laplace promised the past as well as the future; check that promise."""
    pasts = preimages(state, rule)
    lines = [
        f"Pasts that evolve into {state} under rule {rule}: {len(pasts)}",
    ]
    if not pasts:
        lines.append(
            "GARDEN OF EDEN: no yesterday leads here — this state can only be"
            " created, never reached. Retrodiction is impossible."
        )
    elif len(pasts) == 1:
        lines.append(f"Unique past: {pasts[0]}")
        lines.append(
            "The immediately preceding state is determined. This alone does not"
            " guarantee a unique earlier history: check each additional step."
        )
    else:
        shown = ", ".join(pasts[:MAX_LISTED_PASTS])
        suffix = ", ..." if len(pasts) > MAX_LISTED_PASTS else ""
        lines.append(f"Possible pasts: {shown}{suffix}")
        lines.append(
            f"THE ARROW OF TIME: forward the law gives one future, backward it"
            f" gives {len(pasts)} pasts — assuming a uniform prior over them,"
            f" {math.log2(len(pasts)):.3f} bits of history were destroyed."
            " Even a demon with the complete present cannot know which past"
            " happened."
        )
        lines.append(
            "Irreversibility, not ignorance: this is the wall Laplace's own"
            " definition ('the past, like the future, present to its eyes')"
            " runs into."
        )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Predict a finite deterministic universe exactly."
    )
    parser.add_argument("--state", required=True, help="Initial binary state.")
    parser.add_argument("--rule", required=True, type=int, help="Rule from 0 to 255.")
    parser.add_argument("--steps", required=True, type=int, help="Prediction horizon.")
    parser.add_argument("--cell", type=int, help="Optional final cell to inspect.")
    return parser.parse_args(argv)


def run(argv: Sequence[str] | None = None) -> int:
    """Run the predictor and print one machine-readable result."""
    args = parse_args(argv)
    try:
        final_state = predict(args.state, args.rule, args.steps)
        if args.cell is not None and not 0 <= args.cell < len(final_state):
            raise ValueError(f"cell must be between 0 and {len(final_state) - 1}")
    except ValueError as error:
        raise SystemExit(str(error)) from error

    result: dict[str, object] = {
        "initial_state": args.state,
        "rule": args.rule,
        "steps": args.steps,
        "predicted_state": final_state,
        "exact_within_model": True,
    }
    if args.cell is not None:
        result["cell"] = args.cell
        result["cell_value"] = int(final_state[args.cell])

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
