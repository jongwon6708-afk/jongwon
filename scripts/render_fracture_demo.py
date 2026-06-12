"""Before/after demo of the cleanup + fracture-highlight improvements.

Renders the trauma phantom (bone + fracture + scanner table + calcification
flecks) two ways:

  A. Naive: low threshold, heavy smoothing, no cleanup -> the table and noise
     are present and the fracture line is smoothed over / hard to see.
  B. Improved: cortical threshold, light smoothing, denoise + table removal,
     with sharp fracture feature-edges overlaid in red.
"""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.preprocessing import PreprocessParams  # noqa: E402
from bonesim import analysis  # noqa: E402
from bonesim.camera_views import apply_anatomical_view  # noqa: E402
from test_pipeline import make_trauma_phantom  # noqa: E402


def _render(actors, path, size=(760, 760)):
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.12, 0.13, 0.16)
    for a in actors:
        renderer.AddActor(a)

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*size)
    win.AddRenderer(renderer)

    # Oblique-anterior view shows the mid-shaft fracture band.
    apply_anatomical_view(renderer, "Anterior (AP)")
    renderer.GetActiveCamera().Azimuth(25)
    renderer.GetActiveCamera().Elevation(15)
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


def _surface_actor(mesh, color=(0.92, 0.87, 0.78)):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(mesh)
    mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetSpecular(0.3)
    actor.GetProperty().SetSpecularPower(20)
    return actor


def main():
    out = os.path.join(os.path.dirname(__file__), "..", "demo_output")
    os.makedirs(out, exist_ok=True)
    volume = make_trauma_phantom()

    # A. Naive reconstruction.
    naive = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=400, smoothing_iterations=25, island_min_fraction=0.0,
        preprocess=PreprocessParams(median_denoise=False)))
    print(f"naive: {naive.GetNumberOfCells()} triangles")
    _render([_surface_actor(naive)], os.path.join(out, "fracture_A_naive.png"))

    # B. Improved: denoise + crop out the table (keeps both fracture fragments)
    #    + light smoothing + sharp fracture edges.
    improved = reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=500, smoothing_iterations=3, island_min_fraction=0.03,
        preprocess=PreprocessParams(
            median_denoise=True,
            crop_bounds=(-10.0, 80.0, -10.0, 60.0, -10.0, 50.0))))
    print(f"improved: {improved.GetNumberOfCells()} triangles")
    edges = analysis.fracture_feature_edges(improved, feature_angle=50.0)
    edge_actor = vtk.vtkActor()
    em = vtk.vtkPolyDataMapper()
    em.SetInputData(edges)
    em.ScalarVisibilityOff()
    edge_actor.SetMapper(em)
    edge_actor.GetProperty().SetColor(1.0, 0.15, 0.15)
    edge_actor.GetProperty().SetLineWidth(3.0)
    _render([_surface_actor(improved), edge_actor],
            os.path.join(out, "fracture_B_improved.png"))


if __name__ == "__main__":
    main()
