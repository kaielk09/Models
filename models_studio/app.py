from __future__ import annotations

import json, sys, uuid
from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QDoubleSpinBox,
    QGroupBox, QDockWidget, QFileDialog, QMessageBox, QToolBar, QFrame,
    QComboBox, QSlider, QInputDialog, QColorDialog, QDialog, QDialogButtonBox,
    QFormLayout, QStatusBar
)
from pyvistaqt import QtInteractor

APP_NAME = "Models Studio"
APP_VERSION = "0.2.0"
THEME = """
QMainWindow, QWidget { background:#111018; color:#e9e5f3; }
QLabel { color:#e9e5f3; }
QGroupBox { border:1px solid #30283b; border-radius:9px; margin-top:10px; padding:9px; color:#c5a7ff; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }
QPushButton { background:#241b30; color:#eee8ff; border:1px solid #443258; border-radius:7px; padding:8px 11px; }
QPushButton:hover { background:#38254f; border-color:#9b6bff; }
QPushButton:pressed { background:#583887; }
QPushButton:disabled { color:#70687d; background:#19151f; border-color:#292330; }
QListWidget { background:#17141e; border:1px solid #342b40; border-radius:7px; padding:4px; }
QListWidget::item { padding:8px; border-radius:5px; }
QListWidget::item:selected { background:#51337c; color:white; }
QDoubleSpinBox,QComboBox { background:#1b1723; border:1px solid #392e49; border-radius:5px; padding:5px; color:#f1eaff; }
QToolBar { background:#17131e; border:none; spacing:5px; padding:7px; }
QDockWidget::title { background:#191421; padding:9px; color:#c7a3ff; }
QStatusBar { background:#17131e; color:#aaa0b9; }
QMenuBar,QMenu { background:#17131e; color:#eee8ff; }
QMenu::item:selected { background:#51337c; }
"""

class ModelObject:
    def __init__(self, name, mesh, color="#a78bfa"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.mesh = mesh.copy()
        self.color = color
        self.position = [0.,0.,0.]
        self.rotation = [0.,0.,0.]
        self.scale = [1.,1.,1.]

    def transformed_mesh(self):
        m = self.mesh.copy()
        m.scale(self.scale, inplace=True)
        m.rotate_x(self.rotation[0], inplace=True)
        m.rotate_y(self.rotation[1], inplace=True)
        m.rotate_z(self.rotation[2], inplace=True)
        m.translate(self.position, inplace=True)
        return m

    def to_record(self):
        return {"name":self.name,"color":self.color,"position":self.position,
                "rotation":self.rotation,"scale":self.scale,
                "vertices":self.mesh.points.tolist(),"faces":self.mesh.faces.tolist()}

class PrimitiveDialog(QDialog):
    def __init__(self, parent, primitive):
        super().__init__(parent)
        self.setWindowTitle(f"Create {primitive}")
        self.setMinimumWidth(310)
        self.primitive = primitive
        self.values = {}
        form = QFormLayout(self)
        for axis in ("X","Y","Z"):
            spin=QDoubleSpinBox()
            spin.setRange(0.01,10000)
            spin.setDecimals(3)
            spin.setValue(1.0)
            spin.setSuffix(" units")
            self.values[axis]=spin
            form.addRow(f"{axis} size",spin)
        if primitive in ("Sphere","Torus"):
            self.values["Z"].setEnabled(False)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)
    def dimensions(self):
        return tuple(self.values[a].value() for a in ("X","Y","Z"))

class ModelsStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  ·  {APP_VERSION}")
        self.resize(1500,940)
        self.setMinimumSize(1100,720)
        self.objects=[]; self.actor_map={}; self.selected_id=None
        self.current_file=None; self._updating=False; self._undo=[]; self._redo=[]
        self._setup_viewport(); self._setup_menu(); self._setup_toolbar(); self._setup_panels()
        self.statusBar().showMessage("Ready · Create an object or import a mesh")

    def _setup_viewport(self):
        self.plotter=QtInteractor(self)
        self.plotter.set_background("#111018")
        self.plotter.add_axes(color="#a18bbf")
        self.plotter.show_grid(color="#41364d",xlabel="X",ylabel="Y",zlabel="Z")
        self.plotter.view_isometric(); self.plotter.camera.zoom(1.12)
        self.setCentralWidget(self.plotter)

    def _action(self, menu, label, callback, shortcut=None):
        act=QAction(label,self)
        if shortcut: act.setShortcut(shortcut)
        act.triggered.connect(callback); menu.addAction(act)
        return act

    def _setup_menu(self):
        m=self.menuBar().addMenu("&File")
        self._action(m,"New scene",self.new_scene,"Ctrl+N")
        self._action(m,"Open project…",self.open_scene,"Ctrl+O")
        self._action(m,"Save project",self.save_scene,"Ctrl+S")
        self._action(m,"Save project as…",self.save_as,"Ctrl+Shift+S")
        m.addSeparator(); self._action(m,"Import mesh…",self.import_mesh,"Ctrl+I")
        self._action(m,"Export scene…",self.export_meshes,"Ctrl+E")
        m.addSeparator(); self._action(m,"Exit",self.close,"Alt+F4")
        edit=self.menuBar().addMenu("&Edit")
        self._action(edit,"Undo",self.undo,"Ctrl+Z")
        self._action(edit,"Redo",self.redo,"Ctrl+Y")
        edit.addSeparator()
        self._action(edit,"Duplicate selected",self.duplicate_selected,"Ctrl+D")
        self._action(edit,"Delete selected",self.delete_selected,"Delete")
        view=self.menuBar().addMenu("&View")
        self._action(view,"Fit all objects",self.fit_view,"F")
        self._action(view,"Isometric",self.set_iso_view)
        self._action(view,"Front view",lambda:self._view("front"))
        self._action(view,"Top view",lambda:self._view("xy_top"))
        self._action(view,"Side view",lambda:self._view("side"))

    def _setup_toolbar(self):
        bar=QToolBar("Quick tools"); bar.setMovable(False); self.addToolBar(bar)
        for label,cb in [("New",self.new_scene),("Open",self.open_scene),("Save",self.save_scene),
                          ("Import",self.import_mesh),("Export",self.export_meshes),("Undo",self.undo),("Redo",self.redo),
                          ("Duplicate",self.duplicate_selected),("Fit view",self.fit_view)]:
            act=QAction(label,self); act.triggered.connect(cb); bar.addAction(act)
        bar.addSeparator()
        tag=QLabel("   MODELS STUDIO  /  MESH WORKSPACE")
        tag.setStyleSheet("color:#b99bff;font-weight:700;")
        bar.addWidget(tag)

    def _panel_button(self, layout, label, cb):
        b=QPushButton(label); b.clicked.connect(cb); layout.addWidget(b); return b

    def _setup_panels(self):
        left=QDockWidget("Create · Geometry",self); left.setAllowedAreas(Qt.LeftDockWidgetArea)
        panel=QWidget(); layout=QVBoxLayout(panel); layout.setSpacing(10)
        heading=QLabel("PRIMITIVES"); heading.setStyleSheet("color:#a98bdf;font-weight:800;letter-spacing:1px;")
        layout.addWidget(heading)
        grid=QGridLayout()
        primitives=[("Cube","Cube"),("Sphere","Sphere"),("Cylinder","Cylinder"),("Cone","Cone"),("Plane","Plane"),("Torus","Torus")]
        for idx,(label,key) in enumerate(primitives):
            btn=QPushButton(label); btn.setMinimumHeight(38)
            btn.clicked.connect(lambda _,p=key:self.add_primitive(p))
            grid.addWidget(btn,idx//2,idx%2)
        layout.addLayout(grid)
        layout.addWidget(QLabel("MESH TOOLS"))
        self._panel_button(layout,"Duplicate selected  ·  Ctrl+D",self.duplicate_selected)
        self._panel_button(layout,"Center at origin",self.center_selected)
        self._panel_button(layout,"Smooth mesh",self.smooth_selected)
        self._panel_button(layout,"Subdivide mesh",self.subdivide_selected)
        self._panel_button(layout,"Set object color",self.color_selected)
        layout.addStretch()
        left.setWidget(panel); self.addDockWidget(Qt.LeftDockWidgetArea,left); left.setMinimumWidth(215)

        right=QDockWidget("Scene · Properties",self); right.setAllowedAreas(Qt.RightDockWidgetArea)
        rp=QWidget(); rl=QVBoxLayout(rp)
        hdr=QLabel("SCENE OUTLINER"); hdr.setStyleSheet("color:#bda1ec;font-weight:800;letter-spacing:1px;")
        rl.addWidget(hdr)
        self.outliner=QListWidget(); self.outliner.currentItemChanged.connect(self.select_from_list); rl.addWidget(self.outliner,2)
        row=QHBoxLayout(); self._panel_button(row,"Rename",self.rename_selected); self._panel_button(row,"Remove",self.delete_selected); rl.addLayout(row)
        self.props=QGroupBox("Transform"); pg=QGridLayout(self.props); self.spin_controls={}
        for rownum,(target,title) in enumerate([("position","Position"),("rotation","Rotation °"),("scale","Scale")]):
            pg.addWidget(QLabel(title),rownum*4,0,1,4)
            for i,axis in enumerate("XYZ"):
                spin=QDoubleSpinBox(); spin.setRange(-100000,100000); spin.setDecimals(3)
                spin.setSingleStep(5 if target=="rotation" else 0.1)
                if target=="scale": spin.setValue(1.0)
                spin.valueChanged.connect(lambda val,t=target,idx=i:self.change_transform(t,idx,val))
                self.spin_controls[target,i]=spin
                pg.addWidget(QLabel(axis),rownum*4+1,i)
                pg.addWidget(spin,rownum*4+2,i)
        rl.addWidget(self.props)
        footer=QLabel("Transforms are non-destructive scene properties.")
        footer.setWordWrap(True); footer.setStyleSheet("color:#81788e;")
        rl.addWidget(footer)
        right.setWidget(rp); self.addDockWidget(Qt.RightDockWidgetArea,right); right.setMinimumWidth(300)
        self._enable_controls(False)

    def _snapshot(self):
        self._undo.append(json.dumps({"objects":[o.to_record() for o in self.objects]},separators=(",",":")))
        if len(self._undo)>40: self._undo.pop(0)
        self._redo.clear()

    def _restore_records(self, records):
        self._clear_scene()
        for rec in records:
            mesh=pv.PolyData(np.asarray(rec["vertices"],float),np.asarray(rec["faces"],np.int64))
            obj=ModelObject(rec.get("name","Object"),mesh,rec.get("color","#a78bfa"))
            obj.position=list(rec.get("position",[0,0,0])); obj.rotation=list(rec.get("rotation",[0,0,0])); obj.scale=list(rec.get("scale",[1,1,1]))
            self.objects.append(obj)
            actor=self.plotter.add_mesh(obj.transformed_mesh(),color=obj.color,smooth_shading=True,name=obj.id)
            self.actor_map[obj.id]=actor
        self.selected_id=self.objects[0].id if self.objects else None
        self._refresh_outliner()
        self._enable_controls(bool(self.objects))
        if self.selected_id: self.select_object(self.selected_id)
        self.plotter.render()

    def undo(self):
        if not self._undo: return
        self._redo.append(json.dumps({"objects":[o.to_record() for o in self.objects]}))
        records=json.loads(self._undo.pop())["objects"]; self._restore_records(records)
        self.statusBar().showMessage("Undo")
    def redo(self):
        if not self._redo: return
        self._undo.append(json.dumps({"objects":[o.to_record() for o in self.objects]}))
        records=json.loads(self._redo.pop())["objects"]; self._restore_records(records)
        self.statusBar().showMessage("Redo")

    def add_primitive(self,kind):
        dialog=PrimitiveDialog(self,kind)
        if dialog.exec()!=QDialog.Accepted: return
        x,y,z=dialog.dimensions()
        if kind=="Cube": mesh=pv.Cube(x_length=x,y_length=y,z_length=z)
        elif kind=="Sphere": mesh=pv.Sphere(radius=x/2,theta_resolution=64,phi_resolution=64)
        elif kind=="Cylinder": mesh=pv.Cylinder(radius=x/2,height=z,resolution=64)
        elif kind=="Cone": mesh=pv.Cone(radius=x/2,height=z,resolution=64)
        elif kind=="Plane": mesh=pv.Plane(i_size=x,j_size=y,i_resolution=1,j_resolution=1)
        elif kind=="Torus":
            try: mesh=pv.ParametricTorus(ringradius=x/2,crosssection=max(0.02,y/10))
            except Exception as e: QMessageBox.warning(self,"Torus",str(e)); return
        self._add_object(kind,mesh)

    def _add_object(self,name,mesh):
        self._snapshot(); mesh=mesh.triangulate().clean()
        obj=ModelObject(name,mesh); self.objects.append(obj)
        actor=self.plotter.add_mesh(obj.transformed_mesh(),color=obj.color,smooth_shading=True,name=obj.id)
        self.actor_map[obj.id]=actor; self._refresh_outliner(); self.select_object(obj.id)
        self.fit_view(); self.statusBar().showMessage(f"Created {name}")

    def _refresh_outliner(self):
        self.outliner.blockSignals(True); self.outliner.clear()
        for obj in self.objects:
            item=QListWidgetItem("◆  "+obj.name); item.setData(Qt.UserRole,obj.id)
            self.outliner.addItem(item)
            if obj.id==self.selected_id: self.outliner.setCurrentItem(item)
        self.outliner.blockSignals(False)
    def select_from_list(self,item,previous):
        if item: self.select_object(item.data(Qt.UserRole))
    def select_object(self,oid):
        self.selected_id=oid; obj=self._selected()
        self._refresh_outliner(); self._enable_controls(bool(obj))
        if obj:
            self._updating=True
            for target,values in [("position",obj.position),("rotation",obj.rotation),("scale",obj.scale)]:
                for i,v in enumerate(values): self.spin_controls[target,i].setValue(v)
            self._updating=False
    def _selected(self):
        return next((o for o in self.objects if o.id==self.selected_id),None)
    def _enable_controls(self,enabled):
        for s in self.spin_controls.values(): s.setEnabled(enabled)
    def change_transform(self,target,axis,value):
        if self._updating: return
        obj=self._selected()
        if not obj: return
        self._snapshot(); getattr(obj,target)[axis]=value; self._replace_actor(obj)
    def _replace_actor(self,obj):
        old=self.actor_map.get(obj.id)
        if old: self.plotter.remove_actor(old,render=False)
        actor=self.plotter.add_mesh(obj.transformed_mesh(),color=obj.color,smooth_shading=True,name=obj.id,render=False)
        self.actor_map[obj.id]=actor; self.plotter.render()
    def rename_selected(self):
        obj=self._selected()
        if not obj: return
        name,ok=QInputDialog.getText(self,"Rename","Object name:",text=obj.name)
        if ok and name.strip(): self._snapshot(); obj.name=name.strip(); self._refresh_outliner()
    def delete_selected(self):
        obj=self._selected()
        if not obj: return
        self._snapshot(); actor=self.actor_map.pop(obj.id,None)
        if actor: self.plotter.remove_actor(actor,render=False)
        self.objects.remove(obj); self.selected_id=self.objects[-1].id if self.objects else None
        self._refresh_outliner(); self._enable_controls(bool(self.objects))
        if self.selected_id: self.select_object(self.selected_id)
        self.plotter.render(); self.statusBar().showMessage("Object deleted")
    def duplicate_selected(self):
        obj=self._selected()
        if not obj: return
        self._snapshot(); new=ModelObject(obj.name+" Copy",obj.mesh,obj.color)
        new.position=list(obj.position); new.position[0]+=obj.mesh.bounds[1]-obj.mesh.bounds[0]+0.25
        new.rotation=list(obj.rotation); new.scale=list(obj.scale); self.objects.append(new)
        self.actor_map[new.id]=self.plotter.add_mesh(new.transformed_mesh(),color=new.color,smooth_shading=True,name=new.id)
        self.select_object(new.id); self.statusBar().showMessage("Object duplicated")
    def center_selected(self):
        obj=self._selected()
        if not obj: return
        self._snapshot(); obj.position=[0.,0.,0.]; self._replace_actor(obj); self.select_object(obj.id)
    def color_selected(self):
        obj=self._selected()
        if not obj: return
        color=QColorDialog.getColor(QColor(obj.color),self,"Object color")
        if color.isValid(): self._snapshot(); obj.color=color.name(); self._replace_actor(obj)
    def smooth_selected(self):
        obj=self._selected()
        if not obj: return
        self._snapshot()
        try: obj.mesh=obj.mesh.smooth(n_iter=20,relaxation_factor=0.01)
        except Exception as e: QMessageBox.warning(self,"Smooth mesh",str(e)); return
        self._replace_actor(obj); self.statusBar().showMessage("Mesh smoothing applied")
    def subdivide_selected(self):
        obj=self._selected()
        if not obj: return
        self._snapshot()
        try: obj.mesh=obj.mesh.subdivide(1,subfilter="linear")
        except Exception as e: QMessageBox.warning(self,"Subdivide",str(e)); return
        self._replace_actor(obj); self.statusBar().showMessage("Mesh subdivided")
    def fit_view(self):
        if self.objects: self.plotter.reset_camera()
        else: self.plotter.camera.zoom(1.0)
        self.plotter.render()
    def set_iso_view(self): self.plotter.view_isometric(); self.plotter.render()
    def _view(self,kind):
        if kind=="xy": self.plotter.view_yz()
        elif kind=="xy_top": self.plotter.view_xy()
        elif kind=="yz": self.plotter.view_xz()
        self.plotter.render()

    def import_mesh(self):
        path,_=QFileDialog.getOpenFileName(self,"Import 3D mesh","","Meshes (*.stl *.obj *.glb *.gltf *.ply *.3mf);;All files (*)")
        if not path: return
        try:
            loaded=trimesh.load(path,force="mesh")
            if isinstance(loaded,trimesh.Scene): loaded=loaded.to_geometry()
            mesh=pv.wrap(loaded).triangulate().clean()
            self._add_object(Path(path).stem,mesh)
        except Exception as e: QMessageBox.critical(self,"Import error",f"Could not import mesh:\n{e}")

    def export_meshes(self):
        if not self.objects:
            QMessageBox.information(self,"Export","The scene is empty."); return
        path,_=QFileDialog.getSaveFileName(self,"Export scene","scene.stl","STL (*.stl);;OBJ (*.obj);;GLB (*.glb);;PLY (*.ply)")
        if not path: return
        try:
            scene=trimesh.Scene()
            for obj in self.objects:
                mesh=obj.transformed_mesh().triangulate()
                faces=mesh.faces.reshape(-1,4)[:,1:]
                tm=trimesh.Trimesh(vertices=np.asarray(mesh.points),faces=faces,process=False)
                scene.add_geometry(tm,node_name=obj.name,geom_name=obj.id)
            scene.export(path)
            self.statusBar().showMessage(f"Export successful · {Path(path).name}")
        except Exception as e: QMessageBox.critical(self,"Export error",str(e))

    def _clear_scene(self):
        self.plotter.clear(); self.plotter.add_axes(color="#a18bbf")
        self.plotter.show_grid(color="#41364d",xlabel="X",ylabel="Y",zlabel="Z")
        self.objects.clear(); self.actor_map.clear(); self.selected_id=None
        self._refresh_outliner(); self._enable_controls(False)
    def new_scene(self):
        if self.objects and QMessageBox.question(self,"New scene","Discard current scene? Unsaved changes will be lost.")!=QMessageBox.Yes: return
        self._snapshot(); self._clear_scene(); self.current_file=None; self.statusBar().showMessage("New scene")
    def save_scene(self):
        if not self.current_file: return self.save_as()
        self._write_scene(self.current_file)
    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self,"Save project as","scene.models.json","Models Studio (*.models.json);;JSON (*.json)")
        if path: self._write_scene(path)
    def _write_scene(self,path):
        data={"format":"ModelsStudio","version":2,"objects":[o.to_record() for o in self.objects]}
        try:
            Path(path).write_text(json.dumps(data,indent=2),encoding="utf-8")
            self.current_file=path; self.statusBar().showMessage(f"Saved · {Path(path).name}")
        except Exception as e: QMessageBox.critical(self,"Save error",str(e))
    def open_scene(self):
        path,_=QFileDialog.getOpenFileName(self,"Open project","","Models Studio (*.models.json);;JSON (*.json)")
        if not path: return
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            records=data.get("objects",[])
            if self.objects and QMessageBox.question(self,"Open project","Replace current scene?")!=QMessageBox.Yes: return
            self._snapshot(); self._restore_records(records); self.current_file=path
            self.fit_view(); self.statusBar().showMessage(f"Opened · {Path(path).name}")
        except Exception as e: QMessageBox.critical(self,"Open error",f"Invalid project file:\n{e}")

def run():
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI",10)); app.setStyleSheet(THEME)
    win=ModelsStudio(); win.show(); sys.exit(app.exec())

if __name__=="__main__":
    run()
