"""Parametric orthopaedic implants: screws and plates.

Why generated rather than imported: vendor CAD (DePuy Synthes, Stryker) is not
publicly licensable, and model-library files (GrabCAD, Printables) carry
per-model terms that generally forbid redistribution. Generating AO-style
geometry sidesteps that entirely -- and it makes length, diameter, hole count
and curvature *parameters*, which is what the clinical question ("which plate
and which screw fit this patient?") actually needs.

Geometry is built from implicit functions sampled onto a grid and contoured,
rather than by boolean operations on surfaces. Surface booleans in VTK are
fragile -- they crash on the coplanar faces this kind of geometry produces --
while implicit modelling is robust and always yields a closed surface, which
the volume-overlap metrics downstream require.

Fidelity: shafts are smooth cylinders, not threaded helices. Thread form does
not change screw trajectory, length selection, articular breach or cortical
purchase, which are the questions this tool answers; modelling it would cost
mesh complexity for no planning value.
"""

from __future__ import annotations

from dataclasses import dataclass

import vtk

Vec3 = tuple[float, float, float]

# AO reference dimensions (mm) for the common trauma screws.
AO_CORTICAL_3_5 = 3.5
AO_CORTICAL_4_5 = 4.5
AO_CANCELLOUS_4_0 = 4.0


# ------------------------------------------------------------ implicit core
def _contour_implicit(
    function: vtk.vtkImplicitFunction,
    bounds: tuple[float, float, float, float, float, float],
    spacing: float = 0.25,
) -> vtk.vtkPolyData:
    """Sample an implicit function over *bounds* and extract its zero surface."""
    dims = [
        max(8, int((bounds[i * 2 + 1] - bounds[i * 2]) / spacing) + 1)
        for i in range(3)
    ]
    sample = vtk.vtkSampleFunction()
    sample.SetImplicitFunction(function)
    sample.SetModelBounds(*bounds)
    sample.SetSampleDimensions(*dims)
    sample.ComputeNormalsOff()
    sample.Update()

    surface = vtk.vtkContourFilter()
    surface.SetInputConnection(sample.GetOutputPort())
    surface.SetValue(0, 0.0)
    surface.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(surface.GetOutputPort())
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.Update()
    return normals.GetOutput()


def _axis_cylinder(radius: float, half_length: float) -> vtk.vtkImplicitFunction:
    """Implicit solid cylinder of given radius along +z, centred on the origin."""
    # vtkCylinder is infinite along y; rotate it to z and cap with two planes.
    cylinder = vtk.vtkCylinder()
    cylinder.SetCenter(0.0, 0.0, 0.0)
    cylinder.SetRadius(radius)
    cylinder.SetAxis(0.0, 0.0, 1.0)

    top = vtk.vtkPlane()
    top.SetOrigin(0.0, 0.0, half_length)
    top.SetNormal(0.0, 0.0, 1.0)
    bottom = vtk.vtkPlane()
    bottom.SetOrigin(0.0, 0.0, -half_length)
    bottom.SetNormal(0.0, 0.0, -1.0)

    solid = vtk.vtkImplicitBoolean()
    solid.SetOperationTypeToIntersection()
    solid.AddFunction(cylinder)
    solid.AddFunction(top)
    solid.AddFunction(bottom)
    return solid


# ------------------------------------------------------------------- screws
@dataclass
class ScrewSpec:
    """A screw described the way it is chosen on the ward: size and length."""

    length_mm: float = 40.0
    diameter_mm: float = AO_CORTICAL_3_5
    head_diameter_mm: float = 6.0
    head_height_mm: float = 2.0

    @property
    def radius(self) -> float:
        return self.diameter_mm / 2.0


def make_screw(spec: ScrewSpec, spacing: float = 0.25) -> vtk.vtkPolyData:
    """Build a screw along +z, head at z=0, tip at z=-length.

    The shaft is a smooth cylinder (see module docstring on thread fidelity);
    the head is a wider disc so a plate/bone interface is visible.
    """
    shaft_half = spec.length_mm / 2.0
    shaft = _axis_cylinder(spec.radius, shaft_half)
    shaft_shift = vtk.vtkTransform()
    shaft_shift.Translate(0.0, 0.0, -shaft_half)
    shaft.SetTransform(shaft_shift.GetInverse())

    head_half = spec.head_height_mm / 2.0
    head = _axis_cylinder(spec.head_diameter_mm / 2.0, head_half)
    head_shift = vtk.vtkTransform()
    head_shift.Translate(0.0, 0.0, head_half)
    head.SetTransform(head_shift.GetInverse())

    whole = vtk.vtkImplicitBoolean()
    whole.SetOperationTypeToUnion()
    whole.AddFunction(shaft)
    whole.AddFunction(head)

    pad = 1.0
    r = max(spec.radius, spec.head_diameter_mm / 2.0) + pad
    bounds = (-r, r, -r, r,
              -spec.length_mm - pad, spec.head_height_mm + pad)
    return _contour_implicit(whole, bounds, spacing)


