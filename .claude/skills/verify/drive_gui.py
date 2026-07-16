"""Full-app drive of the Laplace Demon Laboratory GUI: every tab, button,
animation, keystroke filter and error dialog, through the real widgets."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "demon_laplas"))

import tkinter as tk  # noqa: E402

import gui as gui_module  # noqa: E402
from gui import DemonGUI  # noqa: E402

RESULTS = []
DIALOGS = []


def check(name, condition, detail=""):
    RESULTS.append((bool(condition), name, detail))
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")


# Dialogs block automation; record them instead (the only patched seam).
gui_module.messagebox.showerror = lambda title, message, **kw: DIALOGS.append(
    (title, message)
)

root = tk.Tk()
app = DemonGUI(root)
root.update()

WIDGETS = []


def walk(w):
    for child in w.winfo_children():
        WIDGETS.append(child)
        walk(child)


walk(root)


def by_var(variable):
    name = str(variable)
    for w in WIDGETS:
        if w.winfo_class() in ("TEntry", "TSpinbox") and str(
            w.cget("textvariable")
        ) == name:
            return w
    raise LookupError(name)


def button(text):
    for w in WIDGETS:
        if w.winfo_class() == "TButton" and text in str(w.cget("text")):
            return w
    raise LookupError(text)


def select_tab(label):
    for w in WIDGETS:
        if w.winfo_class() == "TNotebook":
            for tab_id in w.tabs():
                if w.tab(tab_id, "text") == label:
                    w.select(tab_id)
                    root.update()
                    return
    raise LookupError(label)


def type_text(widget, text):
    """Clear and retype through Tk key-validation (fires per insert)."""
    widget.focus_set()
    widget.delete(0, "end")
    for char in text:
        widget.insert("end", char)
    root.update()
    return widget.get()


def canvas_texts(canvas):
    return [
        canvas.itemcget(i, "text")
        for i in canvas.find_all()
        if canvas.type(i) == "text"
    ]


def pump_until_done(timeout=30.0):
    """Pump the event loop until the animator goes idle."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        root.update()
        if app._animator._job is None:
            return True
        time.sleep(0.03)
    return False


def has_text(canvas, marker):
    return any(marker in t for t in canvas_texts(canvas))


def pop_dialog(expect):
    if DIALOGS and expect in DIALOGS[-1][1]:
        DIALOGS.pop()
        return True
    return False


def result_text(widget):
    return widget.get("1.0", "end")


# ---------------- Classical ----------------
select_tab("Classical")
button("Compute event A").invoke()
root.update()
check(
    "classical: compute is exact",
    "DETERMINED" in result_text(app.classical_result),
    result_text(app.classical_result),
)
check(
    "classical: state filter blocks x/2",
    type_text(by_var(app.classical_state), "0x120011") == "010011",
    by_var(app.classical_state).get(),
)
type_text(by_var(app.classical_state), "0001000")
check(
    "classical: event picker composes cell3=1",
    app.classical_event.get() == "cell3=1",
    app.classical_event.get(),
)
check(
    "classical: picker index blocks 12 in a 7-cell world",
    type_text(app.classical_event_field.index_spin, "12") == "1",
    app.classical_event_field.index_spin.get(),
)
type_text(app.classical_event_field.index_spin, "3")
check(
    "classical: rule spinbox blocks 300",
    type_text(by_var(app.classical_rule), "300") == "30",
    by_var(app.classical_rule).get(),
)
type_text(by_var(app.classical_rule), "30")
app.classical_event_field.kind.set("exact state")
type_text(app.classical_event_field.state_entry, "001")
button("Compute event A").invoke()
root.update()
check(
    "classical: width-mismatch dialog fires",
    pop_dialog("3 cells but the world has 7"),
    str(DIALOGS[-3:]),
)
app.classical_event_field.kind.set("cell N = value")
type_text(by_var(app.classical_steps), "12")
button("Animate spacetime").invoke()
button("Animate spacetime").invoke()  # double-click probe: must not crash
done = pump_until_done()
check(
    "classical: spacetime animation completes after double-click",
    done and has_text(app.classical_canvas, "done: 12 step(s)"),
    str(canvas_texts(app.classical_canvas)),
)

