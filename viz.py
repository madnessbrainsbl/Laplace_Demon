"""Canvas animations: watch the demon work, frame by frame.

Every animation is a generator that draws one frame per `next()` call and leaves
the finished diagram on the canvas when it ends. The animation IS the plot.
"""

from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Iterator

from demon import next_state, validate_rule, validate_state
from fep import greedy_epistemic_path
from mechanics import (
    BALL_START,
    PENDULUM_START,
    ball_flow,
    lyapunov_exponent,
    pendulum_flow,
    prediction_horizon,
    rk4_step,
)

PALETTE = {
    "bg": "#101418",
    "panel": "#161C23",
    "field": "#1F2733",
    "border": "#2A3442",
    "fg": "#F2F4F7",
    "muted": "#8C97A5",
    "accent": "#C9A227",
    "accent_active": "#E0B93B",
    "accent_fg": "#15181D",
    "result_bg": "#0B0E12",
    "result_fg": "#D3DAE3",
    "ghost": "#D9534F",
    "grid": "#232C38",
    "anim": "#3FB950",
    "anim_bright": "#56D364",
    "anim_dim": "#2EA043",
}

FRAME_DELAY_MS = 28
FORAGE_DELAY_MS = 700
SIM_STEP = 0.002
PENDULUM_STEPS_PER_FRAME = 8
BALL_STEP = 0.001
BALL_STEPS_PER_FRAME = 16
BALL_DOMAIN = (50.0, 26.0)


class Animator:
    """Drives one generator-based animation on the Tk event loop."""

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._job: str | None = None

    def stop(self) -> None:
        """Cancel the running animation, if any."""
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None

    def play(self, frames: Iterator[None], delay: int = FRAME_DELAY_MS) -> None:
        """Replace any running animation with this one."""
        self.stop()

        def tick() -> None:
            try:
                next(frames)
            except StopIteration:
                self._job = None
                return
            self._job = self.root.after(delay, tick)

        tick()


def canvas_size(canvas: tk.Canvas) -> tuple[int, int]:
    """Current canvas size, with a sane fallback before it is mapped."""
    canvas.update_idletasks()
    width = canvas.winfo_width()
    height = canvas.winfo_height()
    return (width if width > 1 else 640, height if height > 1 else 240)


def _label(
    canvas: tk.Canvas, x: int, y: int, text: str, color: str, tags: str = ""
) -> None:
    canvas.create_text(
        x, y, text=text, fill=color, anchor="nw", font=("Consolas", 10), tags=tags
    )


def animate_spacetime(
    canvas: tk.Canvas, state: str, rule: int, steps: int, event_cell: int | None
) -> Iterator[None]:
    """Draw the world's spacetime one row per frame: no shortcut, only living it.

    Validation runs eagerly, before the first frame, so bad input fails at the
    call site (where the GUI can show a dialog) — not inside the timer callback.
    """
    validate_state(state)
    validate_rule(rule)
    if steps < 0:
        raise ValueError("steps must not be negative")
    return _spacetime_frames(canvas, state, rule, steps, event_cell)


def _spacetime_frames(
    canvas: tk.Canvas, state: str, rule: int, steps: int, event_cell: int | None
) -> Iterator[None]:
    """Generator body of animate_spacetime; inputs are already validated."""
    width, height = canvas_size(canvas)
    rows = steps + 1
    columns = len(state)
    # LED-matrix look: dots on a dark panel. The grid stretches to fill the
    # WHOLE canvas — no aspect cap, dots become ellipses under extreme ratios.
    cell_h = max(1.0, (height - 8) / rows)
    cell_w = max(1.0, (width - 24) / columns)
    left = (width - cell_w * columns) / 2
    top = max(4.0, (height - cell_h * rows) / 2)
    # True LED circles only while a circle is actually visible; below that the
    # honest rendering is a solid pixel fill — pure texture, no squashed shapes.
    use_dots = min(cell_w, cell_h) >= 6
    dot = min(cell_w, cell_h) * 0.8

    canvas.delete("all")
    canvas.create_rectangle(
        left,
        top,
        left + cell_w * columns,
        top + cell_h * rows,
        fill=PALETTE["result_bg"],
        outline=PALETTE["border"],
    )

    def cell_box(row: int, column: int) -> tuple[float, float, float, float]:
        x = left + column * cell_w
        y = top + row * cell_h
        if use_dots:
            cx, cy = x + cell_w / 2, y + cell_h / 2
            return cx - dot / 2, cy - dot / 2, cx + dot / 2, cy + dot / 2
        return x, y, x + cell_w, y + cell_h

    draw = canvas.create_oval if use_dots else canvas.create_rectangle
    current = state
    for row in range(rows):
        for index, value in enumerate(current):
            if value != "1":
                continue
            draw(*cell_box(row, index), fill=PALETTE["anim"], outline="")
        if event_cell is not None and row == rows - 1 and event_cell < len(current):
            draw(
                *cell_box(row, event_cell), outline=PALETTE["ghost"], width=2
            )
        canvas.delete("hud")
        canvas.create_line(
            left - 12,
            top + row * cell_h + cell_h / 2,
            left - 4,
            top + row * cell_h + cell_h / 2,
            fill=PALETTE["anim_bright"],
            width=3,
            tags="hud",
        )
        _label(canvas, 8, 6, f"step {row}/{steps}", PALETTE["muted"], tags="hud")
        yield
        current = next_state(current, rule)
    canvas.delete("hud")
    _label(canvas, 8, 6, f"done: {steps} step(s)", PALETTE["muted"])


