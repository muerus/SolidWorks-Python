"""Editor services for the task pane: completion, signature help, hover, syntax check, API help links.

Called through swpy._host.call(method, json) with the live session namespace, so completion knows
real objects (`doc.`, `model.`, your variables). SOLIDWORKS objects are completed from the interop's
.NET type information, which also follows calls statically:

    doc.Extension.            -> IModelDocExtension members      (no COM call is made)
    part.FeatureManager.FeatureExtrusion2(...).   -> IFeature members

Names not yet defined at runtime are inferred from assignments in the buffer (`x = sldworks.IPartDoc(...)`).
Nothing here calls SOLIDWORKS methods or user functions; only plain attribute reads on Python objects.
"""
import builtins
import inspect
import keyword
import re
import sys
import types

from swpy import com as _com

INTEROP_NS = "SolidWorks.Interop.sldworks"
HELP_URL = "https://help.solidworks.com/{year}/english/api/sldworksapi/{topic}.html"

_TYPE_ALIASES = {
    "System.Object": "object", "System.Boolean": "bool", "System.Int16": "int", "System.Int32": "int",
    "System.Int64": "int", "System.Double": "float", "System.Single": "float", "System.String": "str",
    "System.Void": "None",
}
_PY_EQUIVALENT = {"System.String": str, "System.Double": float, "System.Int32": int, "System.Boolean": bool}


# --------------------------------------------------------------------------- resolved values

class _Val:
    """A live Python object from the session (never a Com: those become _Net)."""
    def __init__(self, obj):
        self.obj = obj


class _Net:
    """An instance of one or more SOLIDWORKS interop interfaces (static .NET type information)."""
    def __init__(self, net_types):
        self.types = [t for t in net_types if t is not None]


class _NetMethod:
    def __init__(self, owner, name, overloads):
        self.owner, self.name, self.overloads = owner, name, overloads


class _Inst:
    """An instance of a Python class, known only by its type (not evaluated)."""
    def __init__(self, cls):
        self.cls = cls


class _Func:
    """A Python function/method known statically (for return annotations), with its owning class."""
    def __init__(self, func, owner=None):
        self.func, self.owner = func, owner


def _net_type(name):
    return _com._ASM.GetType(f"{INTEROP_NS}.{name}") if name else None


def _wrap(obj):
    """Live object -> resolved value; SOLIDWORKS objects are described by their interfaces."""
    if obj is None:
        return None
    if type(obj).__name__ == "Com":
        return _Net(_net_type(n) for n in obj._names)
    if _com.is_com(obj):
        return _Net(_net_type(n) for n in _com.interfaces_of(obj))
    return _Val(obj)


def _from_net_type(t):
    if t is None:
        return None
    if t.IsByRef:
        t = t.GetElementType()
    if t.Namespace == INTEROP_NS:
        return _Net([t])
    py = _PY_EQUIVALENT.get(t.FullName)
    return _Inst(py) if py else None


# --------------------------------------------------------------------------- .NET reflection (cached)

_MEMBERS = {}


def _net_members(t):
    """{name: PropertyInfo | [MethodInfo]} including inherited interfaces."""
    key = t.AssemblyQualifiedName
    members = _MEMBERS.get(key)
    if members is None:
        members = {}
        for tt in [t] + list(t.GetInterfaces()):
            for p in tt.GetProperties():
                if len(p.GetIndexParameters()) == 0:
                    members.setdefault(p.Name, p)
                    continue
                # parameterized COM properties are only callable as accessors: get_X(arg) / set_X(arg, value)
                for prefix, accessor in (("get_", p.GetGetMethod()), ("set_", p.GetSetMethod())):
                    if accessor is not None:
                        members.setdefault(prefix + p.Name, []).append(accessor)
            for m in tt.GetMethods():
                if not m.IsSpecialName:
                    members.setdefault(m.Name, [])
                    if isinstance(members[m.Name], list):
                        members[m.Name].append(m)
        _MEMBERS[key] = members
    return members


def _tname(t):
    if t.IsByRef:
        t = t.GetElementType()
    if t.IsArray:
        return _tname(t.GetElementType()) + "[]"
    return _TYPE_ALIASES.get(t.FullName, t.Name)


