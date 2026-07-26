"""Osteotomy and fragment repositioning -- the simulation half of the tool.

This is what turns a measurement viewer into a planning simulator:

  * :func:`osteotomy_cut` splits a bone along a plane into two closed
    fragments -- the virtual saw cut.
  * :func:`build_transform` / :func:`transform_mesh` reposition a fragment
    (translate + rotate about its own centroid), which is how a reduction or a
    corrective osteotomy is simulated.
  * :func:`transform_point` moves landmarks with the fragment they sit on, so
    the radiographic measurements re-derive automatically on the simulated
    result. That coupling is the point: it is what lets you ask "did my plan
    reach the target angle?" rather than just looking at a picture.

Rotations are applied about the fragment centroid rather than the world
origin, because a surgeon thinks in terms of "angulate this fragment by 10
degrees", not "rotate it about the scanner isocentre".
"""

from __future__ import annotations

import vtk

Vec3 = tuple[float, float, float]


# ---------------------------------------------------------------- osteotomy
def osteotomy_cut(
    mesh: vtk.vtkPolyData, origin: Vec3, normal: Vec3
) -> tuple[vtk.vtkPolyData, vtk.vtkPolyData]:
    """Cut *mesh* with a plane into two capped fragments.

    Returns ``(positive_side, negative_side)`` relative to *normal*. Both come
    back closed (the cut face is capped), so each fragment is a solid body that
    can be repositioned and measured -- the same reason a real osteotomy leaves
    two bone ends rather than an open shell.
    """
    def _half(flip: bool) -> vtk.vtkPolyData:
        plane = vtk.vtkPlane()
        plane.SetOrigin(*origin)
        plane.SetNormal(*[-n if flip else n for n in normal])
        planes = vtk.vtkPlaneCollection()
        planes.AddItem(plane)
        clip = vtk.vtkClipClosedSurface()
        clip.SetInputData(mesh)
        clip.SetClippingPlanes(planes)
        clip.GenerateFacesOn()
        clip.GenerateOutlineOff()
        clip.Update()
        return clip.GetOutput()

    return _half(flip=False), _half(flip=True)


# ---------------------------------------------------------------- transform
def centroid(mesh: vtk.vtkPolyData) -> Vec3:
    """Centre of the mesh bounding box, used as the default rotation pivot."""
    b = mesh.GetBounds()
    return ((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, (b[4] + b[5]) / 2.0)


def build_transform(
    translation: Vec3 = (0.0, 0.0, 0.0),
    rotation_xyz: Vec3 = (0.0, 0.0, 0.0),
    pivot: Vec3 | None = None,
) -> vtk.vtkTransform:
    """Build a rigid transform: rotate about *pivot*, then translate.

    *rotation_xyz* is in degrees about the world X, Y and Z axes, applied in
    that order. With *pivot* given, the fragment spins about that point (its
    own centroid, normally) instead of about the world origin.
    """
    transform = vtk.vtkTransform()
    transform.PostMultiply()
    if pivot is not None:
        transform.Translate(-pivot[0], -pivot[1], -pivot[2])
    transform.RotateX(rotation_xyz[0])
    transform.RotateY(rotation_xyz[1])
    transform.RotateZ(rotation_xyz[2])
    if pivot is not None:
        transform.Translate(*pivot)
    transform.Translate(*translation)
    return transform


def transform_mesh(
    mesh: vtk.vtkPolyData, transform: vtk.vtkTransform
) -> vtk.vtkPolyData:
    """Apply *transform* to a mesh, returning a new mesh."""
    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetInputData(mesh)
    tf.SetTransform(transform)
    tf.Update()
    return tf.GetOutput()


def transform_point(point: Vec3, transform: vtk.vtkTransform) -> Vec3:
    """Apply *transform* to a single point (used to carry landmarks along)."""
    return tuple(transform.TransformPoint(point))


def transform_landmarks(
    landmarks: dict, names: set[str], transform: vtk.vtkTransform
) -> dict:
    """Return landmark positions with *names* moved by *transform*.

    ``landmarks`` maps name -> position tuple. Names not listed are returned
    unchanged, which is how a fragment carries only its own landmarks.
    """
    moved = {}
    for name, position in landmarks.items():
        moved[name] = (
            transform_point(position, transform) if name in names else position
        )
    return moved


# ------------------------------------------------------------------ metrics
def fragment_gap(a: vtk.vtkPolyData, b: vtk.vtkPolyData) -> float:
    """Smallest distance in mm between two fragment surfaces.

    After a simulated reduction this is the residual fracture gap -- one of the
    numbers that decides whether the plan is acceptable.
    """
    if a.GetNumberOfPoints() == 0 or b.GetNumberOfPoints() == 0:
        raise ValueError("Cannot measure a gap against an empty fragment")

    locator = vtk.vtkPointLocator()
    locator.SetDataSet(b)
    locator.BuildLocator()

    best = float("inf")
    for i in range(a.GetNumberOfPoints()):
        p = a.GetPoint(i)
        j = locator.FindClosestPoint(p)
        q = b.GetPoint(j)
        d = ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2) ** 0.5
        if d < best:
            best = d
    return best


