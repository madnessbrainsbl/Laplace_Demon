"""The second law as designed ignorance: deterministic micro, growing macro doubt.

The observer sees only block sums (a coarse-grained macrostate); the micro
dynamics underneath is exactly deterministic. Start with the macrostate known
perfectly, evolve every compatible micro-world, and watch the observer's
uncertainty about the NEXT macrostates grow — thermodynamic randomness without
a single random event underneath (Israeli & Goldenfeld's coarse-graining line).
"""

from __future__ import annotations

import argparse
from collections import Counter
from itertools import product

from demon import next_state, validate_rule
from information import ENTROPY_TOLERANCE, entropy_from_counts

BLOCK = 3
MAX_ENSEMBLE = 4096
# ponytail: one particle per block — a dilute-gas macrostate with 3^(w/3) micros.
BLOCK_MICROS = ("100", "010", "001")


def macro_state(state: str) -> tuple[int, ...]:
    """Block sums: all the coarse observer ever sees."""
    if len(state) % BLOCK:
        raise ValueError(f"width must be divisible by {BLOCK}")
    return tuple(
        sum(int(bit) for bit in state[i : i + BLOCK])
        for i in range(0, len(state), BLOCK)
    )


def dilute_ensemble(width: int) -> list[str]:
    """Every micro-world compatible with 'one particle in each block'."""
    if width % BLOCK or width <= 0:
        raise ValueError(f"width must be a positive multiple of {BLOCK}")
    blocks = width // BLOCK
    if len(BLOCK_MICROS) ** blocks > MAX_ENSEMBLE:
        raise ValueError("width exceeds the macro-ensemble limit")
    return ["".join(parts) for parts in product(BLOCK_MICROS, repeat=blocks)]


def macro_entropy_series(width: int, rule: int, steps: int) -> list[float]:
    """H(macro_t | macro_0) in bits for t = 0..steps."""
    validate_rule(rule)
    if steps < 0:
        raise ValueError("steps must not be negative")
    worlds = dilute_ensemble(width)
    series = []
    for _ in range(steps + 1):
        counts = Counter(macro_state(world) for world in worlds)
        series.append(entropy_from_counts(tuple(counts.values())))
        worlds = [next_state(world, rule) for world in worlds]
    return series


def macro_report(width: int, rule: int, steps: int) -> str:
    """Show the coarse observer's uncertainty over time, with an honest verdict."""
    series = macro_entropy_series(width, rule, steps)
    ensemble = len(dilute_ensemble(width))
    lines = [
        f"Coarse world: {width} cells in blocks of {BLOCK}; the observer sees"
        " only block sums.",
        f"Macrostate at t=0 is known exactly ({ensemble} compatible"
        " micro-worlds, all equally likely).",
        "H(macro_t) in bits:",
        "  " + "  ".join(f"t={t}: {h + 0.0:.3f}" for t, h in enumerate(series)),
    ]
    start, end = series[0], series[-1]
    peak = max(series)
    if peak <= ENTROPY_TOLERANCE:
        lines.append(
            "This law preserves the macrostate exactly: coarse ignorance never"
            " appears. Not every rule makes a thermodynamic world."
        )
    elif end > start + ENTROPY_TOLERANCE:
        lines.append(
            "SECOND LAW FOR THE COARSE OBSERVER: not one random event happened"
            " below — every micro-world moved deterministically — yet the"
            " observer's uncertainty grew. Thermodynamic randomness is"
            " ignorance built into the level of description."
        )
    else:
        lines.append(
            "Macro uncertainty rose and then collapsed: a dissipative law"
            " contracts many micro-pasts into few futures — the same"
            " irreversibility the Retrodict button shows one state at a time."
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Macro entropy of a coarse observer over a deterministic CA."
    )
    parser.add_argument("--width", type=int, default=12)
    parser.add_argument("--rule", type=int, default=30)
    parser.add_argument("--steps", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    """Run the coarse observer from the command line."""
    args = parse_args()
    try:
        print(macro_report(args.width, args.rule, args.steps))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
