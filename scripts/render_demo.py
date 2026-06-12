"""Offscreen render demo: prove the reconstruction pipeline produces a 3D bone.

Builds a synthetic cortical-bone phantom (a hollow cylinder with a drilled
hole), reconstructs the surface, and renders it from several anatomical
angles to PNG files -- no display required. This mirrors exactly what the GUI
does, just rendered offscreen so it can run in a headless CLI environment.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.camera_views import apply_anatomical_view  # noqa: E402

# Reuse the phantom builder from the tests.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))
from test_pipeline import make_phantom  # noqa: E402


def render_views(out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)

    volume = make_phantom()
    mesh = reconstruct_bone(volume, ReconstructionParams(threshold_hu=400.0))
    print(f"Reconstructed mesh: {mesh.GetNumberOfPoints()} points, "
          f"{mesh.GetNumberOfCells()} triangles")

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(mesh)
    mapper.ScalarVisibilityOff()

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(0.92, 0.87, 0.78)
    actor.GetProperty().SetSpecular(0.3)
    actor.GetProperty().SetSpecularPower(20)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.12, 0.13, 0.16)
    renderer.AddActor(actor)

    render_window = vtk.vtkRenderWindow()
    render_window.SetOffScreenRendering(1)
    render_window.SetSize(700, 700)
    render_window.AddRenderer(renderer)

    paths = []
    for name in ["Anterior (AP)", "Left", "Superior (Axial)"]:
        apply_anatomical_view(renderer, name)
        render_window.Render()

        w2i = vtk.vtkWindowToImageFilter()
        w2i.SetInput(render_window)
        w2i.Update()

        safe = name.split(" ")[0].lower()
        path = os.path.join(out_dir, f"phantom_{safe}.png")
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(path)
        writer.SetInputConnection(w2i.GetOutputPort())
        writer.Write()
        paths.append(path)
        print(f"Wrote {path}")
    return paths


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "demo_output")
    render_views(out)
