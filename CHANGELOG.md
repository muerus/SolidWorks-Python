# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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

### Fixed
- Test fixtures no longer depend on stock plane names or on the selection state after closing a sketch.
- Closing a tab right after editing no longer raises an error dialog (syntax-check timer on a disposed editor).

### Removed
- Research spikes, the exit-crash bisection script and `tools/load.py` (superseded by `SwPy.Launcher`).

## [0.1.0] - 2026-10-06

### Added
- SOLIDWORKS add-in hosting embedded CPython via pythonnet, per-user COM registration without admin rights.
- Sessions, live output streaming, REPL-style results, user-only tracebacks, logging.
- Auto-typed COM proxies (`swpy.com`), generated typed casts and `swconst` enums.
- Pythonic model layer: units, dimensions, global variables, batch edits, mass, face/edge queries.
- Task-pane script editor with REPL.
- Out-of-process client (`swpy.client`), `# r:` package requirements, launcher, installer, bundled runtime.
