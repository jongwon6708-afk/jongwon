"""Headless tests for preprocessing, fracture highlighting, and comparison."""

import os
import sys

import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.preprocessing import PreprocessParams  # noqa: E402
from bonesim import analysis  # noqa: E402
from test_pipeline import make_trauma_phantom  # noqa: E402


def _count(mesh):
    return mesh.GetNumberOfPoints(), mesh.GetNumberOfCells()


def test_island_removal_reduces_fragments():
    volume = make_trauma_phantom()
    base = ReconstructionParams(threshold_hu=500.0, smoothing_iterations=0,
                                decimation=0.0, island_min_fraction=0.0,
                                preprocess=PreprocessParams(median_denoise=False))
    cleaned = ReconstructionParams(threshold_hu=500.0, smoothing_iterations=0,
                                   decimation=0.0, island_min_fraction=0.05,
                                   preprocess=PreprocessParams(median_denoise=False))
    raw_mesh = reconstruct_bone(volume, base)
    clean_mesh = reconstruct_bone(volume, cleaned)
    # Removing calcification islands should not increase the cell count.
    assert _count(clean_mesh)[1] <= _count(raw_mesh)[1]
    assert clean_mesh.GetNumberOfCells() > 0


def test_crop_removes_table_keeps_fragments():
    volume = make_trauma_phantom()
    base = ReconstructionParams(threshold_hu=500.0, smoothing_iterations=0,
                                decimation=0.0, island_min_fraction=0.0,
                                preprocess=PreprocessParams(median_denoise=False))
    uncropped = reconstruct_bone(volume, base)
    assert uncropped.GetBounds()[3] > 62.0  # table band present near y~64mm

    # Crop out the table (y above 60mm) while keeping the whole bone.
    cropped_params = ReconstructionParams(
        threshold_hu=500.0, smoothing_iterations=0, decimation=0.0,
        island_min_fraction=0.0,
        preprocess=PreprocessParams(
            median_denoise=False,
            crop_bounds=(-10.0, 80.0, -10.0, 60.0, -10.0, 50.0),
        ),
    )
    cropped = reconstruct_bone(volume, cropped_params)
    cb = cropped.GetBounds()
    assert cropped.GetNumberOfCells() > 0
    assert cb[3] < 62.0          # table removed
    # Both fracture fragments survive -> mesh still spans most of the z axis.
    assert cb[5] - cb[4] > 20.0


def test_curvature_scalars_present():
    volume = make_trauma_phantom()
    mesh = reconstruct_bone(volume, ReconstructionParams(threshold_hu=500.0))
    colored = analysis.curvature_scalars(mesh, "maximum")
    assert colored.GetPointData().GetScalars() is not None


def test_feature_edges_find_fracture():
    volume = make_trauma_phantom()
    mesh = reconstruct_bone(volume, ReconstructionParams(threshold_hu=500.0,
                                                         smoothing_iterations=0))
    edges = analysis.fracture_feature_edges(mesh, feature_angle=50.0)
    assert edges.GetNumberOfCells() > 0  # crack rim produces edges


def test_mirror_and_distance():
    volume = make_trauma_phantom()
    mesh = reconstruct_bone(volume, ReconstructionParams(threshold_hu=500.0))
    mirrored = analysis.mirror_mesh(mesh, "x")
    assert mirrored.GetNumberOfPoints() == mesh.GetNumberOfPoints()

    aligned, matrix = analysis.register_icp(mirrored, mesh, iterations=50)
    assert isinstance(matrix, vtk.vtkMatrix4x4)

    dist = analysis.surface_distance(aligned, mesh)
    scalars = dist.GetPointData().GetScalars()
    assert scalars is not None
    assert scalars.GetNumberOfTuples() > 0


if __name__ == "__main__":
    test_island_removal_reduces_fragments()
    test_crop_removes_table_keeps_fragments()
    test_curvature_scalars_present()
    test_feature_edges_find_fracture()
    test_mirror_and_distance()
    print("All analysis tests passed.")
