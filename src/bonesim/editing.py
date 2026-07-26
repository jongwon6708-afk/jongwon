"""Interactive bone selection and removal.

Mirrors how radiographers actually clean up a 3D CT reconstruction in clinical
software (Materialise Mimics, 3D Slicer Segment Editor, syngo.via):

  1. **Region / island picking** -- click a bone and the whole *connected*
     structure is selected, then kept or deleted. This is the primary tool
     (Mimics "Region Grow", Slicer "Islands"). It separates the femur from the
     pelvis, the table, contralateral bones, etc. in one click.

  2. **Scissors lasso** -- draw a closed loop on screen and cut everything
     inside (or outside) it, straight through along the view direction (Slicer
     "Scissors"). This is the fallback for structures that *touch*, where
     connectivity alone cannot separate them -- e.g. across a joint space, or
     an acetabulum fused to the femoral head by partial volume.

Both operate on the surface mesh and return a new mesh, so they compose with
the rest of the pipeline and can be undone by keeping the previous mesh.
"""

from __future__ import annotations

import vtk

REGION_ARRAY = "RegionId"


# ------------------------------------------------------------------ regions
def label_regions(mesh: vtk.vtkPolyData) -> tuple[vtk.vtkPolyData, int]:
    """Tag every cell/point with a connected-region id.

    Returns the labelled mesh and the number of regions found. The label array
    is named :data:`REGION_ARRAY` and lets us select a whole bone by id.
    """
    connectivity = vtk.vtkPolyDataConnectivityFilter()
    connectivity.SetInputData(mesh)
    connectivity.SetExtractionModeToAllRegions()
    connectivity.ColorRegionsOn()
    connectivity.Update()
    return connectivity.GetOutput(), connectivity.GetNumberOfExtractedRegions()


def region_id_at_point(
    mesh: vtk.vtkPolyData, point: tuple[float, float, float]
) -> int | None:
    """Return the connected-region id containing the surface point *point*.

    Used by click-picking: the user clicks a bone, we find which connected
    structure was hit.
    """
    labelled, n_regions = label_regions(mesh)
    if n_regions == 0:
        return None

    locator = vtk.vtkPointLocator()
    locator.SetDataSet(labelled)
    locator.BuildLocator()
    pid = locator.FindClosestPoint(point)
    if pid < 0:
        return None

    array = labelled.GetPointData().GetArray(REGION_ARRAY)
    if array is None:
        return None
    return int(array.GetTuple1(pid))


def extract_regions(
    mesh: vtk.vtkPolyData, region_ids: set[int], invert: bool = False
) -> vtk.vtkPolyData:
    """Keep (or with *invert*, delete) the given connected regions.

    ``invert=False`` -> "keep only selected" (isolate the bone of interest).
    ``invert=True``  -> "delete selected" (remove the table, the other limb).
    """
    labelled, n_regions = label_regions(mesh)
    if n_regions <= 1 and not region_ids:
        return mesh

    wanted = (
        {i for i in range(n_regions) if i not in region_ids}
        if invert
        else set(region_ids)
    )
    if not wanted:
        return vtk.vtkPolyData()  # everything removed

    selector = vtk.vtkPolyDataConnectivityFilter()
    selector.SetInputData(mesh)
    selector.SetExtractionModeToSpecifiedRegions()
    for rid in sorted(wanted):
        selector.AddSpecifiedRegion(rid)
    selector.Update()

    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(selector.GetOutput())
    cleaner.Update()
    return cleaner.GetOutput()


def region_sizes(mesh: vtk.vtkPolyData) -> list[int]:
    """Cell count per connected region, indexed by region id."""
    connectivity = vtk.vtkPolyDataConnectivityFilter()
    connectivity.SetInputData(mesh)
    connectivity.SetExtractionModeToAllRegions()
    connectivity.Update()
    sizes = connectivity.GetRegionSizes()
    return [
        int(sizes.GetValue(i))
        for i in range(connectivity.GetNumberOfExtractedRegions())
    ]


# ----------------------------------------------------------------- scissors
def scissors_cut(
    mesh: vtk.vtkPolyData,
    loop_points: list[tuple[float, float, float]],
    view_normal: tuple[float, float, float],
    keep_inside: bool = False,
) -> vtk.vtkPolyData:
    """Cut *mesh* with a screen-drawn lasso, extruded along the view direction.

    *loop_points* are world-space points of the drawn loop (they only need to
    be correct in the two screen axes; the loop is treated as an infinite prism
    along *view_normal*). ``keep_inside=False`` deletes what is inside the loop
    -- the usual "lasso the junk and cut it away" gesture.
    """
    if len(loop_points) < 3:
        return mesh

    points = vtk.vtkPoints()
    for p in loop_points:
        points.InsertNextPoint(*p)

    loop = vtk.vtkImplicitSelectionLoop()
    loop.SetLoop(points)
    loop.SetNormal(*view_normal)  # project along the camera direction
    loop.AutomaticNormalGenerationOff()

    extract = vtk.vtkExtractPolyDataGeometry()
    extract.SetInputData(mesh)
    extract.SetImplicitFunction(loop)
    # ExtractInside=1 keeps what is inside the loop.
    extract.SetExtractInside(1 if keep_inside else 0)
    extract.SetExtractBoundaryCells(0)
    extract.Update()

    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(extract.GetOutput())
    cleaner.Update()
    return cleaner.GetOutput()
