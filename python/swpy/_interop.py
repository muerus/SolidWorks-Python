"""SOLIDWORKS interop bound to the real interop assemblies.

`sldworks.IPartDoc(obj)` returns a `Com` proxy that prefers that interface. Casting goes through a
generated C# method (SwPy.Scripting.Cast) whose declared return type is the real interface.
Never import from `SolidWorks.Interop.*` directly: other add-ins (e.g. McMaster-Carr) embed
trimmed copies of those types and pythonnet may bind to them.
"""
import clr  # noqa: F401  (pythonnet)
from SwPy.Scripting import Cast

from swpy import swconst  # noqa: F401  (generated pure-Python constants)
from swpy.com import Com


class _Casts:
    def __getattr__(self, name):
        if name.startswith("_") or not hasattr(Cast, name):
            raise AttributeError(f"SOLIDWORKS interop has no interface {name!r}")

        def cast(obj):
            return None if obj is None else Com(obj, prefer=name)
        cast.__name__ = name
        cast.__swpy_interface__ = name   # lets the editor type `sldworks.IFoo(x).` statically
        cast.__doc__ = f"View a SOLIDWORKS object as {name} (returns a typed Com proxy, None for None)."
        setattr(self, name, cast)   # cache
        return cast

    def __dir__(self):
        return [n for n in dir(Cast) if not n.startswith("_") and n[0].isupper()]

    def __repr__(self):
        return "<SOLIDWORKS interop casts>"


sldworks = _Casts()
