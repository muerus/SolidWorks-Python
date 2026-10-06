"""In-process script host, called from the C# add-in (SwPy.Scripting.PythonHost).

Everything that can be done in Python is done here, so the C# layer stays thin:
sessions, stdout capture, REPL-style result of a trailing expression, tracebacks.
"""
import ast
import contextlib
import io
import json
import traceback

from swpy._interop import sldworks, swconst

_sw = None          # ISldWorks
_addin = None       # SwPy.SwPyAddIn
_sessions = {}

FILENAME = "<swpy>"


def attach(raw_sw, addin):
    """Receive the live SOLIDWORKS application from the add-in."""
    global _sw, _addin
    _sw = sldworks.ISldWorks(raw_sw)
    _addin = addin


def active_doc():
    raw = _sw.ActiveDoc if _sw is not None else None
    return sldworks.IModelDoc2(raw) if raw is not None else None


def _new_globals(name):
    return {
        "__name__": "__main__",
        "__swpy_session__": name,
        "sw": _sw,
        "sldworks": sldworks,
        "swconst": swconst,
    }


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
    g["doc"] = active_doc()

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
