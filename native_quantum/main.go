package main

import (
	"bufio"
	"errors"
	"fmt"
	"math"
	"math/cmplx"
	"os"
	"regexp"
	"strconv"
	"strings"
)

const (
	maxQubits = 10
	tolerance = 1e-12
)

type matrix2 [2][2]complex128

var (
	hadamard = matrix2{
		{complex(1/math.Sqrt2, 0), complex(1/math.Sqrt2, 0)},
		{complex(1/math.Sqrt2, 0), complex(-1/math.Sqrt2, 0)},
	}
	pauliX           = matrix2{{0, 1}, {1, 0}}
	singleQubitEvent = regexp.MustCompile(`(?i)^q([0-9]+)\s*=\s*([01])$`)
	equalQubitsEvent = regexp.MustCompile(`(?i)^q([0-9]+)\s*=\s*q([0-9]+)$`)
	basisEvent       = regexp.MustCompile(`(?i)^state\s*=\s*([01]+)$`)
)

func validateQubit(qubit, qubits int) error {
	if qubit < 0 || qubit >= qubits {
		return fmt.Errorf("qubit must be between 0 and %d", qubits-1)
	}
	return nil
}

func basisState(bits string) ([]complex128, error) {
	if len(bits) < 1 || len(bits) > maxQubits {
		return nil, fmt.Errorf("basis width must be between 1 and %d", maxQubits)
	}
	for _, bit := range bits {
		if bit != '0' && bit != '1' {
			return nil, errors.New("basis state must contain only 0 and 1")
		}
	}
	index, err := strconv.ParseInt(bits, 2, 64)
	if err != nil {
		return nil, fmt.Errorf("parse basis state: %w", err)
	}
	state := make([]complex128, 1<<len(bits))
	state[index] = 1
	return state, nil
}

func applySingleQubit(
	state []complex128,
	qubits, qubit int,
	gate matrix2,
) ([]complex128, error) {
	if err := validateQubit(qubit, qubits); err != nil {
		return nil, err
	}
	if len(state) != 1<<qubits {
		return nil, errors.New("state size does not match qubit count")
	}
	result := append([]complex128(nil), state...)
	mask := 1 << (qubits - qubit - 1)
	for zeroIndex := range state {
		if zeroIndex&mask != 0 {
			continue
		}
		oneIndex := zeroIndex | mask
		zeroAmplitude := state[zeroIndex]
		oneAmplitude := state[oneIndex]
		result[zeroIndex] = gate[0][0]*zeroAmplitude + gate[0][1]*oneAmplitude
		result[oneIndex] = gate[1][0]*zeroAmplitude + gate[1][1]*oneAmplitude
	}
	return result, nil
}

func applyCNOT(state []complex128, qubits, control, target int) ([]complex128, error) {
	if err := validateQubit(control, qubits); err != nil {
		return nil, err
	}
	if err := validateQubit(target, qubits); err != nil {
		return nil, err
	}
	if control == target {
		return nil, errors.New("control and target must differ")
	}
	if len(state) != 1<<qubits {
		return nil, errors.New("state size does not match qubit count")
	}
	controlMask := 1 << (qubits - control - 1)
	targetMask := 1 << (qubits - target - 1)
	result := make([]complex128, len(state))
	for index, amplitude := range state {
		destination := index
		if index&controlMask != 0 {
			destination ^= targetMask
		}
		result[destination] = amplitude
	}
	return result, nil
}

func applyGates(bits, commands string) ([]complex128, error) {
	state, err := basisState(bits)
	if err != nil {
		return nil, err
	}
	qubits := len(bits)
	for _, rawCommand := range strings.Split(commands, ";") {
		parts := strings.Fields(strings.ToUpper(rawCommand))
		if len(parts) == 0 {
			continue
		}
		if len(parts) == 2 && (parts[0] == "H" || parts[0] == "X") {
			qubit, parseErr := strconv.Atoi(parts[1])
			if parseErr != nil {
				return nil, fmt.Errorf("parse qubit in %q: %w", rawCommand, parseErr)
			}
			gate := hadamard
			if parts[0] == "X" {
				gate = pauliX
			}
			state, err = applySingleQubit(state, qubits, qubit, gate)
			if err != nil {
				return nil, fmt.Errorf("apply %q: %w", rawCommand, err)
			}
			continue
		}
		if len(parts) == 3 && parts[0] == "CNOT" {
			control, controlErr := strconv.Atoi(parts[1])
			target, targetErr := strconv.Atoi(parts[2])
			if controlErr != nil || targetErr != nil {
				return nil, fmt.Errorf("parse qubits in %q", rawCommand)
			}
			state, err = applyCNOT(state, qubits, control, target)
			if err != nil {
				return nil, fmt.Errorf("apply %q: %w", rawCommand, err)
			}
			continue
		}
		return nil, fmt.Errorf("unsupported gate command: %s", strings.TrimSpace(rawCommand))
	}
	return state, nil
}

