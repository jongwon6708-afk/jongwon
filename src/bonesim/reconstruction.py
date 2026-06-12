"""Surface reconstruction of bone from a CT volume.

Given a CT volume in Hounsfield Units, extract an isosurface at a bone
threshold using Flying Edges (a fast, modern Marching Cubes variant), then
optionally smooth and decimate the mesh for smoother interactive viewing.
"""

from __future__ import annotations

from dataclasses import dataclass

import vtk

from .dicom_loader import CTVolume

# Sensible default HU thresholds. Cortical bone is dense (>~700 HU); a lower
# threshold (~300) also captures trabecular bone but more soft-tissue noise.
DEFAULT_BONE_HU = 300.0
CORTICAL_BONE_HU = 700.0


@dataclass
class ReconstructionParams:
    threshold_hu: float = DEFAULT_BONE_HU
    smoothing_iterations: int = 15
    decimation: float = 0.25  # fraction of triangles to remove (0..1)
    largest_component_only: bool = False


def reconstruct_bone(volume: CTVolume, params: ReconstructionParams) -> vtk.vtkPolyData:
    """Reconstruct a bone surface mesh from *volume* at the given threshold."""
    surface = vtk.vtkFlyingEdges3D()
    surface.SetInputData(volume.image)
    surface.SetValue(0, params.threshold_hu)
    surface.ComputeNormalsOn()
    surface.ComputeScalarsOff()

    pipeline_output = surface.GetOutputPort()

    if params.largest_component_only:
        connectivity = vtk.vtkPolyDataConnectivityFilter()
        connectivity.SetInputConnection(pipeline_output)
        connectivity.SetExtractionModeToLargestRegion()
        pipeline_output = connectivity.GetOutputPort()

    if params.decimation > 0.0:
        decimate = vtk.vtkDecimatePro()
        decimate.SetInputConnection(pipeline_output)
        decimate.SetTargetReduction(params.decimation)
        decimate.PreserveTopologyOn()
        pipeline_output = decimate.GetOutputPort()

    if params.smoothing_iterations > 0:
        smoother = vtk.vtkWindowedSincPolyDataFilter()
        smoother.SetInputConnection(pipeline_output)
        smoother.SetNumberOfIterations(params.smoothing_iterations)
        smoother.SetPassBand(0.1)
        smoother.NonManifoldSmoothingOn()
        smoother.NormalizeCoordinatesOn()
        pipeline_output = smoother.GetOutputPort()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(pipeline_output)
    normals.SetFeatureAngle(60.0)
    normals.Update()

    return normals.GetOutput()


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
