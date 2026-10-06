"""Out-of-process client: drive SwPy inside a running SOLIDWORKS from any Python (Jupyter, scripts).

    import swpy.client as swc
    sw = swc.connect()                      # attaches, loads the add-in if needed
    sw.eval("model.mass['volume']")         # -> 1.2e-4  (JSON-able results come back as values)
    sw.exec("model.dims['D1@Boss-Extrude1'] = 30*mm")
    sw.eval("doc")                          # non-JSON results -> their repr string

Needs only pywin32. Code runs in-process on SOLIDWORKS' main thread (~3 ms per round trip), in a
named session whose variables persist between calls. Other COM clients (Excel VBA, C#/Grasshopper)
can do the same: GetObject -> SldWorks.Application -> GetAddInObject("SwPy.AddIn").Execute(session, code).
"""
import json
import time
import winreg

PROGID = "SwPy.AddIn"
CLSID = "{10C1BD59-4D33-4878-BDDA-DE5D879D6213}"


class SwPyError(RuntimeError):
    """A script raised inside SOLIDWORKS; the message is the remote traceback."""


def addin_dll():
    """Path of the registered add-in DLL (per-user or per-machine COM registration)."""
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, rf"Software\Classes\CLSID\{CLSID}\InprocServer32") as k:
                code_base = winreg.QueryValueEx(k, "CodeBase")[0]
                return code_base.replace("file:///", "").replace("/", "\\")
        except OSError:
            continue
    raise RuntimeError("SwPy add-in is not registered (run tools\\install.ps1)")


def _solidworks(start, timeout):
    import pythoncom
    import win32com.client as w32
    try:
        return w32.GetActiveObject("SldWorks.Application")
    except pythoncom.com_error:
        if not start:
            raise RuntimeError("SOLIDWORKS is not running") from None
    sw = w32.Dispatch("SldWorks.Application")
    sw.Visible = True
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if sw.StartupProcessCompleted:
                return sw
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("SOLIDWORKS did not finish starting")


class Client:
    def __init__(self, sw, session="client"):
        import win32com.client as w32
        self.sw = sw
        self.session = session
        obj = sw.GetAddInObject(PROGID)
        if obj is None:
            sw.LoadAddIn(addin_dll())
            obj = sw.GetAddInObject(PROGID)
            if obj is None:
                raise RuntimeError("SwPy add-in failed to load; see %LOCALAPPDATA%\\SwPy\\logs\\swpy.log")
        self._addin = w32.Dispatch(obj)

    def version(self):
        return self._addin.Version()

    def run(self, code, session=None):
        """Raw result dict: ok, stdout, result (repr), value (if JSON-able), error."""
        return json.loads(self._addin.Execute(session or self.session, code))

    def exec(self, code, session=None):
        """Run statements; returns captured stdout. Raises SwPyError on failure."""
        r = self.run(code, session)
        if not r["ok"]:
            raise SwPyError(r["error"])
        return r["stdout"]

    def eval(self, expr, session=None):
        """Evaluate; JSON-able results come back as Python values, others as their repr."""
        r = self.run(expr, session)
        if not r["ok"]:
            raise SwPyError(r["error"])
        return r["value"] if "value" in r else r["result"]

    def reset(self, session=None):
        self.run(f"import swpy._host as _h; _h.reset({(session or self.session)!r})", "_admin")

    __call__ = eval


def connect(session="client", start=False, timeout=300):
    """Connect to the running SOLIDWORKS (start=True launches it) and load SwPy if needed."""
    return Client(_solidworks(start, timeout), session)
