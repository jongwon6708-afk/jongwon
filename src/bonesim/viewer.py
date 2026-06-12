"""Interactive 3D viewer window (PyQt5 + VTK).

Loads pre-operative and post-operative CT series, reconstructs each as a bone
surface, and shows them in a trackball-navigable 3D scene. The surgeon can:

  * drag to rotate / scroll to zoom (default VTK trackball interactor),
  * snap to anatomical preset views,
  * save and recall a custom "surgeon's view" orientation,
  * toggle pre-op vs post-op visibility and opacity,
  * adjust the bone HU threshold and re-reconstruct,
  * export the current mesh to STL.
"""

from __future__ import annotations

from dataclasses import dataclass

import vtk
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from .camera_views import ANATOMICAL_VIEWS, CameraPose, apply_anatomical_view
from .dicom_loader import CTVolume, load_dicom_series
from .reconstruction import ReconstructionParams, export_mesh, reconstruct_bone

# Distinct colours so the two studies are easy to tell apart.
PREOP_COLOR = (0.92, 0.87, 0.78)   # bone ivory
POSTOP_COLOR = (0.55, 0.78, 0.92)  # cool blue


@dataclass
class BoneModel:
    """A loaded study and its current reconstruction in the scene."""

    volume: CTVolume | None = None
    actor: vtk.vtkActor | None = None
    color: tuple[float, float, float] = PREOP_COLOR
    label: str = ""


class ViewerWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("3D Bone CT Simulator")
        self.resize(1280, 820)

        self.models: dict[str, BoneModel] = {
            "preop": BoneModel(color=PREOP_COLOR, label="Pre-op"),
            "postop": BoneModel(color=POSTOP_COLOR, label="Post-op"),
        }
        self.saved_pose: CameraPose | None = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        # --- 3D render area ---
        self.vtk_widget = QVTKRenderWindowInteractor(central)
        layout.addWidget(self.vtk_widget, stretch=1)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.12, 0.13, 0.16)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)

        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        style = vtk.vtkInteractorStyleTrackballCamera()  # drag to rotate
        self.interactor.SetInteractorStyle(style)

        self._add_orientation_widget()

        # --- control panel ---
        panel = self._build_control_panel()
        layout.addWidget(panel)

    def _build_control_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setFixedWidth(300)
        v = QtWidgets.QVBoxLayout(panel)

        # Load buttons
        load_box = QtWidgets.QGroupBox("Load CT series")
        load_layout = QtWidgets.QVBoxLayout(load_box)
        btn_pre = QtWidgets.QPushButton("Load Pre-op CT...")
        btn_post = QtWidgets.QPushButton("Load Post-op CT...")
        btn_pre.clicked.connect(lambda: self._load_study("preop"))
        btn_post.clicked.connect(lambda: self._load_study("postop"))
        load_layout.addWidget(btn_pre)
        load_layout.addWidget(btn_post)
        v.addWidget(load_box)

        # Threshold
        thr_box = QtWidgets.QGroupBox("Bone threshold (HU)")
        thr_layout = QtWidgets.QVBoxLayout(thr_box)
        self.thr_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.thr_slider.setRange(100, 1500)
        self.thr_slider.setValue(int(ReconstructionParams().threshold_hu))
        self.thr_label = QtWidgets.QLabel(f"{self.thr_slider.value()} HU")
        self.thr_slider.valueChanged.connect(
            lambda val: self.thr_label.setText(f"{val} HU")
        )
        self.thr_slider.sliderReleased.connect(self._rebuild_all)
        thr_layout.addWidget(self.thr_slider)
        thr_layout.addWidget(self.thr_label)
        v.addWidget(thr_box)

        # Visibility / opacity
        vis_box = QtWidgets.QGroupBox("Visibility")
        vis_layout = QtWidgets.QGridLayout(vis_box)
        self.chk_pre = QtWidgets.QCheckBox("Pre-op")
        self.chk_post = QtWidgets.QCheckBox("Post-op")
        self.chk_pre.setChecked(True)
        self.chk_post.setChecked(True)
        self.chk_pre.toggled.connect(lambda s: self._set_visible("preop", s))
        self.chk_post.toggled.connect(lambda s: self._set_visible("postop", s))
        self.opa_pre = self._make_opacity_slider("preop")
        self.opa_post = self._make_opacity_slider("postop")
        vis_layout.addWidget(self.chk_pre, 0, 0)
        vis_layout.addWidget(self.opa_pre, 0, 1)
        vis_layout.addWidget(self.chk_post, 1, 0)
        vis_layout.addWidget(self.opa_post, 1, 1)
        v.addWidget(vis_box)

        # Anatomical views
        view_box = QtWidgets.QGroupBox("Surgeon's view")
        view_layout = QtWidgets.QVBoxLayout(view_box)
        grid = QtWidgets.QGridLayout()
        for i, name in enumerate(ANATOMICAL_VIEWS):
            btn = QtWidgets.QPushButton(name)
            btn.clicked.connect(lambda _=False, n=name: self._apply_view(n))
            grid.addWidget(btn, i // 2, i % 2)
        view_layout.addLayout(grid)
        btn_save = QtWidgets.QPushButton("Save current view")
        btn_recall = QtWidgets.QPushButton("Recall saved view")
        btn_save.clicked.connect(self._save_view)
        btn_recall.clicked.connect(self._recall_view)
        view_layout.addWidget(btn_save)
        view_layout.addWidget(btn_recall)
        v.addWidget(view_box)

        # Export
        btn_export = QtWidgets.QPushButton("Export visible mesh (STL)...")
        btn_export.clicked.connect(self._export)
        v.addWidget(btn_export)

        v.addStretch(1)
        self.status = QtWidgets.QLabel("Load a CT series to begin.")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        return panel

    def _make_opacity_slider(self, key: str) -> QtWidgets.QSlider:
        slider = QtWidgets.QSlider(Qt.Horizontal)
        slider.setRange(10, 100)
        slider.setValue(100)
        slider.valueChanged.connect(
            lambda val, k=key: self._set_opacity(k, val / 100.0)
        )
        return slider

    def _add_orientation_widget(self) -> None:
        axes = vtk.vtkAxesActor()
        self.orientation_marker = vtk.vtkOrientationMarkerWidget()
        self.orientation_marker.SetOrientationMarker(axes)
        self.orientation_marker.SetInteractor(self.interactor)
        self.orientation_marker.SetViewport(0.0, 0.0, 0.18, 0.22)
        self.orientation_marker.EnabledOn()
        self.orientation_marker.InteractiveOff()

    # -------------------------------------------------------------- actions
    def _current_params(self) -> ReconstructionParams:
        return ReconstructionParams(threshold_hu=float(self.thr_slider.value()))

    def _load_study(self, key: str) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, f"Select {self.models[key].label} DICOM folder"
        )
        if not directory:
            return
        self.status.setText(f"Loading {self.models[key].label}...")
        QtWidgets.QApplication.processEvents()
        try:
            volume = load_dicom_series(directory)
        except Exception as exc:  # surface load errors to the user
            QtWidgets.QMessageBox.critical(self, "Load failed", str(exc))
            self.status.setText("Load failed.")
            return
        self.models[key].volume = volume
        self._rebuild(key, reset_camera=True)
        lo, hi = volume.hu_range
        self.status.setText(
            f"{self.models[key].label} loaded: {volume.description}\n"
            f"HU range [{lo:.0f}, {hi:.0f}], spacing {volume.spacing}"
        )

    def _rebuild_all(self) -> None:
        for key in self.models:
            if self.models[key].volume is not None:
                self._rebuild(key, reset_camera=False)

    def _rebuild(self, key: str, reset_camera: bool) -> None:
        model = self.models[key]
        if model.volume is None:
            return
        mesh = reconstruct_bone(model.volume, self._current_params())

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(mesh)
        mapper.ScalarVisibilityOff()

        if model.actor is None:
            model.actor = vtk.vtkActor()
            self.renderer.AddActor(model.actor)
        model.actor.SetMapper(mapper)
        model.actor.GetProperty().SetColor(*model.color)
        model.actor.GetProperty().SetSpecular(0.3)
        model.actor.GetProperty().SetSpecularPower(20)

        if reset_camera:
            self.renderer.ResetCamera()
        self.vtk_widget.GetRenderWindow().Render()

    def _set_visible(self, key: str, visible: bool) -> None:
        actor = self.models[key].actor
        if actor is not None:
            actor.SetVisibility(visible)
            self.vtk_widget.GetRenderWindow().Render()

    def _set_opacity(self, key: str, opacity: float) -> None:
        actor = self.models[key].actor
        if actor is not None:
            actor.GetProperty().SetOpacity(opacity)
            self.vtk_widget.GetRenderWindow().Render()

    def _apply_view(self, name: str) -> None:
        apply_anatomical_view(self.renderer, name)
        self.vtk_widget.GetRenderWindow().Render()

    def _save_view(self) -> None:
        self.saved_pose = CameraPose.capture(self.renderer.GetActiveCamera())
        self.status.setText("Surgeon's view saved.")

    def _recall_view(self) -> None:
        if self.saved_pose is None:
            self.status.setText("No saved view yet.")
            return
        self.saved_pose.apply(self.renderer.GetActiveCamera())
        self.renderer.ResetCameraClippingRange()
        self.vtk_widget.GetRenderWindow().Render()

    def _export(self) -> None:
        # Export the first visible model with a reconstruction.
        for key, model in self.models.items():
            if model.actor is not None and model.actor.GetVisibility():
                path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Export STL", f"{key}.stl", "Mesh (*.stl *.ply *.obj)"
                )
                if not path:
                    return
                mesh = model.actor.GetMapper().GetInput()
                export_mesh(mesh, path)
                self.status.setText(f"Exported to {path}")
                return
        self.status.setText("Nothing visible to export.")

    def start(self) -> None:
        self.show()
        self.interactor.Initialize()
