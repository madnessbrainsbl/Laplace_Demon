import io
import math
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from demon import next_state, predict
from events import consistent_rules, event_report, observe_law, parse_history
from experiment import (
    Scenario,
    predictability,
    print_summary,
    run_experiment,
    simulate,
)
from fep import active_inference_report, greedy_epistemic_path
from godel import (
    STRATEGIES,
    diagonal_next_cell,
    diagonal_report,
    external_next_cell,
    mutual_inference_fails,
    mutual_inference_report,
)
from gui import DemonGUI, build_quantum_input, classical_report, run_native_quantum
from information import (
    calculate_report,
    conditional_entropy_for_mask,
    enumerate_laplace_formula,
    irreducible_profile,
    irreducible_report,
)
from interactive import classical_event_occurs
from mechanics import (
    BALL_START,
    PENDULUM_START,
    ball_flow,
    integrate,
    lyapunov_exponent,
    mechanics_report,
    pendulum_flow,
    prediction_horizon,
    simulate_ball,
)
import tkinter as tk

from quantum import apply_gates, classify_probability, quantum_event_probability
from viz import animate_foraging, animate_spacetime
from walls import (
    bekenstein_bits,
    bekenstein_report,
    binary_entropy,
    minimal_radius,
    quantum_wall_report,
)


