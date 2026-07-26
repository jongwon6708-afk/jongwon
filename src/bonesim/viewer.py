"""Interactive 3D viewer window (PyQt5 + VTK).

Loads pre-operative and post-operative CT series, reconstructs each as a bone
surface, and shows them in a trackball-navigable 3D scene. The surgeon can:

  * drag to rotate / scroll to zoom (default VTK trackball interactor),
  * snap to anatomical preset views and save a custom "surgeon's view",
  * toggle pre-op vs post-op visibility and opacity,
  * tune the bone HU threshold, denoising, table removal and smoothing,
  * highlight fracture lines (surface curvature + sharp feature edges),
  * compare against a standard: mirror the healthy side or load a reference
    STL, register it (ICP) and colour the bone by deviation,
  * export the mesh to STL.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import vtk
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from . import analysis, editing
from .analysis import cross_section
from .camera_views import ANATOMICAL_VIEWS, CameraPose, apply_anatomical_view
from .dicom_loader import CTVolume, load_dicom_series
from .preprocessing import PreprocessParams
from .reconstruction import ReconstructionParams, export_mesh, reconstruct_bone

# Distinct colours so the two studies are easy to tell apart.
PREOP_COLOR = (0.92, 0.87, 0.78)   # bone ivory
POSTOP_COLOR = (0.55, 0.78, 0.92)  # cool blue
FRACTURE_EDGE_COLOR = (1.0, 0.15, 0.15)  # red crack lines
REFERENCE_COLOR = (0.45, 0.85, 0.5)      # green standard/reference
SELECTION_COLOR = (1.0, 0.55, 0.1)       # orange picked structure


@dataclass
class BoneModel:
    """A loaded study and its current reconstruction in the scene."""

    volume: CTVolume | None = None
    mesh: vtk.vtkPolyData | None = None
    actor: vtk.vtkActor | None = None
    edge_actor: vtk.vtkActor | None = None
    color: tuple[float, float, float] = PREOP_COLOR
    label: str = ""


class ViewerWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("3D Bone CT Simulator")
        self.resize(1320, 860)

        self.models: dict[str, BoneModel] = {
            "preop": BoneModel(color=PREOP_COLOR, label="Pre-op"),
            "postop": BoneModel(color=POSTOP_COLOR, label="Post-op"),
        }
        self.saved_pose: CameraPose | None = None
        self.reference_mesh: vtk.vtkPolyData | None = None
        self.reference_actor: vtk.vtkActor | None = None
        self.scalar_bar: vtk.vtkScalarBarActor | None = None
        self.crop_bounds: tuple | None = None
        self.box_widget: vtk.vtkBoxWidget2 | None = None

        # Bone-editing state.
        self.edit_key = "preop"           # which study edits apply to
        self.selected_regions: set[int] = set()
        self.selection_actor: vtk.vtkActor | None = None
        self.undo_mesh: vtk.vtkPolyData | None = None
        self.lasso_widget = None
        self._pick_observer = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        self.vtk_widget = QVTKRenderWindowInteractor(central)
        layout.addWidget(self.vtk_widget, stretch=1)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.12, 0.13, 0.16)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)

        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

        self._add_orientation_widget()

        # Scrollable control panel (many options).
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(320)
        scroll.setWidget(self._build_control_panel())
        layout.addWidget(scroll)

    def _build_control_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(panel)

        # --- Load ---
        load_box = QtWidgets.QGroupBox("Load CT series")
        load_layout = QtWidgets.QVBoxLayout(load_box)
        btn_pre = QtWidgets.QPushButton("Load Pre-op CT...")
        btn_post = QtWidgets.QPushButton("Load Post-op CT...")
        btn_pre.clicked.connect(lambda: self._load_study("preop"))
        btn_post.clicked.connect(lambda: self._load_study("postop"))
        load_layout.addWidget(btn_pre)
        load_layout.addWidget(btn_post)
        v.addWidget(load_box)

        # --- Threshold ---
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

        # --- Reconstruction quality / cleanup ---
        clean_box = QtWidgets.QGroupBox("Cleanup & quality")
        clean_layout = QtWidgets.QVBoxLayout(clean_box)
        self.chk_denoise = QtWidgets.QCheckBox("Median denoise (specks)")
        self.chk_denoise.setChecked(True)
        self.chk_largest = QtWidgets.QCheckBox("Keep largest bone only")
        self.chk_largest.setToolTip(
            "Caution: removes ALL disconnected pieces, including displaced "
            "fracture fragments. Use the crop box to remove the table instead."
        )
        self.chk_solid = QtWidgets.QCheckBox("Solid fill (hollow interiors)")
        self.chk_solid.setToolTip(
            "Fill enclosed low-HU cavities (e.g. femoral head trabecular "
            "interior) so it looks solid. Visualisation only -- not for FEA."
        )
        for chk in (self.chk_denoise, self.chk_largest, self.chk_solid):
            chk.toggled.connect(self._rebuild_all)
            clean_layout.addWidget(chk)
        # Crop box: the fracture-safe way to remove the table / back board.
        crop_row = QtWidgets.QHBoxLayout()
        btn_box = QtWidgets.QPushButton("Show crop box")
        btn_apply_crop = QtWidgets.QPushButton("Apply crop")
        btn_clear_crop = QtWidgets.QPushButton("Clear")
        btn_box.clicked.connect(self._toggle_crop_box)
        btn_apply_crop.clicked.connect(self._apply_crop)
        btn_clear_crop.clicked.connect(self._clear_crop)
        crop_row.addWidget(btn_box)
        crop_row.addWidget(btn_apply_crop)
        crop_row.addWidget(btn_clear_crop)
        clean_layout.addWidget(QtWidgets.QLabel("Remove table: crop box"))
        clean_layout.addLayout(crop_row)
        clean_layout.addWidget(QtWidgets.QLabel("Smoothing (low = sharp fracture)"))
        self.smooth_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.smooth_slider.setRange(0, 30)
        self.smooth_slider.setValue(ReconstructionParams().smoothing_iterations)
        self.smooth_slider.sliderReleased.connect(self._rebuild_all)
        clean_layout.addWidget(self.smooth_slider)
        v.addWidget(clean_box)

        # --- Bone editing (clinical clean-up workflow) ---
        edit_box = QtWidgets.QGroupBox("Edit / isolate bone")
        edit_layout = QtWidgets.QVBoxLayout(edit_box)
        edit_layout.addWidget(QtWidgets.QLabel(
            "Left-click a bone to select it"))
        self.lbl_selection = QtWidgets.QLabel("Selected: none")
        self.lbl_selection.setWordWrap(True)
        edit_layout.addWidget(self.lbl_selection)

        pick_row = QtWidgets.QHBoxLayout()
        self.btn_pick = QtWidgets.QPushButton("Pick mode")
        self.btn_pick.setCheckable(True)
        self.btn_pick.toggled.connect(self._toggle_pick_mode)
        btn_clear_sel = QtWidgets.QPushButton("Clear")
        btn_clear_sel.clicked.connect(self._clear_selection)
        pick_row.addWidget(self.btn_pick)
        pick_row.addWidget(btn_clear_sel)
        edit_layout.addLayout(pick_row)

        keep_row = QtWidgets.QHBoxLayout()
        btn_keep = QtWidgets.QPushButton("Keep only")
        btn_delete = QtWidgets.QPushButton("Delete")
        btn_keep.setToolTip("Isolate the selected bone, remove everything else")
        btn_delete.setToolTip("Remove the selected structure (table, other limb)")
        btn_keep.clicked.connect(lambda: self._apply_selection(invert=False))
        btn_delete.clicked.connect(lambda: self._apply_selection(invert=True))
        keep_row.addWidget(btn_keep)
        keep_row.addWidget(btn_delete)
        edit_layout.addLayout(keep_row)

        # Scissors: for structures that touch, where connectivity can't split.
        self.btn_scissors = QtWidgets.QPushButton("Scissors lasso")
        self.btn_scissors.setCheckable(True)
        self.btn_scissors.setToolTip(
            "Drag to draw a loop; everything inside is cut away through the "
            "view direction. Use where bones touch across a joint."
        )
        self.btn_scissors.toggled.connect(self._toggle_scissors)
        edit_layout.addWidget(self.btn_scissors)
        btn_apply_lasso = QtWidgets.QPushButton("Apply lasso cut")
        btn_apply_lasso.clicked.connect(self._apply_lasso)
        edit_layout.addWidget(btn_apply_lasso)
        self.chk_scissors_keep = QtWidgets.QCheckBox("Keep inside instead")
        edit_layout.addWidget(self.chk_scissors_keep)

        btn_undo = QtWidgets.QPushButton("Undo edit")
        btn_undo.clicked.connect(self._undo_edit)
        edit_layout.addWidget(btn_undo)
        v.addWidget(edit_box)

        # --- Fracture analysis ---
        frac_box = QtWidgets.QGroupBox("Fracture analysis")
        frac_layout = QtWidgets.QVBoxLayout(frac_box)
        self.chk_curvature = QtWidgets.QCheckBox("Highlight curvature")
        self.chk_curvature.toggled.connect(self._refresh_display)
        self.chk_edges = QtWidgets.QCheckBox("Show fracture edges (red)")
        self.chk_edges.toggled.connect(self._refresh_display)
        frac_layout.addWidget(self.chk_curvature)
        frac_layout.addWidget(self.chk_edges)
        v.addWidget(frac_box)

        # --- Cross-section (cut the bone open to see inside) ---
        xs_box = QtWidgets.QGroupBox("Cross-section")
        xs_layout = QtWidgets.QVBoxLayout(xs_box)
        self.chk_xs = QtWidgets.QCheckBox("Enable cutting plane")
        self.chk_xs.toggled.connect(self._refresh_display)
        xs_layout.addWidget(self.chk_xs)
        axis_row = QtWidgets.QHBoxLayout()
        axis_row.addWidget(QtWidgets.QLabel("Axis"))
        self.xs_axis = QtWidgets.QComboBox()
        self.xs_axis.addItems(["X (sagittal)", "Y (coronal)", "Z (axial)"])
        self.xs_axis.setCurrentIndex(2)
        self.xs_axis.currentIndexChanged.connect(self._refresh_display)
        axis_row.addWidget(self.xs_axis)
        xs_layout.addLayout(axis_row)
        xs_layout.addWidget(QtWidgets.QLabel("Cut position"))
        self.xs_pos = QtWidgets.QSlider(Qt.Horizontal)
        self.xs_pos.setRange(0, 100)
        self.xs_pos.setValue(50)
        self.xs_pos.valueChanged.connect(self._refresh_display)
        xs_layout.addWidget(self.xs_pos)
        self.chk_xs_flip = QtWidgets.QCheckBox("Flip side")
        self.chk_xs_flip.toggled.connect(self._refresh_display)
        self.chk_xs_cap = QtWidgets.QCheckBox("Fill cut face (solid)")
        self.chk_xs_cap.setChecked(True)
        self.chk_xs_cap.setToolTip(
            "Cap the cut so a solid interior shows a filled face and a hollow "
            "one shows a ring -- the way to tell solid from hollow."
        )
        self.chk_xs_cap.toggled.connect(self._refresh_display)
        xs_layout.addWidget(self.chk_xs_flip)
        xs_layout.addWidget(self.chk_xs_cap)
        v.addWidget(xs_box)

        # --- Visibility / opacity ---
        vis_box = QtWidgets.QGroupBox("Visibility")
        vis_layout = QtWidgets.QGridLayout(vis_box)
        self.chk_pre = QtWidgets.QCheckBox("Pre-op")
        self.chk_post = QtWidgets.QCheckBox("Post-op")
        self.chk_pre.setChecked(True)
        self.chk_post.setChecked(True)
        self.chk_pre.toggled.connect(lambda s: self._set_visible("preop", s))
        self.chk_post.toggled.connect(lambda s: self._set_visible("postop", s))
        vis_layout.addWidget(self.chk_pre, 0, 0)
        vis_layout.addWidget(self._make_opacity_slider("preop"), 0, 1)
        vis_layout.addWidget(self.chk_post, 1, 0)
        vis_layout.addWidget(self._make_opacity_slider("postop"), 1, 1)
        v.addWidget(vis_box)

        # --- Compare to standard ---
        cmp_box = QtWidgets.QGroupBox("Compare to standard")
        cmp_layout = QtWidgets.QVBoxLayout(cmp_box)
        btn_mirror = QtWidgets.QPushButton("Mirror Pre-op -> standard")
        btn_loadref = QtWidgets.QPushButton("Load reference STL...")
        btn_dev = QtWidgets.QPushButton("Register + deviation map")
        btn_mirror.clicked.connect(self._mirror_to_reference)
        btn_loadref.clicked.connect(self._load_reference)
        btn_dev.clicked.connect(self._deviation_map)
        cmp_layout.addWidget(btn_mirror)
        cmp_layout.addWidget(btn_loadref)
        cmp_layout.addWidget(btn_dev)
        v.addWidget(cmp_box)

        # --- Views ---
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

    # -------------------------------------------------------------- params
    def _current_params(self) -> ReconstructionParams:
        return ReconstructionParams(
            threshold_hu=float(self.thr_slider.value()),
            smoothing_iterations=int(self.smooth_slider.value()),
            largest_component_only=self.chk_largest.isChecked(),
            solid_fill=self.chk_solid.isChecked(),
            preprocess=PreprocessParams(
                median_denoise=self.chk_denoise.isChecked(),
                crop_bounds=self.crop_bounds,
            ),
        )

    # --------------------------------------------------------------- load
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
        except Exception as exc:
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
        self.status.setText(f"Reconstructing {model.label}...")
        QtWidgets.QApplication.processEvents()
        model.mesh = reconstruct_bone(model.volume, self._current_params())

        if model.actor is None:
            model.actor = vtk.vtkActor()
            self.renderer.AddActor(model.actor)

        self._apply_model_display(key)

        if reset_camera:
            self.renderer.ResetCamera()
        self.vtk_widget.GetRenderWindow().Render()

    # ------------------------------------------------------------ display
    def _refresh_display(self) -> None:
        for key in self.models:
            if self.models[key].mesh is not None:
                self._apply_model_display(key)
        self.vtk_widget.GetRenderWindow().Render()

    def _apply_model_display(self, key: str) -> None:
        """Set up the mapper/actor for a model per the current display mode."""
        model = self.models[key]
        mesh = model.mesh
        if mesh is None or model.actor is None:
            return

        mapper = vtk.vtkPolyDataMapper()
        if self.chk_xs.isChecked():
            # Cross-section view takes priority: cut the bone open. Curvature
            # colouring is dropped here so the cut face reads as solid.
            section = cross_section(
                mesh, *self._section_plane(mesh),
                capped=self.chk_xs_cap.isChecked(),
            )
            mapper.SetInputData(section)
            mapper.ScalarVisibilityOff()
        elif self.chk_curvature.isChecked():
            colored = analysis.curvature_scalars(mesh, "mean")
            mapper.SetInputData(colored)
            mapper.SetLookupTable(_curvature_lut())
            rng = _robust_range(colored)
            mapper.SetScalarRange(*rng)
            mapper.ScalarVisibilityOn()
        else:
            mapper.SetInputData(mesh)
            mapper.ScalarVisibilityOff()

        model.actor.SetMapper(mapper)
        prop = model.actor.GetProperty()
        prop.SetColor(*model.color)
        prop.SetSpecular(0.3)
        prop.SetSpecularPower(20)

        self._update_edges(key)

    def _section_plane(self, mesh: vtk.vtkPolyData):
        """Return (origin, normal) for the current cross-section controls."""
        axis = self.xs_axis.currentIndex()  # 0=x, 1=y, 2=z
        bounds = mesh.GetBounds()
        center = [
            (bounds[0] + bounds[1]) / 2.0,
            (bounds[2] + bounds[3]) / 2.0,
            (bounds[4] + bounds[5]) / 2.0,
        ]
        lo, hi = bounds[axis * 2], bounds[axis * 2 + 1]
        frac = self.xs_pos.value() / 100.0
        center[axis] = lo + (hi - lo) * frac

        normal = [0.0, 0.0, 0.0]
        normal[axis] = -1.0 if self.chk_xs_flip.isChecked() else 1.0
        return tuple(center), tuple(normal)

    def _update_edges(self, key: str) -> None:
        model = self.models[key]
        # Suppress the full-bone edge overlay while cross-sectioning.
        if (self.chk_edges.isChecked() and model.mesh is not None
                and not self.chk_xs.isChecked()):
            edges = analysis.fracture_feature_edges(model.mesh, feature_angle=55.0)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(edges)
            mapper.ScalarVisibilityOff()
            if model.edge_actor is None:
                model.edge_actor = vtk.vtkActor()
                self.renderer.AddActor(model.edge_actor)
            model.edge_actor.SetMapper(mapper)
            model.edge_actor.GetProperty().SetColor(*FRACTURE_EDGE_COLOR)
            model.edge_actor.GetProperty().SetLineWidth(2.0)
            model.edge_actor.SetVisibility(model.actor.GetVisibility())
        elif model.edge_actor is not None:
            model.edge_actor.SetVisibility(False)

    def _set_visible(self, key: str, visible: bool) -> None:
        model = self.models[key]
        if model.actor is not None:
            model.actor.SetVisibility(visible)
        if model.edge_actor is not None:
            model.edge_actor.SetVisibility(visible and self.chk_edges.isChecked())
        self.vtk_widget.GetRenderWindow().Render()

    def _set_opacity(self, key: str, opacity: float) -> None:
        actor = self.models[key].actor
        if actor is not None:
            actor.GetProperty().SetOpacity(opacity)
            self.vtk_widget.GetRenderWindow().Render()

    # -------------------------------------------------------------- edit
    def _active_edit_model(self) -> BoneModel | None:
        """The model edits apply to: post-op if loaded, else pre-op."""
        for key in ("preop", "postop"):
            if self.models[key].mesh is not None:
                self.edit_key = key
                return self.models[key]
        return None

    def _toggle_pick_mode(self, enabled: bool) -> None:
        """Left-click on the bone selects its connected structure."""
        if enabled:
            if self.btn_scissors.isChecked():
                self.btn_scissors.setChecked(False)
            self._pick_observer = self.interactor.AddObserver(
                "LeftButtonPressEvent", self._on_pick_click, 1.0
            )
            self.status.setText("Pick mode: click a bone to select it.")
        elif self._pick_observer is not None:
            self.interactor.RemoveObserver(self._pick_observer)
            self._pick_observer = None
            self.status.setText("Pick mode off.")

    def _on_pick_click(self, caller, event) -> None:
        model = self._active_edit_model()
        if model is None or model.mesh is None:
            return
        x, y = self.interactor.GetEventPosition()
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        if not picker.Pick(x, y, 0, self.renderer):
            return
        rid = editing.region_id_at_point(model.mesh, picker.GetPickPosition())
        if rid is None:
            return
        # Ctrl-click adds to the selection, plain click replaces it.
        if not self.interactor.GetControlKey():
            self.selected_regions.clear()
        self.selected_regions.add(rid)
        self._show_selection()

    def _show_selection(self) -> None:
        model = self.models[self.edit_key]
        if model.mesh is None or not self.selected_regions:
            self._clear_selection_actor()
            return
        highlight = editing.extract_regions(
            model.mesh, self.selected_regions, invert=False
        )
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(highlight)
        mapper.ScalarVisibilityOff()
        if self.selection_actor is None:
            self.selection_actor = vtk.vtkActor()
            self.renderer.AddActor(self.selection_actor)
        self.selection_actor.SetMapper(mapper)
        self.selection_actor.GetProperty().SetColor(*SELECTION_COLOR)
        self.selection_actor.GetProperty().SetOpacity(0.65)
        self.selection_actor.SetVisibility(True)
        sizes = editing.region_sizes(model.mesh)
        total = sum(sizes) or 1
        picked = sum(sizes[i] for i in self.selected_regions if i < len(sizes))
        self.lbl_selection.setText(
            f"Selected: {len(self.selected_regions)} structure(s), "
            f"{picked * 100 // total}% of surface"
        )
        self.vtk_widget.GetRenderWindow().Render()

    def _clear_selection_actor(self) -> None:
        if self.selection_actor is not None:
            self.selection_actor.SetVisibility(False)
        self.lbl_selection.setText("Selected: none")
        self.vtk_widget.GetRenderWindow().Render()

    def _clear_selection(self) -> None:
        self.selected_regions.clear()
        self._clear_selection_actor()

    def _apply_selection(self, invert: bool) -> None:
        """Keep only, or delete, the currently selected structures."""
        model = self._active_edit_model()
        if model is None or model.mesh is None:
            self.status.setText("Load a study first.")
            return
        if not self.selected_regions:
            self.status.setText("Nothing selected -- click a bone first.")
            return
        self.undo_mesh = model.mesh
        model.mesh = editing.extract_regions(
            model.mesh, self.selected_regions, invert=invert
        )
        self.selected_regions.clear()
        self._clear_selection_actor()
        self._apply_model_display(self.edit_key)
        self.vtk_widget.GetRenderWindow().Render()
        self.status.setText(
            f"{'Deleted' if invert else 'Isolated'} selection on {model.label}."
        )

    def _toggle_scissors(self, enabled: bool) -> None:
        """Draw a closed loop on screen; cut everything inside it."""
        if not enabled:
            if self.lasso_widget is not None:
                self.lasso_widget.Off()
                self.lasso_widget = None
            self.status.setText("Scissors off.")
            return
        if self.btn_pick.isChecked():
            self.btn_pick.setChecked(False)
        model = self._active_edit_model()
        if model is None or model.mesh is None:
            self.status.setText("Load a study first.")
            self.btn_scissors.setChecked(False)
            return

        # Freehand loop drawn on screen with a contour widget.
        rep = vtk.vtkOrientedGlyphContourRepresentation()
        rep.GetLinesProperty().SetColor(1.0, 0.4, 0.1)
        rep.GetLinesProperty().SetLineWidth(3.0)
        widget = vtk.vtkContourWidget()
        widget.SetRepresentation(rep)
        widget.SetInteractor(self.interactor)
        widget.ContinuousDrawOn()
        widget.On()
        self.lasso_widget = widget
        self.status.setText(
            "Scissors: drag to draw a loop around the part to remove, "
            "then press 'Apply lasso cut'."
        )

    def _apply_lasso(self) -> None:
        """Cut the mesh with the drawn loop, along the current view direction."""
        model = self._active_edit_model()
        if self.lasso_widget is None or model is None or model.mesh is None:
            self.status.setText("Draw a lasso first.")
            return
        rep = self.lasso_widget.GetRepresentation()
        node_poly = vtk.vtkPolyData()
        rep.GetNodePolyData(node_poly)
        n = node_poly.GetNumberOfPoints()
        if n < 3:
            self.status.setText("Lasso needs at least 3 points.")
            return
        loop = [node_poly.GetPoint(i) for i in range(n)]
        normal = self.renderer.GetActiveCamera().GetDirectionOfProjection()

        self.undo_mesh = model.mesh
        model.mesh = editing.scissors_cut(
            model.mesh, loop, normal,
            keep_inside=self.chk_scissors_keep.isChecked(),
        )
        self.lasso_widget.Off()
        self.lasso_widget = None
        self.btn_scissors.setChecked(False)
        self._apply_model_display(self.edit_key)
        self.vtk_widget.GetRenderWindow().Render()
        self.status.setText("Lasso cut applied.")

    def _undo_edit(self) -> None:
        model = self.models[self.edit_key]
        if self.undo_mesh is None:
            self.status.setText("Nothing to undo.")
            return
        model.mesh, self.undo_mesh = self.undo_mesh, None
        self._clear_selection()
        self._apply_model_display(self.edit_key)
        self.vtk_widget.GetRenderWindow().Render()
        self.status.setText("Edit undone.")

    # -------------------------------------------------------------- crop
    def _toggle_crop_box(self) -> None:
        if self.box_widget is not None:
            self.box_widget.Off()
            self.box_widget = None
            self.vtk_widget.GetRenderWindow().Render()
            return
        bounds = self.renderer.ComputeVisiblePropBounds()
        if bounds[1] < bounds[0]:
            self.status.setText("Load and reconstruct a study first.")
            return
        rep = vtk.vtkBoxRepresentation()
        rep.SetPlaceFactor(1.0)
        rep.PlaceWidget(bounds)
        self.box_widget = vtk.vtkBoxWidget2()
        self.box_widget.SetRepresentation(rep)
        self.box_widget.SetInteractor(self.interactor)
        self.box_widget.On()
        self.status.setText("Drag the box to enclose the bone, then Apply crop.")
        self.vtk_widget.GetRenderWindow().Render()

    def _apply_crop(self) -> None:
        if self.box_widget is None:
            self.status.setText("Show the crop box first.")
            return
        self.crop_bounds = tuple(self.box_widget.GetRepresentation().GetBounds())
        self.box_widget.Off()
        self.box_widget = None
        self._rebuild_all()
        self.status.setText("Cropped. Table/board outside the box is removed.")

    def _clear_crop(self) -> None:
        self.crop_bounds = None
        self._rebuild_all()
        self.status.setText("Crop cleared.")

    # ----------------------------------------------------------- compare
    def _first_loaded_mesh(self) -> vtk.vtkPolyData | None:
        for key in ("preop", "postop"):
            if self.models[key].mesh is not None:
                return self.models[key].mesh
        return None

    def _mirror_to_reference(self) -> None:
        mesh = self.models["preop"].mesh or self._first_loaded_mesh()
        if mesh is None:
            self.status.setText("Load a study first.")
            return
        self.reference_mesh = analysis.mirror_mesh(mesh, "x")
        self._show_reference()
        self.status.setText("Mirrored healthy side set as standard (green).")

    def _load_reference(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load reference mesh", "", "Mesh (*.stl *.ply *.obj)"
        )
        if not path:
            return
        reader = _mesh_reader(path)
        if reader is None:
            self.status.setText("Unsupported mesh format.")
            return
        reader.SetFileName(path)
        reader.Update()
        self.reference_mesh = reader.GetOutput()
        self._show_reference()
        self.status.setText(f"Reference loaded: {path}")

    def _show_reference(self) -> None:
        if self.reference_mesh is None:
            return
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(self.reference_mesh)
        mapper.ScalarVisibilityOff()
        if self.reference_actor is None:
            self.reference_actor = vtk.vtkActor()
            self.renderer.AddActor(self.reference_actor)
        self.reference_actor.SetMapper(mapper)
        self.reference_actor.GetProperty().SetColor(*REFERENCE_COLOR)
        self.reference_actor.GetProperty().SetOpacity(0.4)
        self.vtk_widget.GetRenderWindow().Render()

    def _deviation_map(self) -> None:
        if self.reference_mesh is None:
            self.status.setText("Set a standard first (mirror or load STL).")
            return
        target_key = "postop" if self.models["postop"].mesh is not None else "preop"
        model = self.models[target_key]
        if model.mesh is None:
            self.status.setText("No reconstruction to compare.")
            return

        self.status.setText("Registering to standard (ICP)...")
        QtWidgets.QApplication.processEvents()
        aligned, _ = analysis.register_icp(model.mesh, self.reference_mesh)
        dist = analysis.surface_distance(aligned, self.reference_mesh)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(dist)
        scalars = dist.GetPointData().GetScalars()
        rng = scalars.GetRange() if scalars else (0.0, 1.0)
        mapper.SetScalarRange(0.0, max(rng[1], 1.0))
        mapper.SetLookupTable(_deviation_lut(max(rng[1], 1.0)))
        mapper.ScalarVisibilityOn()
        model.actor.SetMapper(mapper)
        # Replace the on-screen mesh with the aligned, coloured one.
        model.actor.SetPosition(0, 0, 0)

        self._add_scalar_bar(mapper.GetLookupTable(), "Deviation (mm)")
        self.vtk_widget.GetRenderWindow().Render()
        self.status.setText(
            f"Deviation of {model.label} vs standard: max {rng[1]:.1f} mm."
        )

    def _add_scalar_bar(self, lut: vtk.vtkScalarsToColors, title: str) -> None:
        if self.scalar_bar is None:
            self.scalar_bar = vtk.vtkScalarBarActor()
            self.scalar_bar.SetNumberOfLabels(5)
            self.scalar_bar.SetPosition(0.86, 0.1)
            self.scalar_bar.SetWidth(0.12)
            self.scalar_bar.SetHeight(0.8)
            self.renderer.AddActor2D(self.scalar_bar)
        self.scalar_bar.SetLookupTable(lut)
        self.scalar_bar.SetTitle(title)
        self.scalar_bar.SetVisibility(True)

    # ------------------------------------------------------------- views
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
        for key, model in self.models.items():
            if model.actor is not None and model.actor.GetVisibility() and model.mesh:
                path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, "Export STL", f"{key}.stl", "Mesh (*.stl *.ply *.obj)"
                )
                if not path:
                    return
                export_mesh(model.mesh, path)
                self.status.setText(f"Exported to {path}")
                return
        self.status.setText("Nothing visible to export.")

    def start(self) -> None:
        self.show()
        self.interactor.Initialize()


# ----------------------------------------------------------------- helpers
def _mesh_reader(path: str):
    lower = path.lower()
    if lower.endswith(".stl"):
        return vtk.vtkSTLReader()
    if lower.endswith(".ply"):
        return vtk.vtkPLYReader()
    if lower.endswith(".obj"):
        return vtk.vtkOBJReader()
    return None


def _curvature_lut() -> vtk.vtkLookupTable:
    lut = vtk.vtkLookupTable()
    lut.SetHueRange(0.667, 0.0)  # blue (flat) -> red (high curvature)
    lut.SetNumberOfColors(256)
    lut.Build()
    return lut


def _deviation_lut(max_mm: float) -> vtk.vtkLookupTable:
    lut = vtk.vtkLookupTable()
    lut.SetHueRange(0.667, 0.0)  # blue (match) -> red (large deviation)
    lut.SetTableRange(0.0, max_mm)
    lut.SetNumberOfColors(256)
    lut.Build()
    return lut


def _robust_range(mesh: vtk.vtkPolyData) -> tuple[float, float]:
    """Symmetric curvature range clamped to suppress outliers."""
    scalars = mesh.GetPointData().GetScalars()
    if scalars is None:
        return (0.0, 1.0)
    lo, hi = scalars.GetRange()
    bound = max(abs(lo), abs(hi)) * 0.3 or 1.0
    return (-bound, bound)
