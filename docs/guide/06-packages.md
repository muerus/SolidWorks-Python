# 6. Packages

Any pure-Python or binary wheel from PyPI works in SwPy scripts: numpy, pandas, openpyxl, scipy,
matplotlib ... Declare what a script needs in a `# r:` comment (the same convention as Rhino 8):

```python
# r: openpyxl
import openpyxl

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Dimension", "Value (mm)"])
for name, value in model.dims.items().items():
    ws.append([name, to(value, mm)])
wb.save(r"C:\temp\dimensions.xlsx")
```

When the script runs, missing packages are installed first (progress appears in the output panel),
then the script continues. Later runs start immediately because the package is already there.

## Syntax

```python
# r: numpy
# r: pandas>=2, openpyxl
# r: requests==2.32.3
```

* One or more packages per line, separated by commas or spaces; several `# r:` lines are allowed,
  anywhere in the script.
* Use pip requirement syntax: a package name, optional extras and version specifiers
  (`requests[socks]>=2.31,<3`). An exact pin (`==`) is checked against the installed version and
  re-installed if different; other specifiers install the package if it is missing.
* For safety only PyPI package names are accepted: pip options (`--index-url ...`), URLs and paths are
  rejected with an error, so a script header cannot point pip at another package source.

## Where packages go

Packages are installed **per user**, into `%LOCALAPPDATA%\SwPy\site-packages\py3.12` - never into a
Python installation, and no admin rights are needed. This folder is on `sys.path` for every script and
the REPL, so once installed a package can also be imported without the `# r:` line (keep the line
anyway, so the script works on other machines).

To remove packages, delete their folders there (with SOLIDWORKS closed), or the whole folder to start
over.

## Notes

* Installing needs internet access to PyPI (or your configured pip index: pip reads the usual
  `%APPDATA%\pip\pip.ini`).
* Packages with compiled parts must offer a wheel for Python 3.12, Windows x64 (almost all popular ones
  do).
* Large packages (numpy, pandas) take a few seconds to import the first time in a session; after that
  imports are instant because the session keeps them.
* GUI toolkits that need their own event loop (tkinter main loops, Qt apps) do not mix well with
  SOLIDWORKS' UI thread. Use them from an [external Python](07-remote-control.md) instead.
