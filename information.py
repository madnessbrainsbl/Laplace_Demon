"""Empirical Shannon metrics for the local Laplace formula."""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from demon import predict, validate_rule
from interactive import classical_event_occurs

MAX_ENUMERATION_WIDTH = 14
MAX_ENUMERATION_WORK = 1_000_000
MAX_IRREDUCIBLE_WIDTH = 10
ENTROPY_TOLERANCE = 1e-12


@dataclass(frozen=True)
class LaplaceMetrics:
    """All terms of R=H(E|K) and L=I(E;K)/H(E)."""

    event_entropy: float
    conditional_entropy: float
    mutual_information: float
    coefficient: float
    samples: int
    knowledge_states: int
    trivial_event: bool


def entropy_from_counts(counts: Sequence[int]) -> float:
    """Calculate Shannon entropy in bits from non-negative counts."""
    if not counts or any(count < 0 for count in counts):
        raise ValueError("counts must be non-empty and non-negative")
    total = sum(counts)
    if total == 0:
        raise ValueError("counts must have a positive total")
    return -sum(
        (count / total) * math.log2(count / total) for count in counts if count
    )


def laplace_metrics(
    events: Sequence[bool], knowledge: Sequence[Hashable]
) -> LaplaceMetrics:
    """Estimate H(E), H(E|K), I(E;K) and normalized information."""
    if not events or len(events) != len(knowledge):
        raise ValueError("events and knowledge must have one equal positive length")

    event_counts = Counter(events)
    event_entropy = entropy_from_counts(tuple(event_counts.values()))
    grouped: dict[Hashable, Counter[bool]] = defaultdict(Counter)
    for event, label in zip(events, knowledge):
        grouped[label][event] += 1

    sample_count = len(events)
    conditional_entropy = sum(
        (sum(counts.values()) / sample_count)
        * entropy_from_counts(tuple(counts.values()))
        for counts in grouped.values()
    )
    mutual_information = event_entropy - conditional_entropy
    if abs(mutual_information) <= ENTROPY_TOLERANCE:
        mutual_information = 0.0
    if mutual_information < 0:
        raise ValueError("conditional entropy exceeded event entropy")

    trivial_event = event_entropy <= ENTROPY_TOLERANCE
    coefficient = 1.0 if trivial_event else mutual_information / event_entropy
    return LaplaceMetrics(
        event_entropy=event_entropy,
        conditional_entropy=conditional_entropy,
        mutual_information=mutual_information,
        coefficient=coefficient,
        samples=sample_count,
        knowledge_states=len(grouped),
        trivial_event=trivial_event,
    )


@dataclass(frozen=True)
class IrreducibleLevel:
    """Best achievable H(E|K) among all knowledge sets of a given size."""

    cells: int
    entropy: float
    best_cells: tuple[int, ...]


def enumerate_event_outcomes(
    width: int, rule: int, steps: int, event: str
) -> list[bool]:
    """Event outcome for every equally likely initial state, indexed by state."""
    if not 1 <= width <= MAX_ENUMERATION_WIDTH:
        raise ValueError(f"width must be between 1 and {MAX_ENUMERATION_WIDTH}")
    validate_rule(rule)
    if steps < 0:
        raise ValueError("steps must not be negative")
    if (1 << width) * max(steps, 1) > MAX_ENUMERATION_WORK:
        raise ValueError("width and steps exceed the local enumeration limit")
    return [
        classical_event_occurs(predict(f"{value:0{width}b}", rule, steps), event)
        for value in range(1 << width)
    ]


def conditional_entropy_for_mask(outcomes: Sequence[bool], mask: int) -> float:
    """H(E|K) when the observer knows exactly the cells in the bit mask."""
    if not outcomes:
        raise ValueError("outcomes must not be empty")
    if mask < 0:
        raise ValueError("knowledge mask must be non-negative")
    groups: dict[int, list[int]] = {}
    for value, outcome in enumerate(outcomes):
        hits_total = groups.setdefault(value & mask, [0, 0])
        hits_total[0] += outcome
        hits_total[1] += 1
    total = len(outcomes)
    return sum(
        (group_total / total)
        * entropy_from_counts((hits, group_total - hits))
        for hits, group_total in groups.values()
    )


def irreducible_profile(
    width: int, rule: int, steps: int, event: str
) -> list[IrreducibleLevel]:
    """H_irr(m) = min H(E|K) over every knowledge set K of m cells (audit formula)."""
    if not 1 <= width <= MAX_IRREDUCIBLE_WIDTH:
        raise ValueError(f"width must be between 1 and {MAX_IRREDUCIBLE_WIDTH}")
    outcomes = enumerate_event_outcomes(width, rule, steps, event)

    best: list[tuple[float, int] | None] = [None] * (width + 1)
    for mask in range(1 << width):
        size = bin(mask).count("1")
        entropy = conditional_entropy_for_mask(outcomes, mask)
        if best[size] is None or entropy < best[size][0] - ENTROPY_TOLERANCE:
            best[size] = (entropy, mask)

    levels: list[IrreducibleLevel] = []
    for size, (entropy, mask) in enumerate(best):
        cells = tuple(
            sorted(width - 1 - bit for bit in range(width) if (mask >> bit) & 1)
        )
        levels.append(IrreducibleLevel(size, entropy, cells))
    return levels