def animate_pendulum(
    canvas: tk.Canvas, horizon: float, initial_error: float, tolerance: float
) -> Iterator[None]:
    """Two pendulums from almost the same start: watch determinism go unusable."""
    exponent = lyapunov_exponent(pendulum_flow, PENDULUM_START)
    limit = prediction_horizon(exponent, initial_error, tolerance)
    return _pendulum_frames(canvas, horizon, initial_error, tolerance, limit)


def _pendulum_frames(
    canvas: tk.Canvas,
    horizon: float,
    initial_error: float,
    tolerance: float,
    limit: float,
) -> Iterator[None]:
    """Generator body of animate_pendulum; inputs are already validated."""
    width, height = canvas_size(canvas)
    origin = (width // 2, height // 3)
    scale = min(width, height) / 5.5

    reference = list(PENDULUM_START)
    shadow = list(PENDULUM_START)
    shadow[0] += initial_error
    trail: list[tuple[float, float]] = []
    ghost_trail: list[tuple[float, float]] = []
    elapsed = 0.0
    diverged_at: float | None = None

    def bobs(state: list[float]) -> tuple[tuple[float, float], tuple[float, float]]:
        x1 = origin[0] + scale * math.sin(state[0])
        y1 = origin[1] + scale * math.cos(state[0])
        x2 = x1 + scale * math.sin(state[1])
        y2 = y1 + scale * math.cos(state[1])
        return (x1, y1), (x2, y2)

    def draw_arm(
        state: list[float],
        color: str,
        trace: list[tuple[float, float]],
    ) -> None:
        first, second = bobs(state)
        if len(trace) > 1:
            canvas.create_line(*[c for point in trace for c in point], fill=color)
        canvas.create_line(*origin, *first, fill=color, width=2)
        canvas.create_line(*first, *second, fill=color, width=2)
        canvas.create_oval(
            second[0] - 5, second[1] - 5, second[0] + 5, second[1] + 5,
            fill=color, outline="",
        )

    while elapsed < horizon:
        for _ in range(PENDULUM_STEPS_PER_FRAME):
            reference = rk4_step(pendulum_flow, reference, SIM_STEP)
            shadow = rk4_step(pendulum_flow, shadow, SIM_STEP)
            elapsed += SIM_STEP
        gap = abs(reference[0] - shadow[0])
        if diverged_at is None and gap > tolerance:
            diverged_at = elapsed

        trail.append(bobs(reference)[1])
        ghost_trail.append(bobs(shadow)[1])
        trail[:] = trail[-160:]
        ghost_trail[:] = ghost_trail[-160:]

        canvas.delete("all")
        draw_arm(shadow, PALETTE["ghost"], ghost_trail)
        draw_arm(reference, PALETTE["anim"], trail)
        _label(canvas, 8, 6, f"t = {elapsed:5.2f} s", PALETTE["fg"])
        _label(canvas, 8, 22, f"gap = {gap:.2e} rad", PALETTE["muted"])
        _label(
            canvas,
            8,
            38,
            "T_pred = inf" if math.isinf(limit) else f"T_pred = {limit:.2f} s",
            PALETTE["muted"],
        )
        if diverged_at is not None:
            _label(
                canvas,
                8,
                54,
                f"BEYOND HORIZON since t={diverged_at:.2f} s",
                PALETTE["ghost"],
            )
        yield


def animate_ball(canvas: tk.Canvas, horizon: float) -> Iterator[None]:
    """The non-chaotic event: the demon calls the landing before it happens."""
    width, height = canvas_size(canvas)
    span_x, span_y = BALL_DOMAIN
    scale = min(width / span_x, (height - 20) / span_y)
    ground = height - 12

    def to_screen(x: float, y: float) -> tuple[float, float]:
        return 10 + x * scale, ground - y * scale

    state = list(BALL_START)
    trail = [to_screen(state[0], state[1])]
    elapsed = 0.0
    impact: float | None = None

    while elapsed < horizon and impact is None:
        for _ in range(BALL_STEPS_PER_FRAME):
            previous = state
            state = rk4_step(ball_flow, state, BALL_STEP)
            elapsed += BALL_STEP
            if state[1] <= 0.0 < previous[1]:
                fraction = previous[1] / (previous[1] - state[1])
                state = [p + fraction * (c - p) for p, c in zip(previous, state)]
                state[1] = 0.0
                impact = elapsed - BALL_STEP + fraction * BALL_STEP
                break
        trail.append(to_screen(state[0], state[1]))

        canvas.delete("all")
        canvas.create_line(0, ground, width, ground, fill=PALETTE["border"], width=2)
        if len(trail) > 1:
            canvas.create_line(
                *[c for point in trail for c in point], fill=PALETTE["anim_dim"]
            )
        x, y = trail[-1]
        canvas.create_oval(
            x - 6, y - 6, x + 6, y + 6, fill=PALETTE["anim"], outline=""
        )
        _label(canvas, 8, 6, f"t = {elapsed:5.2f} s", PALETTE["fg"])
        _label(canvas, 8, 22, f"y = {state[1]:6.2f} m", PALETTE["muted"])
        if impact is not None:
            _label(
                canvas,
                8,
                38,
                f"LANDED at t={impact:.3f} s, x={state[0]:.2f} m",
                PALETTE["anim_bright"],
            )
        yield


def animate_foraging(
    canvas: tk.Canvas,
    width_cells: int,
    rule: int,
    steps: int,
    event: str,
    budget: int | None,
) -> Iterator[None]:
    """Watch an agent buy cells until it turns into a demon (or stalls)."""
    path = greedy_epistemic_path(width_cells, rule, steps, event, budget)
    return _foraging_frames(canvas, width_cells, path)


def _foraging_frames(canvas: tk.Canvas, width_cells: int, path: list) -> Iterator[None]:
    """Generator body of animate_foraging; the path is already computed."""
    width, height = canvas_size(canvas)
    cell = max(14, min(48, (width - 40) // width_cells))
    left = (width - cell * width_cells) // 2
    top = 40
    bar_top = top + cell + 34
    bar_height = 20
    bar_width = width - 80

    previous_entropy = path[0].entropy
    for index, step in enumerate(path):
        canvas.delete("all")
        _label(canvas, 8, 6, "world cells — gold means observed", PALETTE["muted"])
        for position in range(width_cells):
            x = left + position * cell
            observed = position in step.cells
            canvas.create_rectangle(
                x,
                top,
                x + cell,
                top + cell,
                fill=PALETTE["anim"] if observed else PALETTE["field"],
                outline=PALETTE["border"],
            )
            canvas.create_text(
                x + cell / 2,
                top + cell / 2,
                text=str(position),
                fill=PALETTE["accent_fg"] if observed else PALETTE["muted"],
                font=("Consolas", 9),
            )

        canvas.create_rectangle(
            40,
            bar_top,
            40 + bar_width,
            bar_top + bar_height,
            outline=PALETTE["border"],
        )
        canvas.create_rectangle(
            40,
            bar_top,
            40 + bar_width * max(step.coefficient, 0.0),
            bar_top + bar_height,
            fill=PALETTE["anim"],
            outline="",
        )
        _label(
            canvas,
            40,
            bar_top + bar_height + 8,
            f"L_O = {step.coefficient:.6f}   H(E|K) = {step.entropy:.6f} bits",
            PALETTE["fg"],
        )
        if index and step.entropy >= previous_entropy - 1e-12:
            _label(
                canvas,
                40,
                bar_top + bar_height + 26,
                f"cell {step.cells[-1]} bought ZERO information — epistemic plateau",
                PALETTE["ghost"],
            )
        elif index:
            _label(
                canvas,
                40,
                bar_top + bar_height + 26,
                f"observed cell {step.cells[-1]}",
                PALETTE["muted"],
            )
        previous_entropy = step.entropy
        yield

GAME_DOT = 16
GAME_GAP = 4


def draw_game_board(
    canvas: tk.Canvas,
    width_cells: int,
    history: list[str],
    shown: int,
    reveal: str | None = None,
    ring: str | None = None,
    wave: int | None = None,
) -> None:
    """The game's whole mechanics in one picture.

    Top: the hidden world — masked tiles, only the center cell open.
    Bottom: the center cell's history trail and the '?' slot to call.
    """
    width, height = canvas_size(canvas)
    canvas.delete("all")
    tile = max(8, min(20, (width - 48) // max(width_cells, 1)))
    top = 30
    left = (width - tile * width_cells) / 2
    center = width_cells // 2
    _label(
        canvas,
        8,
        6,
        f"THE HIDDEN WORLD — {width_cells} cells running the law;"
        " you see only the open one",
        PALETTE["muted"],
    )
    for index in range(width_cells):
        x = left + index * tile
        is_center = index == center
        canvas.create_rectangle(
            x,
            top,
            x + tile,
            top + tile,
            fill=PALETTE["result_bg"] if is_center else PALETTE["field"],
            outline=PALETTE["border"],
        )
        if is_center:
            if reveal is not None:
                if reveal == "1":
                    canvas.create_oval(
                        x + 4,
                        top + 4,
                        x + tile - 4,
                        top + tile - 4,
                        fill=PALETTE["anim"],
                        outline="",
                    )
                else:
                    canvas.create_oval(
                        x + 5,
                        top + 5,
                        x + tile - 5,
                        top + tile - 5,
                        outline=PALETTE["muted"],
                    )
        else:
            canvas.create_text(
                x + tile / 2,
                top + tile / 2,
                text="?",
                fill=PALETTE["muted"],
                font=("Consolas", max(7, tile - 10)),
            )
    if wave is not None and 0 <= wave < width_cells:
        x = left + wave * tile
        canvas.create_rectangle(
            x,
            top,
            x + tile,
            top + tile,
            outline=PALETTE["accent_active"],
            width=2,
        )
        _label(
            canvas,
            left + tile * width_cells + 8,
            top + 2,
            "one lawful step...",
            PALETTE["accent_active"],
        )

    trail_top = top + tile + 34
    _label(
        canvas,
        8,
        trail_top - 22,
        "THE CENTER CELL'S HISTORY — call the next bit",
        PALETTE["muted"],
    )
    pitch = GAME_DOT + GAME_GAP
    max_fit = max(4, int((width - 48) / pitch) - 1)
    dots = history[-min(shown, max_fit):]
    total = pitch * (len(dots) + 1)
    trail_left = (width - total) / 2
    cy = trail_top + GAME_DOT / 2 + 4
    for position, bit in enumerate(dots):
        cx = trail_left + position * pitch + GAME_DOT / 2
        if bit == "1":
            canvas.create_oval(
                cx - GAME_DOT / 2,
                cy - GAME_DOT / 2,
                cx + GAME_DOT / 2,
                cy + GAME_DOT / 2,
                fill=PALETTE["anim"],
                outline="",
            )
        else:
            canvas.create_oval(
                cx - GAME_DOT / 2 + 2,
                cy - GAME_DOT / 2 + 2,
                cx + GAME_DOT / 2 - 2,
                cy + GAME_DOT / 2 - 2,
                outline=PALETTE["muted"],
            )
        if ring is not None and position == len(dots) - 1:
            canvas.create_oval(
                cx - GAME_DOT / 2 - 4,
                cy - GAME_DOT / 2 - 4,
                cx + GAME_DOT / 2 + 4,
                cy + GAME_DOT / 2 + 4,
                outline=ring,
                width=2,
            )
    slot_x = trail_left + len(dots) * pitch + GAME_DOT / 2
    canvas.create_oval(
        slot_x - GAME_DOT / 2 - 2,
        cy - GAME_DOT / 2 - 2,
        slot_x + GAME_DOT / 2 + 2,
        cy + GAME_DOT / 2 + 2,
        outline=PALETTE["accent"],
        width=2,
    )
    canvas.create_text(
        slot_x, cy, text="?", fill=PALETTE["accent"], font=("Consolas", 11)
    )


def animate_game_step(
    canvas: tk.Canvas,
    width_cells: int,
    history: list[str],
    shown: int,
    correct: bool,
) -> Iterator[None]:
    """One round: a lawful update sweeps the hidden world, the bit drops in."""
    new_bit = history[-1]
    prior = history[:-1]
    for wave in range(0, width_cells, 2):
        draw_game_board(canvas, width_cells, prior, shown, wave=wave)
        yield
    for _ in range(3):
        draw_game_board(canvas, width_cells, prior, shown, reveal=new_bit)
        yield
    ring = PALETTE["anim_bright"] if correct else PALETTE["ghost"]
    draw_game_board(
        canvas, width_cells, history, shown, reveal=new_bit, ring=ring
    )
    yield
