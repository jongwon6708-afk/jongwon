# Iterative surgical planning by radiographic measurement

Why this document exists: the point of this tool is **not** to render a pretty
bone. It is to let a surgeon state a plan before the operation — this
osteotomy, this reduction, this plate, these lag screws — simulate it, and see
whether the *numbers that matter clinically* land where they should. Those
numbers are radiographic measurements, and getting them right takes several
passes. This describes the loop and how the tool stores it.

## The loop

```
  ┌─────────────────────────────────────────────────────────────┐
  │  1. Reconstruct pre-op CT                                    │
  │  2. Isolate the bone of interest (region pick / scissors)     │
  │  3. Place landmarks                                          │
  │  4. Measure  -> baseline deformity                            │
  │  5. Define the TARGET (contralateral mirror, or normal range) │
  │  6. Simulate the plan (move fragments / osteotomy / implant)   │
  │  7. Re-measure on the simulated result                        │
  │  8. Compare vs target -> within tolerance?                    │
  │        no  -> adjust the plan, back to 6                      │
  │        yes -> freeze this as the operative plan               │
  │  9. Post-op CT -> measure again -> compare against the plan    │
  └─────────────────────────────────────────────────────────────┘
```

Steps 6→8 are the part that repeats, and step 9 is what closes the audit loop
and tells you whether the plan was achievable.

## Why measurements are stored as *definitions*, not numbers

A measurement is stored as a name, a kind, and the **names of the landmarks**
it uses — never as a copied-out value. Consequences:

- Moving a landmark re-derives every measurement that depends on it. No stale
  numbers.
- The same measurement definition is evaluated on every stage (pre-op,
  plan-v1, plan-v2, post-op), so stages are directly comparable.
- A simulated reduction moves the bone and therefore the landmarks; the
  definition is untouched. That is why landmarks live **per stage** while
  measurements live **per session**.

See `src/bonesim/measurement.py`: `Measurement`, `PlanStage`,
`PlanningSession`.

## Data model

```
PlanningSession
├── patient_ref
├── measurements: [Measurement]        # definitions, shared by all stages
│     name, kind, points[landmark names], target, tolerance
└── stages: [PlanStage]                # one per version
      label ("pre-op", "plan-v1", "post-op")
      landmarks: {name -> Landmark(position in patient mm)}
```

Everything serialises to JSON (`session.save(path)` / `PlanningSession.load`),
so a plan is a file that can be versioned, diffed, and re-opened next week.

Landmarks are stored in **patient (world) coordinates in millimetres**, taken
straight from the DICOM frame — not in screen or voxel coordinates — so they
stay valid when the model is re-reconstructed at a different threshold, and so
pre-op and post-op studies are comparable once registered.

## Measurement kinds

| kind | points | meaning |
|---|---|---|
| `distance` | `[a, b]` | straight-line mm (fracture gap, offset, LLD) |
| `angle` | `[p1, vertex, p2]` | angle subtended at a vertex |
| `line_angle` | `[a1, a2, b1, b2]` | angle between two lines |

### Convention trap worth knowing

The **neck-shaft angle** is measured clinically as the angle opening *medially*
at the neck/shaft junction — normally ~125–135°. Computing it as the angle
between the neck axis line and the shaft axis line returns the acute
*supplement* (~40°), which looks plausible and is wrong. The preset therefore
uses a **vertex angle** (`femoral_head_center` → `neck_shaft_junction` →
`shaft_distal`), and a regression test pins the value. Any new angle added here
should get the same treatment: decide the clinical convention first, then pin
it with a test on known geometry.

## Defining the target

Three ways, in descending order of preference:

1. **Contralateral mirror** — mirror the healthy side and measure it. This is
   the patient's own normal and is the most defensible target in trauma. The
   tool already supports mirroring + ICP registration (`analysis.mirror_mesh`,
   `analysis.register_icp`).
2. **Population normal range** — e.g. NSA 125–135°, used when the other side
   is also injured or absent.
3. **Explicit surgeon intent** — "I want 5° of valgus over-correction". Set
   `target` and `tolerance` directly.

`tolerance` is what turns a measurement into a pass/fail: `within_target()`
returns True/False, and `compare()` reports it per measurement.

## Comparing versions

