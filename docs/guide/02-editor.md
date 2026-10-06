# 2. The editor

The SwPy task pane is a small IDE: tabs, IntelliSense that knows the live SOLIDWORKS objects, a REPL
and an output panel. Everything runs in one Python **session** shared by all tabs and the REPL, so a
variable defined by a script is available in the REPL afterwards.

## Running code

| Action | How |
|---|---|
| Run the whole script | **F5**, **Ctrl+Enter** or ▶ Run |
| Run only some lines | Select them, then F5 / Ctrl+Enter |
| Evaluate one expression | Type it in the `>>>` line below the output and press Enter |
| Forget all variables | **Reset** |
| Clear the output | **Clear** |

The value of the last line of a script (or a REPL line) is printed in blue, like in Jupyter.
Output from `print` appears **while the script runs**, so long loops show progress.

### Errors

When a script fails:

* the traceback is printed in red in the output panel,
* the failing line gets a red dot in the margin and the error message is shown **under that line**
  (it disappears as soon as you edit),
* the caret jumps to that line. This also works when you ran only a selection.

Double-click any `File "<swpy>", line N` line in the output to jump to line N.

Syntax errors are underlined with a red squiggle while you type (about half a second after you
stop). Hover the squiggle to read the message.

## IntelliSense

### Completion

A completion list opens automatically after `.` and after typing two letters of a name. **Ctrl+Space**
opens it anywhere. Icons show what each entry is: **m** method, **p** property, **v** variable or
field, **C** class, **M** module, **k** keyword. Tab or Enter inserts the selection, Esc closes the list.

Completion is driven by the **live session**, so it knows your real objects:

```text
doc.Extension.Sel          # -> SelectByID2, SelectAll ...  (IModelDocExtension members)
model.faces.planar().      # -> normal, radius, largest, select ...
swconst.swDocumentTypes_e. # -> swDocPART, swDocASSEMBLY ...
```

For SOLIDWORKS objects it uses the API's type information, so it also works **through calls without
running them**:

```text
part.FeatureManager.FeatureExtrusion2(...).   # -> IFeature members (Name, GetTypeName2 ...)
model.faces.largest().                        # -> IFace2 members
```

Many API methods are declared as returning a plain `object` (for example `GetMotionStudyManager()`).
Once your code has called such a method, the editor remembers what it returned and completes its result
from then on.

Variables that do not exist yet (you have not run the script) are inferred from their assignment in
the editor: after `x = sldworks.IPartDoc(doc)` the editor knows `x.` is an `IPartDoc`, and inside
`for f in model.faces:` it knows `f.` is a face.

### Parameter hints

Typing `(` after a function or method shows its signature, with the parameter you are typing
highlighted; it updates as you type `,`. **Ctrl+Shift+Space** shows it again.

```
SelectByID2(
    Name: str,
    Type: str,
    X: float,          <- highlighted
    ...
) -> bool
```

SOLIDWORKS parameters show their .NET types (`str`, `float`, `int`, `bool`, interface names);
`out` parameters are marked - see [out-parameters](05-solidworks-api.md#out-parameters).

### Hover and F1 help

Rest the mouse on a name to see what it is: the type of a variable, the signature and documentation
of a Python function, or `IModelDoc2.Extension: ModelDocExtension (property)` for API members.

Press **F1** with the caret on a SOLIDWORKS member to open its page in the official online API help
(`help.solidworks.com`) for your SOLIDWORKS version.

## Editing

| Shortcut | Action |
|---|---|
| Ctrl+/ | Toggle `#` comment on the selected lines |
| Tab / Shift+Tab | Indent / dedent the selection |
| Alt+Up / Alt+Down | Move line(s) up / down |
| Shift+Alt+Down | Duplicate line(s) |
| Ctrl+Shift+K | Delete line |
| Ctrl+D | Add the next occurrence of the word to the selection (multi-caret editing) |
| Ctrl+Shift+L | Select all occurrences |
| Ctrl+Click | Add a caret |
| Alt+Drag | Column (rectangular) selection |
| Ctrl+Z / Ctrl+Y | Undo / redo |
| Ctrl+= / Ctrl+- / Ctrl+0 or Ctrl+Wheel | Zoom in / out / reset |

Typing helpers:

* Brackets and quotes close automatically; typing the closing character steps over it, and
  Backspace in an empty pair deletes both.
* Enter keeps the indentation, indents after `:` and dedents after `return`, `pass`, `break`,
  `continue` and `raise`.
* The matching bracket is highlighted (red when unmatched), and all other occurrences of the word under
  the caret are highlighted.
* Blocks (`def`, `class`, `if`, `for` ...) can be folded with the +/- markers in the margin.

## Find, replace, go to line

| Shortcut | Action |
|---|---|
| Ctrl+F | Find bar (pre-filled with the selection). All matches are highlighted and counted |
| Ctrl+H | Find and replace |
| F3 / Shift+F3 or Enter / Shift+Enter | Next / previous match (wraps around) |
| Esc | Close the find bar |
| Ctrl+G | Go to line |

The find bar has toggles for **Aa** (match case), **W** (whole word) and **.\*** (regular expression;
use `\1` in the replacement for groups). *Replace All* is a single undo step.

## Tabs and files

| Shortcut | Action |
|---|---|
| Ctrl+N | New untitled tab |
| Ctrl+O | Open one or more `.py` files (the ▾ next to *Open* lists recent files) |
| Ctrl+S / Ctrl+Shift+S | Save / Save As |
| Ctrl+W or middle-click a tab | Close the tab |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous tab |
| Right-click a tab | Close, Close others, Copy path, Show in Explorer |

* A **●** after a file name means unsaved changes. Closing such a tab asks whether to save.
* **Untitled tabs are never lost**: they are written to `%LOCALAPPDATA%\SwPy\scratch\` while you type
  (and `scratch.py` for the first one). Saving one to a file moves it to that file.
* Open tabs, the active tab, theme and zoom are restored the next time SOLIDWORKS starts.

## Themes

**Theme** switches between light and dark. The choice is remembered.

## Scripts menu

**Scripts ▾** lists the scripts of your script folder: click one to run it. See
[Script buttons and user interaction](11-scripts-and-ui.md).

## The REPL line

* Enter runs the line in the same session as the editor.
* Up / Down walk through the history.
* **Tab** completes: it inserts the completion if there is one candidate (or their common prefix),
  otherwise it prints the candidates in the output.

## Shortcut cheat sheet

Click **?** in the toolbar to print all shortcuts into the output panel.