class DemonTests(unittest.TestCase):
    def test_rule_30_known_step(self) -> None:
        self.assertEqual(next_state("0001000", 30), "0011100")

    def test_rule_zero_erases_every_cell(self) -> None:
        self.assertEqual(predict("10101", 0, 1), "00000")

    def test_cycle_skip_matches_direct_evolution(self) -> None:
        state = "0001000"
        direct = state
        for _ in range(100):
            direct = next_state(direct, 30)
        self.assertEqual(predict(state, 30, 100), direct)

    def test_invalid_state_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "only 0 and 1"):
            predict("10x01", 30, 1)

    def test_perfect_knowledge_stays_exact(self) -> None:
        rows = run_experiment(
            "0001000",
            30,
            steps=5,
            runs=10,
            seed=42,
            scenarios=(Scenario("perfect", 0.0, 0.0, 0.0),),
        )
        self.assertTrue(all(row["predictability"] == 1.0 for row in rows))
        self.assertTrue(all(row["exact_match_rate"] == 1.0 for row in rows))

    def test_random_noise_creates_disagreement(self) -> None:
        trajectories = [
            simulate("0001000", 30, 1, 0.5, random.Random(seed))
            for seed in range(20)
        ]
        states = [trajectory[1] for trajectory in trajectories]
        self.assertLess(predictability(states), 1.0)

    def test_experiment_is_reproducible(self) -> None:
        scenario = (Scenario("noise", 0.0, 0.0, 0.1),)
        first = run_experiment("0001000", 30, 3, 10, 7, scenario)
        second = run_experiment("0001000", 30, 3, 10, 7, scenario)
        self.assertEqual(first, second)

    def test_classical_event_is_determined(self) -> None:
        final_state = predict("0001000", 30, 1)
        self.assertTrue(classical_event_occurs(final_state, "cell3=1"))

    def test_bell_qubits_are_always_equal(self) -> None:
        state = apply_gates("00", "H 0; CNOT 0 1")
        self.assertAlmostEqual(quantum_event_probability(state, 2, "q0=q1"), 1.0)

    def test_bell_single_qubit_is_not_determined(self) -> None:
        state = apply_gates("00", "H 0; CNOT 0 1")
        self.assertAlmostEqual(quantum_event_probability(state, 2, "q0=0"), 0.5)

    def test_quantum_x_gate_determines_event(self) -> None:
        state = apply_gates("0", "X 0")
        self.assertAlmostEqual(quantum_event_probability(state, 1, "q0=1"), 1.0)

    def test_gui_classical_report_is_exact(self) -> None:
        report = classical_report("0001000", 30, 1, "cell3=1")
        self.assertIn("P(A)=100%", report)

    def test_gui_quantum_input_has_native_prompt_order(self) -> None:
        value = build_quantum_input("00", "H 0", 0, 0.1, 0.2, "q0=0")
        self.assertEqual(value, "00\nH 0\n0\n0.1\n0.2\nq0=0\n")
        empty = build_quantum_input("0", "", 0, 0.0, 0.0, "q0=0")
        self.assertEqual(empty, "0\n;\n0\n0.0\n0.0\nq0=0\n")

    def test_gui_calls_native_quantum_kernel(self) -> None:
        report = run_native_quantum("00", "H 0; CNOT 0 1", 0, 0.5, 0, "q0=q1")
        self.assertIn("P(A)=100%", report)
        self.assertIn("Tr(rho^2): 0.750000", report)
        identity = run_native_quantum("0", "", 0, 0.0, 0.0, "q0=0")
        self.assertIn("P(A)=100%", identity)

    def test_laplace_formula_without_knowledge_is_zero(self) -> None:
        metrics = enumerate_laplace_formula(3, (), 30, 0, "cell0=1")
        self.assertAlmostEqual(metrics.event_entropy, 1.0)
        self.assertAlmostEqual(metrics.conditional_entropy, 1.0)
        self.assertAlmostEqual(metrics.coefficient, 0.0)

    def test_laplace_formula_with_complete_relevant_knowledge_is_one(self) -> None:
        metrics = enumerate_laplace_formula(3, (0,), 30, 0, "cell0=1")
        self.assertAlmostEqual(metrics.event_entropy, 1.0)
        self.assertAlmostEqual(metrics.conditional_entropy, 0.0)
        self.assertAlmostEqual(metrics.coefficient, 1.0)

    def test_laplace_report_contains_every_term(self) -> None:
        report = calculate_report(3, "0", 30, 0, "cell0=1")
        self.assertIn("H(E)", report)
        self.assertIn("H(E|K)", report)
        self.assertIn("I(E;K)", report)

    def test_single_state_history_allows_every_rule(self) -> None:
        self.assertEqual(len(consistent_rules(observe_law(["0001000"]))), 256)

    def test_observed_law_narrows_consistent_rules(self) -> None:
        table = observe_law(["0001000", "0011100"])
        self.assertEqual(table, {0: 0, 1: 1, 2: 1, 4: 1})
        rules = consistent_rules(table)
        self.assertEqual(len(rules), 16)
        self.assertIn(30, rules)

    def test_contradictory_history_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "contradicts"):
            observe_law(["000", "000", "111"])

    def test_full_history_makes_event_determined(self) -> None:
        history = ["0001000"]
        for _ in range(7):
            history.append(next_state(history[-1], 30))
        expected = "state=" + next_state(history[-1], 30)
        report = event_report("; ".join(history), 1, expected)
        self.assertIn("Consistent rules: 1", report)
        self.assertIn("P(A)=100%", report)

    def test_partial_history_leaves_event_undetermined(self) -> None:
        report = event_report("0001000", 1, "cell3=1")
        self.assertIn("Consistent rules: 256", report)
        self.assertIn("UNDETERMINED", report)

    def test_agreeing_rules_determine_event_without_full_law(self) -> None:
        report = event_report("111; 000; 000", 1, "state=000")
        self.assertIn("Consistent rules: 64", report)
        self.assertIn("P(A)=100%", report)

    def test_history_widths_must_match(self) -> None:
        with self.assertRaisesRegex(ValueError, "one width"):
            parse_history("0001000; 001")

    def test_laplace_formula_defines_trivial_event_as_one(self) -> None:
        metrics = enumerate_laplace_formula(3, (), 0, 1, "cell0=0")
        self.assertEqual(metrics.event_entropy, 0.0)
        self.assertEqual(metrics.coefficient, 1.0)
        self.assertTrue(metrics.trivial_event)

    def test_empty_outcome_distribution_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            conditional_entropy_for_mask([], 0)

    def test_ball_stops_at_ground_impact(self) -> None:
        state, impact_time = simulate_ball(BALL_START, 5.0)
        self.assertIsNotNone(impact_time)
        self.assertAlmostEqual(impact_time, 3.306, delta=0.01)
        self.assertEqual(state[1], 0.0)

    def test_ball_error_does_not_grow(self) -> None:
        self.assertLess(abs(lyapunov_exponent(ball_flow, BALL_START)), 0.05)

    def test_pendulum_lyapunov_is_measured_positive(self) -> None:
        self.assertGreater(lyapunov_exponent(pendulum_flow, PENDULUM_START), 0.1)

    def test_prediction_horizon_formula(self) -> None:
        self.assertAlmostEqual(
            prediction_horizon(2.0, 1e-6, 1.0), math.log(1e6) / 2.0
        )
        self.assertEqual(prediction_horizon(0.0, 1e-6, 1.0), math.inf)

    def test_mechanics_rejects_invalid_time_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            integrate(ball_flow, BALL_START, -1.0)
        with self.assertRaisesRegex(ValueError, "finite"):
            prediction_horizon(1.0, math.nan, 1.0)
        with self.assertRaisesRegex(ValueError, "duration"):
            lyapunov_exponent(ball_flow, BALL_START, duration=0.0)

    def test_integration_uses_fractional_final_step(self) -> None:
        state = integrate(lambda values: [1.0], [0.0], 0.25, step=0.1)
        self.assertAlmostEqual(state[0], 0.25)

    def test_mechanics_ball_event_is_determined(self) -> None:
        report = mechanics_report("ball", 5.0, 1e-6, 1.0)
        self.assertIn("LANDED", report)
        self.assertIn("DETERMINED", report)

    def test_mechanics_chaos_beyond_horizon_is_honest(self) -> None:
        report = mechanics_report("pendulum", 30.0, 1e-3, 1.0)
        self.assertIn("BEYOND HORIZON", report)

    def test_irreducible_profile_finds_minimal_knowledge(self) -> None:
        levels = irreducible_profile(3, 30, 0, "cell0=1")
        self.assertAlmostEqual(levels[0].entropy, 1.0)
        self.assertAlmostEqual(levels[1].entropy, 0.0)
        self.assertEqual(levels[1].best_cells, (0,))

    def test_irreducible_profile_is_monotone_and_reaches_zero(self) -> None:
        levels = irreducible_profile(5, 30, 2, "cell2=1")
        entropies = [level.entropy for level in levels]
        self.assertEqual(entropies, sorted(entropies, reverse=True))
        self.assertAlmostEqual(entropies[-1], 0.0)

    def test_irreducible_report_names_minimal_demon(self) -> None:
        report = irreducible_report(3, 30, 0, "cell0=1")
        self.assertIn("Minimal demon: 1 cell(s) of 3", report)

    def test_no_inner_strategy_survives_diagonal(self) -> None:
        for strategy in STRATEGIES.values():
            for cell in (0, 1):
                prediction = strategy(cell)
                self.assertNotEqual(prediction, diagonal_next_cell(prediction))

    def test_external_demon_exists_for_same_law(self) -> None:
        invert = STRATEGIES["invert the cell"]
        for cell in (0, 1):
            self.assertEqual(invert(cell), external_next_cell(cell))

    def test_diagonal_report_shows_both_sides(self) -> None:
        report = diagonal_report()
        self.assertIn("wrong 2 of 2", report)
        self.assertIn("is right 2 of 2", report)

    def test_no_pair_of_devices_infers_each_other(self) -> None:
        for first in (0, 1):
            for second in (0, 1):
                first_ok, second_ok = mutual_inference_fails(first, second)
                self.assertFalse(first_ok and second_ok)

    def test_mutual_inference_report_counts_zero_survivors(self) -> None:
        self.assertIn("both devices are right: 0 of 4", mutual_inference_report())

    def test_binary_entropy_endpoints(self) -> None:
        self.assertEqual(binary_entropy(0.0), 0.0)
        self.assertEqual(binary_entropy(1.0), 0.0)
        self.assertAlmostEqual(binary_entropy(0.5), 1.0)

    def test_bekenstein_bound_matches_known_value(self) -> None:
        # A 1 kg, 1 m sphere holds at most ~2.577e43 bits.
        bits = bekenstein_bits(1.0, 1.0 * 299792458.0**2)
        self.assertAlmostEqual(bits / 2.577e43, 1.0, places=2)

    def test_minimal_radius_inverts_the_bound(self) -> None:
        radius = minimal_radius(bekenstein_bits(0.5, 2.0), 2.0)
        self.assertAlmostEqual(radius, 0.5)

    def test_bekenstein_report_states_whether_the_wall_bites(self) -> None:
        self.assertIn("does NOT bite", bekenstein_report(0.1, 1.0, 3))
        self.assertIn("BITES", bekenstein_report(1e-30, 1e-30, 1000))

    def test_bekenstein_bound_rejects_nonfinite_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            bekenstein_bits(math.nan, 1.0)

    def test_quantum_wall_leaves_no_information_to_gain(self) -> None:
        report = quantum_wall_report("00", "H 0; CNOT 0 1", "q0=1")
        self.assertIn("L_O               = 0.000000", report)
        self.assertIn("THE QUANTUM WALL", report)

    def test_quantum_wall_allows_determined_correlation(self) -> None:
        report = quantum_wall_report("00", "H 0; CNOT 0 1", "q0=q1")
        self.assertIn("L_O               = 1.000000", report)

    def test_complementarity_bound_holds_for_eigenstate(self) -> None:
        report = quantum_wall_report("0", "", "q0=1")
        self.assertIn("H(Z) = 0.000000   H(X) = 1.000000", report)
        self.assertIn("H(Z)+H(X) = 1.000000 >= 1.0", report)

    def test_agent_becomes_a_demon_by_epistemic_action(self) -> None:
        path = greedy_epistemic_path(7, 30, 1, "cell3=1")
        self.assertAlmostEqual(path[0].coefficient, 0.0)
        self.assertAlmostEqual(path[-1].coefficient, 1.0)
        self.assertEqual(path[-1].cells, (2, 3, 4))

    def test_epistemic_value_rises_monotonically(self) -> None:
        path = greedy_epistemic_path(7, 30, 1, "cell3=1")
        coefficients = [step.coefficient for step in path]
        self.assertEqual(coefficients, sorted(coefficients))

    def test_greedy_curiosity_stalls_on_xor_law(self) -> None:
        report = active_inference_report(7, 60, 1, "cell3=1")
        self.assertIn("EPISTEMIC PLATEAU", report)
        self.assertIn("Greedy is NOT optimal", report)

    def test_budget_limits_the_agent(self) -> None:
        path = greedy_epistemic_path(7, 30, 1, "cell3=1", budget=1)
        self.assertEqual(len(path), 2)
        self.assertLess(path[-1].coefficient, 1.0)

    def test_event_error_suggests_cell_for_quantum_syntax(self) -> None:
        with self.assertRaisesRegex(ValueError, "cell0=1"):
            classical_event_occurs("000", "q0=1")

    def test_event_error_detects_wrong_keyboard_layout(self) -> None:
        with self.assertRaisesRegex(ValueError, "English keyboard"):
            classical_event_occurs("000", "сell0=1")

    def test_event_error_explains_bad_cell_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "can only be 0 or 1"):
            classical_event_occurs("000", "cell0=2")

    def test_event_error_names_the_world_size(self) -> None:
        with self.assertRaisesRegex(ValueError, r"cells 0\.\.2"):
            classical_event_occurs("000", "cell5=1")

    def test_event_error_explains_empty_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "field is empty"):
            classical_event_occurs("000", "")

    def test_quantum_event_error_suggests_qubit_syntax(self) -> None:
        state = apply_gates("0", "")
        with self.assertRaisesRegex(ValueError, "q0=1"):
            quantum_event_probability(state, 1, "cell0=1")

    def test_probability_classifier_rejects_nan(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            classify_probability(math.nan)

    def test_gate_error_lists_supported_gates(self) -> None:
        with self.assertRaisesRegex(ValueError, "H n, X n, CNOT"):
            apply_gates("00", "Z 0")

    def test_spinbox_filter_blocks_typing_beyond_range(self) -> None:
        from tkinter import ttk

        from gui import spin_text_ok

        root = tk.Tk()
        try:
            rule = ttk.Spinbox(root, from_=0, to=255, increment=1)
            self.assertTrue(spin_text_ok("30", rule))
            self.assertTrue(spin_text_ok("", rule))
            self.assertFalse(spin_text_ok("300", rule))
            self.assertFalse(spin_text_ok("3a", rule))
            self.assertFalse(spin_text_ok("3.5", rule))
            unit = ttk.Spinbox(root, from_=0, to=1, increment=0.05)
            self.assertTrue(spin_text_ok("0.5", unit))
            self.assertTrue(spin_text_ok(".", unit))
            self.assertFalse(spin_text_ok("1.5", unit))
            self.assertFalse(spin_text_ok("0..5", unit))
        finally:
            root.update_idletasks()
            root.destroy()

    def test_bits_filter_allows_only_binary(self) -> None:
        from gui import bits_text_ok

        self.assertTrue(bits_text_ok("010101"))
        self.assertFalse(bits_text_ok("0121"))
        self.assertFalse(bits_text_ok("0" * 11, limit=10))
        self.assertTrue(bits_text_ok("01; 10", extra="; "))

    def test_light_cone_seat_decides_who_can_be_a_demon(self) -> None:
        from cone import embedded_demon_profile, light_cone_cells

        self.assertEqual(light_cone_cells(7, 3, 1), (2, 3, 4))
        self.assertEqual(light_cone_cells(7, 0, 1), (0, 1, 6))
        profile = embedded_demon_profile(7, 30, 1, "cell3=1")
        self.assertAlmostEqual(profile[3], 1.0)
        self.assertLess(profile[0], 1.0)
        self.assertLess(profile[5], 1.0)

    def test_light_cone_report_names_the_wall(self) -> None:
        from cone import light_cone_report

        report = light_cone_report(7, 30, 1, "cell3=1")
        self.assertIn("full demon here", report)
        self.assertIn("WHERE you sit", report)
        long_horizon = light_cone_report(5, 30, 3, "cell2=1")
        self.assertIn("light to cross the whole ring", long_horizon)

    def test_macro_entropy_grows_under_rule_30(self) -> None:
        from macro import macro_entropy_series, macro_report

        series = macro_entropy_series(12, 30, 6)
        self.assertAlmostEqual(series[0], 0.0)
        self.assertGreater(series[-1], 1.0)
        self.assertIn("SECOND LAW", macro_report(12, 30, 6))

    def test_macro_entropy_stays_zero_for_identity_rule(self) -> None:
        from macro import macro_entropy_series, macro_report

        self.assertEqual(max(macro_entropy_series(9, 204, 4)), 0.0)
        self.assertIn("preserves the macrostate", macro_report(9, 204, 4))

    def test_macro_requires_block_aligned_width(self) -> None:
        from macro import macro_entropy_series

        with self.assertRaisesRegex(ValueError, "multiple of 3"):
            macro_entropy_series(10, 30, 2)

    def test_reading_a_qubit_halves_bell_purity(self) -> None:
        from gui import read_qubit_report

        report = read_qubit_report("00", "H 0; CNOT 0 1", 0, "q0=q1")
        self.assertIn("1.000000 -> 0.500000", report)
        self.assertIn("MEASUREMENT DISTURBS", report)

    def test_reading_a_classical_bit_is_free(self) -> None:
        from gui import read_qubit_report

        report = read_qubit_report("00", "X 0", 0, "q0=1")
        self.assertIn("1.000000 -> 1.000000", report)
        self.assertIn("Nothing to disturb", report)

    def test_game_round_animation_ends_on_a_ringed_board(self) -> None:
        from viz import animate_game_step, draw_game_board

        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=900, height=170)
            canvas.pack()
            root.update()
            history = ["0", "1"] * 17
            frames = list(animate_game_step(canvas, 31, history, 32, True))
            self.assertEqual(len(frames), 31 // 2 + 1 + 3 + 1)
            self.assertGreater(len(canvas.find_all()), 31)
            draw_game_board(canvas, 31, history, 32, reveal="1")
            self.assertGreater(len(canvas.find_all()), 31)
        finally:
            root.destroy()

    def test_rewind_returns_exactly_without_observation(self) -> None:
        from quantum import rewind_probabilities

        pure_return, read_return = rewind_probabilities("00", "H 0; CNOT 0 1", 0)
        self.assertAlmostEqual(pure_return, 1.0)
        self.assertAlmostEqual(read_return, 0.5)

    def test_rewind_reading_a_classical_bit_leaves_no_fingerprint(self) -> None:
        from quantum import rewind_probabilities, rewind_report

        pure_return, read_return = rewind_probabilities("00", "X 0", 0)
        self.assertAlmostEqual(pure_return, 1.0)
        self.assertAlmostEqual(read_return, 1.0)
        self.assertIn("no fingerprint", rewind_report("00", "X 0", 0))
        self.assertIn(
            "UNITARY WORLD REMEMBERS", rewind_report("00", "H 0; CNOT 0 1", 0)
        )

    def test_reversed_program_inverts_order(self) -> None:
        from quantum import reversed_program

        self.assertEqual(
            reversed_program("H 0; CNOT 0 1; X 1"), "X 1; CNOT 0 1; H 0"
        )

    def test_retrodiction_identity_rule_has_unique_past(self) -> None:
        from demon import preimages

        self.assertEqual(preimages("0110", 204), ["0110"])

    def test_retrodiction_rule_zero_shows_the_arrow_of_time(self) -> None:
        from demon import preimages, retrodiction_report

        self.assertEqual(len(preimages("0000", 0)), 16)
        self.assertEqual(preimages("0100", 0), [])
        self.assertIn("ARROW OF TIME", retrodiction_report("0000", 0))
        self.assertIn("GARDEN OF EDEN", retrodiction_report("0100", 0))

    def test_retrodiction_preimages_actually_evolve_into_state(self) -> None:
        from demon import preimages

        target = predict("0001000", 30, 1)
        pasts = preimages(target, 30)
        self.assertTrue(pasts)
        for past in pasts:
            self.assertEqual(next_state(past, 30), target)

    def test_fast_forward_matches_lived_evolution(self) -> None:
        import random

        from shortcut import fast_forward, linear_coefficients

        self.assertEqual(linear_coefficients(90), (1, 0, 1))
        self.assertIsNone(linear_coefficients(30))
        generator = random.Random(11)
        for rule in (60, 90, 102, 150, 170, 204, 240, 0):
            state = "".join(generator.choice("01") for _ in range(9))
            steps = generator.randint(0, 50)
            self.assertEqual(
                fast_forward(state, rule, steps), predict(state, rule, steps)
            )

    def test_fast_forward_jumps_beyond_any_lived_horizon(self) -> None:
        from shortcut import fast_forward

        result = fast_forward("0" * 30 + "1" + "0" * 30, 90, 10**18)
        self.assertEqual(len(result), 61)
        self.assertEqual(set(result) | {"0", "1"}, {"0", "1"})

    def test_shortcut_report_refuses_rule_30_honestly(self) -> None:
        from shortcut import shortcut_report

        report = shortcut_report("0001000", 30, 1000)
        self.assertIn("NOT linear", report)
        self.assertIn("irreducibility", report)
        self.assertIn("REDUCIBLE", shortcut_report("0001000", 90, 1000))

    def test_landauer_cost_matches_kT_ln2(self) -> None:
        import math

        from walls import BOLTZMANN, landauer_cost_joules, landauer_report

        expected = BOLTZMANN * 300.0 * math.log(2)
        self.assertAlmostEqual(landauer_cost_joules(1, 300.0), expected)
        self.assertEqual(landauer_cost_joules(0, 300.0), 0.0)
        with self.assertRaisesRegex(ValueError, "temperature"):
            landauer_cost_joules(1, 0.0)
        self.assertIn("Maxwell", landauer_report(3, 300.0))

    def test_chsh_bell_pair_reaches_tsirelson(self) -> None:
        from walls import TSIRELSON_BOUND, chsh_value

        bell_states = (
            ("00", "H 0; CNOT 0 1"),
            ("10", "H 0; CNOT 0 1"),
            ("00", "H 0; CNOT 0 1; X 1"),
            ("10", "H 0; CNOT 0 1; X 1"),
        )
        for bits, gates in bell_states:
            with self.subTest(bits=bits, gates=gates):
                self.assertAlmostEqual(
                    chsh_value(bits, gates), TSIRELSON_BOUND, places=9
                )

    def test_chsh_product_states_respect_the_classical_bound(self) -> None:
        from walls import chsh_value

        self.assertLessEqual(chsh_value("00", ""), 2.0 + 1e-9)
        self.assertLessEqual(chsh_value("00", "H 0"), 2.0 + 1e-9)
        self.assertLessEqual(chsh_value("00", "X 0; X 1"), 2.0 + 1e-9)

    def test_chsh_report_declares_the_violation(self) -> None:
        from walls import chsh_report

        self.assertIn("BELL VIOLATION", chsh_report("00", "H 0; CNOT 0 1"))
        self.assertIn("Within the classical bound", chsh_report("00", ""))

    def test_mutual_inference_names_the_monotheism_theorem(self) -> None:
        self.assertIn("monotheism", mutual_inference_report())

    def test_gate_builder_composes_and_refuses_bad_cnot(self) -> None:
        from tkinter import ttk

        import gui

        root = tk.Tk()
        try:
            frame = ttk.Frame(root)
            frame.grid()
            variable = tk.StringVar(value="")
            builder = gui.GateBuilder(frame, 0, variable, lambda: 2)
            builder.kind.set("H")
            builder.index.set("0")
            builder.add()
            builder.kind.set("CNOT")
            builder.index.set("0")
            builder.partner.set("1")
            builder.add()
            self.assertEqual(variable.get(), "H 0; CNOT 0 1")
            builder.partner.set("0")
            builder.add()
            self.assertEqual(variable.get(), "H 0; CNOT 0 1")
            self.assertIn("must differ", str(builder.hint.cget("text")))
            builder.undo()
            self.assertEqual(variable.get(), "H 0")
            builder.clear()
            self.assertEqual(variable.get(), "")
        finally:
            root.update_idletasks()
            root.destroy()

    def test_gate_errors_name_the_offending_command(self) -> None:
        with self.assertRaisesRegex(ValueError, "in gate 'CNOT 0 0'"):
            apply_gates("00", "CNOT 0 0")
        with self.assertRaisesRegex(ValueError, "in gate 'H 9'"):
            apply_gates("00", "H 9")

    def test_known_cells_filter_blocks_digit_spam(self) -> None:
        from gui import known_cells_text_ok

        for good in ("", "2,3,4", "2, 13", "all", "none", "a", "no"):
            self.assertTrue(known_cells_text_ok(good), good)
        for bad in ("2,3,422", "abc", "2;3", "all4", "1234"):
            self.assertFalse(known_cells_text_ok(bad), bad)

    def test_numeric_filters_block_leading_zero_runs(self) -> None:
        from tkinter import ttk

        from gui import float_text_ok, spin_text_ok

        self.assertFalse(float_text_ok("01"))
        self.assertTrue(float_text_ok("0.5"))
        self.assertTrue(float_text_ok("1e-06"))
        root = tk.Tk()
        try:
            spin = ttk.Spinbox(root, from_=0, to=9, increment=1)
            self.assertFalse(spin_text_ok("01", spin))
            self.assertTrue(spin_text_ok("0", spin))
            horizon = ttk.Spinbox(root, from_=0.5, to=60, increment=0.5)
            self.assertTrue(spin_text_ok("12.5", horizon))
            self.assertFalse(spin_text_ok("5.04444", horizon))
        finally:
            root.update_idletasks()
            root.destroy()

    def test_quantum_state_width_error_is_diagnostic(self) -> None:
        state = apply_gates("00", "H 0")
        with self.assertRaisesRegex(ValueError, "1 digit.*2 qubit"):
            quantum_event_probability(state, 2, "state=1")

    def test_float_filter_allows_scientific_but_blocks_garbage(self) -> None:
        from gui import float_text_ok

        for good in ("", "1", "1.", "1.0", "1e-6", "1.5e-10", "0.000000001", "-3"):
            self.assertTrue(float_text_ok(good), good)
        for bad in ("1.0.", "1ee6", "1e6e", "abc", "1.2.3", "1x"):
            self.assertFalse(float_text_ok(bad), bad)
        self.assertFalse(float_text_ok("1.0" + "4" * 20))
        self.assertFalse(float_text_ok("1e-6444"))
        self.assertFalse(float_text_ok("1.0333333333"))

    def test_event_field_composes_and_clamps(self) -> None:
        from tkinter import ttk

        import gui

        root = tk.Tk()
        try:
            frame = ttk.Frame(root)
            frame.grid()
            variable = tk.StringVar(value="cell3=1")
            width = {"cells": 7}
            field = gui.EventField(
                frame, 0, "Event", variable, lambda: width["cells"]
            )
            self.assertEqual(variable.get(), "cell3=1")
            field.value.set("0")
            self.assertEqual(variable.get(), "cell3=0")
            width["cells"] = 3
            field.refresh()
            self.assertEqual(float(field.index_spin.cget("to")), 2.0)
            self.assertEqual(variable.get(), "cell3=0")
            field.kind.set("exact state")
            self.assertEqual(variable.get(), "state=000")
        finally:
            root.update_idletasks()
            root.destroy()

    def test_event_field_quantum_pair(self) -> None:
        from tkinter import ttk

        import gui

        root = tk.Tk()
        try:
            frame = ttk.Frame(root)
            frame.grid()
            variable = tk.StringVar(value="q0=q1")
            field = gui.EventField(
                frame, 0, "Event", variable, lambda: 2, quantum=True
            )
            self.assertEqual(variable.get(), "q0=q1")
            field.kind.set("qubit N = value")
            self.assertEqual(variable.get(), "q0=1")
        finally:
            root.update_idletasks()
            root.destroy()

    def test_errors_are_logged_to_file(self) -> None:
        from gui import log_error

        marker = "unit-test-log-entry"
        with tempfile.TemporaryDirectory() as directory:
            log_file = Path(directory) / "errors.log"
            with patch("gui.LOG_FILE", log_file):
                log_error(marker)
            self.assertIn(marker, log_file.read_text(encoding="utf-8"))

    def test_summary_supports_custom_scenarios(self) -> None:
        rows = run_experiment(
            "0001000",
            30,
            steps=1,
            runs=2,
            seed=1,
            scenarios=(Scenario("custom", 0.0, 0.0, 0.0),),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            print_summary(rows)
        self.assertIn("custom", output.getvalue())

    def test_animation_validates_before_first_frame(self) -> None:
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root)
            with self.assertRaisesRegex(ValueError, "rule must be"):
                animate_spacetime(canvas, "0001000", 300, 5, None)
            with self.assertRaisesRegex(ValueError, "width must be"):
                animate_foraging(canvas, 99, 30, 1, "cell3=1", None)
        finally:
            root.update_idletasks()
            root.destroy()

    def test_gui_does_not_animate_an_invalid_event(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = DemonGUI(root)
            app.classical_event.set("cell99=1")
            with (
                patch.object(app._animator, "play") as play,
                patch.object(app, "_show_error") as show_error,
            ):
                app._animate_classical()
            play.assert_not_called()
            show_error.assert_called_once()
        finally:
            root.update_idletasks()
            root.destroy()

    def test_initial_error_is_a_required_readonly_preset(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = DemonGUI(root)
            self.assertIn("readonly", app.mechanics_error_box.state())
            self.assertEqual(app.mechanics_error.get(), "1e-6")
            app.mechanics_error_box.focus_force()
            app.mechanics_error_box.selection_range(0, "end")
            app.mechanics_error_box.event_generate("<BackSpace>")
            root.update()
            self.assertEqual(app.mechanics_error.get(), "1e-6")
        finally:
            root.update_idletasks()
            root.destroy()

    def test_gui_chsh_uses_the_selected_qubit_pair(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            app = DemonGUI(root)
            app.quantum_bits.set("0000")
            app.quantum_event_field.kind.set("qubit N = qubit M")
            app.quantum_event_field.index.set("2")
            app.quantum_event_field.partner.set("3")
            app._show_chsh()
            report = app.quantum_result.get("1.0", "end")
            self.assertIn("qubits 2 and 3", report)
            self.assertIn("S_max = 2.000000", report)
        finally:
            root.update_idletasks()
            root.destroy()

    def test_spacetime_animation_yields_one_frame_per_step(self) -> None:
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root)
            frames = list(animate_spacetime(canvas, "0001000", 30, 5, 3))
            self.assertEqual(len(frames), 6)
        finally:
            root.update_idletasks()
            root.destroy()

    def test_foraging_animation_yields_one_frame_per_action(self) -> None:
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root)
            path = greedy_epistemic_path(7, 30, 1, "cell3=1")
            frames = list(animate_foraging(canvas, 7, 30, 1, "cell3=1", None))
            self.assertEqual(len(frames), len(path))
        finally:
            root.update_idletasks()
            root.destroy()


if __name__ == "__main__":
    unittest.main()