button("Retrodict the past").invoke()
root.update()
check(
    "classical: retrodiction reports the pasts",
    "Pasts that evolve into" in result_text(app.classical_result),
    result_text(app.classical_result),
)
button("Linear shortcut").invoke()
root.update()
check(
    "classical: rule 30 refuses the shortcut honestly",
    "NOT linear" in result_text(app.classical_result),
    result_text(app.classical_result),
)
type_text(by_var(app.classical_rule), "90")
button("Linear shortcut").invoke()
root.update()
check(
    "classical: rule 90 fast-forwards (reducible)",
    "REDUCIBLE" in result_text(app.classical_result),
    result_text(app.classical_result),
)
type_text(by_var(app.classical_rule), "30")

# ---------------- From Events ----------------
select_tab("From Events")
button("Infer the law and predict").invoke()
root.update()
check(
    "events: law inference works",
    "Consistent rules: 16" in result_text(app.events_result),
    result_text(app.events_result),
)
check(
    "events: history filter blocks letters",
    type_text(by_var(app.events_history), "00a1;b11") == "001;11",
    by_var(app.events_history).get(),
)
type_text(by_var(app.events_history), "000; 000; 111")
button("Infer the law and predict").invoke()
root.update()
check(
    "events: contradiction dialog fires",
    pop_dialog("contradicts"),
    str(DIALOGS[-3:]),
)
type_text(by_var(app.events_history), "0001000; 0011100")

# ---------------- Continuous ----------------
select_tab("Continuous")
type_text(by_var(app.mechanics_horizon), "3.5")
button("Compute event and horizon").invoke()
root.update()
check(
    "mechanics: ball lands, determined",
    "LANDED" in result_text(app.mechanics_result)
    and "DETERMINED" in result_text(app.mechanics_result),
    result_text(app.mechanics_result),
)
button("Animate the system").invoke()
done = pump_until_done()
check(
    "mechanics: ball animation reaches impact",
    done and has_text(app.mechanics_canvas, "LANDED"),
    str(canvas_texts(app.mechanics_canvas)),
)
check(
    "mechanics: tolerance field blocks garbage, keeps float prefix",
    type_text(by_var(app.mechanics_tolerance), "1.0xyz44") == "1.044",
    by_var(app.mechanics_tolerance).get(),
)
check(
    "mechanics: horizon spinbox cuts decimal spam",
    type_text(by_var(app.mechanics_horizon), "5.0444444444") == "5.0444",
    by_var(app.mechanics_horizon).get(),
)
type_text(by_var(app.mechanics_horizon), "3.5")
check(
    "mechanics: initial error is a readonly preset box",
    str(app.mechanics_error_box.cget("state")) == "readonly"
    and app.mechanics_error.get() in app.mechanics_error_box.cget("values"),
    f"{app.mechanics_error_box.cget('state')} | {app.mechanics_error.get()}",
)
type_text(by_var(app.mechanics_tolerance), "0.000000001")
button("Compute event and horizon").invoke()
root.update()
check(
    "mechanics: tolerance<error dialog fires",
    pop_dialog("tolerance must exceed"),
    str(DIALOGS[-3:]),
)
type_text(by_var(app.mechanics_tolerance), "1.0")
app.mechanics_error.set("1e-1")
type_text(by_var(app.mechanics_tolerance), "0.01")
button("Compute event and horizon").invoke()
root.update()
check(
    "mechanics: preset error above tolerance is diagnosed",
    pop_dialog("tolerance must exceed"),
    str(DIALOGS[-3:]),
)
app.mechanics_error.set("1e-6")
type_text(by_var(app.mechanics_tolerance), "1.0")
app.mechanics_system.set("Double pendulum — chaos")
type_text(by_var(app.mechanics_horizon), "2.0")
button("Animate the system").invoke()
done = pump_until_done(40.0)
check(
    "mechanics: pendulum animation runs to the end",
    done and has_text(app.mechanics_canvas, "t = "),
    str(canvas_texts(app.mechanics_canvas)),
)

