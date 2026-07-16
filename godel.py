"""Finite illustrations of Wolpert's impossibility results (arXiv:0708.1362).

Two of his results get an exhaustive finite demonstration here:
  * no device can strongly infer itself      -> diagonal_report()
  * no two distinguishable devices can       -> mutual_inference_report()
    strongly infer each other
These are enumerations over every strategy in a one-bit world, not proofs of the
general theorems; they show the contradiction has nothing to do with complexity.
"""

from __future__ import annotations

from collections.abc import Callable

Predictor = Callable[[int], int]

# All four deterministic strategies over a one-bit observation: the enumeration
# is exhaustive, so the failure below is a proof for this finite world.
STRATEGIES: dict[str, Predictor] = {
    "always 0": lambda cell: 0,
    "always 1": lambda cell: 1,
    "copy the cell": lambda cell: cell,
    "invert the cell": lambda cell: 1 - cell,
}


def diagonal_next_cell(prediction: int) -> int:
    """World law with the demon inside: the cell becomes NOT the prediction."""
    return 1 - prediction


def external_next_cell(cell: int) -> int:
    """The same law without feedback: the world never reads the prediction."""
    return 1 - cell


def diagonal_report() -> str:
    """Show that every inner demon fails on X* while an outer demon succeeds."""
    lines = [
        'X* := "the cell becomes NOT whatever the demon predicts".',
        "The world reads the demon's published prediction (the demon is INSIDE).",
        "Every possible strategy over one bit:",
    ]
    for name, strategy in STRATEGIES.items():
        wrong = sum(
            strategy(cell) != diagonal_next_cell(strategy(cell)) for cell in (0, 1)
        )
        lines.append(f"  {name:16} wrong {wrong} of 2")

    correct_outside = max(
        STRATEGIES.items(),
        key=lambda item: sum(
            item[1](cell) == external_next_cell(cell) for cell in (0, 1)
        ),
    )
    outside_hits = sum(
        correct_outside[1](cell) == external_next_cell(cell) for cell in (0, 1)
    )
    lines += [
        "",
        "No strategy inside the world can be right — the Godel/Wolpert diagonal.",
        "The same law with the demon OUTSIDE (the world never reads the prediction):",
        f'  strategy "{correct_outside[0]}" is right {outside_hits} of 2 —'
        " a complete demon exists.",
        "Completeness breaks not with complexity but with membership in the world.",
    ]
    return "\n".join(lines)


def mutual_inference_fails(first: int, second: int) -> tuple[bool, bool]:
    """Strength means answering ANY question about the other device.

    So device A is asked "what will B output?" and device B is asked "will A
    output 0?". Each publishes its answer as its own output.
    """
    return first == second, second == 1 - first


def mutual_inference_report() -> str:
    """Enumerate every joint output: no pair satisfies both inferences."""
    lines = [
        "Two devices, each strong enough to answer any question about the other.",
        'A is asked "what will B output?"; B is asked "will A output 0?".',
        "Each device publishes its answer as its own output bit.",
        "",
        "  A  B | A right | B right",
    ]
    survivors = 0
    for first in (0, 1):
        for second in (0, 1):
            first_ok, second_ok = mutual_inference_fails(first, second)
            survivors += first_ok and second_ok
            lines.append(
                f"  {first}  {second} |  {str(first_ok):5} |  {str(second_ok):5}"
            )
    lines += [
        "",
        f"Joint outputs where both devices are right: {survivors} of 4.",
        "No two distinguishable devices can strongly infer each other"
        " (Wolpert, Physical Limits of Inference, arXiv:0708.1362) —"
        " his 'monotheism theorem': a universe fits at most ONE all-knowing"
        " inference device.",
        "The pair fails for the same reason a single device fails on X*:"
        " self-reference, not lack of power.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(diagonal_report())
    print()
    print(mutual_inference_report())
