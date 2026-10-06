# SwPy - Python for SOLIDWORKS

Embedded CPython inside SOLIDWORKS: run Python in-process against the live API, from a
script editor (planned) or from external clients over COM.

Status: add-in host, embedded Python, task-pane editor + REPL, auto-typed API, Pythonic model layer (74 live tests).
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/RESEARCH.md](docs/RESEARCH.md).

## Dev setup (Windows, no admin needed)

```powershell
py -3.12 -m venv .venv; .venv\Scripts\pip install pythonnet pywin32 pytest
.venv\Scripts\python tools\gen_interop.py         # regenerate casts + swconst (after SW upgrade)
dotnet build src\SwPy.AddIn -c Debug              # SOLIDWORKS must be closed (DLL lock)
powershell tools\register.ps1                      # per-user COM registration
.venv\Scripts\python -m pytest tests -q            # starts SOLIDWORKS, loads add-in, runs suite
```

Python is found via `SWPY_PYTHON_HOME`, a bundled `python-runtime\` folder, or the registered
installs (3.12 preferred). Logs: `%LOCALAPPDATA%\SwPy\logs\swpy.log`.

## Using it from a script (current API)

```python
from tests import harness
swpy = harness.SwPy()                  # attaches to SOLIDWORKS, loads the add-in
swpy.run("doc.GetTitle()")             # -> {'ok': True, 'result': "'Part1'", 'stdout': '', 'error': None}
```

Inside scripts: `sw` (ISldWorks), `doc` (active IModelDoc2), `sldworks.IFoo(obj)` typed casts,
`swconst` enums. Never import from `SolidWorks.Interop.*` directly (see RESEARCH.md §4).

## Pythonic API (in scripts / REPL)

```python
model                                   # <Model 'Part1'> for the active document
model.dims["D1@Boss-Extrude1"] = 30*mm  # SI units everywhere; rebuilds
model.globals["Width"] = 120*mm         # global variables (equation manager)
with model.batch():                     # many edits, one rebuild, no flicker
    model.dims["D1@Boss-Extrude1"] = 25*mm
    model.globals["Width"] = 90*mm
model.faces.planar().normal(Z).largest().Select4(False, None)
model.faces.radius(10*mm)               # cylindrical faces of radius 10 mm
model.edges.parallel(Z).select()        # selects in the viewport
model.mass["volume"]
model.planes.top.Select2(False, 0)      # default planes by position (renamed in custom templates)
doc.FirstFeature().Name                 # raw API, auto-typed
```
