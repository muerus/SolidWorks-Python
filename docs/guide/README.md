# SwPy user guide

SwPy runs real CPython **inside** SOLIDWORKS: a script editor in the task pane, a Pythonic layer over
the API (`model.dims["D1@Boss-Extrude1"] = 30*mm`), the full SOLIDWORKS API with automatic typing, pip
packages, and remote control from Jupyter or any Python.

| Guide | What you learn |
|---|---|
| [1. Getting started](01-getting-started.md) | Install, open the editor, run your first script |
| [2. The editor](02-editor.md) | Tabs, IntelliSense, signature help, F1 API help, find/replace, shortcuts |
| [3. Scripting basics](03-scripting-basics.md) | What is predefined in a script, sessions, output, errors |
| [4. The model API](04-model-api.md) | Units, dimensions, global variables, batch edits, mass, face/edge queries |
| [5. The SOLIDWORKS API from Python](05-solidworks-api.md) | Auto-typed objects, casts, enums, arrays, out-parameters, translating VBA/C# samples |
| [6. Packages](06-packages.md) | `# r: numpy` - using pip packages in scripts |
| [7. Remote control](07-remote-control.md) | Drive SOLIDWORKS from Jupyter, scripts, Excel or C# |
| [8. Recipes](08-recipes.md) | Copy-paste solutions: parts, studies, exports, properties, assemblies |
| [9. Troubleshooting](09-troubleshooting.md) | Logs, common errors and their fixes |
| [API reference](api-reference.md) | Every public class, function and constant of `swpy` |

Conventions used throughout:

* **SI units everywhere** - metres, radians, kilograms - exactly like the SOLIDWORKS API. Write
  `30 * mm`, read with `to(value, mm)`.
* Python code blocks are complete scripts: paste them into the editor and press F5. Unless a guide
  says otherwise they expect an open part. The examples are executed against SOLIDWORKS by the test
  suite (`tests/test_docs.py`), so they stay correct.