def irreducible_report(width: int, rule: int, steps: int, event: str) -> str:
    """Format the H_irr profile: the Bekenstein-style knowledge-capacity wall."""
    levels = irreducible_profile(width, rule, steps, event)
    lines = ["H_irr(m) = min H(E|K) over every knowledge set K of m cells:"]
    for level in levels:
        cells = ",".join(map(str, level.best_cells)) if level.best_cells else "-"
        lines.append(
            f"m={level.cells}: H_irr={level.entropy:.6f} bits; best K: {cells}"
        )

    if levels[0].entropy <= ENTROPY_TOLERANCE:
        lines.append("H(E)=0: the event is trivial, no knowledge is needed.")
        return "\n".join(lines)

    minimal = next(
        level for level in levels if level.entropy <= ENTROPY_TOLERANCE
    )
    lines.append(
        f"Minimal selected-cell observation: {minimal.cells} cell(s) of {width}."
        " This is not a universal lower bound on memory: a derived feature can"
        " encode an event with fewer bits."
    )
    lines.append(
        "H_irr over all selected cells = 0: this event is fixed in the finite"
        " classical model under the chosen observation scheme."
    )
    return "\n".join(lines)


def parse_known_cells(value: str, width: int) -> tuple[int, ...]:
    """Parse comma-separated observed cell indexes."""
    normalized = value.strip().lower()
    if normalized in {"", "none"}:
        return ()
    if normalized == "all":
        return tuple(range(width))
    try:
        cells = tuple(sorted({int(part.strip()) for part in value.split(",")}))
    except ValueError as error:
        raise ValueError("known cells must be comma-separated indexes") from error
    if any(cell < 0 or cell >= width for cell in cells):
        raise ValueError(f"known cells must be between 0 and {width - 1}")
    return cells


def enumerate_laplace_formula(
    width: int,
    known_cells: Sequence[int],
    rule: int,
    steps: int,
    event: str,
) -> LaplaceMetrics:
    """Evaluate the formula over every equally likely initial state."""
    if len(set(known_cells)) != len(known_cells):
        raise ValueError("known cells must not repeat")
    if any(cell < 0 or cell >= width for cell in known_cells):
        raise ValueError(f"known cells must be between 0 and {width - 1}")

    events = enumerate_event_outcomes(width, rule, steps, event)
    knowledge = [
        "".join(f"{value:0{width}b}"[cell] for cell in known_cells)
        for value in range(1 << width)
    ]
    return laplace_metrics(events, knowledge)


def metrics_report(metrics: LaplaceMetrics) -> str:
    """Format every term and the zero-entropy convention."""
    lines = [
        f"H(E)       = {metrics.event_entropy:.6f} bits",
        f"R = H(E|K) = {metrics.conditional_entropy:.6f} bits",
        f"I(E;K)     = {metrics.mutual_information:.6f} bits",
        f"L           = {metrics.coefficient:.6f}",
        f"Worlds: {metrics.samples}; knowledge states K: {metrics.knowledge_states}",
    ]
    if metrics.trivial_event:
        lines.append(
            "H(E)=0: by convention L=1 for a trivially fixed event."
        )
    elif math.isclose(metrics.coefficient, 1.0, abs_tol=ENTROPY_TOLERANCE):
        lines.append("The observer is a local demon for this class of events.")
    elif math.isclose(metrics.coefficient, 0.0, abs_tol=ENTROPY_TOLERANCE):
        lines.append("Knowledge K removes none of the event's uncertainty.")
    else:
        lines.append("Knowledge K removes only part of the event's uncertainty.")
    return "\n".join(lines)


def calculate_report(
    width: int,
    known_cells_text: str,
    rule: int,
    steps: int,
    event: str,
) -> str:
    """Parse observer knowledge and return a complete report."""
    known_cells = parse_known_cells(known_cells_text, width)
    metrics = enumerate_laplace_formula(width, known_cells, rule, steps, event)
    return metrics_report(metrics)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Calculate the local Laplace formula.")
    parser.add_argument("--width", type=int, default=7)
    parser.add_argument("--known", default="2,3,4")
    parser.add_argument("--rule", type=int, default=30)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--event", default="cell3=1")
    parser.add_argument(
        "--min-knowledge",
        action="store_true",
        help="Find H_irr over every knowledge set K.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the formula from the command line."""
    args = parse_args()
    try:
        if args.min_knowledge:
            report = irreducible_report(args.width, args.rule, args.steps, args.event)
        else:
            report = calculate_report(
                args.width,
                args.known,
                args.rule,
                args.steps,
                args.event,
            )
        print(report)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
