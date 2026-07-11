"""Demo: hollow trabecular interior (like a femoral head) vs solid-fill.

Reconstructs a cortical-shell sphere two ways and clips each with a plane so
the interior is visible:

  A. Default surface -> only a shell; the interior reads as hollow.
  B. Solid fill -> enclosed low-HU cavity is filled; interior is solid.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from test_pipeline import make_hollow_sphere_phantom  # noqa: E402


def _clipped_actor(mesh, color=(0.92, 0.87, 0.78)):
    plane = vtk.vtkPlane()
    plane.SetOrigin(40, 40, 40)
    plane.SetNormal(0, 1, 0)  # cut to reveal the interior
    clipper = vtk.vtkClipPolyData()
    clipper.SetInputData(mesh)
    clipper.SetClipFunction(plane)
    clipper.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(clipper.GetOutputPort())
    mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetSpecular(0.3)
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
    renderer.GetActiveCamera().SetPosition(40, -120, 60)
    renderer.GetActiveCamera().SetFocalPoint(40, 40, 40)
    renderer.GetActiveCamera().SetViewUp(0, 0, 1)
    renderer.ResetCameraClippingRange()
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

    hollow = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=400, smoothing_iterations=8, solid_fill=False))
    _render(_clipped_actor(hollow), os.path.join(out, "head_A_hollow.png"))

    solid = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=400, smoothing_iterations=8, solid_fill=True))
    _render(_clipped_actor(solid, color=(0.85, 0.8, 0.72)),
            os.path.join(out, "head_B_solid.png"))


if __name__ == "__main__":
    main()