def _voxelize(
    mesh: vtk.vtkPolyData, bounds: tuple, spacing: float
) -> "object":
    """Rasterise a closed surface into a binary numpy array on a fixed grid."""
    import numpy as np
    from vtk.util import numpy_support

    dims = [
        max(2, int((bounds[i * 2 + 1] - bounds[i * 2]) / spacing) + 1)
        for i in range(3)
    ]
    image = vtk.vtkImageData()
    image.SetOrigin(bounds[0], bounds[2], bounds[4])
    image.SetSpacing(spacing, spacing, spacing)
    image.SetDimensions(*dims)
    image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    image.GetPointData().GetScalars().Fill(1)

    stencil = vtk.vtkPolyDataToImageStencil()
    stencil.SetInputData(mesh)
    stencil.SetOutputOrigin(image.GetOrigin())
    stencil.SetOutputSpacing(image.GetSpacing())
    stencil.SetOutputWholeExtent(image.GetExtent())
    stencil.Update()

    painter = vtk.vtkImageStencil()
    painter.SetInputData(image)
    painter.SetStencilData(stencil.GetOutput())
    painter.ReverseStencilOff()
    painter.SetBackgroundValue(0)
    painter.Update()

    array = numpy_support.vtk_to_numpy(
        painter.GetOutput().GetPointData().GetScalars())
    return np.asarray(array, dtype=bool)


def overlap_volume(
    a: vtk.vtkPolyData, b: vtk.vtkPolyData, spacing: float = 1.0
) -> float:
    """Volume in mm^3 where two closed fragments interpenetrate.

    A surface gap of zero is ambiguous: two fragments may be perfectly reduced
    *or* driven into each other. Bone cannot interpenetrate, so this separates
    the two cases.

    Measured by rasterising both fragments onto a shared grid and counting
    voxels inside both. A boolean-intersection filter would be the obvious
    approach but is unreliable here: fragments produced by the same cut share a
    coplanar face, which makes VTK's boolean operation crash. Sampling is
    slower but robust, and 1 mm voxels are well below any clinically relevant
    overlap.
    """
    if a.GetNumberOfPoints() == 0 or b.GetNumberOfPoints() == 0:
        return 0.0

    ba, bb = a.GetBounds(), b.GetBounds()
    # Only the region where the two bounding boxes intersect can overlap.
    region = []
    for i in range(3):
        lo = max(ba[i * 2], bb[i * 2])
        hi = min(ba[i * 2 + 1], bb[i * 2 + 1])
        if hi <= lo:
            return 0.0
        region += [lo, hi]

    mask_a = _voxelize(a, tuple(region), spacing)
    mask_b = _voxelize(b, tuple(region), spacing)
    shared = int((mask_a & mask_b).sum())
    return shared * spacing ** 3


# Overlap below which an apparent intersection is just the shared cut face.
CONTACT_TOLERANCE_MM3 = 50.0


def reduction_quality(
    a: vtk.vtkPolyData, b: vtk.vtkPolyData, spacing: float = 1.0
) -> dict:
    """Summarise how well two fragments are reduced.

    Returns the surface gap in mm, the interpenetration volume in mm^3, and a
    plain verdict a surgeon can read: reduced / gapped / over-reduced.
    """
    gap = fragment_gap(a, b)
    overlap = overlap_volume(a, b, spacing)
    if overlap > CONTACT_TOLERANCE_MM3:
        verdict = "over-reduced (fragments interpenetrate)"
    elif gap <= 2.0:
        verdict = "reduced"
    else:
        verdict = "gapped"
    return {"gap_mm": gap, "overlap_mm3": overlap, "verdict": verdict}
