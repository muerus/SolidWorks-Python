"""In-process script host, called from the C# add-in (SwPy.Scripting.PythonHost).

Everything that can be done in Python is done here, so the C# layer stays thin:
sessions, stdout capture, REPL-style result of a trailing expression, tracebacks.

Reload-safe: `importlib.reload` keeps the attached application and live sessions.
"""
import ast
import contextlib
import io
import json
import traceback

from swpy._interop import sldworks, swconst
from swpy.com import Com

_sw = globals().get("_sw")              # Com(ISldWorks), set by attach()
_addin = globals().get("_addin")        # SwPy.SwPyAddIn
_sessions = globals().get("_sessions", {})
if _sw is not None and not isinstance(_sw, Com):   # upgraded from an older host version
    _sw = Com(_sw, prefer="ISldWorks")

FILENAME = "<swpy>"


def attach(raw_sw, addin):
    """Receive the live SOLIDWORKS application from the add-in."""
    global _sw, _addin
    _sw = Com(raw_sw, prefer="ISldWorks")
    _addin = addin


def active_doc():
    return _sw.ActiveDoc if _sw is not None else None   # auto-typed by the proxy


def _new_globals(name):
    from swpy import model as _model, units as _units
    g = {
        "__name__": "__main__",
        "__swpy_session__": name,
        "sw": _sw,
        "sldworks": sldworks,
        "swconst": swconst,
        "Model": _model.Model, "Vec": _model.Vec, "X": _model.X, "Y": _model.Y, "Z": _model.Z,
    }
    g.update({k: getattr(_units, k) for k in ("mm", "cm", "m", "inch", "ft", "deg", "rad", "kg", "g", "to")})
    return g


def _split_trailing_expression(tree):
    """Return (module, expression) where expression is the last statement if it is one."""
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = tree.body.pop()
        return tree, ast.Expression(last.value)
    return tree, None


def run(session, code):
    """Execute code in a persistent session. Returns a JSON string."""
    g = _sessions.get(session)
    if g is None:
        g = _sessions[session] = _new_globals(session)
    g["sw"] = _sw
    try:
        g["doc"] = active_doc()
        if g["doc"] is not None:
            from swpy.model import Model
            g["model"] = Model(g["doc"])
        else:
            g["model"] = None
    except Exception:   # never let a doc lookup block running code (e.g. the reload that fixes it)
        g["doc"] = g["model"] = None

    out = io.StringIO()
    res = {"ok": True, "stdout": "", "result": None, "error": None}
    try:
        tree, last = _split_trailing_expression(ast.parse(code, FILENAME, "exec"))
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(compile(tree, FILENAME, "exec"), g)
            if last is not None:
                value = eval(compile(last, FILENAME, "eval"), g)
                if value is not None:
                    g["_"] = value
                    res["result"] = repr(value)
    except BaseException as e:   # SystemExit/KeyboardInterrupt must not escape into SOLIDWORKS
        res["ok"] = False
        res["error"] = _format_user_error(e)
    res["stdout"] = out.getvalue()
    return json.dumps(res)


def _format_user_error(e):
    """Traceback without this module's own frames - users only care about their code."""
    tb = e.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename == __file__:
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(e), e, tb))


def reset(session):
    _sessions.pop(session, None)


def reload_package():
    """Dev: reload swpy from disk without restarting SOLIDWORKS (keeps sessions)."""
    import importlib
    import sys
    import swpy
    for name in sorted(m for m in sys.modules if m == "swpy" or m.startswith("swpy.")):
        if name not in ("swpy._host", "swpy.swconst"):
            importlib.reload(sys.modules[name])
    importlib.reload(sys.modules["swpy._host"])
    for g in _sessions.values():
        g["sldworks"] = sys.modules["swpy._interop"].sldworks
    return swpy.__version__
