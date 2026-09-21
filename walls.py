"""Physical walls on any demon: Bekenstein capacity and the quantum floor."""

from __future__ import annotations

import argparse
import math

from quantum import (
    HADAMARD,
    PROBABILITY_TOLERANCE,
    apply_gates,
    apply_single_qubit,
    quantum_event_probability,
    validate_qubit,
)

HBAR = 1.054571817e-34
LIGHT_SPEED = 299792458.0
BOLTZMANN = 1.380649e-23
# Maassen-Uffink for two mutually unbiased bases of one qubit: H(Z)+H(X) >= 1 bit.
COMPLEMENTARITY_BOUND_BITS = 1.0
LOCAL_DETERMINISM_BOUND = 2.0
TSIRELSON_BOUND = 2.0 * math.sqrt(2.0)
Operator = tuple[tuple[complex, complex], tuple[complex, complex]]
PAULI_OPERATORS = (
    ((0j, 1 + 0j), (1 + 0j, 0j)),
    ((0j, -1j), (1j, 0j)),
    ((1 + 0j, 0j), (0j, -1 + 0j)),
)


def binary_entropy(probability: float) -> float:
    """Shannon entropy of one binary outcome, in bits."""
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    if probability <= PROBABILITY_TOLERANCE or probability >= 1 - PROBABILITY_TOLERANCE:
        return 0.0
    return -(
        probability * math.log2(probability)
        + (1 - probability) * math.log2(1 - probability)
    )


def bekenstein_bits(radius: float, energy: float) -> float:
    """Max information in a region: I <= 2*pi*R*E / (hbar*c*ln2), in bits."""
    if not math.isfinite(radius) or not math.isfinite(energy):
        raise ValueError("radius and energy must be finite")
    if radius <= 0 or energy <= 0:
        raise ValueError("radius and energy must be positive")
    return 2 * math.pi * radius * energy / (HBAR * LIGHT_SPEED * math.log(2))


def minimal_radius(bits: float, energy: float) -> float:
    """Smallest region that can hold the given bits at the given energy."""
    if not math.isfinite(bits) or not math.isfinite(energy):
        raise ValueError("bits and energy must be finite")
    if bits < 0 or energy <= 0:
        raise ValueError("bits must be non-negative and energy positive")
    return bits * HBAR * LIGHT_SPEED * math.log(2) / (2 * math.pi * energy)


def bekenstein_report(radius: float, energy: float, required_bits: int) -> str:
    """Compare a demon's required knowledge with what physics lets it carry."""
    if required_bits < 0:
        raise ValueError("required bits must be non-negative")
    capacity = bekenstein_bits(radius, energy)
    needed_radius = minimal_radius(required_bits, energy)
    lines = [
        "Bekenstein bound: I <= 2*pi*R*E / (hbar*c*ln2)",
        f"Carrier: R={radius:g} m, E={energy:g} J",
        f"Capacity:      {capacity:.3e} bits",
        f"Demon needs:   {required_bits} bits of knowledge K",
        f"Minimal radius for those bits at this energy: {needed_radius:.3e} m",
    ]
    if capacity >= required_bits:
        lines.append(
            "The wall does NOT bite here: the carrier holds the knowledge with"
            " room to spare."
        )
    else:
        lines.append(
            "The wall BITES: this carrier physically cannot hold the knowledge"
            " the event requires."
        )
    lines.append(
        "Honest note: for finite toy worlds the bound is astronomically loose."
        " It constrains a demon only when the system approaches cosmic scale —"
        " it does not by itself prove a predictor must exceed its world."
    )
    return "\n".join(lines)


def landauer_cost_joules(bits: float, temperature: float) -> float:
    """Minimum heat to erase the demon's memory: bits * kT * ln2 (Landauer)."""
    if not math.isfinite(bits) or not math.isfinite(temperature):
        raise ValueError("bits and temperature must be finite")
    if bits < 0:
        raise ValueError("bits must be non-negative")
    if temperature <= 0:
        raise ValueError("temperature must be positive kelvin")
    return bits * BOLTZMANN * temperature * math.log(2)


