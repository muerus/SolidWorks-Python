"""Probe pythonnet 3.2.0 PyType.Get crash (standalone, no SOLIDWORKS)."""
import sys
from pythonnet import load
load("netfx")
import clr  # noqa: E402

BIN = r"F:\Projects\SolidWorks-Python\src\SwPy.AddIn\bin\Debug\net48"
clr.AddReference(BIN + r"\SolidWorks.Interop.sldworks.dll")
clr.AddReference(BIN + r"\SwPy.AddIn.dll")
from SwPy.Scripting import InteropTypes  # noqa: E402

case = sys.argv[1]
if case == "imported-first":
    from SolidWorks.Interop.sldworks import ISldWorks
    print("imported", ISldWorks)
print("Get ->", InteropTypes.Get("SolidWorks.Interop.sldworks.ISldWorks"))
