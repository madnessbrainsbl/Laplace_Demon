"""No global 'now': a demon embedded in the world only ever knows a light cone.

Information in the cellular universe travels at most one cell per step. A demon
sitting at cell p that must predict an event T steps ahead has had time to hear
from cells within ring-distance T — nothing farther. The event, in turn, depends
on the initial cells within distance T of ITS location. Where those cones fail
to overlap, no amount of intelligence closes the gap: the demon's seat in the
world decides what it can be a demon for.
"""

from __future__ import annotations

import argparse

from information import (
    ENTROPY_TOLERANCE,
    MAX_ENUMERATION_WIDTH,
    enumerate_laplace_formula,
)

MAX_CONE_WORK = 2_000_000


def light_cone_cells(width: int, center: int, radius: int) -> tuple[int, ...]:
    """Cells within ring-distance radius of center."""
    if not 0 <= center < width:
        raise ValueError(f"position must be between 0 and {width - 1}")
    if radius < 0:
        raise ValueError("radius must not be negative")
    reach = min(radius, width)
    return tuple(sorted({(center + o) % width for o in range(-reach, reach + 1)}))


def embedded_demon_profile(
    width: int, rule: int, horizon: int, event: str
) -> list[float]:
    """L_O for a demon seated at every cell, knowing only its light cone."""
    if not 1 <= width <= MAX_ENUMERATION_WIDTH:
        raise ValueError(f"width must be between 1 and {MAX_ENUMERATION_WIDTH}")
    if (1 << width) * max(horizon, 1) * width > MAX_CONE_WORK:
        raise ValueError("width and horizon exceed the light-cone sweep limit")
    profile = []
    for position in range(width):
        cone = light_cone_cells(width, position, horizon)
        metrics = enumerate_laplace_formula(width, cone, rule, horizon, event)
        profile.append(metrics.coefficient)
    return profile


def light_cone_report(width: int, rule: int, horizon: int, event: str) -> str:
    """Show that no seat inside the world sees the whole present."""
    profile = embedded_demon_profile(width, rule, horizon, event)
    cone_size = len(light_cone_cells(width, 0, horizon))
    lines = [
        f"Embedded demon: signals travel 1 cell/step, so a demon predicting"
        f" {horizon} step(s) ahead knows only {cone_size} of {width} cells.",
        "L_O by the demon's seat in the world:",
    ]
    for position, coefficient in enumerate(profile):
        mark = "  <- full demon here" if coefficient >= 1 - ENTROPY_TOLERANCE else ""
        lines.append(f"  cell {position}: L_O = {coefficient:.6f}{mark}")

    full_seats = sum(1 for c in profile if c >= 1 - ENTROPY_TOLERANCE)
    if cone_size >= width:
        lines.append(
            "The horizon is long enough for light to cross the whole ring:"
            " every seat sees everything — the external demon's privilege,"
            " earned by waiting."
        )
    elif full_seats == 0:
        lines.append(
            "NO GLOBAL NOW: no seat inside the world can predict this event —"
            " the knowledge it needs lies outside every light cone."
        )
    else:
        lines.append(
            f"Only {full_seats} of {width} seats can be a demon for this event:"
            " being all-knowing is a property of WHERE you sit, not how smart"
            " you are. The external demon of the other tabs gets the whole"
            " present as a gift no inhabitant receives."
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="L_O of a light-cone-limited demon at every seat."
    )
    parser.add_argument("--width", type=int, default=7)
    parser.add_argument("--rule", type=int, default=30)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--event", default="cell3=1")
    return parser.parse_args()


def main() -> int:
    """Run the embedded demon from the command line."""
    args = parse_args()
    try:
        print(light_cone_report(args.width, args.rule, args.horizon, args.event))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
