# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-06 - first public release

### Security
- `# r:` headers only accept PyPI package names and version specifiers (pip options, URLs and paths
  are rejected).
- `tools/fetch_python.ps1` pins Python and pip and verifies their SHA-256.
- F1 help only opens help.solidworks.com URLs.
- `SECURITY.md`: trust model and private vulnerability reporting.

### Added
- **Building models**: `model.sketch(...)` (line, rect, circle, arc, polyline, centerline ...),
  `extrude`, `cut`, `revolve`, `fillet`, `chamfer`, `shell`; assemblies (`add_component`, `components`,
  `mate`, `mates`, `bom`, `component_planes`, faces/edges across components); drawings
  (`create_drawing`, `add_view`, `sheets`, `views`); `save` and `export` by file extension (PDF of all
  sheets); `FeatureError` instead of silent failures.
- **Script buttons**: every `.py` in the script folder (default `Documents\SwPy\Scripts`) is a tool in
  the pane's Scripts menu and on a SwPy toolbar / menu / CommandManager tab (shown by SOLIDWORKS for
  machine-wide installs); `startup\` scripts run when SOLIDWORKS is first idle; failing scripts open with
  the error line marked.
- **`swpy.ui`** (`ui` in scripts): progress bar with Esc to cancel, message boxes, yes/no questions, text
  prompt, file/folder dialogs, status bar text.
- **Events** (`swpy.events`, `on`/`off` in scripts): Python handlers for any SOLIDWORKS event with
  friendly aliases, flexible handler signatures, error isolation, automatic removal on Reset, document
  close and add-in unload.
- **All SOLIDWORKS API libraries**: Simulation (`cosworks`), motion studies, DimXpert, Routing, Costing,
  Design Checker, FeatureWorks, Utilities, Toolbox, Sustainability, 3D printing, Design Library,
  command IDs (`swcommands`), Document Manager, PDM (`EdmLib`) and Workgroup PDM - typed casts and
  constants generated for each, available in scripts under their interop namespace names.
- Objects returned as plain `object` are typed across all libraries (detection cached per COM class).
- Editor completion learns the actual return types of `object`-returning API members once code ran.
- **Task-pane IDE**: tabs with automatic backups of untitled scripts, recent files, IntelliSense from the
  live session (follows SOLIDWORKS API return types without executing), signature help, hover info,
  F1 to the online SOLIDWORKS API help, live syntax checking, runtime-error markers, find/replace with
  regex, go to line, multi-caret editing, line operations, folding, light/dark themes, REPL Tab
  completion. Settings in `%LOCALAPPDATA%\SwPy\editor.json`.
- `swpy._editor` editor services and `swpy._host.call` entry point.
- `Model.planes`: default Front/Top/Right planes by position (works with templates that rename them).
- Return annotations and docstrings across `swpy.model` (power completion, hover and docs).
- User guide (`docs/guide`) with getting started, editor, scripting, model API, SOLIDWORKS API, packages,
  remote control, recipes, troubleshooting and a full API reference. Every runnable example is executed
  by the test suite (`tests/test_docs.py`).
- `pyproject.toml`, MIT license, contributing guide, `.editorconfig`, `.gitattributes`.
- Release package (`tools/package.ps1`): the SOLIDWORKS interop assemblies are no longer shipped; the
  add-in loads them from the user's SOLIDWORKS installation, whatever its version.

### Fixed
- Test fixtures no longer depend on stock plane names or on the selection state after closing a sketch.
- Closing a tab right after editing no longer raises an error dialog (syntax-check timer on a disposed editor).

### Removed
- Research spikes, the exit-crash bisection script and `tools/load.py` (superseded by `SwPy.Launcher`).

## [0.1.0] - 2026-10-06 (internal milestone)

### Added
- SOLIDWORKS add-in hosting embedded CPython via pythonnet, per-user COM registration without admin rights.
- Sessions, live output streaming, REPL-style results, user-only tracebacks, logging.
- Auto-typed COM proxies (`swpy.com`), generated typed casts and `swconst` enums.
- Pythonic model layer: units, dimensions, global variables, batch edits, mass, face/edge queries.
- Task-pane script editor with REPL.
- Out-of-process client (`swpy.client`), `# r:` package requirements, launcher, installer, bundled runtime.