def _iface_name(t):
    """Interop coclass interfaces (ModelDoc2) are documented under their I-name (IModelDoc2)."""
    n = t.Name
    return n if n.startswith("I") and n[1:2].isupper() else "I" + n


# --------------------------------------------------------------------------- source parsing

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _is_ident_char(c):
    return c.isalnum() or c == "_"


def _parse_chain(text):
    """Attribute chain ending `text`: 'x = a.b(1)[0].c' -> [('a', ''), ('b', '()[]'), ('c', '')]."""
    parts, i = [], len(text.rstrip())
    while True:
        ops = ""
        while i > 0 and text[i - 1] in ")]":
            close = text[i - 1]
            opener = "(" if close == ")" else "["
            depth, k = 0, i - 1
            while k >= 0:
                if text[k] == close:
                    depth += 1
                elif text[k] == opener:
                    depth -= 1
                    if depth == 0:
                        break
                k -= 1
            if k < 0:
                return None
            ops = ("()" if close == ")" else "[]") + ops
            i = k
        k = i
        while k > 0 and _is_ident_char(text[k - 1]):
            k -= 1
        name = text[k:i]
        if not name or name[0].isdigit():
            return None
        parts.insert(0, (name, ops))
        i = k
        if i > 0 and text[i - 1] == ".":
            i -= 1
            continue
        if i > 0 and (_is_ident_char(text[i - 1]) or text[i - 1] in "'\""):
            return None
        return parts


def _open_call(text):
    """(callee_text, arg_index) of the innermost unclosed '(' at the end of text, else None."""
    depth, commas, i = 0, 0, len(text) - 1
    quote = None
    while i >= 0:
        c = text[i]
        if quote:
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c in ")]}":
            depth += 1
        elif c in "([{":
            if depth == 0:
                if c != "(":
                    return None
                return text[:i], commas
            depth -= 1
        elif c == "," and depth == 0:
            commas += 1
        i -= 1
    return None


def _assignment_rhs(name, source_lines):
    """Right-hand side text of the last `name = ...` / `for name in ...` / `with ... as name` before the end."""
    assign = re.compile(rf"^\s*{re.escape(name)}\s*=(?!=)\s*(.+?)\s*$")
    for_in = re.compile(rf"^\s*for\s+{re.escape(name)}\s+in\s+(.+?)\s*:\s*$")
    with_as = re.compile(rf"^\s*with\s+(.+?)\s+as\s+{re.escape(name)}\s*:\s*$")
    for idx in range(len(source_lines) - 1, -1, -1):
        line = source_lines[idx]
        m = assign.match(line)
        if m:
            return m.group(1), "", idx
        m = for_in.match(line)
        if m:
            return m.group(1), "[]", idx
        m = with_as.match(line)
        if m:
            return m.group(1), "", idx
    return None


# --------------------------------------------------------------------------- resolution

def _resolve_name(name, g, lines, depth):
    if name in g:
        return _wrap(g[name])
    if hasattr(builtins, name):
        return _Val(getattr(builtins, name))
    if depth > 6:
        return None
    found = _assignment_rhs(name, lines)
    if found is None:
        return None
    rhs, extra_ops, idx = found
    rhs = rhs.split("#", 1)[0]
    chain = _parse_chain(rhs)
    if not chain:
        return None
    v = _resolve_chain(chain, g, lines[:idx], depth + 1)
    return _apply_ops(v, extra_ops)


def _resolve_chain(chain, g, lines, depth=0):
    name, ops = chain[0]
    v = _apply_ops(_resolve_name(name, g, lines, depth), ops)
    for name, ops in chain[1:]:
        v = _apply_ops(_attr(v, name), ops)
        if v is None:
            return None
    return v


def _attr(v, name):
    if v is None:
        return None
    if isinstance(v, _Net):
        for t in v.types:
            m = _net_members(t).get(name)
            if isinstance(m, list):
                return _NetMethod(t, name, m)
            if m is not None:
                return _from_net_type(m.PropertyType)
        return None
    if isinstance(v, _Inst):
        return _static_attr(v.cls, name)
    if isinstance(v, _Val):
        obj = v.obj
        cls = obj if isinstance(obj, type) else type(obj)
        try:
            static = inspect.getattr_static(obj, name)
        except AttributeError:
            static = None
        if isinstance(static, property):
            r = _annotated(static.fget, cls)
            if r is not None:
                return r
        on_class = name not in getattr(obj, "__dict__", {})   # functions stored on instances are plain values
        if isinstance(static, (types.FunctionType, classmethod, staticmethod)) and on_class:
            return _Func(getattr(static, "__func__", static), cls)
        try:
            return _wrap(getattr(obj, name))   # plain attribute or unannotated property
        except Exception:
            return None
    return None


