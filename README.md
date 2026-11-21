# Models Studio

A desktop 3D modeling starter application built with Python, PySide6, PyVista and trimesh.

## Features
- Dark purple desktop UI
- Primitive mesh creation (cube, sphere, cylinder, cone, plane)
- 3D viewport with orbit, zoom, and grid
- Object selection and scene explorer
- Position, rotation and scale editing
- Import/export: STL, OBJ, GLB, PLY
- Save/open native scene files (.models.json)

## Windows setup
1. Install Python 3.11+.
2. Open CMD in this folder.
3. Run:
   ```bat
   py -m pip install -r requirements.txt
   py main.py
   ```

## Notes
This is the initial desktop MVP. It is intended to be expanded into a full modeling workflow. It is not yet a Blender replacement and has not been packaged as an EXE.
