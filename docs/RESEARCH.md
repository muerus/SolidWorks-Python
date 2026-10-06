# Research notes - Python inside SOLIDWORKS

Working name: **SwPy**. Goal: give SOLIDWORKS what Rhino 8 got - an embedded
CPython with a script editor, REPL, pip packages and a Pythonic API, running
in-process.

## 1. Market gap (confirmed 2026-10)

- SOLIDWORKS officially supports VBA, VB.NET, C#, C++ only. Macros: `.swp` (VBA)
  or VSTA .NET. No embedded Python, no REPL.
- Every Python library drives SW **out-of-process** through COM/pywin32:
  pyswx (typed wrapper, API 2024), pySldWrap, pySW, swxPy, ~6 MCP servers.
- Out-of-process consequences: ~1 ms per COM call, STA marshalling stalls,
  no native UI/events, every user must install Python + pywin32.
- Nearest framework, xCAD.NET (Xarial, MIT), is .NET-only and still alpha
  (0.9.0-alpha.5527).

## 2. Target environment (this dev PC)

| Item | Value |
|---|---|
| SOLIDWORKS | 2020 (API rev 28.0.0.5028), `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS` |
| Interop DLLs | `...\SOLIDWORKS\api\redist\SolidWorks.Interop.sldworks.dll` etc. (v28) |
| Add-in runtime | .NET Framework 4.x (SW hosts the CLR in-process) |
| Build | .NET SDK 10.0.302, net48 targeting pack installed, no Visual Studio |
| Python | 3.9, 3.11-3.14 installed (dev); bundle embeddable dist later |
| Admin | **No** - per-user install path is required |

Implication: build against the **2020 interop** - newer SW versions accept
older interop (API is backward compatible), not the reverse.

## 3. Key technical findings

### 3.1 Add-in hosting
- Add-in = COM class implementing `SolidWorks.Interop.swpublished.ISwAddin`
  (`ConnectToSW(ThisSW, Cookie)` / `DisconnectFromSW`).
- Registration normally: `regasm /codebase` (CLSID under HKLM) +
  `HKLM\SOFTWARE\SolidWorks\Addins\{GUID}` (default=1, Title, Description) +
  optional `HKCU\Software\SolidWorks\AddInsStartup\{GUID}` (load at startup).
- **Open question (spike A):** whether SW 2020 lists/loads an add-in whose
  CLSID is in `HKCU\Software\Classes` and whose Addins key is in HKCU, or via
  `ISldWorks.LoadAddIn(path)`. Per-user COM classes are invisible to
  *elevated* processes - SW must run non-elevated.
- `ISldWorks.GetAddInObject(progId)` returns the live add-in instance to
  external COM clients -> natural hook for tests and the external bridge.

### 3.2 Embedding CPython (pythonnet)
- `pythonnet` 3.2.0 on NuGet targets **netstandard2.0** -> loads in net48.
  Supports Python 3.11-3.15 (3.13/3.14 fixed in 3.0.5+/3.1+).
- Must set `Runtime.PythonDLL` (e.g. `...\python312.dll`) and `PythonHome`
  before `PythonEngine.Initialize()`.
- GIL: after init call `PythonEngine.BeginAllowThreads()`; every entry into
  Python wraps `using (Py.GIL())`.
- .NET objects passed into Python keep their types: the typed
  `ISldWorks` interop object gives attribute access + out-params returned as
  tuples (no pywin32 VARIANT hacks).
- Shutdown of CPython inside a host process is fragile -> initialize once per
  SW session, never finalize (Rhino does the same). "Reset" = fresh globals.

### 3.3 UI
- Task pane: `ISldWorks.CreateTaskpaneView2(icon, title)` then
  `AddControl(progId, "")` (COM-visible WinForms UserControl) or
  `DisplayWindowFromHandlex64(handle)`.
- WPF in task pane via `ElementHost` has known keyboard-input issues ->
  start with **WinForms** (editor: plain RichTextBox first, Scintilla later).
- Commands/toolbar: `ICommandManager.CreateCommandGroup2` + `AddCommandItem2`.

### 3.4 Threading rules
- SW API is STA; all calls must happen on SW's main thread. Add-in callbacks
  (commands, events, task pane UI) already run there.
- External bridge requests arrive on worker threads -> marshal to the UI
  thread (`Control.Invoke` on a hidden control / captured
  `SynchronizationContext`).
- Long scripts block the UI (same as VBA macros). v1 accepts this; add
  "Esc to cancel" via `PyErr_SetInterrupt`-style async exception later.

### 3.5 Units / API pain points the Pythonic layer must hide
- API is always SI (m, rad, kg). Users think in document units.
- By-ref/out params, `VARIANT` arrays returned as `object[]`/`double[]`.
- Selection by name strings (`"Face<1>@Boss-Extrude1"`) is fragile ->
  geometric queries on `IBody2.GetFaces()` etc.
- Every edit can trigger a rebuild -> batch context (`EnableGraphicsUpdate`,
  `FeatureManager.EnableFeatureTree`, single `EditRebuild3`).

## 4. Spike results (2026-10-05, SW 2020 on dev PC)

| Question | Result |
|---|---|
| Per-user COM registration (HKCU\Software\Classes) | **Works.** `CoCreate("SwPy.AddIn")` OK without admin. |
| SW 2020 reads `HKCU\Software\SolidWorks\AddIns` | **No.** Not listed / not auto-loaded. `LoadAddIn(clsid)` -> 3. |
| `ISldWorks.LoadAddIn(<dll path>)` with per-user COM | **Works** (rc 0) -> dev/test path. Auto-load at startup still needs a one-time HKLM key (admin) or a loader - open item for packaging. |
| pythonnet 3.2.0 + Python 3.12 in SW's net48 CLR | **Works.** First call 1.5 s (engine start), then ms. |
| `from SolidWorks.Interop.sldworks import ISldWorks` | **Unsafe.** Binds to McMaster-Carr add-in's embedded (NoPIA) copy with 13 members. Any machine with such add-ins breaks. |
| `PyType.Get(Type)` to hand Python the real type | **Crashes** (AccessViolation in `PyType_GenericAlloc`) whenever the class is not created yet - pythonnet 3.2.0 bug, reproduced standalone (`spikes/pytype`). |
| Fix | Generated `SwPy.Scripting.Cast` (932 typed casts): declared return type => pythonnet wraps with the real interface. `swconst` generated as pure Python (889 enums, 0.18 s import). |
| Thread of external COM calls | MTA RPC thread -> every SW call marshalled to UI STA: **~300 ms per API call**. |
| Fix | `MainThread` dispatcher (hidden WinForms control, `Invoke`): **27-43 µs per API call, 3.2 ms external round trip**. |

## 5. Sources
- pythonnet docs/releases: https://pythonnet.github.io/pythonnet/ ,
  https://github.com/pythonnet/pythonnet/releases
- Add-in manual registration: https://www.codestack.net/solidworks-api/deployment/manual/
- Task pane example (C#): https://help.solidworks.com/2024/English/api/sldworksapi/Create_TaskPaneView_Add-in_Example_CSharp.htm
- WPF in task pane caveats: https://github.com/angelsix/solidworks-api/issues/121 ,
  https://xcad.xarial.com/extensions/panels/task-pane/
- Python libs: https://github.com/deloarts/pyswx , https://github.com/OscarJin/pySldWrap
- xCAD.NET: https://xcad.xarial.com/