```python
report = session.compare("pre-op", "plan-v1")
# {"Fracture gap": {"before": 12.0, "after": 1.5, "delta": -10.5,
#                   "target": 0.0, "within_target": True}, ...}
```

This is the readout the surgeon actually wants: *what did my plan change, and
did it get there?* Iterating means adding `plan-v2`, `plan-v3` … each a new
stage with the landmarks as moved by that version of the plan.

## Suggested measurement sets

Presets live next to the code so they can be extended per anatomy.
`femur_trauma_preset()` ships today (neck-shaft angle, fracture gap, femoral
offset). Natural additions:

- **Proximal femur**: neck-shaft angle, femoral offset, leg-length difference,
  tip-apex distance (for cephalomedullary screws).
- **Knee / deformity**: mLDFA, MPTA, mechanical axis deviation, posterior
  tibial slope.
- **Ankle / pilon**: talocrural angle, medial clear space, fibular length.
- **Calcaneus**: Böhler angle, Gissane angle, height/width.
- **Intra-articular, any site**: articular step-off and gap — the measurements
  that actually predict outcome, and the ones a 3D simulation is best at.

## What has to be built for the loop to close

Current state and what is still missing:

| Loop step | Status |
|---|---|
| 1 Reconstruct | done |
| 2 Isolate bone | done (region pick, scissors lasso, crop) |
| 3 Place landmarks | done (click to place, per stage) |
| 4 Measure | done (distance / vertex angle / line angle) |
| 5 Target from contralateral | mirroring + ICP done; measuring the mirror as a stage still to wire |
| 6a Simulate: osteotomy + reduction | done (cut plane → two fragments, translate/rotate, landmarks follow) |
| 6b Simulate: implants (plate / lag screw) | done (parametric screws/plates, trajectory placement, construct checks) |
| 7 Re-measure | done — moving a fragment moves its landmarks, so measurements re-derive |
| 8 Compare vs target | done (`compare`, plus a reduction verdict) |
| 9 Post-op verification | reconstruct post-op works; needs pre/post registration to share a frame |

### Judging a reduction

`simulation.reduction_quality()` returns the residual **gap in mm**, the
**interpenetration volume in mm³**, and a verdict.

The overlap term matters more than it first appears: a gap of zero is
*ambiguous*. Two fragments read zero gap both when they are perfectly reduced
and when they have been driven into each other — and bone cannot
interpenetrate, so the second case is over-reduction, not success. Reporting
gap alone would score the worst reduction as the best one.

Overlap is measured by rasterising both fragments onto a shared grid and
counting shared voxels. A boolean-intersection filter is the obvious
alternative but crashes here: fragments from one cut share a coplanar face.

### Judging a fixation construct

`fixation.construct_report()` answers the questions asked of a plan before
committing to it:

| Check | Why it decides the plan |
|---|---|
| screw purchase (% of screw in bone) | a screw mostly outside bone will not hold |
| lags the fracture? | a lag screw only compresses if it **crosses** the fracture plane; one contained in a single fragment cannot, however well seated |
| articular breach | a screw in the joint |
| screw-to-screw clearance | two trajectories that collide cannot both be drilled |
| plate standoff (min/mean/max mm) | a straight plate on a curved cortex only contacts along a line — the mean standoff is what tells you how much contouring it needs |

Implants are **generated**, not imported: vendor CAD (DePuy, Stryker) is not
publicly licensable and model-library files forbid redistribution. Generating
AO-style geometry sidesteps that and makes length, diameter, hole count and
curvature *parameters* — which is what "which plate and screw fit this
patient?" actually needs. Screw shafts are smooth cylinders rather than
threaded helices: thread form does not change trajectory, length selection,
breach or purchase, so modelling it would cost mesh complexity for no planning
value.

`implants.place_along()` aims an implant from an entry point toward a target,
but keeps the length it was built with — exactly as a real screw does. Use
`implants.length_for_trajectory()` to size it first.

### What is left

- **Pre/post registration** so a post-op CT shares a frame with the plan.
- **Contoured (anatomic) plates** — currently plates are straight; bending them
  to a patient's cortex is the natural next step, and the standoff map already
  provides the error signal to bend against.
- **FE stress analysis** (FEBio/CalculiX) on the finished construct.
