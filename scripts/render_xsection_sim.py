"""Cross-section simulation test: choose a cutting plane and see inside.

Uses the trauma phantom (a bone with a transverse fracture). It:
  1. shows the intact exterior for reference,
  2. cuts SAGITTALLY along the shaft so the fracture line is seen running
     through the cortex internally,
  3. sweeps an AXIAL cut through the fracture level to show the gap appear.

This verifies the cross-section tool cuts at an arbitrary chosen plane/position
and reveals internal structure (here: the fracture) that the exterior hides.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.analysis import cross_section  # noqa: E402
from test_pipeline import make_trauma_phantom  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "demo_output")


def _actor(mesh, color=(0.88, 0.83, 0.72)):
    m = vtk.vtkPolyDataMapper()
    m.SetInputData(mesh)
    m.ScalarVisibilityOff()
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetSpecular(0.2)
    a.GetProperty().BackfaceCullingOff()
    return a


def _render(mesh, path, cam_pos, focal, view_up=(0, 0, 1), label=""):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.12, 0.13, 0.16)
    ren.AddActor(_actor(mesh))
    if label:
        txt = vtk.vtkTextActor()
        txt.SetInput(label)
        txt.GetTextProperty().SetFontSize(26)
        txt.GetTextProperty().SetColor(1, 1, 1)
        txt.SetPosition(20, 20)
        ren.AddActor2D(txt)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(560, 560)
    win.AddRenderer(ren)
    cam = ren.GetActiveCamera()
    cam.SetPosition(*cam_pos)
    cam.SetFocalPoint(*focal)
    cam.SetViewUp(*view_up)
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
    volume = make_trauma_phantom()
    # Solid fill so cut faces read as filled bone; crop out the table.
    from bonesim.preprocessing import PreprocessParams
    params = ReconstructionParams(
        threshold_hu=500, smoothing_iterations=4, solid_fill=True,
        preprocess=PreprocessParams(
            median_denoise=True,
            crop_bounds=(-10, 80, -10, 60, -10, 50)),
    )
    bone = reconstruct_bone(volume, params)
    b = bone.GetBounds()
    cx = (b[0] + b[1]) / 2
    cy = (b[2] + b[3]) / 2
    cz = (b[4] + b[5]) / 2
    print(f"bone bounds z:[{b[4]:.1f},{b[5]:.1f}]  fracture near z={cz:.1f}")

    # 1) Intact exterior (fracture barely visible from outside).
    _render(bone, os.path.join(OUT, "sim_1_exterior.png"),
            cam_pos=(cx, -160, cz), focal=(cx, cy, cz), view_up=(0, 0, 1),
            label="1. Exterior (intact view)")

    # 2) Sagittal cut (X normal) through the centre -> see the shaft interior
    #    with the fracture crossing it.
    sag = cross_section(bone, (cx, cy, cz), (-1, 0, 0), capped=True)
    _render(sag, os.path.join(OUT, "sim_2_sagittal.png"),
            cam_pos=(160, cy, cz), focal=(cx, cy, cz), view_up=(0, 0, 1),
            label="2. Sagittal cut - fracture inside")

    # 3) Axial sweep: three cuts stepping through the fracture level.
    for i, frac in enumerate([0.40, 0.50, 0.60]):
        zc = b[4] + (b[5] - b[4]) * frac
        axial = cross_section(bone, (cx, cy, zc), (0, 0, -1), capped=True)
        _render(axial, os.path.join(OUT, f"sim_3_axial_{i}.png"),
                cam_pos=(cx, cy, 160), focal=(cx, cy, zc), view_up=(0, 1, 0),
                label=f"3. Axial sweep @ z={zc:.0f}mm")


if __name__ == "__main__":
    main()