def _static_attr(cls, name):
    try:
        a = inspect.getattr_static(cls, name)
    except AttributeError:
        ann = getattr(cls, "__annotations__", {}).get(name)
        return _from_annotation(ann, None, cls) if ann else None
    if isinstance(a, property):
        return _annotated(a.fget, cls)
    if isinstance(a, (types.FunctionType, classmethod, staticmethod)):
        return _Func(getattr(a, "__func__", a), cls)
    return _wrap(a)


def _annotated(func, owner):
    ann = getattr(func, "__annotations__", {}).get("return")
    return _from_annotation(ann, func, owner) if ann is not None else None


def _from_annotation(ann, func, owner):
    if isinstance(ann, type):
        return _Inst(ann)
    if isinstance(ann, str):
        if ann == "ITEM" and owner is not None:     # Query.largest() -> the item interface
            return _Net([_net_type(getattr(owner, "ITEM", None))])
        if ann == "SELF" and owner is not None:     # Query.where() -> same query class
            return _Inst(owner)
        scope = getattr(func, "__globals__", {}) if func else {}
        if owner is not None and owner.__module__ in sys.modules:
            scope = dict(scope, **vars(sys.modules[owner.__module__]))
        target = scope.get(ann)
        if isinstance(target, type):
            return _Inst(target)
        t = _net_type(ann)
        if t is not None:
            return _Net([t])
    return None


def _apply_ops(v, ops):
    for i in range(0, len(ops), 2):
        if v is None:
            return None
        v = _call(v) if ops[i:i + 2] == "()" else _index(v)
    return v


def _call(v):
    if isinstance(v, _NetMethod):
        return _from_net_type(v.overloads[0].ReturnType)
    if isinstance(v, _Func):
        return _annotated(v.func, v.owner)
    if isinstance(v, _Val):
        obj = v.obj
        iface = getattr(obj, "__swpy_interface__", None)   # sldworks.IFoo(...) casts
        if iface:
            return _Net([_net_type(iface)])
        if isinstance(obj, type):
            return _Inst(obj)
        if callable(obj):
            return _annotated(obj, None)
    return None


def _index(v):
    if isinstance(v, _Val) and isinstance(v.obj, (list, tuple)) and v.obj:
        return _wrap(v.obj[0])
    if isinstance(v, _Inst) and getattr(v.cls, "ITEM", None):
        return _Net([_net_type(v.cls.ITEM)])
    return None


# --------------------------------------------------------------------------- member listing

def _kind_of(static):
    if isinstance(static, property):
        return "property"
    if isinstance(static, (types.FunctionType, types.BuiltinFunctionType, types.MethodType,
                           classmethod, staticmethod, types.MethodDescriptorType)):
        return "method"
    if isinstance(static, type):
        return "class"
    if isinstance(static, types.ModuleType):
        return "module"
    if callable(static):
        return "function"
    return "field"


def _members(v, prefix):
    out = {}
    show_private = prefix.startswith("_")
    if isinstance(v, _Net):
        for t in v.types:
            for name, m in _net_members(t).items():
                out.setdefault(name, "method" if isinstance(m, list) else "property")
        if v.types:
            out.update({"as_": "method", "interfaces": "property", "raw": "property"})
    elif isinstance(v, (_Val, _Inst)):
        obj = v.obj if isinstance(v, _Val) else v.cls
        try:
            names = dir(obj)
        except Exception:
            names = []
        for name in names:
            if name.startswith("__") and not prefix.startswith("__"):
                continue
            if name.startswith("_") and not show_private:
                continue
            try:
                out[name] = _kind_of(inspect.getattr_static(obj, name))
            except AttributeError:
                out[name] = "field"
        if isinstance(v, _Inst):
            for name in getattr(v.cls, "__annotations__", {}):
                out.setdefault(name, "field")
    return out


