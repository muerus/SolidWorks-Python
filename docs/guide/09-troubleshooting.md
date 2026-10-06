# 9. Troubleshooting

## Where to look first

* **Log file:** `%LOCALAPPDATA%\SwPy\logs\swpy.log` - add-in start, Python start, errors from the
  editor and the add-in. Launcher messages go to `launcher.log` in the same folder.
* **Output panel:** script errors show the full traceback of your code.

## The SwPy pane does not appear

| Cause | Fix |
|---|---|
| SOLIDWORKS was started normally, not via the **SOLIDWORKS + SwPy** shortcut | Use the shortcut, or install with `install.ps1 -Machine` (admin) so SOLIDWORKS loads SwPy itself |
| The add-in is not registered (moved folder, other Windows user) | Run `tools\install.ps1` again from the SwPy folder |
| SOLIDWORKS runs as administrator | Per-user registration is invisible to elevated processes: start SOLIDWORKS normally |
| A message box "SwPy could not be loaded" | Read the message and `swpy.log`; usually a missing or blocked file in the SwPy folder |

## "Python failed to start"

SwPy looks for Python in this order: the `SWPY_PYTHON_HOME` environment variable, the bundled
`python-runtime` folder next to the add-in, then installed Python versions (3.12 preferred). Check
`swpy.log` for the path it tried. A failed start is remembered until SOLIDWORKS restarts.

## A script "does nothing"

Many API methods **fail silently**: they return `None`, `False` or an error code instead of raising.

* `FeatureExtrusion2(...)` returns `None` when nothing (or the wrong thing) is selected. Closing a sketch
  with `InsertSketch(True)` can leave **nothing selected** - select the sketch explicitly before creating
  the feature: `doc.FeatureByPositionReverse(0).Select2(False, 0)`.
* `SelectByID2("Front Plane", ...)` returns `False` when the plane has another name - company templates
  often rename them (`XY PLANE`). Use `model.planes.front` / `.top` / `.right` instead.
* Check results and raise your own error:

  ```python
  feat = doc.FeatureManager.FeatureExtrusion2(...)
  if feat is None:
      raise RuntimeError("extrusion failed")
  ```

## Common errors

| Error | Meaning / fix |
|---|---|
| `AttributeError: IModelDocExtension has no attribute 'CustomPropertyManager'. Did you mean: 'get_CustomPropertyManager'?` | An indexed property: call `get_CustomPropertyManager("")` ([details](05-solidworks-api.md#indexed-properties-get_x--set_x)) |
| `AttributeError: 'NoneType' object has no attribute ...` | An API call returned `None` (no active document, nothing selected, wrong name). Check the value before using it |
| `KeyError: 'D1@Sketch1'` from `model.dims[...]` | No dimension with that name - print `model.dims.names()` |
| `TypeError: No method matches given arguments` | Wrong number or type of arguments. Check the signature help (type `(`), and pass `None` for unused object parameters |
| `NameError: name 'doc' ...` / `doc` is `None` | No document is open (or the active window is not a document) |
| `RuntimeError: pip install failed` | See the pip output in the message: no internet, a typo in the package name, or no wheel for Python 3.12 x64 |

## Types and units

* Values are SI: a dimension of 30 mm reads `0.03`. Use `to(x, mm)` to display.
* Mass values use the document's material density. Templates can define a default density - if masses
  look 1000× off, check *Mass Properties* and the material in SOLIDWORKS.
* Angles are radians: `45 * deg`.

## Never import the interop assemblies

`from SolidWorks.Interop.sldworks import ...` may bind to a trimmed copy embedded by another add-in and
fail in confusing ways. Use `sldworks.IFoo(obj)` for casts and `swconst` for enums.

## Long scripts freeze SOLIDWORKS

Scripts run on the SOLIDWORKS UI thread, so SOLIDWORKS waits until they finish. Use `model.batch()`
around many edits, print progress, and test loops on a few items first. There is no way to stop a
running script other than closing SOLIDWORKS - save your work before experimenting.

## Reporting a problem

Include the SOLIDWORKS version (`sw.RevisionNumber()`), the script, the full output and the end of
`swpy.log`.
