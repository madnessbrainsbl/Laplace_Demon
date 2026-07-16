"""Law-inferring Laplace demon: learns the rule from observed events."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence

from demon import predict, validate_state
from interactive import classical_event_occurs
from quantum import classify_probability

NEIGHBORHOODS = 8


def parse_history(text: str) -> list[str]:
    """Parse semicolon- or newline-separated observed states."""
    states = [part.strip() for part in text.replace("\n", ";").split(";")]
    states = [state for state in states if state]
    if not states:
        raise ValueError("history must contain at least one state")
    for state in states:
        validate_state(state)
    if len({len(state) for state in states}) != 1:
        raise ValueError("history states must share one width")
    return states


def observe_law(history: Sequence[str]) -> dict[int, int]:
    """Extract known rule-table rows from consecutive observed states."""
    table: dict[int, int] = {}
    for before, after in zip(history, history[1:]):
        width = len(before)
        for index in range(width):
            left = int(before[(index - 1) % width])
            center = int(before[index])
            right = int(before[(index + 1) % width])
            neighborhood = (left << 2) | (center << 1) | right
            output = int(after[index])
            known = table.get(neighborhood)
            if known is not None and known != output:
                raise ValueError(
                    "history contradicts every deterministic local law"
                )
            table[neighborhood] = output
    return table


def consistent_rules(table: dict[int, int]) -> list[int]:
    """Enumerate every elementary rule consistent with the observations."""
    unknown = [n for n in range(NEIGHBORHOODS) if n not in table]
    base = sum(bit << neighborhood for neighborhood, bit in table.items())
    rules: list[int] = []
    for value in range(1 << len(unknown)):
        rule = base
        for position, neighborhood in enumerate(unknown):
            rule |= ((value >> position) & 1) << neighborhood
        rules.append(rule)
    return rules


def event_report(history_text: str, steps: int, event: str) -> str:
    """Predict an event using only laws learnable from the history."""
    history = parse_history(history_text)
    if steps < 0:
        raise ValueError("steps must not be negative")
    table = observe_law(history)
    rules = consistent_rules(table)
    current = history[-1]

    final_states: Counter[str] = Counter()
    hits = 0
    for rule in rules:
        final_state = predict(current, rule, steps)
        final_states[final_state] += 1
        if classical_event_occurs(final_state, event):
            hits += 1
    probability = hits / len(rules)

    lines = [
        f"Observed transitions: {len(history) - 1}",
        f"Known law rows: {len(table)} of {NEIGHBORHOODS}",
        f"Consistent rules: {len(rules)}",
        f"Possible final states: {len(final_states)}",
    ]
    if len(final_states) == 1:
        lines.append(f"Predicted state: {next(iter(final_states))}")
    lines.append(classify_probability(probability))
    if len(rules) > 1:
        lines.append(
            "All laws consistent with the events are treated as equally likely."
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Infer the law from observed events and predict."
    )
    parser.add_argument("--history", required=True, help="States joined by ';'.")
    parser.add_argument("--steps", type=int, default=1, help="Prediction horizon.")
    parser.add_argument("--event", default="cell3=1", help="cellN=0/1 or state=bits.")
    return parser.parse_args()


def main() -> int:
    """Run the event demon from the command line."""
    args = parse_args()
    try:
        print(event_report(args.history, args.steps, args.event))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