def _global_names(g, source):
    out = {k: "keyword" for k in keyword.kwlist}
    out.update({k: _kind_of(getattr(builtins, k)) for k in dir(builtins) if not k.startswith("_")})
    for k, val in g.items():
        if not k.startswith("__"):
            out[k] = "class" if isinstance(val, type) else "module" if isinstance(val, types.ModuleType) \
                else "function" if callable(val) and not type(val).__name__ == "Com" else "variable"
    for k in _IDENT.findall(source):
        if len(k) > 2:
            out.setdefault(k, "variable")
    return out


# --------------------------------------------------------------------------- public services

def complete(g, before, source=""):
    """Completions at the end of `before`.

    Returns {"start": len(prefix), "items": [[name, kind], ...]} (sorted case-insensitively).
    """
    j = len(before)
    while j > 0 and _is_ident_char(before[j - 1]):
        j -= 1
    prefix = before[j:]
    if j > 0 and before[j - 1] == ".":
        chain = _parse_chain(before[:j - 1])
        if not chain:
            return {"start": len(prefix), "items": []}
        lines = before.split("\n")
        members = _members(_resolve_chain(chain, g, lines), prefix)
    else:
        members = _global_names(g, source or before)
        if prefix and (source or before).count(prefix) == 1:
            members.pop(prefix, None)   # its only occurrence is the word being typed
    p = prefix.lower()
    items = sorted(([n, k] for n, k in members.items() if n.lower().startswith(p)), key=lambda x: x[0].lower())
    return {"start": len(prefix), "items": items}


def _py_signature(obj, label=None):
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return None
    name = label or getattr(obj, "__name__", "call")
    params = list(sig.parameters.values())
    text, spans = name + "(", []
    for i, p in enumerate(params):
        if i:
            text += ", "
        s = str(p)
        spans.append([len(text), len(text) + len(s)])
        text += s
    text += ")"
    if sig.return_annotation is not inspect.Signature.empty:
        ra = sig.return_annotation
        text += " -> " + (ra if isinstance(ra, str) else getattr(ra, "__name__", str(ra)))
    return {"label": text, "params": spans, "doc": _doc(obj)}


def _net_signature(m):
    text, spans = m.Name + "(", []
    for i, p in enumerate(m.GetParameters()):
        if i:
            text += ", "
        s = f"{p.Name}: {_tname(p.ParameterType)}"
        if p.IsOut or p.ParameterType.IsByRef:
            s = "out " + s
        spans.append([len(text), len(text) + len(s)])
        text += s
    return {"label": text + ") -> " + _tname(m.ReturnType), "params": spans, "doc": ""}


def _doc(obj):
    d = inspect.getdoc(obj) or ""
    return "\n".join(d.strip().split("\n")[:12])


def _signatures(v, label):
    if isinstance(v, _NetMethod):
        return [_net_signature(m) for m in v.overloads]
    if isinstance(v, _Func):
        s = _py_signature(v.func, label)
        if s and s["params"] and re.match(r"(self|cls)\b", s["label"][s["params"][0][0]:]):
            s = _drop_self(s)   # reached through a class or an inferred instance
        return [s] if s else []
    if isinstance(v, _Val):
        iface = getattr(v.obj, "__swpy_interface__", None)
        if iface:
            return [{"label": f"{iface}(obj) -> {iface}", "params": [[len(iface) + 1, len(iface) + 4]],
                     "doc": f"View a SOLIDWORKS object as {iface} (typed proxy)."}]
        s = _py_signature(v.obj, label)
        return [s] if s else []
    return []


def _drop_self(s):
    label = s["label"]
    start = label.index("(") + 1
    first = s["params"][0]
    cut = first[1] + (2 if len(s["params"]) > 1 else 0)
    removed = cut - start
    label = label[:start] + label[cut:]
    spans = [[a - removed, b - removed] for a, b in s["params"][1:]]
    return {"label": label, "params": spans, "doc": s["doc"]}


