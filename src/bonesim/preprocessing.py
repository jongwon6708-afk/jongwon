"""CT volume pre-processing: denoising and artefact removal.

These operate in the image (voxel) domain *before* surface extraction, which
is the right place to suppress problems that would otherwise become baked into
the mesh:

  * speckle noise and tiny calcification flecks  -> median / Gaussian smoothing
  * the scanner table / positioning board behind the patient -> it shows up as
    a high-HU structure but is physically *disconnected* from the bone, so a
    largest-connected-component mask on the thresholded volume removes it.

All filters are VTK-only (no extra dependencies).
"""

from __future__ import annotations

from dataclasses import dataclass

import vtk

from .dicom_loader import CTVolume, _numpy_to_vtk_image  # noqa: F401  (re-used type)


@dataclass
class PreprocessParams:
    median_denoise: bool = True       # remove speckle / small calcifications
    gaussian_sigma: float = 0.0       # extra smoothing in voxels (0 = off)
    # Axis-aligned crop in world millimetres: (xmin, xmax, ymin, ymax, zmin,
    # zmax). The robust way to drop the scanner table / back board WITHOUT
    # risking deletion of displaced fracture fragments -- enclose the bone in a
    # box and discard everything outside it. None disables cropping.
    crop_bounds: tuple[float, float, float, float, float, float] | None = None


def preprocess_volume(volume: CTVolume, params: PreprocessParams) -> vtk.vtkImageData:
    """Return a cleaned ``vtkImageData`` ready for surface extraction."""
    image = volume.image

    if params.median_denoise:
        median = vtk.vtkImageMedian3D()
        median.SetInputData(image)
        median.SetKernelSize(3, 3, 3)
        median.Update()
        image = median.GetOutput()

    if params.gaussian_sigma > 0.0:
        gauss = vtk.vtkImageGaussianSmooth()
        gauss.SetInputData(image)
        gauss.SetStandardDeviation(params.gaussian_sigma)
        gauss.Update()
        image = gauss.GetOutput()

    if params.crop_bounds is not None:
        image = _crop_image(image, params.crop_bounds)

    return image


def _crop_image(
    image: vtk.vtkImageData,
    world_bounds: tuple[float, float, float, float, float, float],
) -> vtk.vtkImageData:
    """Crop *image* to an axis-aligned world-coordinate box (millimetres).

    Unlike connectivity-based table removal, cropping keeps every bone fragment
    inside the box, so displaced fracture fragments are preserved.
    """
    origin = image.GetOrigin()
    spacing = image.GetSpacing()
    extent = image.GetExtent()

    def to_index(world: float, axis: int) -> int:
        idx = round((world - origin[axis]) / spacing[axis])
        return int(min(max(idx, extent[axis * 2]), extent[axis * 2 + 1]))

    xmin = to_index(world_bounds[0], 0)
    xmax = to_index(world_bounds[1], 0)
    ymin = to_index(world_bounds[2], 1)
    ymax = to_index(world_bounds[3], 1)
    zmin = to_index(world_bounds[4], 2)
    zmax = to_index(world_bounds[5], 2)

    clip = vtk.vtkImageClip()
    clip.SetInputData(image)
    clip.SetOutputWholeExtent(
        min(xmin, xmax), max(xmin, xmax),
        min(ymin, ymax), max(ymin, ymax),
        min(zmin, zmax), max(zmin, zmax),
    )
    clip.ClipDataOn()
    clip.Update()
    return clip.GetOutput()
