from __future__ import annotations

import json
import math
import sys
import uuid
from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QDoubleSpinBox,
    QGroupBox, QDockWidget, QFileDialog, QMessageBox, QToolBar, QFrame,
    QComboBox, QSlider
)
from pyvistaqt import QtInteractor


APP_NAME = "Models Studio"
THEME = """
QMainWindow, QWidget { background: #111018; color: #e9e5f3; }
QLabel { color: #e9e5f3; }
QGroupBox { border: 1px solid #30283b; border-radius: 8px; margin-top: 10px; padding: 8px; color: #c5a7ff; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QPushButton { background: #241b30; color: #eee8ff; border: 1px solid #443258; border-radius: 6px; padding: 8px 10px; }
QPushButton:hover { background: #38254f; border-color: #9b6bff; }
QPushButton:pressed { background: #583887; }
QListWidget { background: #17141e; border: 1px solid #342b40; border-radius: 6px; padding: 4px; }
QListWidget::item { padding: 7px; border-radius: 5px; }
QListWidget::item:selected { background: #51337c; color: white; }
QDoubleSpinBox, QComboBox { background: #1b1723; border: 1px solid #392e49; border-radius: 5px; padding: 4px; color: #f1eaff; }
QToolBar { background: #17131e; border: none; spacing: 5px; padding: 6px; }
QDockWidget::title { background: #191421; padding: 8px; color: #c7a3ff; }
QStatusBar { background: #17131e; color: #aaa0b9; }
"""

