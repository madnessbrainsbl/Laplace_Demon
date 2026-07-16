"""Native Tkinter interface for the local Laplace demon."""

from __future__ import annotations

import random
import re
import subprocess
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from cone import light_cone_report
from demon import next_state, predict, retrodiction_report
from events import event_report
from macro import macro_report
from fep import active_inference_report
from godel import diagonal_report, mutual_inference_report
from information import calculate_report, irreducible_profile, irreducible_report
from interactive import classical_event_occurs
from mechanics import mechanics_report
from quantum import classify_probability, rewind_report
from shortcut import shortcut_report
from viz import (
    PALETTE,
    Animator,
    animate_ball,
    animate_foraging,
    animate_game_step,
    animate_pendulum,
    animate_spacetime,
    draw_game_board,
)
from walls import (
    bekenstein_report,
    chsh_report,
    landauer_report,
    quantum_wall_report,
)

APP_DIR = Path(__file__).resolve().parent
LOG_FILE = APP_DIR / "errors.log"
QUANTUM_EXE = APP_DIR / "native_quantum" / "quantum-demon.exe"
QUANTUM_TIMEOUT_SECONDS = 30
QUANTUM_MARKER = "Basis state probabilities:"
MECHANICS_SYSTEMS = {
    "Thrown ball — no chaos": "ball",
    "Double pendulum — chaos": "pendulum",
}
INITIAL_ERROR_PRESETS = ("1e-1", "1e-2", "1e-3", "1e-6", "1e-9", "1e-12")

FONT_BODY = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI Semibold", 15)
FONT_HEADER = ("Segoe UI Semibold", 17)
FONT_MONO = ("Consolas", 11)


def safe_int(text: str, fallback: int) -> int:
    """Parse an int for live hints; never raises while the user is typing."""
    try:
        return int(text)
    except ValueError:
        return fallback


def spin_text_ok(text: str, spin: ttk.Spinbox) -> bool:
    """Keystroke filter for bounded numeric fields.

    Blocks anything that can never become a valid value: non-digits, a second
    dot, decimals in integer fields, and any number already above the ceiling
    (appending digits only grows it). Empty and below-minimum prefixes stay
    typeable — they are transient while editing and are diagnosed on compute.
    """
    if text == "":
        return True
    # No spin field needs more: "999", "60.5", "0.333" all fit in 6 chars.
    if len(text) > 6:
        return False
    if any(char not in "0123456789." for char in text) or text.count(".") > 1:
        return False
    if not _no_leading_zero_run(text):
        return False
    low = float(str(spin.cget("from")))
    high = float(str(spin.cget("to")))
    increment = float(str(spin.cget("increment")))
    integers_only = low.is_integer() and high.is_integer() and increment.is_integer()
    if integers_only and "." in text:
        return False
    if text == ".":
        return True
    return float(text) <= high


def bits_text_ok(text: str, limit: int = 0, extra: str = "") -> bool:
    """Keystroke filter for binary-state fields: only 0, 1 and listed extras."""
    if limit and len(text) > limit:
        return False
    return set(text) <= set("01" + extra)


def _no_leading_zero_run(text: str) -> bool:
    """Reject 01, 007 etc.; 0, 0.5 and exponents like 1e-06 stay typeable."""
    digits = text[1:] if text[:1] in "+-" else text
    return not (len(digits) > 1 and digits[0] == "0" and digits[1].isdigit())


KNOWN_WORDS = ("all", "none")


def known_cells_text_ok(text: str) -> bool:
    """Keystroke filter for the K field: index lists, 'all' or 'none'.

    Cell indexes never exceed two digits (width caps at 14), so a runaway
    digit spam is cut at the third digit of any token; ranges themselves are
    checked by the diagnostic dialog on compute.
    """
    lower = text.strip().lower()
    if any(word.startswith(lower) for word in KNOWN_WORDS):
        return True
    if set(text) <= set("0123456789, "):
        return all(len(token.strip()) <= 2 for token in text.split(","))
    return False


# Bounded runs: <=3 integer digits, <=9 decimals, <=3 exponent digits — every
# physical input here fits (1e-6, 0.000000001, 8.99e16); spam cannot.
_FLOAT_PREFIX = re.compile(r"[+-]?\d{0,3}\.?\d{0,9}([eE][+-]?\d{0,3})?")


def float_text_ok(text: str, limit: int = 16) -> bool:
    """Keystroke filter for scientific-notation floats (1e-6, 0.5, 1.5e-10).

    Accepts only a prefix of a valid float with bounded digit runs — a second
    dot, a stray letter, a second exponent or a digit spam in any part are
    blocked at the keystroke. Sign and magnitude are still range-checked by
    the diagnostic dialog on compute.
    """
    return (
        len(text) <= limit
        and _FLOAT_PREFIX.fullmatch(text) is not None
        and _no_leading_zero_run(text)
    )


def log_error(message: str) -> None:
    """Append one diagnosed error to errors.log next to the app."""
    try:
        with LOG_FILE.open("a", encoding="utf-8") as log:
            log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}\n")
    except OSError:
        pass  # ponytail: a full/locked disk must never break the dialog itself


def read_qubit_report(bits: str, gates: str, qubit: int, event: str) -> str:
    """Measurement as disturbance: reading a qubit is full Z dephasing.

    Runs the Go kernel twice — untouched and fully dephased on the read qubit —
    and compares purity: extracting one bit physically alters the world.
    """
    before = run_native_quantum(bits, gates, qubit, 0.0, 0.0, event)
    after = run_native_quantum(bits, gates, qubit, 1.0, 0.0, event)

    def purity_of(report: str) -> float:
        for line in report.splitlines():
            if "Purity" in line:
                return float(line.rsplit(":", 1)[1])
        raise ValueError("kernel output missing the purity line")

    purity_before, purity_after = purity_of(before), purity_of(after)
    lines = [
        f"READING qubit {qubit} = full dephasing in the measurement basis.",
        f"Purity Tr(rho^2): {purity_before:.6f} -> {purity_after:.6f}",
        "",
        "State after the reading:",
        after,
        "",
    ]
    if purity_after < purity_before - 1e-9:
        lines.append(
            "MEASUREMENT DISTURBS: extracting one bit destroyed coherence the"
            " demon might have needed later — X-basis facts and any Bell"
            " violation through this qubit are gone. Knowledge is not only"
            " paid for in joules (Landauer); taking it leaves fingerprints."
        )
    else:
        lines.append(
            "Nothing to disturb: this qubit held no coherence, so reading it"
            " was free. The wall only bites where superposition lives."
        )
    return "\n".join(lines)


