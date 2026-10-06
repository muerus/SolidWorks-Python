"""Out-of-process test harness: drives SOLIDWORKS and the SwPy add-in over COM (pywin32).

Dev loop:
  * C# changes  -> restart_sw() (the CLR never unloads the add-in DLL), rebuild, start again.
  * Python changes -> SOLIDWORKS started by this harness reads swpy from the repo
    (SWPY_PACKAGE_DIR), so a new session picks them up after `reload_swpy()`.
"""
import json
import os
import subprocess
import time

import pythoncom
import win32com.client as w32

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SW_EXE = os.environ.get("SWPY_SW_EXE", r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe")
PROGID = "SwPy.AddIn"
DLL = os.path.join(ROOT, "src", "SwPy.AddIn", "bin", "Debug", "net48", "SwPy.AddIn.dll")


def _active():
    try:
        return w32.GetActiveObject("SldWorks.Application")
    except pythoncom.com_error:
        return None


def get_sw(start=True, timeout=300):
    """Attach to a running SOLIDWORKS, or start one (dev env) and wait for startup."""
    sw = _active()
    if sw is not None or not start:
        return sw
    env = dict(os.environ, SWPY_PACKAGE_DIR=os.path.join(ROOT, "python"))
    subprocess.Popen([SW_EXE], env=env)
    t0 = time.time()
    while time.time() - t0 < timeout:
        sw = _active()
        if sw is not None:
            try:
                if sw.StartupProcessCompleted:
                    return sw
            except (AttributeError, pythoncom.com_error):
                pass
        time.sleep(2)
    raise TimeoutError("SOLIDWORKS did not start")


def exit_sw(timeout=60):
    """Close SOLIDWORKS without saving (only use on sessions the harness started)."""
    sw = _active()
    if sw is None:
        return
    sw.CloseAllDocuments(True)
    sw.ExitApp()
    del sw
    t0 = time.time()
    while time.time() - t0 < timeout:
        if subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe"],
                          capture_output=True, text=True).stdout.count("SLDWORKS.exe") == 0:
            return
        time.sleep(1)
    raise TimeoutError("SOLIDWORKS did not exit")


class SwPy:
    """Client for the add-in's automation object. Loads the add-in if needed."""

    def __init__(self, sw=None):
        self.sw = sw or get_sw()
        obj = self.sw.GetAddInObject(PROGID)
        if obj is None:
            rc = self.sw.LoadAddIn(DLL)
            obj = self.sw.GetAddInObject(PROGID)
            if obj is None:
                raise RuntimeError(f"SwPy add-in failed to load (LoadAddIn={rc}); see %LOCALAPPDATA%\\SwPy\\logs")
        self.obj = w32.Dispatch(obj)

    def version(self):
        return self.obj.Version()

    def run(self, code, session="test"):
        return json.loads(self.obj.Execute(session, code))

    def ok(self, code, session="test"):
        """Run and raise on error; returns the result dict."""
        r = self.run(code, session)
        if not r["ok"]:
            raise RuntimeError(r["error"])
        return r


def sw_window():
    """Top-level SOLIDWORKS main window handle (largest visible window of SLDWORKS.exe)."""
    import win32gui
    import win32process

    pids = {int(line.split(",")[1].strip('"')) for line in subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq SLDWORKS.exe"],
        capture_output=True, text=True).stdout.splitlines() if "SLDWORKS" in line}
    found = []

    def visit(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1] in pids:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            found.append(((r - l) * (b - t), hwnd))
    win32gui.EnumWindows(visit, None)
    if not found:
        raise RuntimeError("No visible SOLIDWORKS window")
    return max(found)[1]


def screenshot(path, sw=None):
    """Capture the SOLIDWORKS main window (even if covered) to a PNG via PrintWindow."""
    import ctypes
    import win32gui
    import win32ui
    from PIL import Image

    hwnd = sw_window()
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    hdc = win32gui.GetWindowDC(hwnd)
    src = win32ui.CreateDCFromHandle(hdc)
    mem = src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(src, w, h)
    mem.SelectObject(bmp)
    ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)   # PW_RENDERFULLCONTENT
    info = bmp.GetInfo()
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), bmp.GetBitmapBits(True), "raw", "BGRX", 0, 1)
    win32gui.DeleteObject(bmp.GetHandle())
    mem.DeleteDC()
    src.DeleteDC()
    win32gui.ReleaseDC(hwnd, hdc)
    img.save(path)
    return path