def landauer_report(required_bits: int, temperature: float) -> str:
    """Price the demon's knowledge in joules — Bennett's answer to Maxwell."""
    cost = landauer_cost_joules(required_bits, temperature)
    per_bit = landauer_cost_joules(1, temperature)
    lines = [
        "Landauer bound: erasing one bit costs at least kT*ln2 of heat.",
        f"Temperature: {temperature:g} K -> {per_bit:.3e} J per bit",
        f"Selected observation record for this event: {required_bits} bit(s)",
        f"Heat to reset that memory for the next observation: {cost:.3e} J",
        "The cost applies when a memory is reset. It is not a charge for merely"
        " knowing a fact, and it does not establish the minimum memory needed"
        " for every possible predictor.",
        "Verified in the lab (Berut et al., Nature 2012).",
    ]
    return "\n".join(lines)


def _symmetric_eigenvalues(matrix: list[list[float]]) -> list[float]:
    """Return the three eigenvalues of a real symmetric 3x3 matrix."""
    off_diagonal = matrix[0][1] ** 2 + matrix[0][2] ** 2 + matrix[1][2] ** 2
    if off_diagonal <= PROBABILITY_TOLERANCE:
        return sorted((matrix[0][0], matrix[1][1], matrix[2][2]), reverse=True)

    mean = sum(matrix[index][index] for index in range(3)) / 3.0
    variance = (
        sum((matrix[index][index] - mean) ** 2 for index in range(3))
        + 2.0 * off_diagonal
    )
    scale = math.sqrt(variance / 6.0)
    normalized = [
        [
            (matrix[row][column] - (mean if row == column else 0.0)) / scale
            for column in range(3)
        ]
        for row in range(3)
    ]
    determinant = (
        normalized[0][0]
        * (
            normalized[1][1] * normalized[2][2]
            - normalized[1][2] * normalized[2][1]
        )
        - normalized[0][1]
        * (
            normalized[1][0] * normalized[2][2]
            - normalized[1][2] * normalized[2][0]
        )
        + normalized[0][2]
        * (
            normalized[1][0] * normalized[2][1]
            - normalized[1][1] * normalized[2][0]
        )
    )
    angle = math.acos(max(-1.0, min(1.0, determinant / 2.0))) / 3.0
    largest = mean + 2.0 * scale * math.cos(angle)
    smallest = mean + 2.0 * scale * math.cos(angle + 2.0 * math.pi / 3.0)
    middle = 3.0 * mean - largest - smallest
    return sorted((largest, middle, smallest), reverse=True)


def chsh_value(bits: str, gates: str, first: int = 0, second: int = 1) -> float:
    """Maximum CHSH value for the selected pair in the resulting pure state."""
    state = apply_gates(bits, gates)
    qubits = len(bits)
    validate_qubit(first, qubits)
    validate_qubit(second, qubits)
    if first == second:
        raise ValueError("CHSH needs two different qubits")

    def correlation(
        first_operator: Operator,
        second_operator: Operator,
    ) -> float:
        acted = apply_single_qubit(state, qubits, first, first_operator)
        acted = apply_single_qubit(acted, qubits, second, second_operator)
        return sum(
            (amplitude.conjugate() * image).real
            for amplitude, image in zip(state, acted)
        )

    tensor = [
        [
            correlation(first_operator, second_operator)
            for second_operator in PAULI_OPERATORS
        ]
        for first_operator in PAULI_OPERATORS
    ]
    gram = [
        [
            sum(tensor[row][left] * tensor[row][right] for row in range(3))
            for right in range(3)
        ]
        for left in range(3)
    ]
    eigenvalues = _symmetric_eigenvalues(gram)
    value = 2.0 * math.sqrt(max(0.0, eigenvalues[0] + eigenvalues[1]))
    return min(value, TSIRELSON_BOUND)


