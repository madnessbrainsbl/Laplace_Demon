"""Continuous-time local demon: RK4 flow, exact events, Lyapunov horizon."""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable, Sequence

Flow = Callable[[Sequence[float]], list[float]]

GRAVITY = 9.81
BALL_DRAG_PER_MASS = 0.1
BALL_START = (0.0, 20.0, 15.0, 10.0)
PENDULUM_START = (3.0, 3.0, 0.0, 0.0)
DEFAULT_STEP = 0.001
MAX_HORIZON_SECONDS = 60.0
LYAPUNOV_DURATION = 15.0
LYAPUNOV_DELTA = 1e-8
LYAPUNOV_CHUNK = 0.5
LYAPUNOV_STEP = 0.002


def rk4_step(flow: Flow, state: Sequence[float], step: float) -> list[float]:
    """Advance one Runge-Kutta 4 step."""
    k1 = flow(state)
    k2 = flow([x + step * k / 2 for x, k in zip(state, k1)])
    k3 = flow([x + step * k / 2 for x, k in zip(state, k2)])
    k4 = flow([x + step * k for x, k in zip(state, k3)])
    return [
        x + step / 6 * (a + 2 * b + 2 * c + d)
        for x, a, b, c, d in zip(state, k1, k2, k3, k4)
    ]


def integrate(
    flow: Flow, state: Sequence[float], duration: float, step: float = DEFAULT_STEP
) -> list[float]:
    """Deterministic state after duration: same input, same output."""
    validate_time_parameters(duration, step)
    current = list(state)
    elapsed = 0.0
    for _ in range(math.ceil(duration / step)):
        current_step = min(step, duration - elapsed)
        current = rk4_step(flow, current, current_step)
        elapsed += current_step
    return current


def validate_time_parameters(duration: float, step: float) -> None:
    """Reject invalid integration intervals instead of returning fake results."""
    if not math.isfinite(duration) or duration < 0:
        raise ValueError("duration must be finite and non-negative")
    if not math.isfinite(step) or step <= 0:
        raise ValueError("step must be finite and positive")


def ball_flow(state: Sequence[float]) -> list[float]:
    """Thrown ball with linear air drag: not chaotic."""
    _, _, vx, vy = state
    return [vx, vy, -BALL_DRAG_PER_MASS * vx, -GRAVITY - BALL_DRAG_PER_MASS * vy]


def pendulum_flow(state: Sequence[float]) -> list[float]:
    """Double pendulum (Lagrange equations): chaotic."""
    g, l1, l2, m1, m2 = GRAVITY, 1.0, 1.0, 1.0, 1.0
    th1, th2, w1, w2 = state
    d = th1 - th2
    den = 2 * m1 + m2 - m2 * math.cos(2 * d)
    a1 = (
        -g * (2 * m1 + m2) * math.sin(th1)
        - m2 * g * math.sin(th1 - 2 * th2)
        - 2 * math.sin(d) * m2 * (w2**2 * l2 + w1**2 * l1 * math.cos(d))
    ) / (l1 * den)
    a2 = (
        2
        * math.sin(d)
        * (
            w1**2 * l1 * (m1 + m2)
            + g * (m1 + m2) * math.cos(th1)
            + w2**2 * l2 * m2 * math.cos(d)
        )
    ) / (l2 * den)
    return [w1, w2, a1, a2]


def simulate_ball(
    initial: Sequence[float], duration: float, step: float = DEFAULT_STEP
) -> tuple[list[float], float | None]:
    """Integrate the ball, stopping at ground impact (audit fix).

    Returns the final state and the impact time, or None if still airborne.
    """
    validate_time_parameters(duration, step)
    state = list(initial)
    time = 0.0
    for _ in range(math.ceil(duration / step)):
        current_step = min(step, duration - time)
        previous = state
        state = rk4_step(ball_flow, state, current_step)
        time += current_step
        if state[1] <= 0.0 < previous[1]:
            fraction = previous[1] / (previous[1] - state[1])
            impact = [p + fraction * (c - p) for p, c in zip(previous, state)]
            impact[1] = 0.0
            return impact, time - current_step + fraction * current_step
    return state, None


