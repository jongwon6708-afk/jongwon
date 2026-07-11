"""Surface reconstruction of bone from a CT volume.

Given a CT volume in Hounsfield Units, extract an isosurface at a bone
threshold using Flying Edges (a fast, modern Marching Cubes variant), then
optionally smooth and decimate the mesh for smoother interactive viewing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import vtk

from .dicom_loader import CTVolume
from .preprocessing import PreprocessParams, fill_enclosed_cavities, preprocess_volume

# Sensible default HU thresholds. Cortical bone is dense (>~700 HU); a lower
# threshold (~300) also captures trabecular bone but more soft-tissue noise.
DEFAULT_BONE_HU = 300.0
CORTICAL_BONE_HU = 700.0


@dataclass
class ReconstructionParams:
    threshold_hu: float = DEFAULT_BONE_HU
    # Lower smoothing preserves fine detail such as fracture lines; heavy
    # smoothing bridges the fracture cleft and hides it.
    smoothing_iterations: int = 8
    decimation: float = 0.25  # fraction of triangles to remove (0..1)
    largest_component_only: bool = False
    # Remove disconnected mesh fragments (noise specks, calcifications) whose
    # cell count is below this fraction of the largest region. 0 disables it.
    island_min_fraction: float = 0.02
    # Fill enclosed cavities so trabecular-bone interiors (e.g. femoral head)
    # appear solid instead of hollow. For visualisation only -- not for FEA.
    solid_fill: bool = False
    preprocess: PreprocessParams = field(default_factory=PreprocessParams)


def reconstruct_bone(volume: CTVolume, params: ReconstructionParams) -> vtk.vtkPolyData:
    """Reconstruct a bone surface mesh from *volume* at the given threshold.

    Each stage is materialised to a concrete ``vtkPolyData`` before the next, so
    intermediate filters can be released without leaving dangling pipeline
    connections (a common cause of crashes when chaining output ports).
    """
    image = preprocess_volume(volume, params.preprocess)

    surface = vtk.vtkFlyingEdges3D()
    if params.solid_fill:
        # Surface the filled binary mask at its mid-level instead of the HU.
        image = fill_enclosed_cavities(image, params.threshold_hu)
        surface.SetValue(0, 0.5)
    else:
        surface.SetValue(0, params.threshold_hu)
    surface.SetInputData(image)
    surface.ComputeNormalsOff()
    surface.ComputeScalarsOff()
    surface.Update()
    mesh = surface.GetOutput()

    if params.largest_component_only:
        connectivity = vtk.vtkPolyDataConnectivityFilter()
        connectivity.SetInputData(mesh)
        connectivity.SetExtractionModeToLargestRegion()
        connectivity.Update()
        mesh = connectivity.GetOutput()
    elif params.island_min_fraction > 0.0:
        mesh = _remove_small_islands(mesh, params.island_min_fraction)

    if params.decimation > 0.0 and mesh.GetNumberOfCells() > 0:
        decimate = vtk.vtkDecimatePro()
        decimate.SetInputData(mesh)
        decimate.SetTargetReduction(params.decimation)
        decimate.PreserveTopologyOn()
        decimate.Update()
        mesh = decimate.GetOutput()

    if params.smoothing_iterations > 0 and mesh.GetNumberOfCells() > 0:
        smoother = vtk.vtkWindowedSincPolyDataFilter()
        smoother.SetInputData(mesh)
        smoother.SetNumberOfIterations(params.smoothing_iterations)
        smoother.SetPassBand(0.1)
        smoother.NonManifoldSmoothingOn()
        smoother.NormalizeCoordinatesOn()
        smoother.Update()
        mesh = smoother.GetOutput()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(mesh)
    normals.SetFeatureAngle(60.0)
    normals.Update()

    return normals.GetOutput()


def _remove_small_islands(mesh: vtk.vtkPolyData, min_fraction: float) -> vtk.vtkPolyData:
    """Drop disconnected regions smaller than *min_fraction* of the largest.

    Removes calcification flecks and reconstruction noise that survive
    thresholding as tiny free-floating mesh fragments.
    """
    analyzer = vtk.vtkPolyDataConnectivityFilter()
    analyzer.SetInputData(mesh)
    analyzer.SetExtractionModeToAllRegions()
    analyzer.Update()

    n_regions = analyzer.GetNumberOfExtractedRegions()
    sizes = analyzer.GetRegionSizes()
    if n_regions <= 1:
        return mesh

    largest = max(sizes.GetValue(i) for i in range(n_regions))
    keep_threshold = largest * min_fraction

    selector = vtk.vtkPolyDataConnectivityFilter()
    selector.SetInputData(mesh)
    selector.SetExtractionModeToSpecifiedRegions()
    for i in range(n_regions):
        if sizes.GetValue(i) >= keep_threshold:
            selector.AddSpecifiedRegion(i)
    selector.Update()

    # SpecifiedRegions keeps all original points; clean removes orphaned ones.
    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(selector.GetOutput())
    cleaner.Update()
    return cleaner.GetOutput()


def export_mesh(mesh: vtk.vtkPolyData, path: str) -> None:
    """Write *mesh* to an STL or PLY/OBJ file (for 3D printing or reuse)."""
    lower = path.lower()
    if lower.endswith(".stl"):
        writer = vtk.vtkSTLWriter()
    elif lower.endswith(".ply"):
        writer = vtk.vtkPLYWriter()
    elif lower.endswith(".obj"):
        writer = vtk.vtkOBJWriter()
    else:
        raise ValueError(f"Unsupported mesh format: {path}")
    writer.SetFileName(path)
    writer.SetInputData(mesh)
    writer.Write()
