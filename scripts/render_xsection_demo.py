"""Demo: cross-section tool shows hollow vs solid interiors clearly.

Cuts a cortical-shell sphere (femoral-head analogue) with a capped plane. A
hollow shell shows a thin RING at the cut; a solid-filled bone shows a filled
DISC. This is what the exterior view cannot reveal.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.analysis import cross_section  # noqa: E402
from test_pipeline import make_hollow_sphere_phantom  # noqa: E402


def _actor(mesh, color=(0.9, 0.85, 0.75)):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(mesh)
    mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().BackfaceCullingOff()
    return actor


def _render(actor, path):
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.12, 0.13, 0.16)
    renderer.AddActor(actor)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(680, 680)
    win.AddRenderer(renderer)
    # Look straight down the cut normal (+y) at the cut face.
    renderer.GetActiveCamera().SetPosition(40, 130, 40)
    renderer.GetActiveCamera().SetFocalPoint(40, 40, 40)
    renderer.GetActiveCamera().SetViewUp(0, 0, 1)
    renderer.ResetCamera()
    win.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(path)
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()
    print("wrote", path)


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "demo_output")
    os.makedirs(out, exist_ok=True)
    volume = make_hollow_sphere_phantom()
    # Keep the -y half so its flat cut face points toward the +y camera.
    origin, normal = (40, 40, 40), (0, -1, 0)

    hollow = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=400, smoothing_iterations=6, solid_fill=False))
    _render(_actor(cross_section(hollow, origin, normal, capped=True)),
            os.path.join(out, "xsection_A_hollow.png"))

    solid = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=400, smoothing_iterations=6, solid_fill=True))
    _render(_actor(cross_section(solid, origin, normal, capped=True),
                   color=(0.8, 0.85, 0.7)),
            os.path.join(out, "xsection_B_solid.png"))


if __name__ == "__main__":
    main()
