"""Quantitative checks on a simulated fixation construct.

These are the questions a surgeon asks of a plan before committing to it, and
the reason the simulation exists at all:

  * **Does the screw hold?**  How much of it is actually in bone
    (:func:`screw_purchase`), and does it engage the far cortex?
  * **Does it damage anything?**  Does it breach the articular surface
    (:func:`articular_breach`) or leave the bone entirely?
  * **Is it a lag screw?**  A lag screw only compresses if it crosses the
    fracture plane (:func:`crosses_plane`).
  * **Does the plate sit down?**  Standoff between the plate's under-surface
    and the cortex (:func:`plate_standoff`) -- the number that decides whether
    a pre-contoured plate fits or has to be bent.

Volumes are measured by voxel sampling on a shared grid rather than by surface
booleans, which crash on the coplanar geometry implants produce.
"""

from __future__ import annotations

import vtk

from .simulation import overlap_volume

Vec3 = tuple[float, float, float]


# ------------------------------------------------------------------- screws
def screw_purchase(
    screw: vtk.vtkPolyData, bone: vtk.vtkPolyData, spacing: float = 0.5
) -> dict:
    """How much of a placed screw lies inside bone.

    Returns the intersecting volume in mm^3 and it as a fraction of the screw.
    A screw that is mostly outside bone is either too long, aimed into a void,
    or has cut out.
    """
    screw_volume = mesh_volume(screw)
    if screw_volume <= 0.0:
        raise ValueError("Screw mesh has no volume")
    inside = overlap_volume(screw, bone, spacing)
    return {
        "screw_volume_mm3": screw_volume,
        "in_bone_mm3": inside,
        "purchase_fraction": inside / screw_volume,
    }


def articular_breach(
    screw: vtk.vtkPolyData, articular_surface: vtk.vtkPolyData
) -> dict:
    """Distance from the screw to a joint surface, and whether it breaches.

    *articular_surface* is the patch of the reconstruction representing the
    joint (isolate it with the editing tools). A negative clearance means the
    screw has passed through it -- a screw in the joint.
    """
    clearance = min_surface_distance(screw, articular_surface)
    return {
        "clearance_mm": clearance,
        "breached": clearance <= 0.0,
    }


def crosses_plane(
    screw: vtk.vtkPolyData, origin: Vec3, normal: Vec3
) -> bool:
    """True if the screw has material on both sides of a plane.

    With the fracture plane as the argument, this is the defining property of a
    **lag screw**: it must cross the fracture to compress it. A screw entirely
    within one fragment cannot lag, however well it is seated.
    """
    plane = vtk.vtkPlane()
    plane.SetOrigin(*origin)
    plane.SetNormal(*normal)

    positive = negative = False
    for i in range(screw.GetNumberOfPoints()):
        value = plane.EvaluateFunction(screw.GetPoint(i))
        if value > 1e-6:
            positive = True
        elif value < -1e-6:
            negative = True
        if positive and negative:
            return True
    return False


def screw_screw_conflict(
    a: vtk.vtkPolyData, b: vtk.vtkPolyData, clearance_mm: float = 1.0
) -> dict:
    """Whether two screws collide or run closer than *clearance_mm*."""
    distance = min_surface_distance(a, b)
    return {
        "distance_mm": distance,
        "collides": distance <= 0.0,
        "too_close": distance < clearance_mm,
    }


# ------------------------------------------------------------------- plates
def plate_standoff(
    plate: vtk.vtkPolyData, bone: vtk.vtkPolyData, sample_stride: int = 1
) -> dict:
    """Gap between a plate and the bone surface beneath it.

    Reports the minimum, mean and maximum distance from the plate's vertices to
    the nearest bone surface. A pre-contoured plate that stands off the cortex
    by several millimetres will either need bending or will pull the fracture
    out of alignment when the screws are tightened.
    """
    if plate.GetNumberOfPoints() == 0 or bone.GetNumberOfPoints() == 0:
        raise ValueError("Cannot measure standoff against an empty mesh")

    locator = vtk.vtkPointLocator()
    locator.SetDataSet(bone)
    locator.BuildLocator()

    distances = []
    for i in range(0, plate.GetNumberOfPoints(), max(1, sample_stride)):
        p = plate.GetPoint(i)
        q = bone.GetPoint(locator.FindClosestPoint(p))
        distances.append(
            ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2) ** 0.5
        )
    return {
        "min_mm": min(distances),
        "mean_mm": sum(distances) / len(distances),
        "max_mm": max(distances),
    }


# ------------------------------------------------------------------ helpers
def mesh_volume(mesh: vtk.vtkPolyData) -> float:
    """Enclosed volume of a closed surface, in mm^3."""
    triangles = vtk.vtkTriangleFilter()
    triangles.SetInputData(mesh)
    triangles.Update()
    properties = vtk.vtkMassProperties()
    properties.SetInputData(triangles.GetOutput())
    return properties.GetVolume()


def min_surface_distance(a: vtk.vtkPolyData, b: vtk.vtkPolyData) -> float:
    """Smallest vertex-to-surface distance between two meshes, in mm.

    Returns a negative value when they interpenetrate, so callers can treat
    "touching" and "through" differently.
    """
    if a.GetNumberOfPoints() == 0 or b.GetNumberOfPoints() == 0:
        raise ValueError("Cannot measure distance to an empty mesh")

    implicit = vtk.vtkImplicitPolyDataDistance()
    implicit.SetInput(b)
    return min(
        implicit.EvaluateFunction(a.GetPoint(i))
        for i in range(a.GetNumberOfPoints())
    )


def construct_report(
    bone: vtk.vtkPolyData,
    screws: list[vtk.vtkPolyData],
    plate: vtk.vtkPolyData | None = None,
    fracture_plane: tuple[Vec3, Vec3] | None = None,
    articular_surface: vtk.vtkPolyData | None = None,
) -> dict:
    """Assemble the per-screw and plate findings into one plan readout."""
    report: dict = {"screws": [], "plate": None}

    for index, screw in enumerate(screws):
        entry = {"index": index}
        entry.update(screw_purchase(screw, bone))
        if fracture_plane is not None:
            entry["lags_fracture"] = crosses_plane(screw, *fracture_plane)
        if articular_surface is not None:
            entry.update(articular_breach(screw, articular_surface))
        for other_index, other in enumerate(screws):
            if other_index <= index:
                continue
            conflict = screw_screw_conflict(screw, other)
            if conflict["too_close"]:
                entry.setdefault("conflicts_with", []).append(other_index)
        report["screws"].append(entry)

    if plate is not None:
        report["plate"] = plate_standoff(plate, bone)
    return report
