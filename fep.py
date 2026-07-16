"""Active inference: an epistemic agent that buys knowledge until it is a demon.

Friston's expected free energy for an agent with no preferences reduces to pure
epistemic value: pick the observation that minimises expected posterior entropy.
Here the agent observes cells of the world one at a time and watches L_O climb.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from information import (
    ENTROPY_TOLERANCE,
    MAX_IRREDUCIBLE_WIDTH,
    conditional_entropy_for_mask,
    enumerate_event_outcomes,
    irreducible_profile,
)


@dataclass(frozen=True)
class EpistemicStep:
    """One epistemic action and the demon coefficient it bought."""

    cells: tuple[int, ...]
    entropy: float
    coefficient: float


def cell_mask(width: int, cells: Sequence[int]) -> int:
    """Bit mask of observed cells, cell 0 being the most significant bit."""
    mask = 0
    for cell in cells:
        mask |= 1 << (width - 1 - cell)
    return mask


def greedy_epistemic_path(
    width: int, rule: int, steps: int, event: str, budget: int | None = None
) -> list[EpistemicStep]:
    """Greedily observe the cell that removes the most uncertainty about E."""
    if not 1 <= width <= MAX_IRREDUCIBLE_WIDTH:
        raise ValueError(f"width must be between 1 and {MAX_IRREDUCIBLE_WIDTH}")
    limit = width if budget is None else budget
    if not 0 <= limit <= width:
        raise ValueError(f"budget must be between 0 and {width}")

    outcomes = enumerate_event_outcomes(width, rule, steps, event)
    event_entropy = conditional_entropy_for_mask(outcomes, 0)
    coefficient = 1.0 if event_entropy <= ENTROPY_TOLERANCE else 0.0
    path = [EpistemicStep((), event_entropy, coefficient)]

    observed: list[int] = []
    entropy = event_entropy
    while len(observed) < limit and entropy > ENTROPY_TOLERANCE:
        candidates = [cell for cell in range(width) if cell not in observed]
        best_cell = min(
            candidates,
            key=lambda cell: conditional_entropy_for_mask(
                outcomes, cell_mask(width, [*observed, cell])
            ),
        )
        best_entropy = conditional_entropy_for_mask(
            outcomes, cell_mask(width, [*observed, best_cell])
        )
        observed.append(best_cell)
        entropy = best_entropy
        path.append(
            EpistemicStep(
                tuple(observed),
                entropy,
                1.0 - entropy / event_entropy,
            )
        )
    return path


def active_inference_report(
    width: int, rule: int, steps: int, event: str, budget: int | None = None
) -> str:
    """Show the agent's epistemic foraging next to the exhaustive optimum."""
    path = greedy_epistemic_path(width, rule, steps, event, budget)
    optimum = irreducible_profile(width, rule, steps, event)
    event_entropy = path[0].entropy

    lines = ["Epistemic foraging: each action is one observed cell."]
    if event_entropy <= ENTROPY_TOLERANCE:
        lines.append("H(E)=0: the event is already certain, no action is needed.")
        return "\n".join(lines)

    lines.append(f"H(E) = {event_entropy:.6f} bits, L_O starts at 0.000000")
    for step in path[1:]:
        cells = ",".join(map(str, step.cells))
        lines.append(
            f"observe cell {step.cells[-1]}  ->  K={{{cells}}}"
            f"  H(E|K)={step.entropy:.6f}  L_O={step.coefficient:.6f}"
        )

    final = path[-1]
    spent = len(final.cells)
    if final.entropy <= ENTROPY_TOLERANCE:
        lines.append(
            f"The agent became a local demon after {spent} action(s): L_O = 1."
        )
    else:
        lines.append(
            f"Budget spent: L_O = {final.coefficient:.6f}, uncertainty left"
            f" {final.entropy:.6f} bits."
        )

    wasted = [
        step.cells[-1]
        for previous, step in zip(path, path[1:])
        if step.entropy >= previous.entropy - ENTROPY_TOLERANCE
    ]
    if wasted:
        lines.append(
            f"EPISTEMIC PLATEAU: observing cell(s) {','.join(map(str, wasted))}"
            " bought exactly zero information. Curiosity that follows the"
            " gradient can stall: under XOR-like laws a cell pays off only"
            " together with its partner, never alone."
        )

    cheapest = next(
        (level for level in optimum if level.entropy <= ENTROPY_TOLERANCE), None
    )
    if cheapest is not None and cheapest.cells < spent:
        best_cells = ",".join(map(str, cheapest.best_cells))
        lines.append(
            f"Greedy is NOT optimal: it paid {spent} observations, while the"
            f" exhaustive optimum needs {cheapest.cells}"
            f" (cells {best_cells}). Epistemic value is not submodular —"
            " gradient-following curiosity overpays."
        )
    elif final.entropy > optimum[spent].entropy + ENTROPY_TOLERANCE:
        best_cells = ",".join(map(str, optimum[spent].best_cells))
        lines.append(
            f"Greedy is NOT optimal: the best {spent} cells ({best_cells}) leave"
            f" only {optimum[spent].entropy:.6f} bits."
        )
    else:
        lines.append(
            f"Greedy matches the exhaustive optimum at {spent} observation(s)."
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Active inference: buy knowledge until the demon appears."
    )
    parser.add_argument("--width", type=int, default=7)
    parser.add_argument("--rule", type=int, default=30)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--event", default="cell3=1")
    parser.add_argument("--budget", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    """Run the epistemic agent from the command line."""
    args = parse_args()
    try:
        print(
            active_inference_report(
                args.width, args.rule, args.steps, args.event, args.budget
            )
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
