# 1. Getting started

## Requirements

* Windows 10/11 x64, SOLIDWORKS 2020 or newer.
* No admin rights and no Python install needed: SwPy ships its own Python 3.12 runtime.

## Install

Download **SwPy-x.y.z.zip** from the [latest release](https://github.com/muerus/SolidWorks-Python/releases/latest),
unzip it to a permanent folder (for example `%LOCALAPPDATA%\Programs\SwPy`) and run, in that folder:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install.ps1
```

This registers the add-in **for your Windows user only** and creates a **SOLIDWORKS + SwPy**
shortcut on the desktop and in the Start menu. Start SOLIDWORKS with that shortcut: it starts (or
attaches to) SOLIDWORKS and loads SwPy.

> **Why a shortcut?** SOLIDWORKS only auto-loads add-ins registered for the whole machine, which needs
> admin rights. If you have them, `install.ps1 -Machine` also registers SwPy machine-wide so it loads
> with every SOLIDWORKS start and appears in *Tools > Add-Ins*.

Uninstall with `tools\install.ps1 -Uninstall`.

## Open the editor

SwPy adds a **SwPy - Python** tab to the task pane (the panel on the right side of the SOLIDWORKS
window). Click its icon to open it. The pane has:

```
 ▶ Run | New  Open ▾  Save  Find | Clear  Reset | Theme  ?
 [scratch] [bracket.py ●]                          <- script tabs
 ┌─────────────────────────────────────────────┐
 │ 1  for f in model.features():               │  <- editor
 │ 2      print(f.Name)                        │
 └─────────────────────────────────────────────┘
 # run scratch (2 lines)                         <- output
 Boss-Extrude1
 >>> model.mass["volume"]                        <- REPL line
 Ready                         Ln 2, Col 18   Python: ready
```

## Your first script

Open any part, type this into the editor and press **F5** (or Ctrl+Enter, or ▶ Run):

```python live
print("SOLIDWORKS", sw.RevisionNumber())
doc.GetTitle() if doc else "no document open"
```

The first run starts Python (about a second); after that runs take milliseconds. `print` output
appears in the output panel, and the value of the **last line** is shown too, like in a notebook.

Now something useful - list the features of the active part and its volume:

```python live
for f in model.features():
    print(f.GetTypeName2().ljust(16), f.Name)
print("volume:", round(to(model.mass["volume"], mm**3)), "mm^3")
```

Things to notice:

* `sw`, `doc` and `model` are always there: the application, the active document and a Pythonic
  wrapper around it (see [Scripting basics](03-scripting-basics.md)).
* `mm` is a unit: `to(x, mm**3)` converts the SI value to cubic millimetres.
* Type `model.` and a list of everything you can use pops up. Press **F1** on any SOLIDWORKS method
  to open its official API help page.

## Where things are stored

| What | Where |
|---|---|
| Untitled scripts (kept automatically) | `%LOCALAPPDATA%\SwPy\scratch.py`, `%LOCALAPPDATA%\SwPy\scratch\` |
| Editor settings, open tabs, recent files | `%LOCALAPPDATA%\SwPy\editor.json` |
| Packages installed with `# r:` | `%LOCALAPPDATA%\SwPy\site-packages\py3.12` |
| Log file | `%LOCALAPPDATA%\SwPy\logs\swpy.log` |

## Next steps

* Learn the editor's productivity features: [The editor](02-editor.md).
* Change dimensions and query geometry: [The model API](04-model-api.md).
* Port VBA macros and API samples: [The SOLIDWORKS API from Python](05-solidworks-api.md).