# ------------------------------------------------------------------- plates
@dataclass
class PlateSpec:
    """An AO-style straight plate: a slab with evenly spaced screw holes."""

    length_mm: float = 90.0
    width_mm: float = 12.0
    thickness_mm: float = 3.5
    hole_count: int = 6
    hole_diameter_mm: float = 4.0

    @property
    def hole_positions(self) -> list[float]:
        """Hole centres along the plate's long (z) axis, centred on 0."""
        if self.hole_count <= 0:
            return []
        # Leave a margin of one hole-pitch half at each end.
        pitch = self.length_mm / self.hole_count
        start = -self.length_mm / 2.0 + pitch / 2.0
        return [start + i * pitch for i in range(self.hole_count)]


def make_plate(spec: PlateSpec, spacing: float = 0.4) -> vtk.vtkPolyData:
    """Build a plate lying along +z, thickness along y, centred on the origin.

    The plate's under-surface (the side that meets bone) faces -y.
    """
    slab = vtk.vtkBox()
    slab.SetBounds(
        -spec.width_mm / 2.0, spec.width_mm / 2.0,
        -spec.thickness_mm / 2.0, spec.thickness_mm / 2.0,
        -spec.length_mm / 2.0, spec.length_mm / 2.0,
    )

    solid = vtk.vtkImplicitBoolean()
    solid.SetOperationTypeToDifference()
    solid.AddFunction(slab)

    for z in spec.hole_positions:
        hole = vtk.vtkCylinder()
        hole.SetCenter(0.0, 0.0, z)
        hole.SetRadius(spec.hole_diameter_mm / 2.0)
        hole.SetAxis(0.0, 1.0, 0.0)  # bore through the thickness
        solid.AddFunction(hole)

    pad = 1.5
    bounds = (
        -spec.width_mm / 2.0 - pad, spec.width_mm / 2.0 + pad,
        -spec.thickness_mm / 2.0 - pad, spec.thickness_mm / 2.0 + pad,
        -spec.length_mm / 2.0 - pad, spec.length_mm / 2.0 + pad,
    )
    return _contour_implicit(solid, bounds, spacing)


# ---------------------------------------------------------------- placement
def length_for_trajectory(entry: Vec3, target: Vec3) -> float:
    """Screw length in mm needed to reach *target* from *entry*.

    Useful because :func:`place_along` uses the implant's **own** length and
    treats the target as a direction only -- you pick a length off the rack, so
    this tells you which one to pick.
    """
    return sum((target[i] - entry[i]) ** 2 for i in range(3)) ** 0.5


def place_along(
    implant: vtk.vtkPolyData, entry: Vec3, target: Vec3
) -> vtk.vtkPolyData:
    """Aim an implant built along +z so it runs from *entry* toward *target*.

    For a screw this is exactly how a trajectory is specified in planning: an
    entry point on the cortex and a target point defining the direction.

    Note the target sets the **direction only** -- the implant keeps the length
    it was built with, exactly as a real screw does. If the screw is longer
    than the entry-to-target distance it will extend past the target. Use
    :func:`length_for_trajectory` to size it first.
    """
    direction = [target[i] - entry[i] for i in range(3)]
    length = sum(d * d for d in direction) ** 0.5
    if length < 1e-9:
        raise ValueError("Entry and target coincide; no trajectory defined")
    direction = [d / length for d in direction]

    # Rotation taking -z (the screw's tip direction) onto `direction`.
    tip_axis = (0.0, 0.0, -1.0)
    axis = [
        tip_axis[1] * direction[2] - tip_axis[2] * direction[1],
        tip_axis[2] * direction[0] - tip_axis[0] * direction[2],
        tip_axis[0] * direction[1] - tip_axis[1] * direction[0],
    ]
    dot = sum(tip_axis[i] * direction[i] for i in range(3))
    dot = max(-1.0, min(1.0, dot))
    angle_deg = _degrees(dot)

    transform = vtk.vtkTransform()
    transform.PostMultiply()
    if sum(a * a for a in axis) > 1e-12:
        transform.RotateWXYZ(angle_deg, *axis)
    elif dot < 0:  # exactly opposite: spin about any perpendicular axis
        transform.RotateWXYZ(180.0, 1.0, 0.0, 0.0)
    transform.Translate(*entry)

    tf = vtk.vtkTransformPolyDataFilter()
    tf.SetInputData(implant)
    tf.SetTransform(transform)
    tf.Update()
    return tf.GetOutput()


def _degrees(cos_value: float) -> float:
    import math
    return math.degrees(math.acos(cos_value))
