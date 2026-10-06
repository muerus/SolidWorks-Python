"""Auto-typed proxies over SOLIDWORKS COM objects.

The interop declares many members as returning `object` (ActiveDoc, FirstFeature, GetFaces ...),
which pythonnet hands back as an untyped `__ComObject`. `Com` asks the object which interfaces it
implements (QueryInterface against a curated list) and forwards attribute access to all of them,
auto-wrapping every result:

    doc.FirstFeature().Name           # works, no manual casts
    doc.GetBodies2(0, True)[0].GetFaces()   # arrays become lists of Com
    doc                                # <IModelDoc2+IPartDoc 'Part1'>
"""
import clr  # noqa: F401
import System
from System.Runtime.InteropServices import Marshal

from SwPy.Scripting import Cast

# Most specific / most useful first: attribute lookup tries interfaces in this order.
CANDIDATES = (
    "IModelDoc2", "IPartDoc", "IAssemblyDoc", "IDrawingDoc",
    "IFeature", "IFace2", "IEdge", "IVertex", "ILoop2", "ICoEdge", "IBody2",
    "ISketch", "ISketchSegment", "ISketchLine", "ISketchArc", "ISketchSpline", "ISketchPoint",
    "ISurface", "ICurve",
    "IComponent2", "IMate2", "IConfiguration", "IConfigurationManager",
    "IDimension", "IDisplayDimension", "IAnnotation", "INote",
    "IView", "ISheet", "IModelView", "IFrame", "ISketchRelationManager", "IDimXpertManager",
    "IModelDocExtension", "IFeatureManager", "ISketchManager", "ISelectionMgr",
    "ICustomPropertyManager", "IEquationMgr", "IMassProperty",
    "IMathUtility", "IMathPoint", "IMathVector", "IMathTransform",
    "IRefPlane", "IRefAxis", "IRefPoint", "IAttribute",
    "IEntity",
)


def _real_interop_assembly():
    # Filter by assembly name: add-ins that embed copies of these types live in their own assemblies.
    for asm in System.AppDomain.CurrentDomain.GetAssemblies():
        if asm.GetName().Name == "SolidWorks.Interop.sldworks":
            return asm
    raise RuntimeError("SolidWorks.Interop.sldworks is not loaded")


_ASM = _real_interop_assembly()
_TYPES = []
for _n in CANDIDATES:
    _t = _ASM.GetType("SolidWorks.Interop.sldworks." + _n)
    if _t is not None:
        _TYPES.append((_n, _t))
_KNOWN = {n for n, _ in _TYPES}


def is_com(value):
    try:
        return value is not None and Marshal.IsComObject(value)
    except Exception:
        return False


try:   # one native call per object (add-in >= 0.1 with ComInfo); Python fallback otherwise
    from SwPy.Scripting import ComInfo as _ComInfo
except ImportError:
    _ComInfo = None
_CANDIDATES_CSV = ",".join(n for n, _ in _TYPES)


def interfaces_of(raw):
    """Names of the curated interfaces this COM object implements, in priority order."""
    if _ComInfo is not None:
        found = _ComInfo.Implemented(raw, _CANDIDATES_CSV)
        return found.split(",") if found else []
    return [n for n, t in _TYPES if t.IsInstanceOfType(raw)]


def identity(raw):
    """COM identity (IUnknown pointer): equal for every reference to the same object."""
    if _ComInfo is not None:
        return _ComInfo.Identity(raw)
    ptr = Marshal.GetIUnknownForObject(raw)
    try:
        return ptr.ToInt64()
    finally:
        Marshal.Release(ptr)


def _is_method(attr):
    return type(attr).__name__ in ("MethodBinding", "MethodObject")


class NetList(list):
    """A list from a primitive .NET array (double[], byte[] ...) that remembers its element type,
    so passing it back to the API recreates exactly that array (e.g. persistent references)."""

    __slots__ = ("element_type",)


def _net_array(element_type, items):
    arr = System.Array.CreateInstance(element_type, len(items))
    for i, v in enumerate(items):
        arr[i] = v
    return arr


def _infer_array(items):
    """Typed .NET array for a plain Python sequence passed to the API."""
    if items and all(isinstance(v, Com) for v in items):
        return System.Array[System.Object]([v._raw for v in items])
    if items and all(isinstance(v, bool) for v in items):
        return System.Array[System.Boolean](items)
    if items and all(isinstance(v, int) and not isinstance(v, bool) for v in items):
        return System.Array[System.Int32](items)
    if items and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in items):
        return System.Array[System.Double]([float(v) for v in items])
    if items and all(isinstance(v, str) for v in items):
        return System.Array[System.String](items)
    return System.Array[System.Object]([unwrap(v) for v in items])


