"""Demo: isolate one bone the way a radiographer does it.

Scene: two bones (e.g. both femora) plus the scanner table -- three
disconnected structures. Shows:

  A. the raw reconstruction (everything present),
  B. the clicked structure highlighted (region pick),
  C. "Keep only" -> just the bone of interest,
  D. scissors lasso cutting away part of what remains.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.preprocessing import PreprocessParams  # noqa: E402
from bonesim import editing  # noqa: E402
from test_editing import make_two_bones_phantom  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "demo_output")


def _actor(mesh, color=(0.88, 0.83, 0.72), opacity=1.0):
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(mesh)
    m.ScalarVisibilityOff()
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetOpacity(opacity)
    return a


def _render(actors, path, label, bounds):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.12, 0.13, 0.16)
    for a in actors:
        ren.AddActor(a)
    txt = vtk.vtkTextActor()
    txt.SetInput(label)
    txt.GetTextProperty().SetFontSize(24)
    txt.GetTextProperty().SetColor(1, 1, 1)
    txt.SetPosition(18, 16)
    ren.AddActor2D(txt)

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(600, 520)
    win.AddRenderer(ren)
    cx = (bounds[0] + bounds[1]) / 2
    cy = (bounds[2] + bounds[3]) / 2
    cz = (bounds[4] + bounds[5]) / 2
    cam = ren.GetActiveCamera()
    cam.SetPosition(cx, cy, cz + 260)
    cam.SetFocalPoint(cx, cy, cz)
    cam.SetViewUp(0, 1, 0)
    ren.ResetCamera()
    win.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(path)
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    print("wrote", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    volume = make_two_bones_phantom()
    mesh = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=500, smoothing_iterations=3, decimation=0.0,
        island_min_fraction=0.0,
        preprocess=PreprocessParams(median_denoise=False)))
    bounds = mesh.GetBounds()
    sizes = editing.region_sizes(mesh)
    print(f"regions found: {len(sizes)} sizes={sizes}")

    _render([_actor(mesh)], os.path.join(OUT, "edit_A_raw.png"),
            f"A. Raw: {len(sizes)} structures (2 bones + table)", bounds)

    # Emulate the user clicking one bone: the table is a wide, thin slab
    # (very elongated in x vs y), the bones are compact. Pick the left bone.
    candidates = []
    for rid in range(len(sizes)):
        rb = editing.extract_regions(mesh, {rid}, invert=False).GetBounds()
        span_x, span_y = rb[1] - rb[0], rb[3] - rb[2]
        elongation = span_x / max(span_y, 1e-6)
        if elongation < 3.0:  # compact -> a bone, not the table slab
            candidates.append((rb[0], rid))
    target = sorted(candidates)[0][1]  # left-most bone
    print(f"bone candidates: {candidates} -> target region {target}")

    highlight = editing.extract_regions(mesh, {target}, invert=False)
    _render([_actor(mesh, opacity=0.35),
             _actor(highlight, color=(1.0, 0.55, 0.1))],
            os.path.join(OUT, "edit_B_picked.png"),
            "B. Clicked bone selected (orange)", bounds)

    kept = editing.extract_regions(mesh, {target}, invert=False)
    _render([_actor(kept)], os.path.join(OUT, "edit_C_isolated.png"),
            "C. Keep only -> bone isolated", bounds)

    # D. Scissors: lasso off the lower half of the isolated bone.
    kb = kept.GetBounds()
    ymid = (kb[2] + kb[3]) / 2
    loop = [
        (kb[0] - 8, ymid, 0.0),
        (kb[1] + 8, ymid, 0.0),
        (kb[1] + 8, kb[3] + 8, 0.0),
        (kb[0] - 8, kb[3] + 8, 0.0),
    ]
    cut = editing.scissors_cut(kept, loop, view_normal=(0, 0, 1),
                               keep_inside=False)
    _render([_actor(cut, color=(0.75, 0.85, 0.95))],
            os.path.join(OUT, "edit_D_scissors.png"),
            "D. Scissors lasso cut away top half", bounds)


if __name__ == "__main__":
    main()