def lyapunov_exponent(
    flow: Flow,
    initial: Sequence[float],
    duration: float = LYAPUNOV_DURATION,
    delta: float = LYAPUNOV_DELTA,
    chunk: float = LYAPUNOV_CHUNK,
    step: float = LYAPUNOV_STEP,
) -> float:
    """Measure the largest Lyapunov exponent by Benettin renormalization.

    Audit fix: the exponent is computed from the flow, never hand-written.
    """
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    if not math.isfinite(delta) or delta <= 0:
        raise ValueError("delta must be finite and positive")
    validate_time_parameters(chunk, step)
    if chunk == 0:
        raise ValueError("chunk must be positive")

    reference = list(initial)
    shadow = list(initial)
    shadow[0] += delta
    total = 0.0
    elapsed = 0.0
    for _ in range(math.ceil(duration / chunk)):
        current_chunk = min(chunk, duration - elapsed)
        reference = integrate(flow, reference, current_chunk, step)
        shadow = integrate(flow, shadow, current_chunk, step)
        distance = math.dist(reference, shadow)
        if not math.isfinite(distance):
            raise ValueError("flow diverged to a non-finite state")
        if distance <= 0.0:
            distance = delta
        total += math.log(distance / delta)
        shadow = [
            r + (s - r) * (delta / distance) for r, s in zip(reference, shadow)
        ]
        elapsed += current_chunk
    return total / duration


def prediction_horizon(
    exponent: float, initial_error: float, tolerance: float
) -> float:
    """T_pred = (1/lambda)*ln(tolerance/initial_error); infinite without chaos."""
    if not all(math.isfinite(value) for value in (exponent, initial_error, tolerance)):
        raise ValueError("exponent, initial error and tolerance must be finite")
    if initial_error <= 0:
        raise ValueError("initial error must be positive")
    if tolerance <= initial_error:
        raise ValueError("tolerance must exceed the initial error")
    if exponent <= 0:
        return math.inf
    return math.log(tolerance / initial_error) / exponent


def mechanics_report(
    system: str, horizon: float, initial_error: float, tolerance: float
) -> str:
    """Compute one continuous event, the measured horizon and an honest verdict."""
    if not math.isfinite(horizon) or not 0 < horizon <= MAX_HORIZON_SECONDS:
        raise ValueError(
            f"horizon must be greater than 0 and at most {MAX_HORIZON_SECONDS}"
        )
    if system == "ball":
        flow, start, title = ball_flow, BALL_START, "thrown ball with air drag"
    elif system == "pendulum":
        flow, start, title = pendulum_flow, PENDULUM_START, "double pendulum (chaotic)"
    else:
        raise ValueError("system must be ball or pendulum")

    exponent = lyapunov_exponent(flow, start)
    horizon_limit = prediction_horizon(exponent, initial_error, tolerance)

    lines = [f"System: {title}"]
    if system == "ball":
        state, impact_time = simulate_ball(start, horizon)
        if impact_time is not None:
            lines.append(
                f"Event: the ball LANDED at t={impact_time:.3f} s, x={state[0]:.2f} m"
            )
        else:
            lines.append(
                f"Event: the ball is airborne, y={state[1]:.2f} m at t={horizon:.2f} s"
            )
    else:
        state = integrate(pendulum_flow, start, horizon)
        lines.append(f"Outcome: angle theta1({horizon:.2f} s) = {state[0]:.4f} rad")

    lines.append(f"Lyapunov exponent (Benettin): lambda = {exponent:+.4f} 1/s")
    if math.isinf(horizon_limit):
        lines.append(
            "Horizon T_pred is infinite: lambda <= 0, the initial error never grows"
        )
    else:
        lines.append(
            f"T_pred = (1/lambda)*ln(tolerance/error) = {horizon_limit:.2f} s"
            f" (error {initial_error:g}, tolerance {tolerance:g})"
        )
    if horizon <= horizon_limit:
        lines.append(
            f"DETERMINED: the {horizon:.2f} s horizon is inside T_pred —"
            f" the computation is trustworthy"
        )
    else:
        lines.append(
            f"BEYOND HORIZON: the outcome is deterministic, but with initial error"
            f" {initial_error:g} the computation is untrustworthy after"
            f" {horizon_limit:.2f} s"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Continuous event, measured Lyapunov exponent and horizon."
    )
    parser.add_argument("--system", choices=("ball", "pendulum"), default="ball")
    parser.add_argument("--horizon", type=float, default=5.0)
    parser.add_argument("--error", type=float, default=1e-6)
    parser.add_argument("--tolerance", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    """Run the continuous demon from the command line."""
    args = parse_args()
    try:
        print(mechanics_report(args.system, args.horizon, args.error, args.tolerance))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
