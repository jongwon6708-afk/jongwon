# 3D Bone CT Simulator

A Windows-friendly desktop tool for **static (post-operative) 3D bone
reconstruction and viewing** from CT scans. Built with **Python + VTK + PyQt5**.

This is the viewer/reconstruction stage of the project. It is **not** a
real-time cutting simulator — the goal is to reconstruct a bone from CT, let
the surgeon orient it freely the way they see it during surgery, and compare a
**pre-operative** scan against a **post-operative** scan.

## Features (current MVP)

- Load a **pre-op** and a **post-op** DICOM CT series independently.
- Convert stored values to **Hounsfield Units** and extract bone with an
  adjustable **HU threshold** (Marching Cubes / Flying Edges isosurface).
- **Drag to rotate**, scroll to zoom — view the model from any direction.
- **Anatomical preset views** (Anterior/Posterior/Left/Right/Superior/Inferior)
  plus **save & recall a custom "surgeon's view"**.
- Toggle visibility and opacity to overlay pre-op vs post-op.
- **Export** the reconstructed mesh to STL/PLY/OBJ (e.g. for 3D printing).

### Cleanup & artefact removal
- **Median denoise** to suppress speckle and tiny calcification flecks.
- **Island removal** drops free-floating noise/calcification fragments while
  keeping every real bone piece.
- **Crop box** — the fracture-safe way to remove the scanner table / back
  board: enclose the bone in a draggable box and discard everything outside.
  (Unlike "largest component" removal, cropping never deletes a displaced
  fracture fragment.)
- **Solid fill** — a single-isovalue surface is only a shell, and trabecular
  interiors (e.g. the femoral head) sit below the bone threshold, so they read
  as hollow. Solid fill fills enclosed low-HU cavities so the bone looks solid.
  Visualisation only — do **not** use it for FEA, where the real cortical vs
  trabecular HU distribution must be preserved.

### Fracture analysis
- **Curvature highlighting** colours the surface by curvature so fracture
  clefts stand out.
- **Fracture feature edges** extract the sharp crack rim as red overlay lines.
- Lowering **smoothing** preserves the fracture cleft instead of bridging it.

### Cross-section
- A **cutting plane** (X/Y/Z axis, position slider, flip side) cuts the bone
  open so you can see inside — the femoral-head interior, or how a fracture
  runs through the bone.
- **Cap the cut face** to tell solid from hollow: a solid interior shows a
  filled disc, a hollow shell shows only a thin ring. (Note: from the outside
  a solid and a hollow bone look identical — only a cross-section reveals the
  difference.)

### Edit / isolate the bone (clinical clean-up workflow)
- **Region pick** — left-click a bone and its whole connected structure is
  selected (ctrl-click adds more); **Keep only** isolates it, **Delete**
  removes it. This is the one-click way to drop the table, the contralateral
  limb, or scatter, and mirrors Mimics *Region Grow* / Slicer *Islands*.
- **Scissors lasso** — draw a loop and cut through along the view direction,
  for structures that touch and so cannot be separated by connectivity.
- Selection is highlighted in orange and every edit is undoable.

### Simulate the plan
- **Osteotomy** — cut the bone along the current cross-section plane into two
  repositionable fragments (the virtual saw cut).
- **Reposition a fragment** with shift (mm) and rotation (deg) about its own
  centroid; **landmarks travel with the fragment they sit on**, so the
  measurements below re-derive on the simulated result.
- **Reduction verdict** — residual gap in mm plus interpenetration volume, so
  an over-reduction (fragments driven into each other, which also reads as
  zero gap) is flagged rather than scored as a good reduction.
- **Save as plan stage** to compare the simulated result against pre-op.

### Implants (plating / lag screw)
- **Parametric AO-style screws and plates** generated in code — length,
  diameter, hole count and plate length are parameters. (Vendor CAD is not
  publicly licensable, so nothing is imported.)
- Place a **trajectory** with two landmarks (`screw_entry`, `screw_target`),
  then drop a screw on it (auto-length spans the trajectory) or lay a plate
  along it.
- **Check construct** reports screw **purchase** (% in bone), whether a screw
  **lags the fracture** (crosses the fracture plane — the defining property of
  a lag screw), **screw-to-screw conflicts**, and **plate standoff** from the
  cortex.

