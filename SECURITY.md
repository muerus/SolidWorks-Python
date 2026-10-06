# Security

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Report them privately through GitHub's
[private vulnerability reporting](https://github.com/muerus/SolidWorks-Python/security/advisories/new)
(Security tab > *Report a vulnerability*). You will get an answer as soon as possible; please allow time
for a fix before disclosing details.

## Trust model - what SwPy is and is not

SwPy runs Python **inside SOLIDWORKS, with the permissions of the logged-in Windows user**. That is its
purpose, so keep these points in mind:

* **Running a script means running code.** A script can do anything the user can: read and write files,
  start programs, use the network, change models. Only run scripts you trust - exactly like VBA macros.
* **Script folder and startup scripts.** Every `.py` in the script folder becomes a button, and scripts in
  `startup\` run automatically when SOLIDWORKS starts. If you point `ScriptsFolder` at a shared or network
  folder, everyone who can write to it can run code on every machine that uses it: restrict write access.
* **`# r:` package headers** install packages from PyPI into `%LOCALAPPDATA%\SwPy\site-packages` when a
  script runs. Only plain package names and version specifiers are accepted (no pip options, URLs or
  paths), but a package is still third-party code: pin versions you trust (`# r: openpyxl==3.1.5`).
* **Automation interface.** Other programs of the **same Windows user** on the same machine can run code
  through `ISldWorks.GetAddInObject("SwPy.AddIn").Execute(...)` (that is how `swpy.client`, Excel and C#
  integration work). SwPy opens no network port and accepts no remote connections.
* **Event handlers** run inside SOLIDWORKS operations; they are isolated from errors but not from
  malicious code - the same rule as for scripts applies.
* **No elevation.** SwPy installs per user without admin rights. The optional `install.ps1 -Machine`
  writes one SOLIDWORKS add-in registry key under HKLM and nothing else.

## Supply chain

* The bundled Python runtime and pip wheel are downloaded by `tools/fetch_python.ps1` with **pinned
  versions and SHA-256 verification**.
* The add-in depends on `pythonnet` and `Scintilla5.NET` (NuGet, pinned in `SwPy.AddIn.csproj`) and on the
  SOLIDWORKS interop assemblies of the local installation.
* The repository contains no credentials. SOLIDWORKS Document Manager licence keys and PDM credentials
  belong in your own scripts or environment, never in this repository.