def signature(g, before):
    """Signature help for the innermost open call at the end of `before`.

    Returns {"signatures": [{"label", "params": [[start, end], ...], "doc"}], "arg": index} or None.
    """
    found = _open_call(before)
    if not found:
        return None
    callee, arg = found
    chain = _parse_chain(callee)
    if not chain:
        return None
    lines = callee.split("\n")
    v = _resolve_chain(chain, g, lines)
    sigs = _signatures(v, chain[-1][0])
    return {"signatures": sigs, "arg": arg} if sigs else None


def hover(g, before):
    """Description of the dotted name ending `before` (the word under the mouse): {"text", "help"}."""
    chain = _parse_chain(before)
    if not chain:
        return None
    lines = before.split("\n")
    *head, (name, ops) = chain
    owner = _resolve_chain(head, g, lines) if head else None
    v = _attr(owner, name) if head else _resolve_name(name, g, lines, 0)
    text, help_url = None, None
    if isinstance(v, _NetMethod):
        sig = _net_signature(v.overloads[0])["label"]
        text = f"{_iface_name(v.owner)}.{sig}"
        help_url = _help_topic(v.owner, name)
    elif isinstance(owner, _Net):
        for t in owner.types:
            p = _net_members(t).get(name)
            if p is not None and not isinstance(p, list):
                text = f"{_iface_name(t)}.{name}: {_tname(p.PropertyType)}  (property)"
                help_url = _help_topic(t, name)
                break
    elif isinstance(v, _Net) and not head:
        ifaces = ", ".join(_iface_name(t) for t in v.types[:4])
        text = f"{name}: {ifaces}"
        if v.types:
            help_url = _help_topic(v.types[0], None)
    elif isinstance(owner, (_Val, _Inst)) and isinstance(_static_or_none(owner, name), property):
        prop = _static_or_none(owner, name)
        kind = v.cls.__name__ if isinstance(v, _Inst) else _iface_name(v.types[0]) if isinstance(v, _Net) and v.types \
            else type(v.obj).__name__ if isinstance(v, _Val) else "?"
        text = f"{name}: {kind}  (property)" + ("\n\n" + _doc(prop.fget) if _doc(prop.fget) else "")
    elif isinstance(v, (_Func, _Val)):
        sigs = _signatures(v, name)
        if sigs:
            text = sigs[0]["label"] + ("\n\n" + sigs[0]["doc"] if sigs[0]["doc"] else "")
        elif isinstance(v, _Val):
            r = repr(v.obj)
            text = f"{name}: {type(v.obj).__name__} = {r[:120] + ('...' if len(r) > 120 else '')}"
            d = _doc(type(v.obj)) if not isinstance(v.obj, (int, float, str, list, dict, tuple)) else ""
            if d:
                text += "\n\n" + d
    elif isinstance(v, _Inst):
        text = f"{name}: {v.cls.__name__}"
    return {"text": text, "help": help_url} if text else None


def _static_or_none(v, name):
    try:
        return inspect.getattr_static(v.obj if isinstance(v, _Val) else v.cls, name)
    except AttributeError:
        return None


def _help_topic(t, member):
    iface = _iface_name(t)
    topic = f"{INTEROP_NS}~{INTEROP_NS}.{iface}" + (f"~{member}" if member else "")
    return HELP_URL.format(year=_sw_year(), topic=topic)


_YEAR = None


def _sw_year():
    """SOLIDWORKS marketing year from the major revision (28 -> 2020)."""
    global _YEAR
    if _YEAR is None:
        try:
            from swpy import _host
            _YEAR = 1992 + int(str(_host._sw.RevisionNumber()).split(".")[0])
        except Exception:
            _YEAR = 2020
    return _YEAR


def check(g, source):
    """Syntax check: None or {"line": 1-based, "col": 0-based, "end_col", "msg"}."""
    try:
        compile(source, "<swpy>", "exec", dont_inherit=True)
    except SyntaxError as e:
        line = e.lineno or 1
        col = max(0, (e.offset or 1) - 1)
        end = (e.end_offset - 1) if getattr(e, "end_offset", None) and e.end_lineno == e.lineno else col + 1
        return {"line": line, "col": col, "end_col": max(end, col + 1), "msg": f"{type(e).__name__}: {e.msg}"}
    except (ValueError, OverflowError) as e:
        return {"line": 1, "col": 0, "end_col": 1, "msg": str(e)}
    return None
