"""Demo: the full pre-op simulation loop on a phantom bone.

  1. intact bone
  2. osteotomy along a chosen plane -> two fragments
  3. displaced (the injury / an un-reduced state)  -> measured "gapped"
  4. simulated reduction                            -> measured "reduced"
  5. over-reduction                                 -> caught, not called good

Prints the reduction verdict at each step, which is the readout that decides
whether a plan is acceptable.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from bonesim import simulation  # noqa: E402
from test_simulation import _bone  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "demo_output")
COLORS = [(0.92, 0.87, 0.78), (0.62, 0.80, 0.93)]


def _actor(mesh, color):
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(mesh)
    m.ScalarVisibilityOff()
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetSpecular(0.2)
    return a


def _render(meshes, path, label, focus_bounds):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.12, 0.13, 0.16)
    for mesh, color in zip(meshes, COLORS):
        ren.AddActor(_actor(mesh, color))
    txt = vtk.vtkTextActor()
    txt.SetInput(label)
    txt.GetTextProperty().SetFontSize(22)
    txt.GetTextProperty().SetColor(1, 1, 1)
    txt.SetPosition(16, 14)
    ren.AddActor2D(txt)

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(560, 560)
    win.AddRenderer(ren)
    cx = (focus_bounds[0] + focus_bounds[1]) / 2
    cy = (focus_bounds[2] + focus_bounds[3]) / 2
    cz = (focus_bounds[4] + focus_bounds[5]) / 2
    cam = ren.GetActiveCamera()
    cam.SetPosition(cx, cy - 170, cz)      # look from anterior
    cam.SetFocalPoint(cx, cy, cz)
    cam.SetViewUp(0, 0, 1)
    ren.ResetCamera()
    cam.Zoom(0.85)
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
    bone = _bone()
    b = bone.GetBounds()
    zmid = (b[4] + b[5]) / 2
    origin = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, zmid)

    # Wider bounds so displaced states stay framed identically.
    view = (b[0], b[1], b[2], b[3], b[4] - 10, b[5] + 16)

    _render([bone], os.path.join(OUT, "sim_A_intact.png"),
            "1. Intact bone", view)

    upper, lower = simulation.osteotomy_cut(bone, origin, (0, 0, 1))
    _render([upper, lower], os.path.join(OUT, "sim_B_osteotomy.png"),
            "2. Osteotomy: two fragments", view)

    for tag, dz, label in [
        ("C_displaced", 12.0, "3. Displaced"),
        ("D_reduced", 1.0, "4. Simulated reduction"),
        ("E_overreduced", -6.0, "5. Over-reduced"),
    ]:
        moved = simulation.transform_mesh(
            upper, simulation.build_transform(translation=(0.0, 0.0, dz)))
        q = simulation.reduction_quality(moved, lower)
        print(f"{label:26s} gap={q['gap_mm']:5.1f} mm  "
              f"overlap={q['overlap_mm3']:6.0f} mm3  -> {q['verdict']}")
        _render([moved, lower], os.path.join(OUT, f"sim_{tag}.png"),
                f"{label}: {q['verdict']}", view)


if __name__ == "__main__":
    main()