# ---------------- Quantum ----------------
select_tab("Quantum (Go)")
button("Compute event A (Go kernel)").invoke()
root.update()
check(
    "quantum: Go kernel Bell pair",
    "P(A)=100%" in result_text(app.quantum_result)
    and "Purity Tr(rho^2): 1.000000" in result_text(app.quantum_result),
    result_text(app.quantum_result),
)
button("Wavefunction limit").invoke()
root.update()
check(
    "quantum wall: q0=q1 determined, L_O=1",
    "L_O               = 1.000000" in result_text(app.quantum_result),
    result_text(app.quantum_result),
)
app.quantum_event_field.kind.set("qubit N = value")
button("Wavefunction limit").invoke()
root.update()
check(
    "quantum wall: single qubit irreducible, L_O=0",
    "L_O               = 0.000000" in result_text(app.quantum_result)
    and "THE QUANTUM WALL" in result_text(app.quantum_result),
    result_text(app.quantum_result),
)
check(
    "quantum: qubit spinbox blocks 044",
    type_text(by_var(app.quantum_target), "044") == "0",
    by_var(app.quantum_target).get(),
)
check(
    "quantum: picker partner qubit blocks 14 in a 2-qubit world",
    type_text(app.quantum_event_field.partner_spin, "14") == "1",
    app.quantum_event_field.partner_spin.get(),
)
check(
    "quantum: bits filter caps at 10 qubits",
    type_text(by_var(app.quantum_bits), "010101010101") == "0101010101",
    by_var(app.quantum_bits).get(),
)
type_text(by_var(app.quantum_bits), "00")
app.quantum_event_field.kind.set("qubit N = qubit M")
app.gate_builder.clear()
app.gate_builder.kind.set("H")
type_text(app.gate_builder.index_spin, "0")
app.gate_builder.add()
app.gate_builder.kind.set("CNOT")
type_text(app.gate_builder.index_spin, "0")
type_text(app.gate_builder.partner_spin, "1")
app.gate_builder.add()
check(
    "quantum: gate builder composes the Bell program",
    app.quantum_gates.get() == "H 0; CNOT 0 1",
    app.quantum_gates.get(),
)
type_text(app.gate_builder.partner_spin, "0")
app.gate_builder.add()
check(
    "quantum: builder refuses CNOT on one qubit",
    app.quantum_gates.get() == "H 0; CNOT 0 1"
    and "must differ" in str(app.gate_builder.hint.cget("text")),
    str(app.gate_builder.hint.cget("text")),
)
type_text(by_var(app.quantum_bits), "0")
button("Wavefunction limit").invoke()
root.update()
check(
    "quantum: stale gate dialog names the offending command",
    pop_dialog("in gate 'CNOT 0 1'"),
    str(DIALOGS[-3:]),
)
DIALOGS.clear()
type_text(by_var(app.quantum_bits), "00")
app.gate_builder.clear()
button("Compute event A (Go kernel)").invoke()
root.update()
check(
    "quantum: empty gate program runs as the identity circuit",
    "|00>: 1.000000" in result_text(app.quantum_result),
    result_text(app.quantum_result),
)
app.quantum_gates.set("H 0; CNOT 0 1")
button("Read a qubit").invoke()
root.update()
check(
    "quantum: reading a qubit halves the Bell purity",
    "1.000000 -> 0.500000" in result_text(app.quantum_result)
    and "MEASUREMENT DISTURBS" in result_text(app.quantum_result),
    result_text(app.quantum_result),
)
button("Rewind").invoke()
root.update()
check(
    "quantum: rewind returns exactly unless observed",
    "1.000000" in result_text(app.quantum_result)
    and "0.500000" in result_text(app.quantum_result)
    and "UNITARY WORLD REMEMBERS" in result_text(app.quantum_result),
    result_text(app.quantum_result),
)
button("CHSH before environment").invoke()
root.update()
check(
    "quantum: CHSH hits Tsirelson and declares Bell violation",
    "2.828427" in result_text(app.quantum_result)
    and "BELL VIOLATION" in result_text(app.quantum_result),
    result_text(app.quantum_result),
)

# ---------------- Formula L ----------------
select_tab("Formula L")
button("Compute the formula").invoke()
root.update()
check(
    "formula: K=2,3,4 makes a local demon",
    "local demon" in result_text(app.info_result),
    result_text(app.info_result),
)
check(
    "formula: K field cuts digit spam at two digits per token",
    type_text(by_var(app.info_known), "2,3,4222222222") == "2,3,42",
    by_var(app.info_known).get(),
)
check(
    "formula: K field still accepts the word none",
    type_text(by_var(app.info_known), "none") == "none",
    by_var(app.info_known).get(),
)
type_text(by_var(app.info_known), "none")
button("Compute the formula").invoke()
root.update()
check(
    "formula: no knowledge gives L=0",
    "L           = 0.000000" in result_text(app.info_result),
    result_text(app.info_result),
)
type_text(by_var(app.info_width), "3")
root.update()
hints = [
    str(w.cget("text"))
    for w in WIDGETS
    if w.winfo_class() == "TLabel" and "0..2" in str(w.cget("text"))
]
check("formula: hints follow width=3 live", len(hints) >= 1, str(hints))
type_text(by_var(app.info_known), "2,3,4")
button("Compute the formula").invoke()
root.update()
check(
    "formula: out-of-range K dialog fires",
    pop_dialog("between 0 and 2"),
    str(DIALOGS[-3:]),
)
type_text(by_var(app.info_width), "7")
type_text(by_var(app.info_known), "2,3,4")

