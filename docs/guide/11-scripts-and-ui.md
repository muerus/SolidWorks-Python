# 11. Script buttons and user interaction

Turn scripts into one-click tools, run scripts automatically when SOLIDWORKS starts, and talk to the
user from a script: progress bars, messages, questions, text input and file dialogs.

## The script folder

Every `.py` file in the **script folder** becomes a tool:

```
Documents\SwPy\Scripts\
    Export_STEP.py          -> "Export STEP" button / menu entry
    List_features.py        -> created for you the first time, as an example
    _helpers.py             -> files starting with "_" get no button (use them for shared code)
    startup\
        my_events.py        -> runs once after SOLIDWORKS has started
```

* The first comment or docstring line of a script is its tooltip.
* Scripts run in the editor's session, so their variables are available in the REPL afterwards, and
  `print` output appears in the SwPy pane. `__file__` is the script's path, and its folder is importable
  while it runs (`import helpers` finds `helpers.py` next to it).
* If a script fails, it opens in an editor tab with the failing line marked.
* The folder can be changed with `"ScriptsFolder"` in `%LOCALAPPDATA%\SwPy\editor.json` (for example a
  shared network folder for the whole team).

### Running scripts

* **SwPy pane > Scripts ▾**: lists the scripts; click one to run it. The menu also has *Open script
  folder* and *Refresh SwPy toolbar*.
* **SwPy toolbar, menu and CommandManager tab**: one button per script, plus *Refresh scripts* and
  *Script folder*. SOLIDWORKS only shows these for add-ins registered machine-wide, so install with
  `tools\install.ps1 -Machine` (admin) to get them. With a per-user install use the pane's Scripts menu.

After adding or renaming scripts, press *Refresh scripts* (or *Refresh SwPy toolbar* in the pane).

### Startup scripts

Scripts in `startup\` run once, when SOLIDWORKS is first idle after it started (so they never slow
down the start itself). Combine them with [events](10-events.md) to react to documents being opened:

```python
# startup/stamp_author.py - fill in the Author property of every part that is opened
import os

def stamp(*args):
    doc = sw.ActiveDoc
    if doc is not None and doc.GetType() == swconst.swDocumentTypes_e.swDocPART:
        props = doc.Extension.get_CustomPropertyManager("")
        props.Add3("Author", swconst.swCustomInfoType_e.swCustomInfoText, os.getlogin(),
                   swconst.swCustomPropertyAddOption_e.swCustomPropertyOnlyIfNew)

on(sw, "open", stamp)
```

## Talking to the user: `ui`

`ui` is predefined in scripts.

### Progress bar (Esc cancels)

Wrap any loop in `ui.progress` to show the SOLIDWORKS progress bar. Pressing **Esc** stops the loop by
raising `ui.Cancelled` - the way to make long scripts interruptible:

```python live
total = 0
for i in ui.progress(range(200), "Counting"):
    total += i
print(total)
```

Or step manually, with changing titles:

```python live
with ui.progress(3, "Exporting") as bar:
    for name in ["front", "top", "right"]:
        bar.step(title=f"Exporting {name}")
```

Catch the cancellation if you want to clean up:

```python
try:
    for path in ui.progress(paths, "Exporting"):
        export(path)
except ui.Cancelled:
    print("stopped by the user")
```

### Messages and questions

```python
ui.message("Export finished")                                  # icon: info/warning/error/question
if ui.ask("Overwrite existing files?"):                        # True / False
    ...
answer = ui.ask("Save changes?", cancel=True)                  # True / False / None
choice = ui.message("Retry?", "warning", "retry_cancel")       # 'retry' or 'cancel'
```

### Text input and file dialogs

```python
name = ui.prompt("New configuration name", "Default")          # None if cancelled
path = ui.open_file("Parts (*.sldprt)|*.sldprt", "Pick a part")
paths = ui.open_files("STEP (*.step;*.stp)|*.step;*.stp")      # list
target = ui.save_file("PDF (*.pdf)|*.pdf", name="drawing.pdf")
folder = ui.folder("Export folder")
```

All dialogs are modal to the SOLIDWORKS window and return `None` (or an empty list) when cancelled.

### Status bar

```python live
ui.status("SwPy: ready")
```

## Example: a complete tool

```python
# Export all open parts as STEP into a chosen folder
import os

target = ui.folder("Export STEP files to")
if target:
    parts = [d for d in (sw.GetDocuments() or []) if d.GetType() == swconst.swDocumentTypes_e.swDocPART]
    try:
        for part in ui.progress(parts, "Exporting STEP"):
            name = os.path.splitext(part.GetTitle())[0] + ".step"
            part.Extension.SaveAs(os.path.join(target, name), 0, 1, None, 0, 0)
        ui.message(f"Exported {len(parts)} part(s) to {target}")
    except ui.Cancelled:
        ui.message("Export cancelled", "warning")
```

Save it as `Documents\SwPy\Scripts\Export_STEP.py`, refresh, and it is one click away.