class ModelObject:
    def __init__(self, name, mesh, color="#a78bfa"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.mesh = mesh.copy()
        self.color = color
        self.position = [0.0, 0.0, 0.0]
        self.rotation = [0.0, 0.0, 0.0]
        self.scale = [1.0, 1.0, 1.0]

    def transformed_mesh(self):
        m = self.mesh.copy()
        m.scale(self.scale, inplace=True)
        m.rotate_x(self.rotation[0], inplace=True)
        m.rotate_y(self.rotation[1], inplace=True)
        m.rotate_z(self.rotation[2], inplace=True)
        m.translate(self.position, inplace=True)
        return m


class ModelsStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.objects = []
        self.actor_map = {}
        self.selected_id = None
        self.current_file = None
        self._building_controls = False
        self._setup_viewport()
        self._setup_toolbar()
        self._setup_panels()
        self.statusBar().showMessage("Ready · Create a primitive to begin")

    def _setup_viewport(self):
        self.plotter = QtInteractor(self)
        self.plotter.set_background("#111018")
        self.plotter.add_axes(color="#8f82a5")
        self.plotter.show_grid(color="#42364f", xlabel="X", ylabel="Y", zlabel="Z")
        self.setCentralWidget(self.plotter)
        self.plotter.view_isometric()
        self.plotter.camera.zoom(1.15)

    def _setup_toolbar(self):
        bar = QToolBar("Main")
        bar.setMovable(False)
        self.addToolBar(bar)
        for label, callback in [
            ("New", self.new_scene), ("Open", self.open_scene), ("Save", self.save_scene),
            ("Import", self.import_mesh), ("Export", self.export_meshes),
            ("Fit View", self.fit_view)
        ]:
            action = QAction(label, self)
            action.triggered.connect(callback)
            bar.addAction(action)
        bar.addSeparator()
        self.mode_label = QLabel("  MODELING")
        self.mode_label.setStyleSheet("color:#b99bff;font-weight:700;")
        bar.addWidget(self.mode_label)

    def _setup_panels(self):
        left = QDockWidget("Create", self)
        left.setAllowedAreas(Qt.LeftDockWidgetArea)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        intro = QLabel("PRIMITIVES")
        intro.setStyleSheet("color:#9f83d8; font-weight:700; letter-spacing:1px;")
        layout.addWidget(intro)
        grid = QGridLayout()
        choices = [
            ("Cube", self.add_cube), ("Sphere", self.add_sphere),
            ("Cylinder", self.add_cylinder), ("Cone", self.add_cone),
            ("Plane", self.add_plane), ("Torus", self.add_torus),
        ]
        for i, (name, cb) in enumerate(choices):
            b = QPushButton(name)
            b.clicked.connect(cb)
            grid.addWidget(b, i // 2, i % 2)
        layout.addLayout(grid)
        helptext = QLabel("Choose a shape to add it to your scene.")
        helptext.setWordWrap(True)
        helptext.setStyleSheet("color:#81788e;")
        layout.addWidget(helptext)
        layout.addStretch()
        left.setWidget(panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, left)
        left.setMinimumWidth(205)

        right = QDockWidget("Scene & Properties", self)
        right.setAllowedAreas(Qt.RightDockWidgetArea)
        rp = QWidget()
        rl = QVBoxLayout(rp)
        rl.addWidget(QLabel("SCENE OBJECTS"))
        self.outliner = QListWidget()
        self.outliner.currentItemChanged.connect(self.select_from_list)
        rl.addWidget(self.outliner, 2)
        row = QHBoxLayout()
        rename = QPushButton("Rename")
        rename.clicked.connect(self.rename_selected)
        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete_selected)
        row.addWidget(rename)
        row.addWidget(delete)
        rl.addLayout(row)
        self.props_group = QGroupBox("Transform")
        pg = QGridLayout(self.props_group)
        self.spin_controls = {}
        for section, labels, target in [
            ("Position", ["X", "Y", "Z"], "position"),
            ("Rotation °", ["X", "Y", "Z"], "rotation"),
            ("Scale", ["X", "Y", "Z"], "scale"),
        ]:
            rownum = pg.rowCount()
            pg.addWidget(QLabel(section), rownum, 0, 1, 4)
            for i, axis in enumerate(labels):
                spin = QDoubleSpinBox()
                spin.setRange(-100000, 100000)
                spin.setDecimals(3)
                spin.setSingleStep(0.1 if target != "rotation" else 5)
                spin.valueChanged.connect(lambda value, t=target, idx=i: self.change_transform(t, idx, value))
                self.spin_controls[(target, i)] = spin
                pg.addWidget(QLabel(axis), rownum + 1, i)
                pg.addWidget(spin, rownum + 2, i)
        rl.addWidget(self.props_group)
        note = QLabel("Transforms are applied to the selected mesh.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#81788e;")
        rl.addWidget(note)
        right.setWidget(rp)
        self.addDockWidget(Qt.RightDockWidgetArea, right)
        right.setMinimumWidth(290)
        self._set_controls_enabled(False)

    def _add_object(self, name, mesh):
        mesh = mesh.triangulate().clean()
        obj = ModelObject(name, mesh)
        self.objects.append(obj)
        actor = self.plotter.add_mesh(obj.transformed_mesh(), color=obj.color, smooth_shading=True,
                                     show_edges=False, name=obj.id)
        self.actor_map[obj.id] = actor
        self._refresh_outliner()
        self.select_object(obj.id)
        self.fit_view()
        self.statusBar().showMessage(f"Added {name}")

    def add_cube(self):
        self._add_object("Cube", pv.Cube(x_length=1, y_length=1, z_length=1))

    def add_sphere(self):
        self._add_object("Sphere", pv.Sphere(radius=0.5, theta_resolution=48, phi_resolution=48))

    def add_cylinder(self):
        self._add_object("Cylinder", pv.Cylinder(radius=0.5, height=1, resolution=48))

    def add_cone(self):
        self._add_object("Cone", pv.Cone(radius=0.5, height=1, resolution=48))

    def add_plane(self):
        self._add_object("Plane", pv.Plane(i_size=2, j_size=2, i_resolution=1, j_resolution=1))

    def add_torus(self):
        try:
            mesh = pv.ParametricTorus(ringradius=0.5, crosssection=0.18)
            self._add_object("Torus", mesh)
        except Exception as exc:
            QMessageBox.warning(self, "Torus", str(exc))

    def _refresh_outliner(self):
        self.outliner.blockSignals(True)
        self.outliner.clear()
        for obj in self.objects:
            item = QListWidgetItem("◈  " + obj.name)
            item.setData(Qt.UserRole, obj.id)
            self.outliner.addItem(item)
            if obj.id == self.selected_id:
                self.outliner.setCurrentItem(item)
        self.outliner.blockSignals(False)

    def select_from_list(self, item, previous):
        if item:
            self.select_object(item.data(Qt.UserRole))

    def select_object(self, object_id):
        self.selected_id = object_id
        obj = next((o for o in self.objects if o.id == object_id), None)
        self._refresh_outliner()
        self._set_controls_enabled(obj is not None)
        if obj:
            self._building_controls = True
            for target, values in [("position", obj.position), ("rotation", obj.rotation), ("scale", obj.scale)]:
                for i, value in enumerate(values):
                    self.spin_controls[(target, i)].setValue(value)
            self._building_controls = False

    def _set_controls_enabled(self, enabled):
        for control in self.spin_controls.values():
            control.setEnabled(enabled)

    def change_transform(self, target, axis, value):
        if self._building_controls or not self.selected_id:
            return
        obj = next((o for o in self.objects if o.id == self.selected_id), None)
        if not obj:
            return
        getattr(obj, target)[axis] = value
        self._replace_actor(obj)

    def _replace_actor(self, obj):
        old = self.actor_map.get(obj.id)
        if old:
            self.plotter.remove_actor(old, render=False)
        actor = self.plotter.add_mesh(obj.transformed_mesh(), color=obj.color, smooth_shading=True,
                                     show_edges=False, name=obj.id, render=False)
        self.actor_map[obj.id] = actor
        self.plotter.render()

    def rename_selected(self):
        if not self.selected_id:
            return
        from PySide6.QtWidgets import QInputDialog
        obj = next((o for o in self.objects if o.id == self.selected_id), None)
        if obj:
            name, ok = QInputDialog.getText(self, "Rename object", "Object name:", text=obj.name)
            if ok and name.strip():
                obj.name = name.strip()
                self._refresh_outliner()

    def delete_selected(self):
        if not self.selected_id:
            return
        obj = next((o for o in self.objects if o.id == self.selected_id), None)
        if obj:
            actor = self.actor_map.pop(obj.id, None)
            if actor:
                self.plotter.remove_actor(actor, render=False)
            self.objects = [o for o in self.objects if o.id != obj.id]
            self.selected_id = None
            self._refresh_outliner()
            self._set_controls_enabled(False)
            self.plotter.render()
            self.statusBar().showMessage("Object removed")

    def fit_view(self):
        self.plotter.reset_camera()
        self.plotter.render()

    def import_mesh(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import 3D mesh", "", "3D files (*.stl *.obj *.glb *.gltf *.ply *.3mf);;All files (*)")
        if not path:
            return
        try:
            loaded = trimesh.load(path, force="mesh")
            if isinstance(loaded, trimesh.Scene):
                loaded = loaded.to_geometry()
            mesh = pv.wrap(loaded)
            self._add_object(Path(path).stem, mesh)
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", f"Could not import mesh:\n{exc}")

    def export_meshes(self):
        if not self.objects:
            QMessageBox.information(self, "Export", "Create or import an object first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export model", "model.stl", "STL (*.stl);;OBJ (*.obj);;GLB (*.glb);;PLY (*.ply)")
        if not path:
            return
        try:
            ext = Path(path).suffix.lower()
            meshes = []
            for obj in self.objects:
                mesh = obj.transformed_mesh()
                tri = mesh.triangulate()
                faces = tri.faces.reshape(-1, 4)[:, 1:]
                tm = trimesh.Trimesh(vertices=np.asarray(tri.points), faces=faces, process=False)
                meshes.append(tm)
            scene = trimesh.Scene(meshes)
            scene.export(path)
            self.statusBar().showMessage(f"Exported {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", f"Export error:\n{exc}")

    def new_scene(self):
        if self.objects:
            reply = QMessageBox.question(self, "New scene", "Remove all objects and start a new scene?")
            if reply != QMessageBox.Yes:
                return
        self.plotter.clear()
        self.plotter.add_axes(color="#8f82a5")
        self.plotter.show_grid(color="#42364f", xlabel="X", ylabel="Y", zlabel="Z")
        self.objects.clear()
        self.actor_map.clear()
        self.selected_id = None
        self._refresh_outliner()
        self._set_controls_enabled(False)
        self.current_file = None
        self.statusBar().showMessage("New scene")

    def save_scene(self):
        path = self.current_file
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Models Studio project", "Scene.models.json", "Models Studio (*.models.json);;JSON (*.json)")
        if not path:
            return
        data = []
        for obj in self.objects:
            data.append({
                "name": obj.name, "color": obj.color,
                "position": obj.position, "rotation": obj.rotation, "scale": obj.scale,
                "vertices": obj.mesh.points.tolist(),
                "faces": obj.mesh.faces.tolist(),
            })
        try:
            Path(path).write_text(json.dumps({"format": "ModelsStudio", "version": 1, "objects": data}, indent=2), encoding="utf-8")
            self.current_file = path
            self.statusBar().showMessage(f"Saved {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def open_scene(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Models Studio project", "", "Models Studio (*.models.json);;JSON (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.new_scene()
            for record in data.get("objects", []):
                faces = np.asarray(record["faces"], dtype=np.int64)
                verts = np.asarray(record["vertices"], dtype=float)
                mesh = pv.PolyData(verts, faces)
                obj = ModelObject(record.get("name", "Object"), mesh, record.get("color", "#a78bfa"))
                obj.position = record.get("position", [0, 0, 0])
                obj.rotation = record.get("rotation", [0, 0, 0])
                obj.scale = record.get("scale", [1, 1, 1])
                self.objects.append(obj)
                actor = self.plotter.add_mesh(obj.transformed_mesh(), color=obj.color, smooth_shading=True, name=obj.id)
                self.actor_map[obj.id] = actor
            self._refresh_outliner()
            self.current_file = path
            if self.objects:
                self.select_object(self.objects[0].id)
            self.fit_view()
            self.statusBar().showMessage(f"Opened {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", f"Could not open project:\n{exc}")


def run():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(THEME)
    window = ModelsStudio()
    window.show()
    sys.exit(app.exec())
