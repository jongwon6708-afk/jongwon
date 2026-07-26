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

    # Cross-section: cut the bone open, sweep the plane, toggle cap/flip.
    win.chk_curvature.setChecked(False)
    win.chk_edges.setChecked(False)
    win.chk_xs.setChecked(True)
    win.xs_axis.setCurrentIndex(1)
    win.xs_pos.setValue(40)
    win.chk_xs_flip.setChecked(True)
    win.chk_xs_cap.setChecked(True)
    win._refresh_display()
    win.chk_xs_cap.setChecked(False)
    win._refresh_display()
    print("cross-section OK")

    # Bone editing: select a structure, isolate it, undo, then delete.
    win.chk_xs.setChecked(False)
    win._refresh_display()
    mesh = win.models["preop"].mesh
    before_cells = mesh.GetNumberOfCells()
    win.selected_regions = {0}
    win._show_selection()
    assert win.selection_actor is not None
    win._apply_selection(invert=False)          # keep only
    assert win.models["preop"].mesh.GetNumberOfCells() <= before_cells
    win._undo_edit()
    assert win.models["preop"].mesh.GetNumberOfCells() == before_cells
    win.selected_regions = {0}
    win._apply_selection(invert=True)           # delete selected
    win._undo_edit()
    win._clear_selection()
    print("bone editing OK")

    # Measurement / planning loop: landmarks -> measure -> compare -> save.
    import tempfile
    pre = win.session.add_stage("pre-op") if not win.session.stages \
        else win.session.stages[0]
    for nm, pos in [("femoral_head_center", (0.0, 0.0, 50.0)),
                    ("neck_shaft_junction", (40.0, 0.0, 0.0)),
                    ("shaft_distal", (40.0, 0.0, -100.0))]:
        pre.add_landmark(nm, pos)
        win._show_landmark(pre.label, nm, pos)
    win.stage_combo.setCurrentText(pre.label)
    win._measure_stage()
    text = win.measure_output.toPlainText()
    assert "Neck-shaft angle" in text, text
    assert "141" in text, text          # clinical convention preserved

    plan = win.session.add_stage("plan-v1")
    for nm, pos in [("femoral_head_center", (0.0, 0.0, 30.0)),
                    ("neck_shaft_junction", (40.0, 0.0, 0.0)),
                    ("shaft_distal", (40.0, 0.0, -100.0))]:
        plan.add_landmark(nm, pos)
    report = win.session.compare("pre-op", "plan-v1")
    assert report["Neck-shaft angle"]["delta"] != 0
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "plan.json")
        win.session.save(p)
        assert os.path.getsize(p) > 0
    print("measurement / planning OK")

    # Simulation: osteotomy -> displace a fragment -> verdict -> commit stage.
    from bonesim import simulation as _sim
    win.chk_xs.setChecked(False)
    win.chk_xs_flip.setChecked(False)   # fragment A = the +normal side
    win.xs_axis.setCurrentIndex(2)      # axial cut
    win.xs_pos.setValue(50)
    win.stage_combo.setCurrentText("pre-op")
    win._do_osteotomy()
    assert len(win.fragments) == 2, "osteotomy should yield two fragments"
    assert len(win.fragment_actors) == 2

    win.fragment_combo.setCurrentIndex(0)
    win.trans_spin[2].setValue(8.0)     # pull fragment A 8 mm away
    win._measure_fragment_gap()
    out = win.measure_output.toPlainText()
    assert "gapped" in out, out
    a, b = win._current_fragment_meshes()
    assert _sim.fragment_gap(a, b) > 1.0

    # Driving it the other way must be flagged as over-reduction, not "good".
    win.trans_spin[2].setValue(-6.0)
    win._measure_fragment_gap()
    assert "over-reduced" in win.measure_output.toPlainText()

    win._reset_simulation()
    assert win.fragments == []
    print("simulation (osteotomy + reduction) OK")

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
