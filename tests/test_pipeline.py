"""Headless smoke tests for the reconstruction pipeline.

These run without a display: they build a synthetic CT volume (a hollow bone
cylinder with a drilled hole), reconstruct a surface, and assert that the mesh
is non-empty and the threshold behaves sensibly. Run with: pytest tests/
"""

import os
import sys

import numpy as np
import vtk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bonesim.dicom_loader import CTVolume, _numpy_to_vtk_image  # noqa: E402
from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402


def make_phantom(shape=(60, 120, 120), hole=True) -> CTVolume:
    """Synthetic CT: a cortical bone cylinder (~800 HU) in soft tissue (~0 HU)."""
    depth, height, width = shape
    hu = np.full(shape, -200.0, dtype=np.float32)  # surrounding soft tissue/air

    cy, cx = height / 2.0, width / 2.0
    yy, xx = np.mgrid[0:height, 0:width]
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)

    outer, inner = 40.0, 26.0  # cortical shell radii (voxels)
    shell = (radius <= outer) & (radius >= inner)
    for z in range(depth):
        hu[z][shell] = 800.0  # cortical bone

    if hole:
        # A drilled hole through the cortex (low HU channel).
        drill = (radius <= 6.0) & (yy < cy)
        for z in range(depth):
            hu[z][drill] = -200.0

    spacing = (0.5, 0.5, 0.6)
    image = _numpy_to_vtk_image(hu, spacing, (0.0, 0.0, 0.0))
    return CTVolume(hu=hu, spacing=spacing, origin=(0, 0, 0), image=image,
                    description="phantom")


def test_phantom_reconstruction_nonempty():
    volume = make_phantom()
    mesh = reconstruct_bone(volume, ReconstructionParams(threshold_hu=400.0))
    assert isinstance(mesh, vtk.vtkPolyData)
    assert mesh.GetNumberOfPoints() > 0
    assert mesh.GetNumberOfCells() > 0


def test_threshold_above_bone_is_empty():
    volume = make_phantom()
    # No material above 2000 HU in the phantom -> empty surface.
    mesh = reconstruct_bone(volume, ReconstructionParams(threshold_hu=2000.0,
                                                         smoothing_iterations=0,
                                                         decimation=0.0))
    assert mesh.GetNumberOfPoints() == 0


def test_hu_conversion_roundtrip():
    volume = make_phantom()
    assert volume.image.GetDimensions() == (120, 120, 60)
    lo, hi = volume.hu_range
    assert lo < 0 < hi


if __name__ == "__main__":
    test_phantom_reconstruction_nonempty()
    test_threshold_above_bone_is_empty()
    test_hu_conversion_roundtrip()
    print("All smoke tests passed.")
