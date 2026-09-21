"""Small dependency-free state-vector simulator for local quantum experiments."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

MAX_QUBITS = 20
PROBABILITY_TOLERANCE = 1e-12
HADAMARD_FACTOR = 1.0 / math.sqrt(2.0)
HADAMARD = (
    (complex(HADAMARD_FACTOR), complex(HADAMARD_FACTOR)),
    (complex(HADAMARD_FACTOR), complex(-HADAMARD_FACTOR)),
)
PAULI_X = ((0j, 1 + 0j), (1 + 0j, 0j))
SINGLE_QUBIT_EVENT = re.compile(r"q(\d+)\s*=\s*([01])", re.IGNORECASE)
EQUAL_QUBITS_EVENT = re.compile(r"q(\d+)\s*=\s*q(\d+)", re.IGNORECASE)
BASIS_EVENT = re.compile(r"state\s*=\s*([01]+)", re.IGNORECASE)
CLASSICAL_STYLE_EVENT = re.compile(r"cell(\d+)\s*=\s*(\S+)", re.IGNORECASE)


def explain_bad_quantum_event(event: str, qubits: int) -> str:
    """Say exactly what is wrong with a quantum event and how to fix it."""
    text = event.strip()
    if not text:
        return (
            "the event field is empty — enter q0=1 (qubit value), q0=q1"
            f" (equality) or state={'0' * qubits}"
        )
    if any(ord(char) > 127 for char in text):
        return (
            f"'{text}' contains non-Latin characters — delete the event and"
            " retype it in the English keyboard layout"
        )
    classical = CLASSICAL_STYLE_EVENT.fullmatch(text)
    if classical:
        return (
            f"'{text}' is classical syntax — qubits are written"
            f" q{classical.group(1)}={classical.group(2)}"
        )
    return (
        f"'{text}' is not a valid event — write q0=1 (qubit value), q0=q1"
        f" (equality) or state=bits (exactly {qubits} characters of 0/1)"
    )


def validate_qubit_count(qubits: int) -> None:
    """Keep exact state-vector memory bounded on a local machine."""
    if not 1 <= qubits <= MAX_QUBITS:
        raise ValueError(f"qubits must be between 1 and {MAX_QUBITS}")


def validate_qubit(qubit: int, qubits: int) -> None:
    """Reject a qubit index outside the register."""
    if not 0 <= qubit < qubits:
        raise ValueError(f"qubit must be between 0 and {qubits - 1}")


def basis_state(bits: str) -> list[complex]:
    """Create |bits> using q0 as the leftmost qubit."""
    if not bits or set(bits) - {"0", "1"}:
        raise ValueError("basis state must contain only 0 and 1")
    validate_qubit_count(len(bits))
    state = [0j] * (1 << len(bits))
    state[int(bits, 2)] = 1 + 0j
    return state


def apply_single_qubit(
    state: Sequence[complex],
    qubits: int,
    qubit: int,
    gate: tuple[tuple[complex, complex], tuple[complex, complex]],
) -> list[complex]:
    """Apply a 2x2 unitary to one qubit."""
    validate_qubit_count(qubits)
    validate_qubit(qubit, qubits)
    if len(state) != 1 << qubits:
        raise ValueError("state size does not match qubit count")

    result = list(state)
    mask = 1 << (qubits - qubit - 1)
    for zero_index in range(len(state)):
        if zero_index & mask:
            continue
        one_index = zero_index | mask
        zero_amplitude = state[zero_index]
        one_amplitude = state[one_index]
        result[zero_index] = gate[0][0] * zero_amplitude + gate[0][1] * one_amplitude
        result[one_index] = gate[1][0] * zero_amplitude + gate[1][1] * one_amplitude
    return result


def apply_cnot(
    state: Sequence[complex], qubits: int, control: int, target: int
) -> list[complex]:
    """Apply a controlled-NOT gate."""
    validate_qubit_count(qubits)
    validate_qubit(control, qubits)
    validate_qubit(target, qubits)
    if control == target:
        raise ValueError("control and target must differ")
    if len(state) != 1 << qubits:
        raise ValueError("state size does not match qubit count")

    control_mask = 1 << (qubits - control - 1)
    target_mask = 1 << (qubits - target - 1)
    result = [0j] * len(state)
    for index, amplitude in enumerate(state):
        destination = index ^ target_mask if index & control_mask else index
        result[destination] = amplitude
    return result


def apply_gates(bits: str, commands: str) -> list[complex]:
    """Apply semicolon-separated H, X and CNOT commands to |bits>."""
    return apply_commands(basis_state(bits), len(bits), commands)


def apply_commands(
    state: list[complex], qubits: int, commands: str
) -> list[complex]:
    """Apply semicolon-separated H, X and CNOT commands to an existing state."""
    for raw_command in commands.split(";"):
        parts = raw_command.strip().upper().split()
        if not parts:
            continue
        try:
            if len(parts) == 2 and parts[0] in {"H", "X"}:
                gate = HADAMARD if parts[0] == "H" else PAULI_X
                state = apply_single_qubit(state, qubits, int(parts[1]), gate)
                continue
            if len(parts) == 3 and parts[0] == "CNOT":
                state = apply_cnot(state, qubits, int(parts[1]), int(parts[2]))
                continue
        except ValueError as error:
            raise ValueError(f"in gate '{raw_command.strip()}': {error}") from error
        raise ValueError(
            f"unsupported gate command '{raw_command.strip()}' — supported:"
            " H n, X n, CNOT control target (e.g. H 0; CNOT 0 1)"
        )
    return state


def reversed_program(commands: str) -> str:
    """The inverse circuit: H, X and CNOT are self-inverse, so reverse the list."""
    steps = [step.strip() for step in commands.split(";") if step.strip()]
    return "; ".join(reversed(steps))


def rewind_probabilities(bits: str, gates: str, qubit: int) -> tuple[float, float]:
    """P(return to |bits>) after forward+reverse: untouched vs read mid-way.

    Reading with its outcome ignored = full dephasing between forward and reverse
    run, computed exactly by splitting the state into its two projected
    branches and rewinding each.
    """
    qubits = len(bits)
    validate_qubit(qubit, qubits)
    forward = apply_gates(bits, gates)
    backward = reversed_program(gates)
    start = int(bits, 2)

    restored = apply_commands(list(forward), qubits, backward)
    pure_return = abs(restored[start]) ** 2

    mask = 1 << (qubits - qubit - 1)
    read_return = 0.0
    for value in (False, True):
        branch = [
            amplitude if bool(index & mask) == value else 0j
            for index, amplitude in enumerate(forward)
        ]
        rewound = apply_commands(branch, qubits, backward)
        read_return += abs(rewound[start]) ** 2
    return pure_return, read_return


def rewind_report(bits: str, gates: str, qubit: int) -> str:
    """Compare inverse-circuit recovery with and without unrecorded measurement."""
    pure_return, read_return = rewind_probabilities(bits, gates, qubit)
    lines = [
        "Rewind: run the program forward, then reversed (H, X, CNOT are"
        " self-inverse, so the reversed list IS the inverse circuit).",
        f"P(return to |{bits}>) with nothing watching:   {pure_return:.6f}",
        f"P(return) after READING qubit {qubit} mid-way:    {read_return:.6f}",
        "The measurement outcome is ignored; no outcome-conditioned recovery is modeled.",
    ]
    if read_return < pure_return - PROBABILITY_TOLERANCE:
        lines.append(
            "THE UNITARY WORLD REMEMBERS: undisturbed evolution rewinds to the"
            " initial state within floating-point precision. The unrecorded"
            " measurement reduces recovery by this inverse circuit. This model"
            " does not establish a universal origin of the arrow of time."
        )
    else:
        lines.append(
            "Reading left no fingerprint here: the qubit carried no coherence,"
            " so there was no superposed past to lose."
        )
    return "\n".join(lines)


def quantum_event_probability(
    state: Sequence[complex], qubits: int, event: str
) -> float:
    """Calculate P(A) for qN=0/1, qN=qM or state=bits."""
    validate_qubit_count(qubits)
    if len(state) != 1 << qubits:
        raise ValueError("state size does not match qubit count")

    single = SINGLE_QUBIT_EVENT.fullmatch(event.strip())
    if single:
        qubit, value = int(single.group(1)), int(single.group(2))
        validate_qubit(qubit, qubits)
        mask = 1 << (qubits - qubit - 1)
        return sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(state)
            if bool(index & mask) == bool(value)
        )

    equal = EQUAL_QUBITS_EVENT.fullmatch(event.strip())
    if equal:
        first, second = int(equal.group(1)), int(equal.group(2))
        validate_qubit(first, qubits)
        validate_qubit(second, qubits)
        first_mask = 1 << (qubits - first - 1)
        second_mask = 1 << (qubits - second - 1)
        return sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(state)
            if bool(index & first_mask) == bool(index & second_mask)
        )

    basis = BASIS_EVENT.fullmatch(event.strip())
    if basis:
        bits = basis.group(1)
        if len(bits) != qubits:
            raise ValueError(
                f"the event state has {len(bits)} digit(s) but the register"
                f" has {qubits} qubit(s) — use exactly {qubits} digits of 0/1"
            )
        return abs(state[int(bits, 2)]) ** 2

    raise ValueError(explain_bad_quantum_event(event, qubits))


def classify_probability(probability: float) -> str:
    """Explain whether an event is determined by the supplied model."""
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be finite and between 0 and 1")
    if math.isclose(probability, 1.0, abs_tol=PROBABILITY_TOLERANCE):
        return "DETERMINED: event A will occur, P(A)=100%"
    if math.isclose(probability, 0.0, abs_tol=PROBABILITY_TOLERANCE):
        return "DETERMINED: event A is impossible, P(A)=0%"
    return f"UNDETERMINED: the model gives P(A)={probability:.2%}"


def format_state(state: Sequence[complex], qubits: int) -> str:
    """Show nonzero basis amplitudes."""
    terms = []
    for index, amplitude in enumerate(state):
        if abs(amplitude) > PROBABILITY_TOLERANCE:
            terms.append(
                f"({amplitude.real:+.3f}{amplitude.imag:+.3f}i)"
                f"|{index:0{qubits}b}>"
            )
    return " + ".join(terms)
