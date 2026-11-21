# Models Studio

**Models Studio** is a Windows-first desktop mesh/modeling workspace with a dark graphite and purple UI. It is designed for quick 3D creation, game assets, and printable meshes.

> This is an actively evolving project—not a Blender replacement. Features and packaging are still being tested.

## Current feature set
- PySide6 desktop interface, scene outliner, transform properties
- Interactive PyVista 3D viewport, axes, grid, orbit, pan and zoom
- Primitive creation with editable dimensions: cube, sphere, cylinder, cone, plane and torus
- Object operations: duplicate, rename, delete, recenter, color, smooth and linear subdivision
- Undo/redo for supported scene actions
- Project save/open using `.models.json`
- Import/export mesh formats supported by the installed Trimesh/PyVista stack (STL, OBJ, GLB/glTF, PLY; 3MF support depends on installed readers)

## Keyboard shortcuts
| Shortcut | Action |
|---|---|
| Ctrl+N | New scene |
| Ctrl+O | Open project |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save as |
| Ctrl+I | Import mesh |
| Ctrl+E | Export scene |
| Ctrl+D | Duplicate selected |
| Ctrl+Z / Ctrl+Y | Undo / redo |
| Delete | Remove selected |
| F | Fit view |

## Install and run on Windows
1. Install 64-bit Python 3.11 or newer from python.org. During install, enable **Add Python to PATH**.
2. Download the repository ZIP and extract it.
3. Run `install_windows.bat` once to create a local virtual environment and install dependencies.
4. Run `run_windows.bat`.

Manual setup:
```cmd
py -3 -m venv .venv
.venv\\Scripts\\python -m pip install --upgrade pip
.venv\\Scripts\\python -m pip install -r requirements.txt
.venv\\Scripts\\python main.py
```

## Build an EXE
Run `build_windows_exe.bat`. The script attempts a PyInstaller build and places output in `dist\\Models Studio`. Qt/PyVista may need packaging adjustments on some Windows configurations; a successful build is not guaranteed until tested on a Windows machine.

## Project files
- `main.py`: app entry point
- `models_studio/app.py`: application UI and scene logic
- `requirements.txt`: Python dependencies
- Windows batch scripts: install, run and build

## Known limitations
- This is mesh-based, not a full CAD parametric solid system.
- Advanced sculpting, vertex/edge/face edit modes, UV editor, texture painting, animation, rigging, boolean tools and a professional slicer workflow are not implemented yet.
- Undo history is currently in-memory and limited; not every operation is guaranteed to be undoable.
- File import/export compatibility varies by file and dependency version.

## Development checks
```cmd
py -m compileall main.py models_studio
```