func densityFromState(state []complex128) []complex128 {
	dimension := len(state)
	density := make([]complex128, dimension*dimension)
	for row, rowAmplitude := range state {
		for column, columnAmplitude := range state {
			density[row*dimension+column] = rowAmplitude * cmplx.Conj(columnAmplitude)
		}
	}
	return density
}

func withBit(index, mask, bit int) int {
	if bit == 0 {
		return index &^ mask
	}
	return index | mask
}

func applyKraus(
	density []complex128,
	qubits, target int,
	operators []matrix2,
) ([]complex128, error) {
	if err := validateQubit(target, qubits); err != nil {
		return nil, err
	}
	dimension := 1 << qubits
	if len(density) != dimension*dimension {
		return nil, errors.New("density size does not match qubit count")
	}
	mask := 1 << (qubits - target - 1)
	result := make([]complex128, len(density))

	for _, operator := range operators {
		for outRow := 0; outRow < dimension; outRow++ {
			outRowBit := 0
			if outRow&mask != 0 {
				outRowBit = 1
			}
			for outColumn := 0; outColumn < dimension; outColumn++ {
				outColumnBit := 0
				if outColumn&mask != 0 {
					outColumnBit = 1
				}
				for inRowBit := 0; inRowBit < 2; inRowBit++ {
					inRow := withBit(outRow, mask, inRowBit)
					for inColumnBit := 0; inColumnBit < 2; inColumnBit++ {
						inColumn := withBit(outColumn, mask, inColumnBit)
						result[outRow*dimension+outColumn] +=
							operator[outRowBit][inRowBit] *
								density[inRow*dimension+inColumn] *
								cmplx.Conj(operator[outColumnBit][inColumnBit])
					}
				}
			}
		}
	}
	return result, nil
}

func validateProbability(probability float64) error {
	if math.IsNaN(probability) || math.IsInf(probability, 0) || probability < 0 || probability > 1 {
		return errors.New("probability must be finite and between 0 and 1")
	}
	return nil
}

func dephase(
	density []complex128,
	qubits, target int,
	probability float64,
) ([]complex128, error) {
	if err := validateProbability(probability); err != nil {
		return nil, err
	}
	keep := complex(math.Sqrt(1-probability), 0)
	leak := complex(math.Sqrt(probability), 0)
	noPhaseLoss := matrix2{{1, 0}, {0, keep}}
	phaseLoss := matrix2{{0, 0}, {0, leak}}
	return applyKraus(density, qubits, target, []matrix2{noPhaseLoss, phaseLoss})
}

func amplitudeDamp(
	density []complex128,
	qubits, target int,
	probability float64,
) ([]complex128, error) {
	if err := validateProbability(probability); err != nil {
		return nil, err
	}
	stay := complex(math.Sqrt(1-probability), 0)
	decay := complex(math.Sqrt(probability), 0)
	noJump := matrix2{{1, 0}, {0, stay}}
	jump := matrix2{{0, decay}, {0, 0}}
	return applyKraus(density, qubits, target, []matrix2{noJump, jump})
}

