# 7. Remote control: Jupyter, scripts, Excel, C#

Besides the editor, SwPy can be driven **from outside SOLIDWORKS**. The code you send still runs inside
SOLIDWORKS (fast, with `sw`, `doc`, `model`, units and packages), and results come back to the caller.

## From any Python (Jupyter, VS Code, scripts)

The client needs only `pywin32` (`pip install pywin32`) and the `swpy` package folder on `sys.path`
(the `python` folder of the SwPy installation, e.g. `sys.path.append(r"...\SwPy\python")`).

```python
import swpy.client as swc

sw = swc.connect()                        # attach to the running SOLIDWORKS, load SwPy if needed
sw.eval("doc.GetTitle()")                 # -> 'Part1'
sw.eval("model.mass['volume']")           # -> 0.00012  (real Python float)
sw.exec("model.dims['D1@Boss-Extrude1'] = 30 * mm")
print(sw.exec("for f in model.features(): print(f.Name)"))   # exec returns the printed text
```

| Call | Does |
|---|---|
| `swc.connect(session="client", start=False, timeout=300)` | Attach to SOLIDWORKS (`start=True` launches it if needed) and load the add-in |
| `sw.eval(expr)` / `sw(expr)` | Evaluate; JSON-compatible results (numbers, strings, lists, dicts) come back as values, others as their `repr` string |
| `sw.exec(code)` | Run statements; returns the captured `print` output |
| `sw.run(code)` | Raw result dict: `ok`, `stdout`, `result` (repr), `value` (if JSON-able), `error` |
| `sw.reset()` | Forget the session's variables |
| `sw.version()` | Add-in version |

Errors inside SOLIDWORKS raise `swc.SwPyError` with the remote traceback.

### Sessions

Each client uses a named session (default `"client"`); variables persist between calls, so you can
build state step by step in a notebook. Use different names to keep notebooks apart:
`swc.connect(session="study-1")`. The editor pane uses its own session (`"editor"`).

### Example: a parameter study from Jupyter

```python
import swpy.client as swc
import pandas as pd

sw = swc.connect()
rows = []
for t in [10, 15, 20, 25, 30]:
    sw.exec(f"model.dims['D1@Boss-Extrude1'] = {t} * mm")
    rows.append({"thickness_mm": t, "mass_kg": sw.eval("model.mass['mass']")})
pd.DataFrame(rows).plot(x="thickness_mm", y="mass_kg")
```

Each call is a round trip of about 3 ms plus the work inside SOLIDWORKS. For many small operations,
send one larger piece of code instead of many tiny calls.

## From Excel VBA, C#, Grasshopper ...

Any COM client can call the add-in object directly:

```vb
' Excel VBA
Dim swApp As Object, swpy As Object, result As String
Set swApp = GetObject(, "SldWorks.Application")
Set swpy = swApp.GetAddInObject("SwPy.AddIn")
result = swpy.Execute("excel", "model.mass['mass']")
' result is JSON: {"ok": true, "stdout": "", "result": "0.12", "value": 0.12, "error": null}
```

```csharp
// C#
dynamic sw = Marshal.GetActiveObject("SldWorks.Application");   // .NET Framework
dynamic swpy = sw.GetAddInObject("SwPy.AddIn");
string json = swpy.Execute("csharp", "doc.GetTitle()");
```

`Execute(session, code)` always returns a JSON string with the fields `ok`, `stdout`, `result`,
`value` and `error`.
