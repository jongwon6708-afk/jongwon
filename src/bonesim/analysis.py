"""Fracture visualisation and comparison against standard/reference anatomy.

Two groups of tools:

Fracture highlighting
  * curvature colouring -- fracture clefts are high-curvature ridges/valleys,
    so mapping surface curvature to colour makes the fracture line "pop".
  * feature edges -- extract sharp creases (the crack rim) as a line set that
    can be overlaid in red on the bone.

Comparison with a standard
  * mirror_mesh -- reflect a healthy contralateral bone to act as the patient's
    own normative "standard" (a common orthopaedic trick).
  * register_icp -- rigidly align a mesh onto a reference with Iterative
    Closest Point.
  * surface_distance -- per-point distance from the bone to the reference,
    stored as scalars for a deviation heat-map.
"""

from __future__ import annotations

import vtk


# --------------------------------------------------------------- fractures
def curvature_scalars(mesh: vtk.vtkPolyData, kind: str = "maximum") -> vtk.vtkPolyData:
    """Return a copy of *mesh* with per-point curvature stored as scalars.

    kind: "maximum" (sharpest), "mean", "gaussian", or "minimum".
    High |curvature| concentrates along fracture lines and sharp cortical edges.
    """
    curv = vtk.vtkCurvatures()
    curv.SetInputData(mesh)
    mapping = {
        "minimum": curv.SetCurvatureTypeToMinimum,
        "maximum": curv.SetCurvatureTypeToMaximum,
        "gaussian": curv.SetCurvatureTypeToGaussian,
        "mean": curv.SetCurvatureTypeToMean,
    }
    mapping.get(kind, curv.SetCurvatureTypeToMaximum)()
    curv.Update()
    return curv.GetOutput()


def fracture_feature_edges(
    mesh: vtk.vtkPolyData, feature_angle: float = 60.0
) -> vtk.vtkPolyData:
    """Extract sharp creases as a line set highlighting fracture rims/edges."""
    edges = vtk.vtkFeatureEdges()
    edges.SetInputData(mesh)
    edges.BoundaryEdgesOn()
    edges.FeatureEdgesOn()
    edges.SetFeatureAngle(feature_angle)
    edges.NonManifoldEdgesOff()
    edges.ManifoldEdgesOff()
    edges.Update()
    return edges.GetOutput()


# -------------------------------------------------------------- comparison
def mirror_mesh(mesh: vtk.vtkPolyData, axis: str = "x") -> vtk.vtkPolyData:
    """Mirror *mesh* across the given world axis (for contralateral comparison).

    Reflection flips triangle winding, so normals are re-computed afterwards.
    """
    scale = {"x": (-1, 1, 1), "y": (1, -1, 1), "z": (1, 1, -1)}[axis]
    transform = vtk.vtkTransform()
    transform.Scale(*scale)

    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetInputData(mesh)
    tf.SetTransform(transform)
    tf.Update()

    reverse = vtk.vtkReverseSense()
    reverse.SetInputConnection(tf.GetOutputPort())
    reverse.ReverseCellsOn()
    reverse.ReverseNormalsOn()
    reverse.Update()
    return reverse.GetOutput()


def register_icp(
    source: vtk.vtkPolyData, target: vtk.vtkPolyData, iterations: int = 100
) -> tuple[vtk.vtkPolyData, vtk.vtkMatrix4x4]:
    """Rigidly align *source* onto *target* with ICP.

    Returns the transformed source mesh and the 4x4 transform matrix.
    """
    icp = vtk.vtkIterativeClosestPointTransform()
    icp.SetSource(source)
    icp.SetTarget(target)
    icp.GetLandmarkTransform().SetModeToRigidBody()
    icp.SetMaximumNumberOfIterations(iterations)
    icp.StartByMatchingCentroidsOn()
    icp.Modified()
    icp.Update()

    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetInputData(source)
    tf.SetTransform(icp)
    tf.Update()
    return tf.GetOutput(), icp.GetMatrix()


def surface_distance(
    mesh: vtk.vtkPolyData, reference: vtk.vtkPolyData, signed: bool = False
) -> vtk.vtkPolyData:
    """Per-point distance from *mesh* to *reference*, stored as scalars (mm).

    Use the result with a blue->red lookup table for a deviation heat-map that
    shows where the patient's bone departs from the standard.
    """
    dist = vtk.vtkDistancePolyDataFilter()
    dist.SetInputData(0, mesh)
    dist.SetInputData(1, reference)
    dist.SetSignedDistance(signed)
    dist.Update()
    return dist.GetOutput()
