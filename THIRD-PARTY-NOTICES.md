# Third-party notices

SwPy is MIT-licensed (see `LICENSE`). Release packages also contain the following components, each under
its own licence:

| Component | Version | Licence | Source |
|---|---|---|---|
| CPython (Windows embeddable package) | 3.12.10 | Python Software Foundation License Version 2 (`bin\python-runtime\LICENSE.txt`) | https://www.python.org |
| pip (wheel) | 26.2.1 | MIT | https://pypi.org/project/pip/ |
| pythonnet (Python.Runtime) | 3.2.0 | MIT | https://github.com/pythonnet/pythonnet |
| Scintilla5.NET | 7.0.0 | MIT | https://github.com/VPKSoft/Scintilla.NET |
| Scintilla and Lexilla (native editor components, part of Scintilla5.NET) | | Scintilla licence (historical permission notice, MIT-style) | https://www.scintilla.org |

Not included: the SOLIDWORKS API interop assemblies (`SolidWorks.Interop.*`). SwPy loads them at runtime
from the user's own SOLIDWORKS installation. The constant and interface names in `python/swpy/swconst.py`,
`python/swpy/libs/` and `src/SwPy.AddIn/Scripting/*.g.cs` are generated from those assemblies to make the
public SOLIDWORKS API usable from Python.

SOLIDWORKS is a registered trademark of Dassault Systèmes SolidWorks Corporation. SwPy is not affiliated
with or endorsed by Dassault Systèmes.