button("Embedded demon (light cone)").invoke()
root.update()
check(
    "formula: light-cone demon shows seat-dependent L_O",
    "full demon here" in result_text(app.info_result)
    or "NO GLOBAL NOW" in result_text(app.info_result)
    or "light to cross" in result_text(app.info_result),
    result_text(app.info_result),
)
type_text(by_var(app.info_width), "12")
button("Macro entropy (second law)").invoke()
root.update()
check(
    "formula: macro entropy grows for rule 30",
    "SECOND LAW" in result_text(app.info_result),
    result_text(app.info_result),
)
type_text(by_var(app.info_width), "7")

# ---------------- Active Inference ----------------
select_tab("Active Inference")
button("Report").invoke()
root.update()
check(
    "agent: rule 30 demon in 3 actions",
    "local demon after 3 action(s)" in result_text(app.agent_result),
    result_text(app.agent_result),
)
type_text(by_var(app.agent_rule), "60")
button("Report").invoke()
root.update()
check(
    "agent: rule 60 exposes the plateau",
    "EPISTEMIC PLATEAU" in result_text(app.agent_result)
    and "NOT optimal" in result_text(app.agent_result),
    result_text(app.agent_result),
)
button("Animate foraging").invoke()
done = pump_until_done()
check(
    "agent: foraging animation completes",
    done and has_text(app.agent_canvas, "L_O"),
    str(canvas_texts(app.agent_canvas)),
)
type_text(by_var(app.agent_rule), "30")

# ---------------- The Walls ----------------
select_tab("The Walls")
button("H_irr(m)").invoke()
root.update()
check(
    "walls: minimal demon is 3 cells",
    "Minimal demon: 3 cell(s) of 7" in result_text(app.walls_result),
    result_text(app.walls_result),
)
button("Bekenstein bound").invoke()
root.update()
check(
    "walls: Bekenstein verdict present",
    "does NOT bite" in result_text(app.walls_result),
    result_text(app.walls_result),
)
button("Landauer cost of knowledge").invoke()
root.update()
check(
    "walls: Landauer prices the demon's memory in joules",
    "Maxwell" in result_text(app.walls_result)
    and "J per bit" in result_text(app.walls_result),
    result_text(app.walls_result),
)
button("Diagonal X*").invoke()
root.update()
check(
    "walls: diagonal — every inner strategy fails",
    "wrong 2 of 2" in result_text(app.walls_result),
    result_text(app.walls_result),
)
button("Two devices").invoke()
root.update()
check(
    "walls: mutual inference — 0 of 4 survive",
    "0 of 4" in result_text(app.walls_result),
    result_text(app.walls_result),
)

# ---------------- The Game ----------------
select_tab("The Game")
before_total = app.game_total
button("Next bit: 0").invoke()
done = pump_until_done()
check(
    "game: a guess is scored and the round animation completes",
    done
    and app.game_total == before_total + 1
    and "You:" in str(app.game_score_label.cget("text"))
    and len(app.game_canvas.find_all()) > 31,
    str(app.game_score_label.cget("text")),
)
button("New world").invoke()
root.update()
check(
    "game: new world resets the score",
    app.game_total == 0 and len(app.game_history) == app.GAME_HISTORY_SHOWN,
    f"total={app.game_total}, history={len(app.game_history)}",
)

# ---------------- Screenshot: rule 30, width 25 ----------------
select_tab("Classical")
type_text(by_var(app.classical_state), "0000000000001000000000000")
type_text(by_var(app.classical_steps), "24")
type_text(app.classical_event_field.index_spin, "12")
button("Animate spacetime").invoke()
pump_until_done()
button("Compute event A").invoke()
root.update()
root.lift()
root.attributes("-topmost", True)
root.update()
time.sleep(0.5)
try:
    from PIL import ImageGrab

    shot = ImageGrab.grab(all_screens=False)
    shot.save(sys.argv[1] if len(sys.argv) > 1 else "gui_verify.png")
    print("[SHOT] saved")
except Exception as error:  # noqa: BLE001
    print(f"[SHOT] failed: {error}")

root.destroy()

failed = [r for r in RESULTS if not r[0]]
print(f"\n===== {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed =====")
for _, name, detail in failed:
    print(f"FAILED: {name}\n  detail: {detail[:400]}")
if DIALOGS:
    print(f"unconsumed dialogs: {DIALOGS}")
sys.exit(1 if failed else 0)