def chsh_report(bits: str, gates: str, first: int = 0, second: int = 1) -> str:
    """Bell test: a number outside the local-hidden-variable bound."""
    value = chsh_value(bits, gates, first, second)
    lines = [
        "Unitary state only: environment channels are not applied in this report.",
        f"Maximum CHSH on qubits {first} and {second}:",
        f"S_max = {value:.6f}",
        f"Local deterministic bound: S <= {LOCAL_DETERMINISM_BOUND:.1f}",
        f"Quantum maximum (Tsirelson): 2*sqrt(2) = {TSIRELSON_BOUND:.6f}",
    ]
    if value > LOCAL_DETERMINISM_BOUND + PROBABILITY_TOLERANCE:
        lines.append(
            "BELL VIOLATION: no local hidden-variable model under the Bell-test"
            " assumptions can produce these correlations. This does not exclude"
            " all deterministic or nonlocal interpretations."
        )
    else:
        lines.append(
            "Within the classical bound: a local hidden-variable demon could"
            " mimic these two-qubit correlations."
        )
    return "\n".join(lines)


def quantum_wall_report(bits: str, gates: str, event: str, qubit: int = 0) -> str:
    """Operational result for one fixed wavefunction and measurement event."""
    state = apply_gates(bits, gates)
    qubits = len(bits)
    validate_qubit(qubit, qubits)
    probability = quantum_event_probability(state, qubits, event)

    event_entropy = binary_entropy(probability)
    # K is the complete wavefunction available to this operational model.
    # Born's rule still returns the same distribution, so K buys nothing.
    conditional_entropy = event_entropy
    mutual_information = event_entropy - conditional_entropy
    trivial = event_entropy <= PROBABILITY_TOLERANCE
    coefficient = 1.0 if trivial else mutual_information / event_entropy

    z_probability = quantum_event_probability(state, qubits, f"q{qubit}=1")
    x_state = apply_single_qubit(state, qubits, qubit, HADAMARD)
    x_probability = quantum_event_probability(x_state, qubits, f"q{qubit}=1")
    z_entropy = binary_entropy(z_probability)
    x_entropy = binary_entropy(x_probability)

    lines = [
        "Unitary state only: dephasing and damping are not applied in this report.",
        f"P(A) = {probability:.6f}",
        f"H(E)              = {event_entropy:.6f} bits",
        f"H(E | full state) = {conditional_entropy:.6f} bits",
        f"I(E;K)            = {mutual_information:.6f} bits",
        f"L_O               = {coefficient:.6f}",
    ]
    if trivial:
        lines.append(
            "The event is already determined by the unitary evolution:"
            " no randomness to remove, L_O=1 by convention."
        )
    else:
        lines.append(
            "FOR THIS FIXED STATE: K is constant across the ensemble, so it"
            " carries no information about this undetermined measurement event"
            " and L_O = 0 in this calculation."
        )
        lines.append(
            "Knowledge of a preparation can still reduce predictive entropy in a"
            " mixed ensemble. This operational result is not a proof against every"
            " interpretation; deterministic interpretations add variables this"
            " model neither stores nor makes accessible."
        )
    lines += [
        "",
        f"Complementarity on qubit {qubit} (Heisenberg, in bits):",
        f"  H(Z) = {z_entropy:.6f}   H(X) = {x_entropy:.6f}",
        f"  H(Z)+H(X) = {z_entropy + x_entropy:.6f} >="
        f" {COMPLEMENTARITY_BOUND_BITS:.1f} (Maassen-Uffink)",
        "Determining one observable costs ignorance of the other: no knowledge"
        " state drives both to zero.",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Bekenstein and quantum walls.")
    parser.add_argument("--radius", type=float, default=0.1)
    parser.add_argument("--energy", type=float, default=1.0)
    parser.add_argument("--required-bits", type=int, default=3)
    parser.add_argument("--bits", default="0")
    parser.add_argument("--gates", default="H 0")
    parser.add_argument("--event", default="q0=1")
    return parser.parse_args()


def main() -> int:
    """Print both walls from the command line."""
    args = parse_args()
    try:
        print(bekenstein_report(args.radius, args.energy, args.required_bits))
        print()
        print(quantum_wall_report(args.bits, args.gates, args.event))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
