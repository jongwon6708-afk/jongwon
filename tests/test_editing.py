"""Headless tests for interactive bone selection / removal."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from bonesim.dicom_loader import CTVolume, _numpy_to_vtk_image  # noqa: E402
from bonesim.reconstruction import ReconstructionParams, reconstruct_bone  # noqa: E402
from bonesim.preprocessing import PreprocessParams  # noqa: E402
from bonesim import editing  # noqa: E402


def make_two_bones_phantom(shape=(40, 120, 160)) -> CTVolume:
    """Two separate solid bone cylinders (like both femora) plus a table slab.

    Three disconnected structures -> exactly the case a radiographer cleans up
    by clicking the bone they want and deleting the rest. Solid (not hollow)
    cylinders keep the region count unambiguous: one closed surface each.
    Everything is inset from the volume border so each surface closes.
    """
    depth, height, width = shape
    hu = np.full(shape, -200.0, dtype=np.float32)

    yy, xx = np.mgrid[0:height, 0:width]
    for cx in (45.0, 115.0):  # left and right bone
        r = np.sqrt((yy - 50.0) ** 2 + (xx - cx) ** 2)
        disc = r <= 22.0
        for z in range(5, depth - 5):  # inset in z so the ends cap
            hu[z][disc] = 900.0

    # Table slab, disconnected, near the far edge (also inset).
    hu[5 : depth - 5, height - 14 : height - 9, 10 : width - 10] = 1200.0

    spacing = (0.6, 0.6, 0.8)
    image = _numpy_to_vtk_image(hu, spacing, (0.0, 0.0, 0.0))
    return CTVolume(hu=hu, spacing=spacing, origin=(0, 0, 0), image=image,
                    description="two_bones")


def _mesh():
    volume = make_two_bones_phantom()
    return reconstruct_bone(volume, ReconstructionParams(
        threshold_hu=500, smoothing_iterations=0, decimation=0.0,
        island_min_fraction=0.0,
        preprocess=PreprocessParams(median_denoise=False)))


def test_three_regions_detected():
    mesh = _mesh()
    _, n = editing.label_regions(mesh)
    assert n == 3, f"expected 2 bones + table, got {n}"
    sizes = editing.region_sizes(mesh)
    assert len(sizes) == 3
    assert all(s > 0 for s in sizes)


def test_pick_selects_region_under_point():
    mesh = _mesh()
    # Pick a point on the surface of the mesh and confirm we get a valid id.
    pt = mesh.GetPoint(0)
    rid = editing.region_id_at_point(mesh, pt)
    assert rid is not None and 0 <= rid < 3


def test_keep_only_selected_region():
    mesh = _mesh()
    _, n = editing.label_regions(mesh)
    kept = editing.extract_regions(mesh, {0}, invert=False)
    assert kept.GetNumberOfCells() > 0
    # Keeping one of three regions must shrink the mesh.
    assert kept.GetNumberOfCells() < mesh.GetNumberOfCells()
    # And the result is a single connected structure.
    _, kept_n = editing.label_regions(kept)
    assert kept_n == 1


def test_delete_selected_region():
    mesh = _mesh()
    remaining = editing.extract_regions(mesh, {0}, invert=True)
    _, n = editing.label_regions(remaining)
    assert n == 2  # deleted one of three


def test_scissors_cut_removes_inside_loop():
    mesh = _mesh()
    b = mesh.GetBounds()
    # Lasso a box around the left half, cut it away (keep_inside=False).
    xmid = (b[0] + b[1]) / 2
    loop = [
        (b[0] - 5, b[2] - 5, 0.0),
        (xmid, b[2] - 5, 0.0),
        (xmid, b[3] + 5, 0.0),
        (b[0] - 5, b[3] + 5, 0.0),
    ]
    cut = editing.scissors_cut(mesh, loop, view_normal=(0, 0, 1),
                               keep_inside=False)
    assert cut.GetNumberOfCells() > 0
    assert cut.GetNumberOfCells() < mesh.GetNumberOfCells()
    # What remains should sit on the +x side of the cut line.
    assert cut.GetBounds()[0] >= xmid - 2.0


def test_scissors_keep_inside():
    mesh = _mesh()
    b = mesh.GetBounds()
    xmid = (b[0] + b[1]) / 2
    loop = [
        (b[0] - 5, b[2] - 5, 0.0),
        (xmid, b[2] - 5, 0.0),
        (xmid, b[3] + 5, 0.0),
        (b[0] - 5, b[3] + 5, 0.0),
    ]
    kept = editing.scissors_cut(mesh, loop, view_normal=(0, 0, 1),
                                keep_inside=True)
    assert kept.GetNumberOfCells() > 0
    assert kept.GetBounds()[1] <= xmid + 2.0


if __name__ == "__main__":
    test_three_regions_detected()
    test_pick_selects_region_under_point()
    test_keep_only_selected_region()
    test_delete_selected_region()
    test_scissors_cut_removes_inside_loop()
    test_scissors_keep_inside()
    print("All editing tests passed.")
