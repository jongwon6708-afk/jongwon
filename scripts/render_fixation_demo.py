"""Demo: simulate a fixation construct and read out whether it works.

Builds a fractured bone, reduces it, then applies a lag screw and a plate, and
prints the quantitative checks that decide whether the plan is acceptable:
screw purchase, whether the lag screw actually crosses the fracture, screw-to-
screw clearance, and plate standoff from the cortex.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from bonesim import fixation, implants, simulation  # noqa: E402
from test_simulation import _bone  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "demo_output")
BONE_COLOR = (0.92, 0.87, 0.78)
FRAG_COLOR = (0.62, 0.80, 0.93)
METAL_COLOR = (0.75, 0.76, 0.80)
LAG_COLOR = (0.95, 0.55, 0.25)


def _actor(mesh, color, opacity=1.0):
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(mesh)
    m.ScalarVisibilityOff()
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetOpacity(opacity)
    a.GetProperty().SetSpecular(0.4)
    a.GetProperty().SetSpecularPower(30)
    return a


def _render(actors, path, label, view):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.12, 0.13, 0.16)
    for a in actors:
        ren.AddActor(a)
    txt = vtk.vtkTextActor()
    txt.SetInput(label)
    txt.GetTextProperty().SetFontSize(21)
    txt.GetTextProperty().SetColor(1, 1, 1)
    txt.SetPosition(14, 12)
    ren.AddActor2D(txt)

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(600, 600)
    win.AddRenderer(ren)
    cx = (view[0] + view[1]) / 2
    cy = (view[2] + view[3]) / 2
    cz = (view[4] + view[5]) / 2
    cam = ren.GetActiveCamera()
    cam.SetPosition(cx + 40, cy - 190, cz + 30)
    cam.SetFocalPoint(cx, cy, cz)
    cam.SetViewUp(0, 0, 1)
    ren.ResetCamera()
    cam.Zoom(0.9)
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
    cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
    zmid = (b[4] + b[5]) / 2
    view = (b[0] - 12, b[1] + 12, b[2] - 20, b[3] + 12, b[4] - 6, b[5] + 6)
    fracture_plane = ((cx, cy, zmid), (0.0, 0.0, 1.0))

    upper, lower = simulation.osteotomy_cut(bone, *fracture_plane)

    # --- Lag screw across the fracture -------------------------------------
    entry = (cx, cy, zmid + 11.0)
    target = (cx, cy, zmid - 11.0)
    needed = implants.length_for_trajectory(entry, target)
    lag = implants.place_along(
        implants.make_screw(
            implants.ScrewSpec(length_mm=needed, diameter_mm=4.0),
            spacing=0.3),
        entry, target)
    print(f"lag screw length chosen: {needed:.0f} mm")

    purchase = fixation.screw_purchase(lag, bone, spacing=0.4)
    lags = fixation.crosses_plane(lag, *fracture_plane)
    print(f"  purchase in bone : {purchase['purchase_fraction'] * 100:.0f}%")
    print(f"  crosses fracture : {lags}  <- required for a lag screw")

    _render(
        [_actor(upper, BONE_COLOR, 0.45), _actor(lower, FRAG_COLOR, 0.45),
         _actor(lag, LAG_COLOR)],
        os.path.join(OUT, "fix_A_lagscrew.png"),
        f"Lag screw {needed:.0f}mm | purchase "
        f"{purchase['purchase_fraction'] * 100:.0f}% | lags={lags}", view)

    # --- Neutralisation plate on the lateral cortex ------------------------
    plate_mesh = implants.make_plate(
        implants.PlateSpec(length_mm=34.0, width_mm=11.0, thickness_mm=3.0,
                           hole_count=4, hole_diameter_mm=4.0),
        spacing=0.4)
    plate = implants.place_along(
        plate_mesh, (cx, b[2] - 1.5, zmid + 17.0), (cx, b[2] - 1.5, zmid - 17.0))
    standoff = fixation.plate_standoff(plate, bone)
    print(f"  plate standoff   : min {standoff['min_mm']:.1f} mm, "
          f"mean {standoff['mean_mm']:.1f} mm")

    # Two cortical screws through the plate.
    screws = []
    for dz in (11.0, -11.0):
        s_entry = (cx, b[2] - 2.0, zmid + dz)
        s_target = (cx, b[3], zmid + dz)
        s_len = implants.length_for_trajectory(s_entry, s_target) * 0.85
        screws.append(implants.place_along(
            implants.make_screw(
                implants.ScrewSpec(length_mm=s_len, diameter_mm=3.5),
                spacing=0.35),
            s_entry, s_target))

    report = fixation.construct_report(
        bone, screws + [lag], plate=plate, fracture_plane=fracture_plane)
    for entry_r in report["screws"]:
        print(f"  screw {entry_r['index']}: purchase "
              f"{entry_r['purchase_fraction'] * 100:3.0f}%  "
              f"lags={entry_r.get('lags_fracture')}"
              + (f"  CONFLICTS with {entry_r['conflicts_with']}"
                 if "conflicts_with" in entry_r else ""))

    _render(
        [_actor(upper, BONE_COLOR, 0.4), _actor(lower, FRAG_COLOR, 0.4),
         _actor(plate, METAL_COLOR), _actor(lag, LAG_COLOR)]
        + [_actor(s, METAL_COLOR) for s in screws],
        os.path.join(OUT, "fix_B_construct.png"),
        f"Plate + 2 screws + lag | standoff {standoff['min_mm']:.1f}mm", view)


if __name__ == "__main__":
    main()
