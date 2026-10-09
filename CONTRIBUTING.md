# Contributing / development guide

## Prerequisites

* Windows 10/11 x64 with SOLIDWORKS 2020 or newer (the live tests drive a real SOLIDWORKS).
* .NET SDK (builds the .NET Framework 4.8 add-in) and Python 3.12 (`py -3.12`).
* No admin rights needed.

## Setup

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -e .[dev]
powershell tools\fetch_python.ps1                 # optional: bundle the embeddable runtime into the build
dotnet build src\SwPy.AddIn -c Debug              # SOLIDWORKS must be closed (it locks the DLL)
dotnet build src\SwPy.Launcher -c Debug
powershell tools\register.ps1                      # per-user COM registration of the Debug build
```

After a SOLIDWORKS upgrade regenerate the interop bindings: `.venv\Scripts\python tools\gen_interop.py`
(writes `src/SwPy.AddIn/Scripting/Cast.g.cs`, `python/swpy/swconst.py`, and for every other API library
listed in `LIBRARIES` there: `src/SwPy.AddIn/Scripting/Libraries.g.cs` and `python/swpy/libs/`; add
the library's `<Reference>` to `SwPy.AddIn.csproj` when you add one).

## Running the tests

```powershell
.venv\Scripts\python -m pytest tests -q
```

The harness starts SOLIDWORKS if needed (with `SWPY_PACKAGE_DIR` pointing at `python/`, so Python
changes are used directly), loads the add-in and runs everything against it:

| File | Covers |
|---|---|
| `test_static.py` | Python files compile (no SOLIDWORKS) |
| `test_host.py` | Sessions, output, errors, results |
| `test_com.py` | Auto-typed proxies, arrays, casts |
| `test_model.py` | Units, dims, globals, batch, queries, planes |
| `test_props.py` | Custom properties: types, links, configurations, errors |
| `test_build.py` | Sketches, features, save/export, assemblies and mates, drawings |
| `test_ui.py` | Script buttons (via the IDispatch callbacks), startup scripts, `swpy.ui` incl. real dialogs |
| `test_events.py` | Event handlers: aliases, arguments, error isolation, lifetime |
| `test_libraries.py` | Other API libraries: typing, casts, constants, detection safety |
| `test_editor.py` | Editor services: completion, signatures, hover, syntax check |
| `test_pane.py` | Task pane via the `Pane()` automation hook: running, REPL, tabs, find, IntelliSense |
| `test_client.py`, `test_packages.py` | Remote client, `# r:` installs |
| `test_docs.py` | Runs every ` ```python live ` example of `docs/guide`, checks API reference coverage |

Notes:

* The pytest session leaves SOLIDWORKS running. Check `Get-Process SLDWORKS | select StartTime` before
  claiming a cold-start result.
* C# changes need SOLIDWORKS closed, a rebuild, and a new SOLIDWORKS process (the CLR never unloads the
  add-in). Python changes can be reloaded in a running SOLIDWORKS:
  `from swpy import _host; _host.reload_package()`.
* To test Python changes without building and registering the add-in, point the harness at an
  installed one: `$env:SWPY_ADDIN_DLL = "$env:LOCALAPPDATA\Programs\SwPy\bin\SwPy.AddIn.dll"`.
* Parts are created from the user's default template; never rely on stock plane names
  (`model.planes`) or on selection state after API calls.

## Conventions

* **Never import `SolidWorks.Interop.*`** from Python - use `sldworks.IFoo(...)` casts and `swconst`
  (other add-ins embed trimmed copies of the interop types).
* Keep the C# layer thin; script plumbing lives in `swpy._host`, editor intelligence in `swpy._editor`.
* Everything is SI internally.
* Public Python API: docstrings and return annotations (they drive editor completion and hover), an entry
  in `docs/guide/api-reference.md` (enforced by `test_docs.py`), and a guide section with a
  ` ```python live ` example where it helps.
* Editor services must never start Python while the user is typing - only on `.`, Ctrl+Space or explicit
  actions.
* Record user-visible changes in `CHANGELOG.md`.

## Release build

```powershell
powershell tools\fetch_python.ps1
dotnet build src\SwPy.AddIn -c Release
dotnet build src\SwPy.Launcher -c Release
```

`src\SwPy.AddIn\bin\Release\net48` is the distributable folder (add-in, launcher, `python\swpy`,
`python-runtime`). Users install from it with `tools\install.ps1 -BinDir <folder>`.
