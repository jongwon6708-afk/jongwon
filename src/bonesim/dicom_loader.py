"""DICOM CT series loading.

Reads a directory of DICOM slices, sorts them into a 3D volume, converts the
raw stored values to Hounsfield Units (HU) using the Rescale Slope/Intercept
tags, and exposes the result both as a numpy array and as a ``vtkImageData``
object ready for surface reconstruction.

HU reference (used when picking a bone threshold):
    air ~ -1000, water ~ 0, fat ~ -100, soft tissue ~ +40,
    trabecular (spongy) bone ~ +300..+400, cortical bone ~ +700..+3000.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pydicom
import vtk
from vtk.util import numpy_support


@dataclass
class CTVolume:
    """A loaded CT volume in Hounsfield Units.

    Attributes:
        hu: 3D numpy array (z, y, x) of Hounsfield Units, float32.
        spacing: (sx, sy, sz) voxel spacing in millimetres.
        origin: (ox, oy, oz) patient-space origin in millimetres.
        image: ``vtkImageData`` mirror of ``hu`` for VTK pipelines.
        description: short human-readable label (series description, etc.).
    """

    hu: np.ndarray
    spacing: tuple[float, float, float]
    origin: tuple[float, float, float]
    image: vtk.vtkImageData
    description: str

    @property
    def hu_range(self) -> tuple[float, float]:
        return float(self.hu.min()), float(self.hu.max())


def _list_dicom_files(directory: str) -> list[str]:
    """Return DICOM file paths in *directory* (non-recursive first, then deep)."""
    candidates: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            lower = name.lower()
            if lower.endswith((".dcm", ".ima")) or "." not in name:
                candidates.append(os.path.join(root, name))
        # Prefer a flat series directory: if the top level already has files,
        # don't descend into sibling series and mix them together.
        if root == directory and candidates:
            break
    if not candidates:
        raise FileNotFoundError(f"No DICOM files found under: {directory}")
    return candidates


def _slice_sort_key(ds: pydicom.Dataset) -> float:
    """Sort key along the acquisition axis.

    Prefers ImagePositionPatient[2] (true patient Z); falls back to
    SliceLocation, then InstanceNumber.
    """
    ipp = getattr(ds, "ImagePositionPatient", None)
    if ipp is not None and len(ipp) == 3:
        return float(ipp[2])
    loc = getattr(ds, "SliceLocation", None)
    if loc is not None:
        return float(loc)
    return float(getattr(ds, "InstanceNumber", 0))


def load_dicom_series(directory: str) -> CTVolume:
    """Load a CT series from *directory* into a :class:`CTVolume`.

    Slices are sorted by patient position, stacked, and rescaled to HU.
    """
    paths = _list_dicom_files(directory)

    slices: list[pydicom.Dataset] = []
    for path in paths:
        try:
            ds = pydicom.dcmread(path, force=True)
        except Exception:
            continue
        if not hasattr(ds, "PixelData"):
            continue  # skip non-image objects (e.g. DICOMDIR, structured reports)
        slices.append(ds)

    if not slices:
        raise ValueError(f"No readable image slices in: {directory}")

    slices.sort(key=_slice_sort_key)

    first = slices[0]
    rows = int(first.Rows)
    cols = int(first.Columns)

    volume = np.zeros((len(slices), rows, cols), dtype=np.float32)
    for i, ds in enumerate(slices):
        pixels = ds.pixel_array.astype(np.float32)
        slope = float(getattr(ds, "RescaleSlope", 1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))
        volume[i] = pixels * slope + intercept

    # In-plane spacing (row spacing, column spacing) in mm.
    pixel_spacing = getattr(first, "PixelSpacing", [1.0, 1.0])
    sy = float(pixel_spacing[0])
    sx = float(pixel_spacing[1])
    sz = _estimate_slice_spacing(slices)

    ipp = getattr(first, "ImagePositionPatient", [0.0, 0.0, 0.0])
    origin = (float(ipp[0]), float(ipp[1]), float(ipp[2]))

    description = str(getattr(first, "SeriesDescription", "")) or os.path.basename(
        os.path.normpath(directory)
    )

    image = _numpy_to_vtk_image(volume, (sx, sy, sz), origin)

    return CTVolume(
        hu=volume,
        spacing=(sx, sy, sz),
        origin=origin,
        image=image,
        description=f"{description}  [{len(slices)} slices]",
    )


def _estimate_slice_spacing(slices: list[pydicom.Dataset]) -> float:
    """Estimate inter-slice spacing in mm from positions, with fallbacks."""
    if len(slices) >= 2:
        z0 = _slice_sort_key(slices[0])
        z1 = _slice_sort_key(slices[1])
        delta = abs(z1 - z0)
        if delta > 1e-4:
            return float(delta)
    st = getattr(slices[0], "SliceThickness", None)
    if st:
        return float(st)
    return 1.0


def _numpy_to_vtk_image(
    volume: np.ndarray,
    spacing: tuple[float, float, float],
    origin: tuple[float, float, float],
) -> vtk.vtkImageData:
    """Wrap a (z, y, x) numpy array as ``vtkImageData``."""
    image = vtk.vtkImageData()
    depth, height, width = volume.shape
    image.SetDimensions(width, height, depth)
    image.SetSpacing(*spacing)
    image.SetOrigin(*origin)

    # VTK expects a contiguous flat buffer ordered x-fastest.
    flat = np.ascontiguousarray(volume.ravel(order="C"))
    vtk_array = numpy_support.numpy_to_vtk(
        flat, deep=True, array_type=vtk.VTK_FLOAT
    )
    vtk_array.SetName("HounsfieldUnits")
    image.GetPointData().SetScalars(vtk_array)
    return image
