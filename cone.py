"""Prediction from a selected spatial mask of the initial cellular state.

For illustration the mask radius equals the prediction horizon. Communication
and collection times are not simulated; this is not a relativistic observer.
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
    """Compare event knowledge under explicitly supplied initial-state masks."""
    profile = embedded_demon_profile(width, rule, horizon, event)
    cone_size = len(light_cone_cells(width, 0, horizon))
    lines = [
        f"Toy spatial mask: assume exact initial data within radius {horizon}"
        f" ({cone_size} of {width} cells). The radius equals the prediction"
        " horizon by convention; signal travel and collection are not simulated.",
        "L_O by the demon's seat in the world:",
    ]
    for position, coefficient in enumerate(profile):
        mark = "  <- full demon here" if coefficient >= 1 - ENTROPY_TOLERANCE else ""
        lines.append(f"  cell {position}: L_O = {coefficient:.6f}{mark}")

    full_seats = sum(1 for c in profile if c >= 1 - ENTROPY_TOLERANCE)
    if cone_size >= width:
        lines.append(
            "The selected mask covers the whole ring: every seat is supplied"
            " the complete initial state. This does not establish how it was collected."
        )
    elif full_seats == 0:
        lines.append(
            "Under this spatial mask, no seat has enough selected-cell"
            " knowledge for this event. Changing the mask can change the result."
        )
    else:
        lines.append(
            f"Only {full_seats} of {width} seats have enough selected-cell"
            " knowledge for this event under the toy spatial mask. The other"
            " tabs assume the complete model state as an input."
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