### Measure & plan (iterative surgical planning)
- Place named **landmarks** by clicking the bone, per **stage**
  (`pre-op`, `plan-v1`, `post-op`, …).
- **Measure** distances and angles derived from those landmarks, with a
  **target and tolerance** so each reads OK / OFF TARGET.
- **Compare stages** to see what a simulated plan changed and whether it hit
  the target; **save/load the plan** as JSON.
- Ships a proximal-femur trauma preset (neck-shaft angle, fracture gap,
  femoral offset). See [docs/planning-loop.md](docs/planning-loop.md).

### Comparison with a standard
- **Mirror the healthy contralateral side** to use as the patient's own
  normative standard, or **load a reference STL**.
- **ICP registration** aligns the bone to the standard and a **deviation
  heat-map** (mm) colours where it departs from normal.

## Install

```bash
python -m pip install -r requirements.txt
```

Requires Python 3.9–3.12. On Windows, all dependencies install via `pip`.

## Run

```bash
python run.py
```

Then **Load Pre-op CT…** / **Load Post-op CT…** and point each at a folder
containing a DICOM series. Loading a new post-op series re-runs the
reconstruction independently of the pre-op model.

## HU reference for the threshold slider

| Tissue | Approx. HU |
|---|---|
| Air | −1000 |
| Fat | −100 |
| Soft tissue | +40 |
| Trabecular (spongy) bone | +300…+400 |
| Cortical bone | +700…+3000 |

Default threshold is **300 HU** (captures most bone). Raise toward **700+** to
isolate dense cortical bone only.

## Project layout

```
src/bonesim/
  dicom_loader.py    # DICOM series -> HU volume (numpy + vtkImageData)
  preprocessing.py   # median denoise, crop-box table removal, solid fill
  reconstruction.py  # threshold + Flying Edges -> island-cleaned bone mesh
  analysis.py        # fracture curvature/edges, cross-section, mirror, ICP
  editing.py         # region pick + scissors lasso (clinical clean-up)
  simulation.py      # osteotomy cut, fragment transforms, reduction quality
  implants.py        # parametric AO-style screws and plates, placement
  fixation.py        # purchase, lag check, screw conflicts, plate standoff
  measurement.py     # landmarks, measurements, plan stages, compare, JSON
  camera_views.py    # anatomical presets + surgeon's-view save/recall
  viewer.py          # PyQt5 + VTK interactive window
  app.py             # entry point
run.py               # launcher
docs/
  planning-loop.md          # the iterate-until-on-target workflow
  landscape-comparison.md   # what else exists, and the gap this fills
scripts/                    # offscreen render demos (no display needed)
tests/                      # 7 headless suites incl. GUI wiring
```

All tests run headless (no display); the GUI test uses Qt's offscreen platform.

## Tests

```bash
python tests/test_pipeline.py     # or: pytest tests/
```

These build a synthetic bone phantom (cortical cylinder with a drilled hole)
and verify the reconstruction pipeline without needing a display.

## Why this tool exists

The goal is **pre-operative simulation**: let a surgeon state the plan before
the operation — this osteotomy, this reduction, this plate, these lag screws —
simulate it, and see whether the radiographic numbers that matter land where
they should.

A survey of what already exists is in
[docs/landscape-comparison.md](docs/landscape-comparison.md). Short version:
commercial tools (Sectra 3D Trauma, mediCAD, Mimics) do this for €20–40k and
are PACS-locked; open-source tools stop partway — none ships implant geometry,
and *nothing open produces an ortho-specific measurement report*. That report
is the piece this project already has.

## Roadmap (next stages)

1. **Contoured (anatomic) plates** — plates are currently straight; the
   standoff map already gives the error signal to bend against.
2. **Pre/post registration** — align the two studies (ICP / landmark) so
   differences are spatially meaningful.
3. **HU → elastic-modulus mapping** (Bonemat-style) to drive FEA.
4. **FEA export** — generate FEBio / CalculiX input from the mesh for stress
   analysis (drill/saw stress concentration, fracture reduction with
   ligament/tendon effects).
