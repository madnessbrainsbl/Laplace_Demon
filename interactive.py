"""Interactive front end for classical and quantum local predictions."""

from __future__ import annotations

import re

from demon import predict
from quantum import (
    apply_gates,
    classify_probability,
    format_state,
    quantum_event_probability,
)

CLASSICAL_CELL_EVENT = re.compile(r"cell(\d+)\s*=\s*([01])", re.IGNORECASE)
CLASSICAL_STATE_EVENT = re.compile(r"state\s*=\s*([01]+)", re.IGNORECASE)
LOOSE_CELL_EVENT = re.compile(r"cell\s*(\d+)\s*=\s*(\S*)", re.IGNORECASE)
LOOSE_STATE_EVENT = re.compile(r"state\s*=\s*(\S*)", re.IGNORECASE)
QUANTUM_STYLE_EVENT = re.compile(r"q(\d+)\s*=\s*(\S+)", re.IGNORECASE)


def explain_bad_event(event: str, width: int) -> str:
    """Say exactly what is wrong with an event string and how to fix it."""
    text = event.strip()
    if not text:
        return (
            "the event field is empty — enter cell3=1 (one cell) or"
            f" state={'0' * width} (the whole final state)"
        )
    if any(ord(char) > 127 for char in text):
        return (
            f"'{text}' contains non-Latin characters; Cyrillic 'с'/'е' look"
            " identical to Latin ones — delete the event and retype it in the"
            " English keyboard layout"
        )
    quantum = QUANTUM_STYLE_EVENT.fullmatch(text)
    if quantum:
        return (
            f"'{text}' is quantum syntax (Quantum tab only) — in a classical"
            f" world write cell{quantum.group(1)}={quantum.group(2)}"
        )
    cell = LOOSE_CELL_EVENT.fullmatch(text)
    if cell:
        index, value = cell.group(1), cell.group(2)
        if value not in {"0", "1"}:
            return (
                f"a cell can only be 0 or 1, got '{value}' — write"
                f" cell{index}=0 or cell{index}=1"
            )
        return f"remove the spaces: write cell{index}={value}"
    bad_state = LOOSE_STATE_EVENT.fullmatch(text)
    if bad_state:
        return (
            f"state may contain only 0 and 1, got '{bad_state.group(1)}' —"
            f" e.g. state={'0' * width}"
        )
    return (
        f"'{text}' is not a valid event — write cell3=1 (cell 3 ends up 1) or"
        f" state=bits (exactly {width} characters of 0/1)"
    )


def classical_event_occurs(state: str, event: str) -> bool:
    """Evaluate cellN=0/1 or state=bits against a predicted state."""
    text = event.strip()
    cell = CLASSICAL_CELL_EVENT.fullmatch(text)
    if cell:
        index, value = int(cell.group(1)), cell.group(2)
        if not 0 <= index < len(state):
            raise ValueError(
                f"the event asks about cell {index}, but this world only has"
                f" cells 0..{len(state) - 1} — lower the cell index or widen"
                " the world"
            )
        return state[index] == value

    expected_state = CLASSICAL_STATE_EVENT.fullmatch(text)
    if expected_state:
        if len(expected_state.group(1)) != len(state):
            raise ValueError(
                f"the event state has {len(expected_state.group(1))} cells but"
                f" the world has {len(state)} — make both the same length"
            )
        return state == expected_state.group(1)

    raise ValueError(explain_bad_event(event, len(state)))


def prompt(label: str, default: str) -> str:
    """Read one value while exposing a useful default.

    End of input (pipe ran dry, Ctrl+Z) falls back to the default — the same
    behavior as the Go kernel's prompt, instead of an EOFError traceback.
    """
    try:
        value = input(f"{label} [{default}]: ").strip()
    except EOFError:
        print()
        return default
    return value or default


def run_classical() -> None:
    """Interactively predict a classical event with certainty."""
    state = prompt("Initial state", "0001000")
    rule = int(prompt("Rule 0..255", "30"))
    steps = int(prompt("Steps", "1"))
    event = prompt("Event A: cellN=0/1 or state=bits", "cell3=1")
    final_state = predict(state, rule, steps)
    occurs = classical_event_occurs(final_state, event)
    probability = 1.0 if occurs else 0.0
    print(f"\nPredicted state: {final_state}")
    print(classify_probability(probability))


def run_quantum() -> None:
    """Interactively evolve a small quantum register and evaluate an event."""
    bits = prompt("Initial basis state", "00")
    gates = prompt("Gates separated by ';' (H, X, CNOT)", "H 0; CNOT 0 1")
    event = prompt("Event A: qN=0/1, qN=qM or state=bits", "q0=q1")
    state = apply_gates(bits, gates)
    probability = quantum_event_probability(state, len(bits), event)
    print(f"\nQuantum state: {format_state(state, len(bits))}")
    print(classify_probability(probability))


def main() -> int:
    """Select a local universe and run one prediction."""
    print("Local Laplace demon")
    mode = prompt("Mode: classical / quantum", "classical").lower()
    try:
        if mode == "classical":
            run_classical()
        elif mode == "quantum":
            run_quantum()
        else:
            raise ValueError("mode must be classical or quantum")
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
