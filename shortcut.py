"""Fast-forward finite cellular automata where a verified shortcut is available.

Eight of the 256 elementary rules are additive over GF(2) (the new cell is an
XOR of neighbours). For them t steps equal multiplying by the t-th power of the
step polynomial in GF(2)[x]/(x^w + 1), computed in O(log t) squarings. Other
rules may still have shortcuts; this module simply does not implement one.
"""

from __future__ import annotations

import argparse
import time

from demon import predict, validate_rule, validate_state


def linear_coefficients(rule: int) -> tuple[int, int, int] | None:
    """(left, center, right) XOR coefficients, or None if the rule is not linear."""
    validate_rule(rule)
    table = [(rule >> neighborhood) & 1 for neighborhood in range(8)]
    if table[0]:
        return None
    for x in range(8):
        for y in range(8):
            if table[x ^ y] != table[x] ^ table[y]:
                return None
    return table[4], table[2], table[1]


def _rotate(mask: int, shift: int, width: int) -> int:
    shift %= width
    if not shift:
        return mask
    full = (1 << width) - 1
    return ((mask << shift) | (mask >> (width - shift))) & full


def _multiply(p: int, q: int, width: int) -> int:
    """Carry-less product in GF(2)[x]/(x^width + 1): XOR of rotations."""
    result = 0
    for bit in range(width):
        if (q >> bit) & 1:
            result ^= _rotate(p, bit, width)
    return result


def fast_forward(state: str, rule: int, steps: int) -> str:
    """Jump the linear universe t steps ahead in O(width^2 * log t)."""
    validate_state(state)
    if steps < 0:
        raise ValueError("steps must not be negative")
    coefficients = linear_coefficients(rule)
    if coefficients is None:
        raise ValueError(
            f"rule {rule} is not linear over GF(2) — this algebraic shortcut"
            " does not apply"
        )
    width = len(state)
    left, center, right = coefficients

    step_poly = 0
    if left:
        step_poly ^= 1 << (1 % width)
    if center:
        step_poly ^= 1
    if right:
        step_poly ^= 1 << ((width - 1) % width)

    operator, base, remaining = 1, step_poly, steps
    while remaining:
        if remaining & 1:
            operator = _multiply(operator, base, width)
        base = _multiply(base, base, width)
        remaining >>= 1

    mask = sum(int(bit) << index for index, bit in enumerate(state))
    result = _multiply(operator, mask, width)
    return "".join("1" if (result >> index) & 1 else "0" for index in range(width))


def shortcut_report(state: str, rule: int, steps: int) -> str:
    """Show the shortcut working — or honestly refuse where none is known."""
    coefficients = linear_coefficients(rule)
    if coefficients is None:
        start = time.perf_counter()
        final_state = predict(state, rule, steps)
        elapsed = time.perf_counter() - start
        return "\n".join(
            [
                f"Rule {rule} is NOT linear over GF(2): this shortcut does not apply.",
                f"Finite simulation result: {final_state}",
                f"Computed in {elapsed * 1000:.2f} ms; the simulator may skip a"
                " repeated state, but this does not establish a general shortcut.",
                "Try a linear rule (60, 90, 102, 150, 170, 204, 240) for the"
                " verified O(log t) algebraic method.",
            ]
        )
    start = time.perf_counter()
    final_state = fast_forward(state, rule, steps)
    elapsed = time.perf_counter() - start
    doublings = max(steps.bit_length() - 1, 0)
    active_parts = (
        part
        for part, on in zip(("left", "center", "right"), coefficients)
        if on
    )
    formula = " XOR ".join(active_parts) or "0"
    return "\n".join(
        [
            f"Rule {rule} is linear over GF(2): new cell ="
            f" {formula}.",
            f"Fast-forward over {steps} step(s): {final_state}",
            f"Computed in {elapsed * 1000:.2f} ms with ~{doublings} squarings"
            f" instead of {steps} lived steps.",
            "REDUCIBLE: this universe has a shortcut — the demon outruns its"
            " world. Rule 30 has no known shortcut; that contrast is the wall.",
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fast-forward linear rules; refuse honestly elsewhere."
    )
    parser.add_argument("--state", default="0" * 30 + "1" + "0" * 30)
    parser.add_argument("--rule", type=int, default=90)
    parser.add_argument("--steps", type=int, default=10**18)
    return parser.parse_args()


def main() -> int:
    """Run the shortcut from the command line."""
    args = parse_args()
    try:
        print(shortcut_report(args.state, args.rule, args.steps))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