func eventProbability(density []complex128, qubits int, event string) (float64, error) {
	dimension := 1 << qubits
	if len(density) != dimension*dimension {
		return 0, errors.New("density size does not match qubit count")
	}
	event = strings.TrimSpace(event)
	if match := singleQubitEvent.FindStringSubmatch(event); match != nil {
		qubit, err := strconv.Atoi(match[1])
		if err != nil {
			return 0, fmt.Errorf("parse event qubit: %w", err)
		}
		value, err := strconv.Atoi(match[2])
		if err != nil {
			return 0, fmt.Errorf("parse event value: %w", err)
		}
		if err := validateQubit(qubit, qubits); err != nil {
			return 0, err
		}
		mask := 1 << (qubits - qubit - 1)
		probability := 0.0
		for index := 0; index < dimension; index++ {
			if (index&mask != 0) == (value == 1) {
				probability += real(density[index*dimension+index])
			}
		}
		return probability, nil
	}
	if match := equalQubitsEvent.FindStringSubmatch(event); match != nil {
		first, err := strconv.Atoi(match[1])
		if err != nil {
			return 0, fmt.Errorf("parse first event qubit: %w", err)
		}
		second, err := strconv.Atoi(match[2])
		if err != nil {
			return 0, fmt.Errorf("parse second event qubit: %w", err)
		}
		if err := validateQubit(first, qubits); err != nil {
			return 0, err
		}
		if err := validateQubit(second, qubits); err != nil {
			return 0, err
		}
		firstMask := 1 << (qubits - first - 1)
		secondMask := 1 << (qubits - second - 1)
		probability := 0.0
		for index := 0; index < dimension; index++ {
			if (index&firstMask != 0) == (index&secondMask != 0) {
				probability += real(density[index*dimension+index])
			}
		}
		return probability, nil
	}
	if match := basisEvent.FindStringSubmatch(event); match != nil {
		bits := match[1]
		if len(bits) != qubits {
			return 0, fmt.Errorf(
				"the event state has %d digit(s) but the register has %d"+
					" qubit(s) — use exactly %d digits of 0/1",
				len(bits), qubits, qubits,
			)
		}
		index, _ := strconv.ParseInt(bits, 2, 64)
		return real(density[int(index)*dimension+int(index)]), nil
	}
	return 0, errors.New("event must be qN=0, qN=qM or state=bits")
}

func purity(density []complex128) float64 {
	total := 0.0
	for _, value := range density {
		magnitude := cmplx.Abs(value)
		total += magnitude * magnitude
	}
	return total
}

func classify(probability float64) string {
	if math.Abs(probability-1) <= tolerance {
		return "DETERMINED: event A will occur, P(A)=100%"
	}
	if math.Abs(probability) <= tolerance {
		return "DETERMINED: event A is impossible, P(A)=0%"
	}
	return fmt.Sprintf("UNDETERMINED: the model gives P(A)=%.2f%%", probability*100)
}

func prompt(scanner *bufio.Scanner, label, fallback string) (string, error) {
	fmt.Printf("%s [%s]: ", label, fallback)
	if !scanner.Scan() {
		if err := scanner.Err(); err != nil {
			return "", fmt.Errorf("read input: %w", err)
		}
		return fallback, nil
	}
	value := strings.TrimSpace(scanner.Text())
	if value == "" {
		return fallback, nil
	}
	return value, nil
}

func parseFloat(value, name string) (float64, error) {
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf("parse %s: %w", name, err)
	}
	if err := validateProbability(parsed); err != nil {
		return 0, fmt.Errorf("%s: %w", name, err)
	}
	return parsed, nil
}

func run() error {
	scanner := bufio.NewScanner(os.Stdin)
	fmt.Println("Native local quantum demon (Go)")
	bits, err := prompt(scanner, "Initial basis state", "00")
	if err != nil {
		return err
	}
	gates, err := prompt(scanner, "Gates separated by ';'", "H 0; CNOT 0 1")
	if err != nil {
		return err
	}
	targetText, err := prompt(scanner, "Environment qubit", "0")
	if err != nil {
		return err
	}
	target, err := strconv.Atoi(targetText)
	if err != nil {
		return fmt.Errorf("parse environment qubit: %w", err)
	}
	dephasingText, err := prompt(scanner, "Dephasing 0..1", "0")
	if err != nil {
		return err
	}
	dephasing, err := parseFloat(dephasingText, "dephasing")
	if err != nil {
		return err
	}
	dampingText, err := prompt(scanner, "Amplitude damping 0..1", "0")
	if err != nil {
		return err
	}
	damping, err := parseFloat(dampingText, "damping")
	if err != nil {
		return err
	}
	event, err := prompt(scanner, "Event A", "q0=q1")
	if err != nil {
		return err
	}

	state, err := applyGates(bits, gates)
	if err != nil {
		return err
	}
	density := densityFromState(state)
	density, err = dephase(density, len(bits), target, dephasing)
	if err != nil {
		return fmt.Errorf("dephase: %w", err)
	}
	density, err = amplitudeDamp(density, len(bits), target, damping)
	if err != nil {
		return fmt.Errorf("amplitude damping: %w", err)
	}
	probability, err := eventProbability(density, len(bits), event)
	if err != nil {
		return err
	}

	fmt.Println("\nBasis state probabilities:")
	dimension := 1 << len(bits)
	for index := 0; index < dimension; index++ {
		value := real(density[index*dimension+index])
		if value > tolerance {
			fmt.Printf("  |%0*b>: %.6f\n", len(bits), index, value)
		}
	}
	fmt.Printf("Purity Tr(rho^2): %.6f\n", purity(density))
	fmt.Println(classify(probability))
	return nil
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
