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


class _Library:
    """One SOLIDWORKS API library besides sldworks, e.g. `cosworks` (Simulation).

    `cosworks.ICosmosWorks(obj)` casts like `sldworks.IFoo(obj)`; `cosworks.swsAnalysisStudyType_e` are its
    constants. Nothing is loaded until first use.
    """

    def __init__(self, name):
        from swpy.libs import LIBRARIES
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_meta", LIBRARIES[name])

    def _constants(self):
        import importlib
        return importlib.import_module(f"swpy.libs.{self._name}")

    def __getattr__(self, attr):
        if attr.startswith("_"):
            raise AttributeError(attr)
        constants = self._constants()
        if hasattr(constants, attr) and not attr.startswith("_"):
            value = getattr(constants, attr)
        else:
            from swpy.com import library_casts
            if not hasattr(library_casts(self._name), attr):
                raise AttributeError(f"{self._name} ({self._meta['title']}) has no interface or constant {attr!r}")
            qualified = f"{self._name}.{attr}"

            def value(obj):
                return None if obj is None else Com(obj, prefer=qualified)
            value.__name__ = attr
            value.__swpy_interface__ = qualified
            value.__doc__ = f"View a {self._meta['title']} object as {attr} (typed Com proxy, None for None)."
        object.__setattr__(self, attr, value)   # cache: also makes it visible to the editor's static lookups
        return value

    def __dir__(self):
        from swpy.com import library_casts
        import clr
        from System.Reflection import BindingFlags
        casts = [m.Name for m in clr.GetClrType(library_casts(self._name)).GetMethods(BindingFlags.Public | BindingFlags.Static)]
        constants = [n for n in vars(self._constants()) if not n.startswith("_")]
        return sorted(set(casts) | set(constants))

    def __repr__(self):
        m = self._meta
        return f"<{m['title']} API ({self._name}): {m['interfaces']} interfaces, {m['enums']} enums>"


def _libraries():
    from swpy.libs import LIBRARIES
    return {name: _Library(name) for name in LIBRARIES}


libraries = _libraries()   # {"cosworks": <Simulation API>, "swmotionstudy": ..., "EdmLib": ...}