def unwrap(value):
    """Python -> API argument: Com -> raw COM object, lists -> typed .NET arrays."""
    if type(value).__name__ == "Com":
        return value._raw
    if isinstance(value, NetList):
        return _net_array(value.element_type, value)
    if isinstance(value, (list, tuple)):
        return _infer_array(list(value))
    return value


def auto(value):
    """Wrap SOLIDWORKS results: COM objects -> Com, .NET arrays -> lists, tuples element-wise."""
    if value is None or isinstance(value, (str, bool, int, float, Com)):
        return value
    if isinstance(value, tuple):          # out-parameters
        return tuple(auto(v) for v in value)
    if isinstance(value, System.Array):
        element_type = value.GetType().GetElementType()
        items = [auto(v) for v in value]
        if element_type.IsPrimitive:
            items = NetList(items)
            items.element_type = element_type
        return items
    if is_com(value):
        return Com(value)
    return value


class Com:
    """Proxy over one SOLIDWORKS COM object exposing all its known interfaces."""

    __slots__ = ("_raw", "_names", "_views")

    def __init__(self, raw, prefer=None):
        while type(raw).__name__ == "Com":   # also (nested) proxies from before a module reload
            raw = raw._raw
        names = interfaces_of(raw)
        declared = type(raw).__name__
        if declared in _KNOWN and declared not in names:
            names.insert(0, declared)
        if prefer:
            if prefer in names:
                names.remove(prefer)
            names.insert(0, prefer)
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_names", tuple(names))
        object.__setattr__(self, "_views", [None] * len(names))   # typed views, created on demand

    # -- introspection -------------------------------------------------------
    @property
    def raw(self):
        return self._raw

    @property
    def interfaces(self):
        return self._names

    def as_(self, interface):
        """View the object primarily as another interface (also outside the curated list)."""
        return Com(self._raw, prefer=interface)

    def _view(self, i):
        v = self._views[i]
        if v is None:
            v = self._views[i] = getattr(Cast, self._names[i])(self._raw)
        return v

    def _all_views(self):
        return (self._view(i) for i in range(len(self._names)))

    # -- attribute forwarding ------------------------------------------------
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        for view in self._all_views():
            try:
                attr = getattr(view, name)
            except AttributeError:
                continue
            if _is_method(attr):
                return _bound(attr)
            return auto(attr)
        raise AttributeError(f"{'/'.join(self._names) or 'COM object'} has no attribute {name!r}")

    def __setattr__(self, name, value):
        for view in self._all_views():
            if hasattr(view, name):
                setattr(view, name, unwrap(value))
                return
        raise AttributeError(f"{'/'.join(self._names) or 'COM object'} has no attribute {name!r}")

    def __dir__(self):
        seen = set()
        for view in self._all_views():
            seen.update(n for n in dir(view) if not n.startswith("_"))
        return sorted(seen) + ["as_", "interfaces", "raw"]

    # -- identity --------------------------------------------------------------
    def __eq__(self, other):
        return isinstance(other, Com) and identity(self._raw) == identity(other._raw)

    def __hash__(self):
        return hash(identity(self._raw))

    def __repr__(self):
        label = _label(self)
        kind = "+".join(self._names[:2]) or "COM object"
        return f"<{kind} {label!r}>" if label else f"<{kind}>"


def _bound(method):
    def call(*args, **kwargs):
        return auto(method(*[unwrap(a) for a in args], **{k: unwrap(v) for k, v in kwargs.items()}))
    call.__name__ = getattr(method, "__name__", "method")
    call.__doc__ = getattr(method, "__doc__", None)
    return call


_LABELS = (("IModelDoc2", "GetTitle"), ("IComponent2", "Name2"), ("IFeature", "Name"),
           ("IConfiguration", "Name"), ("IDimension", "FullName"), ("IView", "Name"), ("ISheet", "GetName"))


def _label(com):
    for iface, member in _LABELS:
        if iface in com._names:
            try:
                v = getattr(com._view(com._names.index(iface)), member)
                return v() if _is_method(v) else v
            except Exception:
                return None
    return None
