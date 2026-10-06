"""SOLIDWORKS interop bound to the real interop assemblies.

`sldworks.IModelDoc2(obj)` casts through a generated C# method (SwPy.Scripting.Cast) whose
declared return type is the real interface, so pythonnet wraps the object with that type.
Never import from `SolidWorks.Interop.*` directly: other add-ins (e.g. McMaster-Carr) embed
trimmed copies of those types and pythonnet may bind to them.
"""
import clr  # noqa: F401  (pythonnet)
from SwPy.Scripting import Cast

from swpy import swconst  # noqa: F401  (generated pure-Python constants)


class _Casts:
    def __getattr__(self, name):
        fn = None if name.startswith("_") else getattr(Cast, name, None)
        if fn is None:
            raise AttributeError(f"SOLIDWORKS interop has no interface {name!r}")
        setattr(self, name, fn)   # cache
        return fn

    def __dir__(self):
        return [n for n in dir(Cast) if not n.startswith("_") and n[0].isupper()]

    def __repr__(self):
        return "<SOLIDWORKS interop casts>"


sldworks = _Casts()
