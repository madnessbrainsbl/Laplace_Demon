package main

import (
	"math"
	"testing"
)

func closeEnough(actual, expected float64) bool {
	return math.Abs(actual-expected) <= tolerance
}

func bellDensity(t *testing.T) []complex128 {
	t.Helper()
	state, err := applyGates("00", "H 0; CNOT 0 1")
	if err != nil {
		t.Fatalf("create Bell state: %v", err)
	}
	return densityFromState(state)
}

func TestBellCorrelationIsCertain(t *testing.T) {
	probability, err := eventProbability(bellDensity(t), 2, "q0=q1")
	if err != nil {
		t.Fatal(err)
	}
	if !closeEnough(probability, 1) {
		t.Fatalf("probability = %f, want 1", probability)
	}
}

func TestBellSingleOutcomeIsUncertain(t *testing.T) {
	probability, err := eventProbability(bellDensity(t), 2, "q0=0")
	if err != nil {
		t.Fatal(err)
	}
	if !closeEnough(probability, 0.5) {
		t.Fatalf("probability = %f, want 0.5", probability)
	}
}

func TestDephasingStrengthIsMonotonic(t *testing.T) {
	density, err := dephase(bellDensity(t), 2, 0, 0.5)
	if err != nil {
		t.Fatal(err)
	}
	if !closeEnough(purity(density), 0.75) {
		t.Fatalf("purity = %f, want 0.75", purity(density))
	}
	probability, err := eventProbability(density, 2, "q0=q1")
	if err != nil {
		t.Fatal(err)
	}
	if !closeEnough(probability, 1) {
		t.Fatalf("correlation = %f, want 1", probability)
	}
	fullyDephased, err := dephase(bellDensity(t), 2, 0, 1)
	if err != nil {
		t.Fatal(err)
	}
	if !closeEnough(purity(fullyDephased), 0.5) {
		t.Fatalf("full-dephasing purity = %f, want 0.5", purity(fullyDephased))
	}
}

func TestNaNProbabilityIsRejected(t *testing.T) {
	if err := validateProbability(math.NaN()); err == nil {
		t.Fatal("NaN probability was accepted")
	}
}

func TestOversizedEventQubitIsRejected(t *testing.T) {
	_, err := eventProbability(
		bellDensity(t),
		2,
		"q999999999999999999999999999999=1",
	)
	if err == nil {
		t.Fatal("oversized qubit index was accepted")
	}
}

func TestAmplitudeDampingMovesOneToZero(t *testing.T) {
	state, err := basisState("1")
	if err != nil {
		t.Fatal(err)
	}
	density, err := amplitudeDamp(densityFromState(state), 1, 0, 1)
	if err != nil {
		t.Fatal(err)
	}
	probability, err := eventProbability(density, 1, "q0=0")
	if err != nil {
		t.Fatal(err)
	}
	if !closeEnough(probability, 1) {
		t.Fatalf("probability = %f, want 1", probability)
	}
}
