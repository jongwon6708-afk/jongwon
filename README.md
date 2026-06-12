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
  reconstruction.py  # threshold + Flying Edges -> smoothed bone mesh
  camera_views.py    # anatomical presets + surgeon's-view save/recall
  viewer.py          # PyQt5 + VTK interactive window
  app.py             # entry point
run.py               # launcher
tests/test_pipeline.py  # headless smoke tests (no display needed)
```

## Tests

```bash
python tests/test_pipeline.py     # or: pytest tests/
```

These build a synthetic bone phantom (cortical cylinder with a drilled hole)
and verify the reconstruction pipeline without needing a display.

## Roadmap (next stages)

1. **Pre/post registration** — align the two studies (ICP / landmark) so
   differences are spatially meaningful.
2. **HU → elastic-modulus mapping** (Bonemat-style) to drive FEA.
3. **FEA export** — generate FEBio / CalculiX input from the mesh for stress
   analysis (drill/saw stress concentration, fracture reduction with
   ligament/tendon effects).
