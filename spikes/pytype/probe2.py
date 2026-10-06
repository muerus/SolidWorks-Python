import sys
from pythonnet import load
load("netfx")
import clr  # noqa: E402
BIN = r"F:\Projects\SolidWorks-Python\src\SwPy.AddIn\bin\Debug\net48"
clr.AddReference(BIN + r"\SolidWorks.Interop.sldworks.dll")
clr.AddReference(BIN + r"\SwPy.AddIn.dll")
from SwPy.Scripting import InteropTypes  # noqa: E402
case = sys.argv[1]
if case == "module-only":
    import SolidWorks.Interop.sldworks  # noqa: F401
    print("Get ->", InteropTypes.Get("SolidWorks.Interop.sldworks.ISldWorks"))
elif case == "other-type-first":
    from SolidWorks.Interop.sldworks import IModelDoc2  # noqa: F401
    print("Get ->", InteropTypes.Get("SolidWorks.Interop.sldworks.ISldWorks"))
elif case == "bcl-type":
    print("Get ->", InteropTypes.Get("System.Text.StringBuilder"))
elif case == "class-type":
    print("Get ->", InteropTypes.Get("SolidWorks.Interop.sldworks.SldWorksClass"))