class EventField:
    """Structured event picker: an invalid event cannot even be assembled.

    Writes the composed event string (cellN=V, state=bits, qN=V, qN=qM) into
    the tab's existing StringVar, so the compute methods stay untouched.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        width_source: Callable[[], int],
        quantum: bool = False,
    ) -> None:
        self.variable = variable
        self.width_source = width_source
        self.quantum = quantum
        self.kinds = (
            ("qubit N = value", "qubit N = qubit M", "exact state")
            if quantum
            else ("cell N = value", "exact state")
        )
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        self.holder = ttk.Frame(parent)
        self.holder.grid(row=row, column=1, sticky="ew", padx=(14, 10), pady=4)
        self.kind = tk.StringVar(value=self.kinds[1] if quantum else self.kinds[0])
        ttk.Combobox(
            self.holder,
            textvariable=self.kind,
            values=self.kinds,
            state="readonly",
            width=18,
        ).pack(side="left")
        self.index = tk.StringVar(value="0" if quantum else "3")
        self.partner = tk.StringVar(value="1")
        self.value = tk.StringVar(value="1")
        self.state_bits = tk.StringVar(value="")
        self.index_spin = self._spin(self.index)
        self.eq_label = ttk.Label(self.holder, text="=")
        self.value_box = ttk.Combobox(
            self.holder,
            textvariable=self.value,
            values=("0", "1"),
            state="readonly",
            width=3,
        )
        self.partner_spin = self._spin(self.partner)
        self.state_entry = ttk.Entry(self.holder, textvariable=self.state_bits)
        accept = self.state_entry.register(
            lambda text: bits_text_ok(text, limit=max(self.width_source(), 1))
        )
        self.state_entry.configure(validate="key", validatecommand=(accept, "%P"))
        self.hint = ttk.Label(parent, text="", style="Hint.TLabel")
        self.hint.grid(row=row, column=2, sticky="w", pady=4)
        self.kind.trace_add("write", lambda *_: self.refresh())
        for var in (self.index, self.partner, self.value, self.state_bits):
            var.trace_add("write", lambda *_: self._sync())
        self.refresh()

    def _spin(self, variable: tk.StringVar) -> ttk.Spinbox:
        # to=999 at creation: a tight initial bound would clamp the seeded
        # value before refresh() installs the real width-based ceiling.
        spin = ttk.Spinbox(
            self.holder, textvariable=variable, from_=0, to=999, width=4
        )
        accept = spin.register(lambda text, w=spin: spin_text_ok(text, w))
        spin.configure(validate="key", validatecommand=(accept, "%P"))
        return spin

    def refresh(self) -> None:
        """Re-bound the pickers to the current world width, then re-render.

        Existing values are NOT clamped down: the width shrinks transiently
        while the user retypes the state field, and destroying their event
        choice on that flicker is worse than letting the compute-time
        diagnostic catch a genuinely stale index.
        """
        width = max(self.width_source(), 1)
        last = width - 1
        self.index_spin.configure(to=last)
        self.partner_spin.configure(to=last)
        for widget in (
            self.index_spin,
            self.eq_label,
            self.value_box,
            self.partner_spin,
            self.state_entry,
        ):
            widget.pack_forget()
        kind = self.kind.get()
        if "state" in kind:
            if not self.state_bits.get():
                self.state_bits.set("0" * width)
            self.state_entry.pack(side="left", padx=(8, 0), fill="x", expand=True)
        elif "qubit M" in kind:
            self.index_spin.pack(side="left", padx=(8, 0))
            self.eq_label.pack(side="left", padx=4)
            self.partner_spin.pack(side="left")
        else:
            self.index_spin.pack(side="left", padx=(8, 0))
            self.eq_label.pack(side="left", padx=4)
            self.value_box.pack(side="left")
        self._sync()

    def _sync(self) -> None:
        width = max(self.width_source(), 1)
        unit = "qubit" if self.quantum else "cell"
        prefix = "q" if self.quantum else "cell"
        kind = self.kind.get()
        if "state" in kind:
            bits = self.state_bits.get()
            self.variable.set(f"state={bits}")
            missing = width - len(bits)
            self.hint.configure(
                text=f"exactly {width} digits of 0/1"
                + (f" — {missing} more needed" if missing > 0 else "")
            )
        elif "qubit M" in kind:
            self.variable.set(
                f"q{safe_int(self.index.get(), 0)}=q{safe_int(self.partner.get(), 0)}"
            )
            self.hint.configure(text=f"qubits 0..{width - 1}")
        else:
            self.variable.set(
                f"{prefix}{safe_int(self.index.get(), 0)}={self.value.get()}"
            )
            self.hint.configure(text=f"{unit} 0..{width - 1}")


class GateBuilder:
    """Two-row gate-program editor: only real gates on existing qubits.

    The program itself is shown in a read-only entry; gates are appended with
    a kind picker and qubit spinners whose ceiling follows the register size.
    The composed string lands in the tab's existing StringVar.
    """

    KINDS = ("H", "X", "CNOT")

    def __init__(
        self,
        parent: ttk.Frame,
        row: int,
        variable: tk.StringVar,
        width_source: Callable[[], int],
    ) -> None:
        self.variable = variable
        self.width_source = width_source
        ttk.Label(parent, text="Gates").grid(row=row, column=0, sticky="w", pady=4)
        program = ttk.Entry(parent, textvariable=variable, state="readonly")
        program.grid(row=row, column=1, sticky="ew", padx=(14, 10), pady=4)
        ttk.Label(
            parent, text="the program — edit with the row below",
            style="Hint.TLabel",
        ).grid(row=row, column=2, sticky="w", pady=4)

        ttk.Label(parent, text="Add gate").grid(
            row=row + 1, column=0, sticky="w", pady=4
        )
        self.holder = ttk.Frame(parent)
        self.holder.grid(row=row + 1, column=1, sticky="ew", padx=(14, 10), pady=4)
        self.kind = tk.StringVar(value="H")
        ttk.Combobox(
            self.holder,
            textvariable=self.kind,
            values=self.KINDS,
            state="readonly",
            width=6,
        ).pack(side="left")
        self.index = tk.StringVar(value="0")
        self.partner = tk.StringVar(value="1")
        self.index_spin = self._spin(self.index)
        self.index_spin.pack(side="left", padx=(8, 0))
        self.partner_spin = self._spin(self.partner)
        self.add_button = ttk.Button(
            self.holder, text="Add", style="Accent.TButton", width=6,
            command=self.add,
        )
        self.add_button.pack(side="left", padx=(8, 0))
        for text, command in (("Undo", self.undo), ("Clear", self.clear)):
            ttk.Button(
                self.holder, text=text, style="Accent.TButton", width=6,
                command=command,
            ).pack(side="left", padx=(8, 0))
        self.hint = ttk.Label(parent, text="", style="Hint.TLabel")
        self.hint.grid(row=row + 1, column=2, sticky="w", pady=4)
        self.kind.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def _spin(self, variable: tk.StringVar) -> ttk.Spinbox:
        spin = ttk.Spinbox(
            self.holder, textvariable=variable, from_=0, to=999, width=4
        )
        accept = spin.register(lambda text, w=spin: spin_text_ok(text, w))
        spin.configure(validate="key", validatecommand=(accept, "%P"))
        return spin

    def refresh(self) -> None:
        """Follow the register size and the picked gate kind."""
        last = max(self.width_source(), 1) - 1
        self.index_spin.configure(to=last)
        self.partner_spin.configure(to=last)
        if self.kind.get() == "CNOT":
            self.partner_spin.pack(
                side="left", padx=(4, 0), before=self.add_button
            )
        else:
            self.partner_spin.pack_forget()
        self.hint.configure(text=f"qubits 0..{last}")

    def add(self) -> None:
        """Append one gate; a CNOT on a single qubit is refused in place."""
        kind = self.kind.get()
        first = safe_int(self.index.get(), 0)
        if kind == "CNOT":
            second = safe_int(self.partner.get(), 0)
            if first == second:
                self.hint.configure(text="control and target must differ")
                return
            command = f"CNOT {first} {second}"
        else:
            command = f"{kind} {first}"
        current = self.variable.get().strip()
        self.variable.set(f"{current}; {command}" if current else command)
        self.refresh()

    def undo(self) -> None:
        commands = [
            token.strip()
            for token in self.variable.get().split(";")
            if token.strip()
        ]
        self.variable.set("; ".join(commands[:-1]))

    def clear(self) -> None:
        self.variable.set("")


def classical_report(state: str, rule: int, steps: int, event: str) -> str:
    """Build a deterministic report for one classical event."""
    final_state = predict(state, rule, steps)
    probability = 1.0 if classical_event_occurs(final_state, event) else 0.0
    status = classify_probability(probability)
    return f"Predicted state: {final_state}\n{status}"


def build_quantum_input(
    bits: str,
    gates: str,
    target: int,
    dephasing: float,
    damping: float,
    event: str,
) -> str:
    """Encode GUI fields for the interactive Go process."""
    encoded_gates = gates if gates.strip() else ";"
    return f"{bits}\n{encoded_gates}\n{target}\n{dephasing}\n{damping}\n{event}\n"


def run_native_quantum(
    bits: str,
    gates: str,
    target: int,
    dephasing: float,
    damping: float,
    event: str,
) -> str:
    """Run the compiled Go kernel without opening a console window."""
    if not QUANTUM_EXE.is_file():
        raise ValueError(f"Quantum kernel not found: {QUANTUM_EXE}")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [str(QUANTUM_EXE)],
            input=build_quantum_input(
                bits, gates, target, dephasing, damping, event
            ),
            capture_output=True,
            check=False,
            encoding="utf-8",
            timeout=QUANTUM_TIMEOUT_SECONDS,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"Failed to run the quantum kernel: {error}") from error
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(details or "The quantum kernel exited with an error")

    marker_index = completed.stdout.find(QUANTUM_MARKER)
    if marker_index >= 0:
        return completed.stdout[marker_index:].strip()
    return completed.stdout


class DemonGUI:
    """Seven-tab desktop interface."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Laplace Demon")
        self.root.geometry("920x760")
        self.root.minsize(780, 560)
        self._icon = self._build_icon()
        self.root.iconphoto(True, self._icon)
        self._animator = Animator(root)
        self._configure_style()
        self._build_header()

        notebook = ttk.Notebook(root, padding=(14, 6, 14, 14))
        notebook.pack(fill="both", expand=True)
        self._build_classical_tab(notebook)
        self._build_events_tab(notebook)
        self._build_mechanics_tab(notebook)
        self._build_quantum_tab(notebook)
        self._build_information_tab(notebook)
        self._build_agent_tab(notebook)
        self._build_walls_tab(notebook)
        self._build_game_tab(notebook)

    @staticmethod
    def _build_icon() -> tk.PhotoImage:
        """Draw the window icon in code: a gold coin with a dark lambda."""
        size = 32
        icon = tk.PhotoImage(width=size, height=size)
        center = (size - 1) / 2
        radius = center - 1.0
        for y in range(size):
            for x in range(size):
                distance = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
                if distance > radius:
                    continue
                rim = distance > radius - 2.0
                icon.put("#8A6E17" if rim else PALETTE["accent"], (x, y))
        apex_y, base_y, half_spread = 7, 25, 7.0
        for y in range(apex_y, base_y + 1):
            offset = (y - apex_y) * half_spread / (base_y - apex_y)
            for leg_x in (center - offset, center + offset):
                for x in (int(leg_x), int(leg_x) + 1):
                    icon.put(PALETTE["accent_fg"], (x, y))
        return icon

    def _configure_style(self) -> None:
        p = PALETTE
        self.root.configure(bg=p["bg"])
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            ".", background=p["panel"], foreground=p["fg"], font=FONT_BODY
        )
        style.configure("TNotebook", background=p["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=p["bg"],
            foreground=p["muted"],
            padding=(16, 9),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", p["panel"])],
            foreground=[("selected", p["accent"])],
        )
        style.configure("TFrame", background=p["panel"])
        style.configure("TLabel", background=p["panel"], foreground=p["fg"])
        style.configure("Title.TLabel", font=FONT_TITLE, foreground=p["fg"])
        style.configure(
            "Desc.TLabel", foreground=p["muted"], font=FONT_BODY, wraplength=720
        )
        style.configure("Hint.TLabel", foreground=p["muted"])
        style.configure(
            "TEntry",
            fieldbackground=p["field"],
            foreground=p["fg"],
            insertcolor=p["fg"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            padding=6,
        )
        style.configure(
            "TSpinbox",
            fieldbackground=p["field"],
            background=p["field"],
            foreground=p["fg"],
            insertcolor=p["fg"],
            arrowcolor=p["accent"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            padding=6,
        )
        style.configure(
            "TCombobox",
            fieldbackground=p["field"],
            background=p["field"],
            foreground=p["fg"],
            arrowcolor=p["accent"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", p["field"])],
            foreground=[("readonly", p["fg"])],
        )
        self.root.option_add("*TCombobox*Listbox.background", p["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", p["fg"])
        self.root.option_add(
            "*TCombobox*Listbox.selectBackground", p["accent"]
        )
        self.root.option_add(
            "*TCombobox*Listbox.selectForeground", p["accent_fg"]
        )
        style.configure(
            "Accent.TButton",
            background=p["accent"],
            foreground=p["accent_fg"],
            font=("Segoe UI Semibold", 10),
            padding=10,
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", p["accent_active"]), ("pressed", p["accent"])],
        )

    def _build_header(self) -> None:
        p = PALETTE
        header = tk.Frame(self.root, bg=p["bg"], padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(
            header,
            text="LAPLACE  DEMON",
            bg=p["bg"],
            fg=p["accent"],
            font=FONT_HEADER,
        ).pack(anchor="w")
        tk.Label(
            header,
            text=(
                "An honest predictor for finite universes — exact where knowledge"
                " is complete, candid where it is not."
            ),
            bg=p["bg"],
            fg=p["muted"],
            font=FONT_BODY,
        ).pack(anchor="w")

    def _make_tab(
        self, notebook: ttk.Notebook, tab_text: str, title: str, description: str
    ) -> ttk.Frame:
        tab = ttk.Frame(notebook, padding=20)
        tab.columnconfigure(1, weight=1)
        notebook.add(tab, text=tab_text)
        ttk.Label(tab, text=title, style="Title.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(tab, text=description, style="Desc.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 14)
        )
        return tab

    @staticmethod
    def _add_entry(
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        hint: str,
        keyfilter: Callable[[str], bool] | None = None,
    ) -> ttk.Label:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=(14, 10), pady=4)
        if keyfilter is not None:
            accept = entry.register(keyfilter)
            entry.configure(validate="key", validatecommand=(accept, "%P"))
        hint_label = ttk.Label(parent, text=hint, style="Hint.TLabel")
        hint_label.grid(row=row, column=2, sticky="w", pady=4)
        return hint_label

    @staticmethod
    def _add_spin(
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        low: float,
        high: float,
        hint: str,
        increment: float = 1,
    ) -> ttk.Spinbox:
        """A bounded numeric field: arrows offer only the valid range."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        spin = ttk.Spinbox(
            parent,
            textvariable=variable,
            from_=low,
            to=high,
            increment=increment,
        )
        accept = spin.register(lambda text, widget=spin: spin_text_ok(text, widget))
        spin.configure(validate="key", validatecommand=(accept, "%P"))
        spin.grid(row=row, column=1, sticky="ew", padx=(14, 10), pady=4)
        ttk.Label(parent, text=hint, style="Hint.TLabel").grid(
            row=row, column=2, sticky="w", pady=4
        )
        return spin

    @staticmethod
    def _bind_hint(
        source: tk.StringVar,
        hint: ttk.Label,
        formatter: Callable[[], str],
    ) -> None:
        """Keep a dependent hint current whenever the source field changes."""

        def refresh(*_args: object) -> None:
            hint.configure(text=formatter())

        source.trace_add("write", refresh)
        refresh()

    @staticmethod
    def _button_row(
        parent: ttk.Frame, row: int, buttons: tuple[tuple[str, object], ...]
    ) -> None:
        """Lay out equal-width accent buttons on one row."""
        strip = ttk.Frame(parent)
        strip.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        for column, (text, command) in enumerate(buttons):
            strip.columnconfigure(column, weight=1, uniform="buttons")
            ttk.Button(
                strip, text=text, style="Accent.TButton", command=command
            ).grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))

    @staticmethod
    def _add_canvas(tab: ttk.Frame, row: int, height: int = 260) -> tk.Canvas:
        """Add an expanding drawing surface for animations and diagrams."""
        tab.rowconfigure(row, weight=1)
        canvas = tk.Canvas(
            tab,
            height=height,
            bg=PALETTE["result_bg"],
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        canvas.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        return canvas

    @staticmethod
    def _add_result(
        tab: ttk.Frame, row: int, height: int = 12, expand: bool = True
    ) -> tk.Text:
        p = PALETTE
        if expand:
            tab.rowconfigure(row, weight=1)
        widget = tk.Text(
            tab,
            height=height,
            wrap="word",
            font=FONT_MONO,
            bg=p["result_bg"],
            fg=p["result_fg"],
            insertbackground=p["fg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=p["border"],
            highlightcolor=p["accent"],
            padx=12,
            pady=10,
        )
        widget.grid(row=row, column=0, columnspan=3, sticky="nsew")
        widget.configure(state="disabled")
        return widget

    @staticmethod
    def _set_result(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _show_error(self, error: Exception) -> None:
        message = str(error)
        if isinstance(error, KeyError):
            message = f"unknown option {message} — pick a value from the list"
        elif "invalid literal for int" in message:
            value = message.rsplit(":", 1)[-1].strip()
            message = (
                f"{value} is not a whole number — this field needs digits only"
                " (e.g. 30)"
            )
        elif "could not convert string to float" in message:
            value = message.rsplit(":", 1)[-1].strip()
            message = (
                f"{value} is not a number — this field needs a number like 5.0"
                " or 1e-6"
            )
        log_error(message)
        messagebox.showerror("Invalid parameters", message, parent=self.root)

    def _build_classical_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "Classical",
            "Exact event in a cellular universe",
            "The law and the initial state are fully known, so the demon computes"
            " the future exactly: every event comes out at P(A)=0% or P(A)=100%."
            " No coin toss survives complete knowledge.",
        )
        self.classical_state = tk.StringVar(value="0001000")
        self.classical_rule = tk.StringVar(value="30")
        self.classical_steps = tk.StringVar(value="1")
        self.classical_event = tk.StringVar(value="cell3=1")
        self._add_entry(
            tab, 2, "Initial state", self.classical_state, "0 and 1 only",
            keyfilter=bits_text_ok,
        )
        self._add_spin(tab, 3, "Rule", self.classical_rule, 0, 255, "0..255")
        self._add_spin(
            tab, 4, "Horizon", self.classical_steps, 0, 999, "number of steps"
        )
        self.classical_event_field = EventField(
            tab, 5, "Event A", self.classical_event,
            lambda: len(self.classical_state.get().strip()),
        )
        self.classical_state.trace_add(
            "write", lambda *_: self.classical_event_field.refresh()
        )
        self._button_row(
            tab,
            6,
            (
                ("Compute event A", self._calculate_classical),
                ("Animate spacetime", self._animate_classical),
            ),
        )
        self._button_row(
            tab,
            7,
            (
                ("Retrodict the past", self._retrodict),
                ("Linear shortcut (reducibility)", self._shortcut),
            ),
        )
        self.classical_canvas = self._add_canvas(tab, 8)
        self.classical_result = self._add_result(tab, 9, height=4, expand=False)

    def _retrodict(self) -> None:
        try:
            report = retrodiction_report(
                self.classical_state.get().strip(),
                int(self.classical_rule.get()),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.classical_result, report)

    def _shortcut(self) -> None:
        try:
            report = shortcut_report(
                self.classical_state.get().strip(),
                int(self.classical_rule.get()),
                int(self.classical_steps.get()),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.classical_result, report)

    def _classical_cell(self) -> int | None:
        event = self.classical_event.get().strip().lower()
        if event.startswith("cell") and "=" in event:
            return int(event[4 : event.index("=")])
        return None

    def _animate_classical(self) -> None:
        try:
            steps = int(self.classical_steps.get())
            report = classical_report(
                self.classical_state.get().strip(),
                int(self.classical_rule.get()),
                steps,
                self.classical_event.get().strip(),
            )
            frames = animate_spacetime(
                self.classical_canvas,
                self.classical_state.get().strip(),
                int(self.classical_rule.get()),
                steps,
                self._classical_cell(),
            )
        except ValueError as error:
            self._show_error(error)
            return
        # ~4 s for the whole run regardless of step count, one row per frame.
        delay = max(40, min(300, 4000 // max(steps + 1, 1)))
        self._animator.play(frames, delay=delay)
        self._set_result(self.classical_result, report)

    def _calculate_classical(self) -> None:
        try:
            report = classical_report(
                self.classical_state.get().strip(),
                int(self.classical_rule.get()),
                int(self.classical_steps.get()),
                self.classical_event.get().strip(),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.classical_result, report)

    def _build_events_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "From Events",
            "The law is not given — it is inferred from observations",
            "Feed the demon a history of observed states. It reconstructs every"
            " law consistent with the events and answers honestly: DETERMINED"
            " when all consistent laws agree, a fair probability when they"
            " still disagree.",
        )
        self.events_history = tk.StringVar(value="0001000; 0011100")
        self.events_steps = tk.StringVar(value="1")
        self.events_event = tk.StringVar(value="cell3=1")
        self._add_entry(
            tab, 2, "Event history", self.events_history, "states joined by ';'",
            keyfilter=lambda text: bits_text_ok(text, extra="; "),
        )
        self._add_spin(
            tab, 3, "Horizon", self.events_steps, 0, 999, "number of steps"
        )
        def history_width() -> int:
            first = self.events_history.get().replace("\n", ";").split(";")[0]
            return len(first.strip())

        self.events_event_field = EventField(
            tab, 4, "Event A", self.events_event, history_width
        )
        self.events_history.trace_add(
            "write", lambda *_: self.events_event_field.refresh()
        )
        ttk.Button(
            tab,
            text="Infer the law and predict",
            style="Accent.TButton",
            command=self._calculate_events,
        ).grid(row=5, column=0, columnspan=3, sticky="ew", pady=14)
        self.events_result = self._add_result(tab, 6)

    def _calculate_events(self) -> None:
        try:
            report = event_report(
                self.events_history.get(),
                int(self.events_steps.get()),
                self.events_event.get().strip(),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.events_result, report)

    def _build_mechanics_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "Continuous",
            "RK4 flow, measured Lyapunov exponent, prediction horizon",
            "Continuous mechanics without probability: the event is integrated"
            " numerically, the Lyapunov exponent is measured (never assumed), and"
            " the verdict is trusted only inside T_pred ="
            " (1/lambda)·ln(tolerance/error).",
        )
        self.mechanics_system = tk.StringVar(value=next(iter(MECHANICS_SYSTEMS)))
        ttk.Label(tab, text="System").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(
            tab,
            textvariable=self.mechanics_system,
            values=tuple(MECHANICS_SYSTEMS),
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", padx=(14, 10), pady=6)
        ttk.Label(
            tab, text="chaos decides the horizon", style="Hint.TLabel"
        ).grid(row=2, column=2, sticky="w", pady=6)
        self.mechanics_horizon = tk.StringVar(value="5.0")
        self.mechanics_error = tk.StringVar(value="1e-6")
        self.mechanics_tolerance = tk.StringVar(value="1.0")
        self._add_spin(
            tab, 3, "Horizon, s", self.mechanics_horizon, 0.5, 60, "0..60",
            increment=0.5,
        )
        ttk.Label(tab, text="Initial error").grid(
            row=4, column=0, sticky="w", pady=4
        )
        self.mechanics_error_box = ttk.Combobox(
            tab,
            textvariable=self.mechanics_error,
            values=INITIAL_ERROR_PRESETS,
            state="readonly",
        )
        self.mechanics_error_box.grid(
            row=4, column=1, sticky="ew", padx=(14, 10), pady=4
        )
        ttk.Label(
            tab,
            text="fixed precision preset; cannot be empty",
            style="Hint.TLabel",
        ).grid(row=4, column=2, sticky="w", pady=4)
        self._add_entry(
            tab, 5, "Error tolerance", self.mechanics_tolerance,
            "must exceed the initial error",
            keyfilter=float_text_ok,
        )
        self._button_row(
            tab,
            6,
            (
                ("Compute event and horizon", self._calculate_mechanics),
                ("Animate the system", self._animate_mechanics),
            ),
        )
        self.mechanics_canvas = self._add_canvas(tab, 7)
        self.mechanics_result = self._add_result(tab, 8, height=6, expand=False)

    def _animate_mechanics(self) -> None:
        try:
            system = MECHANICS_SYSTEMS[self.mechanics_system.get()]
            horizon = float(self.mechanics_horizon.get())
            initial_error = float(self.mechanics_error.get())
            tolerance = float(self.mechanics_tolerance.get())
            report = mechanics_report(system, horizon, initial_error, tolerance)
            if system == "ball":
                frames = animate_ball(self.mechanics_canvas, horizon)
            else:
                frames = animate_pendulum(
                    self.mechanics_canvas,
                    horizon,
                    initial_error,
                    tolerance,
                )
        except (KeyError, ValueError) as error:
            self._show_error(error)
            return
        self._animator.play(frames)
        self._set_result(self.mechanics_result, report)

    def _calculate_mechanics(self) -> None:
        try:
            report = mechanics_report(
                MECHANICS_SYSTEMS[self.mechanics_system.get()],
                float(self.mechanics_horizon.get()),
                float(self.mechanics_error.get()),
                float(self.mechanics_tolerance.get()),
            )
        except (KeyError, ValueError) as error:
            self._show_error(error)
            return
        self._set_result(self.mechanics_result, report)

    def _build_quantum_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "Quantum (Go)",
            "Density matrix and environment",
            "A native Go kernel evolves up to 10 qubits with dephasing and"
            " amplitude damping. In this operational model, a P(A) strictly"
            " between 0% and 100% does not determine one measurement outcome,"
            " and the program never pretends otherwise.",
        )
        self.quantum_bits = tk.StringVar(value="00")
        self.quantum_gates = tk.StringVar(value="H 0; CNOT 0 1")
        self.quantum_target = tk.StringVar(value="0")
        self.quantum_dephasing = tk.StringVar(value="0")
        self.quantum_damping = tk.StringVar(value="0")
        self.quantum_event = tk.StringVar(value="q0=q1")
        self._add_entry(
            tab, 2, "Initial basis state", self.quantum_bits, "up to 10 qubits",
            keyfilter=lambda text: bits_text_ok(text, limit=10),
        )
        def qubit_count() -> int:
            return len(self.quantum_bits.get().strip())

        self.gate_builder = GateBuilder(tab, 3, self.quantum_gates, qubit_count)
        qubit_spin = self._add_spin(
            tab, 5, "Environment qubit", self.quantum_target, 0, 9, "index from 0"
        )
        self._add_spin(
            tab, 6, "Dephasing", self.quantum_dephasing, 0, 1, "0..1",
            increment=0.05,
        )
        self._add_spin(
            tab, 7, "Amplitude damping", self.quantum_damping, 0, 1, "0..1",
            increment=0.05,
        )
        self.quantum_event_field = EventField(
            tab, 8, "Event A", self.quantum_event, qubit_count, quantum=True
        )

        def refresh_qubits(*_args: object) -> None:
            qubit_spin.configure(to=max(qubit_count() - 1, 0))
            self.quantum_event_field.refresh()
            self.gate_builder.refresh()

        self.quantum_bits.trace_add("write", refresh_qubits)
        refresh_qubits()
        self._button_row(
            tab,
            9,
            (
                ("Compute event A (Go kernel)", self._calculate_quantum),
                ("Wavefunction limit (before environment)", self._show_quantum_wall),
                ("CHSH before environment", self._show_chsh),
            ),
        )
        self._button_row(
            tab,
            10,
            (
                ("Read a qubit — measurement disturbs", self._read_qubit),
                ("Rewind — the unitary world remembers", self._rewind),
            ),
        )
        self.quantum_result = self._add_result(tab, 11)

    def _rewind(self) -> None:
        try:
            report = rewind_report(
                self.quantum_bits.get().strip(),
                self.quantum_gates.get().strip(),
                int(self.quantum_target.get()),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.quantum_result, report)

    def _read_qubit(self) -> None:
        try:
            report = read_qubit_report(
                self.quantum_bits.get().strip(),
                self.quantum_gates.get().strip(),
                int(self.quantum_target.get()),
                self.quantum_event.get().strip(),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.quantum_result, report)

    def _show_chsh(self) -> None:
        try:
            pair_selected = "qubit M" in self.quantum_event_field.kind.get()
            first = safe_int(self.quantum_event_field.index.get(), 0)
            second = safe_int(self.quantum_event_field.partner.get(), 1)
            report = chsh_report(
                self.quantum_bits.get().strip(),
                self.quantum_gates.get().strip(),
                first if pair_selected else 0,
                second if pair_selected else 1,
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.quantum_result, report)

    def _show_quantum_wall(self) -> None:
        try:
            report = quantum_wall_report(
                self.quantum_bits.get().strip(),
                self.quantum_gates.get().strip(),
                self.quantum_event.get().strip(),
                int(self.quantum_target.get()),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.quantum_result, report)

    def _calculate_quantum(self) -> None:
        # ponytail: synchronous for local <=10-qubit runs; use a worker if UI stalls.
        try:
            report = run_native_quantum(
                self.quantum_bits.get().strip(),
                self.quantum_gates.get().strip(),
                int(self.quantum_target.get()),
                float(self.quantum_dephasing.get()),
                float(self.quantum_damping.get()),
                self.quantum_event.get().strip(),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.quantum_result, report)

    def _build_information_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "Formula L",
            "H(E), H(E|K), I(E;K) and the Laplace coefficient L",
            "How much of the event's uncertainty does knowledge K remove?"
            " L = I(E;K)/H(E), computed exactly over every possible initial"
            " world: L = 1 makes the observer a local demon for this event,"
            " L = 0 makes the knowledge useless.",
        )
        self.info_width = tk.StringVar(value="7")
        self.info_known = tk.StringVar(value="2,3,4")
        self.info_rule = tk.StringVar(value="30")
        self.info_steps = tk.StringVar(value="1")
        self.info_event = tk.StringVar(value="cell3=1")
        self._add_spin(tab, 2, "World width", self.info_width, 1, 14, "1..14")
        known_hint = self._add_entry(
            tab, 3, "Known cells K", self.info_known, "",
            keyfilter=known_cells_text_ok,
        )
        self._add_spin(tab, 4, "Rule", self.info_rule, 0, 255, "0..255")
        self._add_spin(
            tab, 5, "Horizon", self.info_steps, 0, 999, "number of steps"
        )
        self.info_event_field = EventField(
            tab, 6, "Event E", self.info_event,
            lambda: safe_int(self.info_width.get(), 14),
        )
        self._bind_hint(
            self.info_width,
            known_hint,
            lambda: (
                f"0..{safe_int(self.info_width.get(), 14) - 1} comma-separated;"
                " all; none"
            ),
        )
        self.info_width.trace_add(
            "write", lambda *_: self.info_event_field.refresh()
        )
        self._button_row(
            tab,
            7,
            (
                ("Compute the formula", self._calculate_information),
                ("Embedded demon (light cone)", self._show_cone),
                ("Macro entropy (second law)", self._show_macro),
            ),
        )
        self.info_result = self._add_result(tab, 8)

    def _show_cone(self) -> None:
        try:
            report = light_cone_report(
                int(self.info_width.get()),
                int(self.info_rule.get()),
                int(self.info_steps.get()),
                self.info_event.get().strip(),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.info_result, report)

    def _show_macro(self) -> None:
        try:
            report = macro_report(
                int(self.info_width.get()),
                int(self.info_rule.get()),
                int(self.info_steps.get()),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.info_result, report)

    def _calculate_information(self) -> None:
        # ponytail: exact enumeration is capped before it can block the UI badly.
        try:
            report = calculate_report(
                int(self.info_width.get()),
                self.info_known.get(),
                int(self.info_rule.get()),
                int(self.info_steps.get()),
                self.info_event.get(),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.info_result, report)

    def _build_agent_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "Active Inference",
            "An agent that buys knowledge until it becomes a demon",
            "Friston's free energy with no preferences is pure curiosity: observe"
            " the cell that removes the most uncertainty. Watch L_O climb with"
            " every epistemic action — and watch greedy curiosity stall on"
            " XOR-like laws (try rule 60), where a cell pays off only in pairs.",
        )
        self.agent_width = tk.StringVar(value="7")
        self.agent_rule = tk.StringVar(value="30")
        self.agent_steps = tk.StringVar(value="1")
        self.agent_event = tk.StringVar(value="cell3=1")
        self.agent_budget = tk.StringVar(value="")
        self._add_spin(tab, 2, "World width", self.agent_width, 1, 10, "1..10")
        self._add_spin(tab, 3, "Rule", self.agent_rule, 0, 255, "0..255; try 60")
        self._add_spin(
            tab, 4, "Horizon", self.agent_steps, 0, 999, "number of steps"
        )
        self.agent_event_field = EventField(
            tab, 5, "Event E", self.agent_event,
            lambda: safe_int(self.agent_width.get(), 10),
        )
        budget_spin = self._add_spin(
            tab, 6, "Action budget", self.agent_budget, 0, 10,
            "empty = unlimited",
        )

        def refresh_agent(*_args: object) -> None:
            budget_spin.configure(to=safe_int(self.agent_width.get(), 10))
            self.agent_event_field.refresh()

        self.agent_width.trace_add("write", refresh_agent)
        refresh_agent()
        self._button_row(
            tab,
            7,
            (
                ("Report", self._calculate_agent),
                ("Animate foraging", self._animate_agent),
            ),
        )
        self.agent_canvas = self._add_canvas(tab, 8)
        self.agent_result = self._add_result(tab, 9, height=6, expand=False)

    def _agent_parameters(self) -> tuple[int, int, int, str, int | None]:
        budget_text = self.agent_budget.get().strip()
        return (
            int(self.agent_width.get()),
            int(self.agent_rule.get()),
            int(self.agent_steps.get()),
            self.agent_event.get().strip(),
            int(budget_text) if budget_text else None,
        )

    def _animate_agent(self) -> None:
        try:
            frames = animate_foraging(self.agent_canvas, *self._agent_parameters())
        except ValueError as error:
            self._show_error(error)
            return
        self._animator.play(frames, delay=700)
        self._calculate_agent()

    def _calculate_agent(self) -> None:
        try:
            report = active_inference_report(*self._agent_parameters())
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.agent_result, report)

    def _build_walls_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "The Walls",
            "Where knowledge stops paying: capacity and self-reference",
            "Bekenstein: the smallest knowledge that determines the event sets"
            " the bits a demon's carrier must physically hold. Godel/Wolpert"
            " (arXiv:0708.1362): a demon inside a world that reads its"
            " prediction is wrong under every strategy — and no two devices can"
            " strongly infer each other. The quantum wall lives on the Quantum tab.",
        )
        self.walls_width = tk.StringVar(value="7")
        self.walls_rule = tk.StringVar(value="30")
        self.walls_steps = tk.StringVar(value="1")
        self.walls_event = tk.StringVar(value="cell3=1")
        self.walls_radius = tk.StringVar(value="0.1")
        self.walls_energy = tk.StringVar(value="1.0")
        self._add_spin(tab, 2, "World width", self.walls_width, 1, 10, "1..10")
        self._add_spin(tab, 3, "Rule", self.walls_rule, 0, 255, "0..255")
        self._add_spin(
            tab, 4, "Horizon", self.walls_steps, 0, 999, "number of steps"
        )
        self.walls_event_field = EventField(
            tab, 5, "Event E", self.walls_event,
            lambda: safe_int(self.walls_width.get(), 10),
        )
        self._add_entry(
            tab, 6, "Carrier radius, m", self.walls_radius, "R > 0",
            keyfilter=float_text_ok,
        )
        self._add_entry(
            tab, 7, "Carrier energy, J", self.walls_energy, "E > 0",
            keyfilter=float_text_ok,
        )
        self.walls_temperature = tk.StringVar(value="300")
        self._add_entry(
            tab, 8, "Temperature, K", self.walls_temperature, "for Landauer",
            keyfilter=float_text_ok,
        )
        self.walls_width.trace_add(
            "write", lambda *_: self.walls_event_field.refresh()
        )
        self._button_row(
            tab,
            9,
            (
                ("H_irr(m): minimum over all knowledge", self._calculate_irreducible),
                ("Bekenstein bound on the carrier", self._show_bekenstein),
                ("Landauer cost of knowledge", self._show_landauer),
            ),
        )
        self._button_row(
            tab,
            10,
            (
                ("Diagonal X*: demon inside the world", self._show_diagonal),
                ("Two devices inferring each other", self._show_mutual),
            ),
        )
        self.walls_result = self._add_result(tab, 11)

    def _walls_parameters(self) -> tuple[int, int, int, str]:
        return (
            int(self.walls_width.get()),
            int(self.walls_rule.get()),
            int(self.walls_steps.get()),
            self.walls_event.get().strip(),
        )

    def _calculate_irreducible(self) -> None:
        # ponytail: 4^width sweep, capped at width 10 to keep the UI responsive.
        try:
            report = irreducible_report(*self._walls_parameters())
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.walls_result, report)

    def _show_bekenstein(self) -> None:
        try:
            levels = irreducible_profile(*self._walls_parameters())
            minimal = next(
                (level for level in levels if level.entropy <= 1e-12), levels[-1]
            )
            report = bekenstein_report(
                float(self.walls_radius.get()),
                float(self.walls_energy.get()),
                minimal.cells,
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.walls_result, report)

    GAME_WIDTH = 31
    GAME_RULE = 30
    GAME_HISTORY_SHOWN = 32

    def _build_game_tab(self, notebook: ttk.Notebook) -> None:
        tab = self._make_tab(
            notebook,
            "The Game",
            "Outrun the demon: call rule 30's next bit",
            "The center column of rule 30 is fully determined — the demon"
            " computes it, never guesses. To a bounded observer it plays like"
            " a fair coin. Your score measures where the randomness really"
            " lives: not in the world, but in what you don't know about it.",
        )
        self.game_canvas = self._add_canvas(tab, 2, height=170)
        self.game_score_label = ttk.Label(tab, text="", font=FONT_BODY)
        self.game_score_label.grid(
            row=3, column=0, columnspan=3, sticky="w", pady=2
        )
        self.game_status_label = ttk.Label(tab, text="", style="Hint.TLabel")
        self.game_status_label.grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(2, 6)
        )
        self._button_row(
            tab,
            5,
            (
                ("Next bit: 0", lambda: self._game_guess("0")),
                ("Next bit: 1", lambda: self._game_guess("1")),
                ("New world", self._game_reset),
            ),
        )
        self._game_reset()

    def _game_advance(self) -> str:
        """Step the hidden world once; return the new center bit."""
        self.game_world = next_state(self.game_world, self.GAME_RULE)
        bit = self.game_world[len(self.game_world) // 2]
        self.game_history.append(bit)
        return bit

    def _game_refresh(self, status: str) -> None:
        total, right = self.game_total, self.game_right
        accuracy = f" ({right / total:.0%})" if total else ""
        self.game_score_label.configure(
            text=(
                f"You: {right}/{total}{accuracy}      Demon: {total}/{total}"
                " (computes, never guesses)      Coin: ~50%"
            )
        )
        self.game_status_label.configure(text=status)

    def _game_reset(self) -> None:
        # ponytail: wall-clock seed; the point is the OBSERVER's ignorance,
        # and the demon predicts any seed equally well.
        generator = random.Random()
        self.game_world = "".join(
            generator.choice("01") for _ in range(self.GAME_WIDTH)
        )
        self.game_history: list[str] = []
        self.game_right = 0
        self.game_total = 0
        for _ in range(self.GAME_HISTORY_SHOWN):
            self._game_advance()
        self._game_refresh(
            "A fresh hidden world is running rule 30. Call the next center bit."
        )
        self._animator.stop()
        draw_game_board(
            self.game_canvas,
            self.GAME_WIDTH,
            self.game_history,
            self.GAME_HISTORY_SHOWN,
            reveal=self.game_history[-1],
        )

    def _game_guess(self, guess: str) -> None:
        actual = self._game_advance()
        self.game_total += 1
        hit = guess == actual
        self.game_right += hit
        verdict = "Correct." if hit else f"Wrong — it was {actual}."
        if self.game_total >= 20:
            accuracy = self.game_right / self.game_total
            if abs(accuracy - 0.5) < 0.12:
                verdict += (
                    "  Hovering at the coin line: the column defeats you"
                    " exactly as it defeats every bounded predictor — yet"
                    " every bit of it was determined before you guessed."
                )
        self._game_refresh(verdict)
        self._animator.play(
            animate_game_step(
                self.game_canvas,
                self.GAME_WIDTH,
                list(self.game_history),
                self.GAME_HISTORY_SHOWN,
                hit,
            ),
            delay=22,
        )

    def _show_landauer(self) -> None:
        try:
            levels = irreducible_profile(*self._walls_parameters())
            minimal = next(
                (level for level in levels if level.entropy <= 1e-12), levels[-1]
            )
            report = landauer_report(
                minimal.cells, float(self.walls_temperature.get())
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._set_result(self.walls_result, report)

    def _show_diagonal(self) -> None:
        self._set_result(self.walls_result, diagonal_report())

    def _show_mutual(self) -> None:
        self._set_result(self.walls_result, mutual_inference_report())


def main() -> int:
    """Open the desktop application."""
    root = tk.Tk()
    DemonGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
