# What the laboratory establishes

The cellular calculations are exact within a finite, specified deterministic
model. Numerical mechanics and quantum calculations have floating-point error.
Passing tests checks implementations and regression cases; it does not prove
that a universal Laplace demon is possible or impossible in nature.

- `mechanics.py`: a finite coordinate sweep and exponential-growth horizon are
  heuristics. Initial-state coordinates mix units, and the input-error parameter
  is not propagated to a rigorous event-error bound. Step halving compares the
  displayed ball position/impact time or pendulum angle. Every mechanics report
  remains **NOT CERTIFIED**, including when the heuristic horizon is long.
- `shortcut.py`: GF(2) exponentiation applies to the eight additive rules.
  Other rules use cycle search with bounded work. Exhausting that budget means
  this implementation has not computed the answer, not that no shortcut exists.
- `cone.py`: the observer receives an exact spatial subset of the initial
  state. Its radius equals the horizon by convention. No collection schedule,
  signal transport or relativistic observer is simulated.
- Measurement and rewind: full Z dephasing describes measurement with its
  outcome ignored. A retained outcome gives a conditional state. The code does
  not simulate an outcome register or an energetic cost of measurement.
  See [IBM's measurement formulation](https://learning.quantum.ibm.com/course/general-formulation-of-quantum-information/general-measurements).
- Bekenstein: the number is a capacity **upper bound**, not an attainable
  memory size; its inverse is a radius lower bound. The stated assumptions are
  a complete weakly self-gravitating system with total energy E inside radius R.
  See [Bekenstein's discussion](https://arxiv.org/abs/quant-ph/0404042).
- Landauer: the displayed reset-heat bound assumes independent unbiased
  classical bits and an isothermal cycle. Record length alone does not account
  for bias, correlations or accessible side information. Knowing a fact is
  not itself an erasure. See [the experimental erasure study](https://arxiv.org/abs/1503.06537).
- CHSH excludes local hidden-variable models under the Bell-test assumptions,
  not every deterministic interpretation. The displayed calculation applies
  to the unitary state before the environment channels.
- Diagonal opposition requires that the target can read the published answer
  and choose its opposite. The finite mutual-inference enumeration illustrates
  a restricted case, not a proof of all versions of the underlying theorem.
- Coarse-grained entropy belongs to a chosen finite ensemble and observation
  map. It is not a derivation of thermodynamics or a monotonicity guarantee.

## Build the Windows executable

With Python, Go and PyInstaller installed, run `./build.ps1` in PowerShell.
The script builds the Go kernel from source and bundles it with the current
Python application into `dist/LaplaceDemon.exe`. Release assets are separate
from source commits and must be rebuilt when the program changes.
