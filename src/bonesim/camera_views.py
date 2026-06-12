"""Anatomical camera presets and surgeon's-view handling.

Standard radiological/anatomical viewing directions are applied to a VTK
camera so the surgeon can snap the reconstruction to a familiar orientation,
then free-drag from there. A custom orientation can also be saved and recalled
("surgeon's view").
"""

from __future__ import annotations

from dataclasses import dataclass

import vtk

# Each preset: (position_direction, view_up). The camera looks from
# position_direction toward the focal point (the model centre).
# Patient axes follow DICOM/LPS-like convention as reconstructed here:
#   +x ~ left, +y ~ posterior, +z ~ superior.
ANATOMICAL_VIEWS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "Anterior (AP)": ((0, -1, 0), (0, 0, 1)),
    "Posterior": ((0, 1, 0), (0, 0, 1)),
    "Left": ((1, 0, 0), (0, 0, 1)),
    "Right": ((-1, 0, 0), (0, 0, 1)),
    "Superior (Axial)": ((0, 0, 1), (0, -1, 0)),
    "Inferior": ((0, 0, -1), (0, 1, 0)),
}


@dataclass
class CameraPose:
    """A serialisable snapshot of a camera orientation."""

    position: tuple[float, float, float]
    focal_point: tuple[float, float, float]
    view_up: tuple[float, float, float]
    parallel_scale: float

    @classmethod
    def capture(cls, camera: vtk.vtkCamera) -> "CameraPose":
        return cls(
            position=camera.GetPosition(),
            focal_point=camera.GetFocalPoint(),
            view_up=camera.GetViewUp(),
            parallel_scale=camera.GetParallelScale(),
        )

    def apply(self, camera: vtk.vtkCamera) -> None:
        camera.SetPosition(*self.position)
        camera.SetFocalPoint(*self.focal_point)
        camera.SetViewUp(*self.view_up)
        camera.SetParallelScale(self.parallel_scale)


def apply_anatomical_view(
    renderer: vtk.vtkRenderer,
    name: str,
    bounds: tuple[float, float, float, float, float, float] | None = None,
) -> None:
    """Point the renderer's active camera along the named anatomical direction."""
    if name not in ANATOMICAL_VIEWS:
        raise KeyError(f"Unknown anatomical view: {name}")

    direction, view_up = ANATOMICAL_VIEWS[name]
    camera = renderer.GetActiveCamera()

    if bounds is None:
        bounds = renderer.ComputeVisiblePropBounds()

    cx = (bounds[0] + bounds[1]) / 2.0
    cy = (bounds[2] + bounds[3]) / 2.0
    cz = (bounds[4] + bounds[5]) / 2.0

    # Distance scaled to the model size so the whole bone stays in frame.
    diagonal = max(
        bounds[1] - bounds[0],
        bounds[3] - bounds[2],
        bounds[5] - bounds[4],
        1.0,
    )
    distance = diagonal * 2.5

    camera.SetFocalPoint(cx, cy, cz)
    camera.SetPosition(
        cx + direction[0] * distance,
        cy + direction[1] * distance,
        cz + direction[2] * distance,
    )
    camera.SetViewUp(*view_up)
    renderer.ResetCameraClippingRange()
