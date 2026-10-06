# SwPy architecture

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │ L5  External bridge   JSON-RPC (named pipe / localhost)              │
 │     clients: Jupyter, Excel, Grasshopper, MCP, tests                 │
 ├──────────────────────────────────────────────────────────────────────┤
 │ L4  Tools & UI        task pane editor + REPL, script toolbar,       │
 │                       event hooks (on_rebuild, on_save ...)          │
 ├──────────────────────────────────────────────────────────────────────┤
 │ L3  Pythonic API      `swpy` pure-Python package: units, dims,       │
 │                       features, geometric selection, batch(), pandas │
 ├──────────────────────────────────────────────────────────────────────┤
 │ L2  Raw API surface   typed interop objects injected as `sw`, `doc`; │
 │                       swconst enums; out-params as tuples            │
 ├──────────────────────────────────────────────────────────────────────┤
 │ L1  Python runtime    pythonnet engine: locate/init CPython once,    │
 │                       GIL, stdout/stderr capture, sessions, `# r:`   │
 ├──────────────────────────────────────────────────────────────────────┤
 │ L0  Host add-in       C# net48 COM ISwAddin: lifecycle, per-user     │
 │                       registration, main-thread dispatcher, logging  │
 └──────────────────────────────────────────────────────────────────────┘
                       SOLIDWORKS process (single STA UI thread)
```

Each layer only depends on layers below it. L3 is plain Python and can also
run out-of-process over pywin32/L5 for users without the add-in.

## L0 - Host add-in (`src/SwPy.AddIn`, C#, net48, x64)
- `SwPyAddIn : ISwAddin`, COM-visible, fixed GUID + ProgID `SwPy.AddIn`.
- `ConnectToSW`: store `ISldWorks`, cookie, `SetAddinCallbackInfo2`,
  create `MainThreadDispatcher` (hidden WinForms control), start L1 lazily.
- Exposes `ISwPyAutomation` (COM-visible) through `GetAddInObject`:
  `Execute(code) -> string json`, `Version()`. This is the first test hook
  and the seed of L5.
- Logging to `%LOCALAPPDATA%\SwPy\logs\swpy.log` (SW swallows exceptions).
- Registration tool (`tools/register.ps1`): per-user CLSID under
  `HKCU\Software\Classes` + SW AddIns/AddInsStartup keys; falls back to an
  elevated one-time HKLM key if SW 2020 ignores HKCU (decided by spike A).

## L1 - Python runtime (`SwPy.AddIn/Python/*`)
- `PythonHost`: find interpreter (config -> bundled embeddable -> `py`
  launcher registry), set `Runtime.PythonDLL`, `PythonHome`, `sys.path`
  (+ `python/` package dir), `Initialize()`, `BeginAllowThreads()`.
- `Session`: a globals dict; `Execute(code)` / `Evaluate(expr)` under GIL,
  stdout/stderr redirected to a buffer/callback, tracebacks formatted.
- Never `Shutdown()` while SW runs; reset = new `Session`.
- Package requirements: parse `# r: pkg` headers -> `pip install --target
  %LOCALAPPDATA%\SwPy\site-packages` (later milestone).

## L2 - Raw API surface
- Injected names: `sw` (ISldWorks), `doc` (active IModelDoc2, refreshed per
  run), `swconst` (SolidWorks.Interop.swconst namespace), `addin`.
- pythonnet handles typed calls; we add a small `swpy._com` helper for
  `object[]` -> list, safe casts (`IPartDoc(doc)`), and VARIANT nulls.

## L3 - Pythonic API (`python/swpy`, pure Python)
- `units`: `mm`, `inch`, `deg` ... (`50*mm` -> 0.05 m internally).
- `Model` wrapper: `.dims["D1@Sketch1"]`, `.globals["Width"]`,
  `.features`, `.mass`, `.rebuild()`, `with model.batch():`.
- Geometry queries: `model.faces.planar().normal(+Z).largest()`,
  `edges.linear().parallel(Z)`.
- `to_frame()` helpers when pandas is available.
- Backend-agnostic: works with in-process pythonnet objects or
  out-of-process pywin32 objects (thin adapter).

## L4 - Tools & UI
- Task pane (WinForms): editor, Run (Ctrl+Enter), REPL line, output log.
- Script toolbar: scripts folder -> command group buttons.
- Events: `swpy.on("rebuild", fn)` wired to `DPartDocEvents` etc.

## L5 - External bridge
- JSON-RPC 2.0 over named pipe `\\.\pipe\swpy` (and/or `localhost`),
  requests marshalled to the UI thread by the dispatcher.
- Methods: `exec`, `eval`, `get_context`. Clients: Python `swpy.connect()`,
  Excel-DNA, Grasshopper, an MCP server.

## Milestones (test as we go)
| # | Deliverable | Test |
|---|---|---|
| 0a | Spike A: minimal add-in loads in SW 2020 without admin | external pywin32 `GetAddInObject` returns object |
| 0b | Spike B: pythonnet inside SW runs code against `sw` | `Execute("result = sw.RevisionNumber()")` |
| 1 | L0+L1+L2 solid: sessions, output capture, errors, logging | pytest suite via pywin32 harness |
| 2 | L3 `swpy` core: units, dims/globals, mass, batch | pytest against a generated test part |
| 3 | L4 task pane editor + REPL | manual + screenshot |
| 4 | L5 named-pipe bridge + `swpy.connect()` | pytest over the pipe |
| 5 | Packaging: embeddable Python, `# r:` installs, installer | clean-user install test |
