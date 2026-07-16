---
name: verify
description: Full runtime verification of the demon_laplas app — drives the real GUI (all 7 tabs, animations, keystroke filters, error dialogs), sweeps every CLI with happy paths and bad-input probes, and captures a screenshot.
---

# Verify demon_laplas

All commands run from `D:\NewOld\программ\theory_all\demon_laplas`.

## 1. GUI drive (the main surface)

```powershell
python -X utf8 .claude\skills\verify\drive_gui.py gui_verify.png
```

Exit 0 = all ~32 checks passed; failures are listed with captured output.
The driver opens the real Tk window, finds buttons by their label text and
fields by their `textvariable`, types through Tk key-validation, waits for
animations via `app._animator._job is None`, and saves a full-screen PNG.

Gotchas:
- `messagebox.showerror` is monkeypatched to a recorder (dialogs would block
  automation); everything else is stock.
- Button lookup is by substring of the label — **if a button is renamed, the
  driver needs the new text** (that is the only maintenance it ever needs).
- Events are set through the structured picker: `app.<tab>_event_field` with
  `.kind` (combobox var), `.index_spin` / `.partner_spin` / `.value` /
  `.state_entry`; the composed string lands in the old `app.<tab>_event` var.
- The quantum gate program is built via `app.gate_builder` (`.kind`,
  `.index_spin`, `.partner_spin`, `.add()/.undo()/.clear()`); the program
  entry itself is read-only and lands in `app.quantum_gates`.
- The window appears on screen for ~1–2 minutes; don't fight it for focus.

## 2. CLI sweep

Happy path + one error probe per module (expected exit codes in parens):

```powershell
python -X utf8 demon.py --state 0001000 --rule 30 --steps 100 --cell 3   # (0) exact_within_model
python -X utf8 demon.py --state 0100x --rule 30 --steps 1                # (1) only 0 and 1
python -X utf8 events.py --history "0001000; 0011100" --steps 1 --event cell3=1  # (0) Consistent rules: 16
python -X utf8 events.py --history "000; 000; 111" --steps 1 --event cell0=1     # (1) contradicts
python -X utf8 information.py --width 7 --rule 30 --steps 1 --event cell3=1 --min-knowledge  # (0) Minimal demon: 3
python -X utf8 mechanics.py --system pendulum --horizon 5 --error 1e-6 --tolerance 1.0       # (0) Lyapunov measured
python -X utf8 fep.py --width 7 --rule 60 --steps 1 --event cell3=1      # (0) EPISTEMIC PLATEAU
python -X utf8 godel.py                                                  # (0) 0 of 4 survive; monotheism
python -X utf8 shortcut.py --rule 90 --steps 1000000000000000000         # (0) REDUCIBLE, ms not eons
python -X utf8 shortcut.py --rule 30 --steps 1000                        # (0) NOT linear, irreducibility
python -X utf8 walls.py                                                  # (0) Maassen-Uffink
python -X utf8 cone.py --width 7 --rule 30 --horizon 1 --event cell3=1   # (0) full demon only at seat 3
python -X utf8 macro.py --width 12 --rule 30 --steps 8                   # (0) SECOND LAW, H grows
python -X utf8 ..\predict_event.py                                       # (0) ball LANDED t=3.306
echo classical| python -X utf8 interactive.py                            # (0) EOF falls back to defaults
```

## 3. Unit tests and Go kernel

```powershell
python -m unittest            # ~72 tests
cd native_quantum; go test -count=1 ./...; go vet ./...; go build -o quantum-demon.exe .
```

Rebuild the exe whenever `main.go` changes — the GUI shells out to the
committed binary, not the source.
