"""Offscreen GUI smoke test: build the window and exercise every action path.

Runs headless via the Qt 'offscreen' platform. It injects a synthetic volume
(bypassing the file dialog), then drives reconstruction, curvature/edge
display, mirroring, and the deviation map -- verifying the GUI wiring without a
real display or DICOM files.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5 import QtWidgets  # noqa: E402

from bonesim.viewer import ViewerWindow  # noqa: E402
from test_pipeline import make_trauma_phantom  # noqa: E402


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    win = ViewerWindow()
    win.start()

    # Inject a phantom as if a DICOM folder had been loaded.
    win.models["preop"].volume = make_trauma_phantom()
    win.thr_slider.setValue(500)
    win._rebuild("preop", reset_camera=True)
    assert win.models["preop"].mesh is not None
    assert win.models["preop"].mesh.GetNumberOfCells() > 0
    print("reconstruction wired OK")

    # Cleanup toggles + crop (fracture-safe table removal).
    win.chk_denoise.setChecked(True)
    win.crop_bounds = (-10.0, 80.0, -10.0, 60.0, -10.0, 50.0)
    win._rebuild_all()
    win._clear_crop()
    print("cleanup + crop OK")

    # Fracture display modes.
    win.chk_curvature.setChecked(True)
    win.chk_edges.setChecked(True)
    win._refresh_display()
    assert win.models["preop"].edge_actor is not None
    print("fracture highlight OK")

    # Compare-to-standard pipeline.
    win._mirror_to_reference()
    assert win.reference_mesh is not None
    win._deviation_map()
    assert win.scalar_bar is not None
    print("comparison + deviation map OK")

    # Anatomical view + render.
    win._apply_view("Anterior (AP)")
    win.vtk_widget.GetRenderWindow().Render()
    print("All GUI smoke checks passed.")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
