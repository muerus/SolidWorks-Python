# 3. Scripting basics

## What every script can use

These names are predefined - no imports needed:

| Name | What it is |
|---|---|
| `sw` | The SOLIDWORKS application (`ISldWorks`) |
| `doc` | The **active document** (`IModelDoc2`, plus `IPartDoc` / `IAssemblyDoc` / `IDrawingDoc` members), or `None` |
| `model` | `Model(doc)`: the Pythonic wrapper of the active document (see [The model API](04-model-api.md)), or `None` |
| `Model` | The wrapper class, for other documents: `Model(other_doc)` |
| `mm`, `cm`, `m`, `inch`, `ft`, `deg`, `rad`, `kg`, `g` | Units (SI factors): `30 * mm == 0.03` |
| `to(value, unit)` | Convert an SI value to a unit: `to(0.03, mm) == 30.0` |
| `X`, `Y`, `Z`, `Vec` | Unit vectors and the 3D vector type |
| `swconst` | All SOLIDWORKS API enums: `swconst.swDocumentTypes_e.swDocPART` |
| `sldworks` | Typed casts: `sldworks.IPartDoc(obj)` (rarely needed, see [chapter 5](05-solidworks-api.md#casts)) |
| `on`, `off` | Subscribe / unsubscribe event handlers (see [Events](10-events.md)) |
| `cosworks`, `swmotionstudy`, ... | The other SOLIDWORKS API libraries (see [chapter 5](05-solidworks-api.md#other-api-libraries)) |
| `_` | The value of the last expression shown |

`doc` and `model` are refreshed **at the start of every run**, so they always follow the document you
are looking at. Inside one run they do not change: if your script creates or opens a document, keep
the returned object instead.

```python live
part = doc                      # remember it: `doc` is fixed for this run anyway
print(part.GetTitle(), part.GetType() == swconst.swDocumentTypes_e.swDocPART)
```

Anything else comes from regular imports: the whole standard library (`math`, `csv`, `json`,
`pathlib`, `datetime` ...) and any pip package (see [Packages](06-packages.md)).

## Sessions: variables persist

All runs from the editor tabs and the REPL share one session. Variables, functions and imports stay
defined between runs until you press **Reset**:

```python live
counter = globals().get("counter", 0) + 1
counter                          # 1, then 2, 3 ... on every run
```

This makes the REPL a great inspector: run a script once, then poke at its variables (`faces[0]`,
`len(rows)` ...) in the `>>>` line.

## Output

* `print` writes to the output panel **as the script runs**.
* If the last line of a script is an expression, its value is shown (like Jupyter), and stored in `_`.
* Errors print a traceback that only contains your code; the failing line is marked in the editor.

```python live
import math
for i in range(3):
    print("step", i)
math.pi * 2                     # shown as the result
```

## Units

The SOLIDWORKS API is SI-only, and so is SwPy. Multiply by a unit when writing a value, divide (or use
`to`) when reading:

```python live
width = 120 * mm                 # 0.12
angle = 45 * deg                 # 0.785...
print(width, to(width, inch), to(angle, deg))
area = model.faces.largest().GetArea()
print(f"largest face: {to(area, mm**2):.1f} mm^2")
```

## Scripts run on the SOLIDWORKS UI thread

Your code runs inside SOLIDWORKS, on its main thread. That is what makes API calls fast (microseconds)
and safe, but it also means SOLIDWORKS waits while a script runs. For long jobs:

* use `model.batch()` to switch off graphics and rebuild once ([details](04-model-api.md#batch-edits)),
* print progress - output appears live,
* there is no "stop" button: avoid infinite loops (save your work before experimenting).

## Organising code

* Save scripts as `.py` files and open them in tabs.
* To import your own modules, add their folder to `sys.path` once per session:

  ```python
  import sys
  sys.path.append(r"C:\work\sw-scripts")
  import my_helpers
  ```

  After editing `my_helpers.py`, reload it with `importlib.reload(my_helpers)`.
* `__name__ == "__main__"` is true in the editor, so `if __name__ == "__main__":` blocks run as usual.
