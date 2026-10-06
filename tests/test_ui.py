"""UI integration: script buttons (toolbar/menu/CommandManager tab), startup scripts, swpy.ui helpers."""
import json
import subprocess
import threading
import time

import pytest

SCRIPTS = {
    "say_hello.py": '# Say hello from a button\nprint("hello from", __file__)\nhello_value = 42\n',
    "uses_import.py": "import helper_mod\nprint(helper_mod.VALUE)\n",
    "helper_mod.py": 'VALUE = "imported ok"\n',
    "_private.py": "raise RuntimeError('underscore scripts get no button')\n",
    "broken.py": '"""Fails on purpose"""\nx = 1\nraise ValueError("button error")\n',
    "startup/boot.py": "startup_ran = True\n",
}


@pytest.fixture(scope="module")
def folder(swpy, tmp_path_factory):
    root = tmp_path_factory.mktemp("scripts")
    for name, text in SCRIPTS.items():
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(text.encode())
    swpy.obj.Pane("scripts_folder", str(root))
    yield root
    swpy.obj.Pane("scripts_folder", "")          # back to the user's folder
    swpy.obj.Pane("forget", str(root))


@pytest.fixture
def pane(swpy, folder):
    p = swpy.obj.Pane
    p("clear", "")
    yield p


def toolbar(pane):
    return json.loads(pane("toolbar", ""))


# ---------------------------------------------------------------- script buttons

def test_toolbar_lists_scripts(pane, folder):
    t = toolbar(pane)
    assert t["folder"] == str(folder)
    assert t["titles"] == ["Refresh scripts", "Script folder", "broken", "helper mod", "say hello", "uses import"]
    assert t["tabs"] is True


def test_button_runs_script_in_editor_session(swpy, pane, folder):
    titles = toolbar(pane)["titles"]
    swpy.obj.SwPyRunScript(str(titles.index("say hello") - 2))
    out = pane("output", "")
    assert "# run say_hello.py" in out and f"hello from {folder / 'say_hello.py'}" in out
    assert "42" in pane("repl", "hello_value")          # same session as the editor


def test_script_folder_is_importable(swpy, pane):
    titles = toolbar(pane)["titles"]
    swpy.obj.SwPyRunScript(str(titles.index("uses import") - 2))
    assert "imported ok" in pane("output", "")


def test_failing_script_opens_with_error_marked(swpy, pane, folder):
    titles = toolbar(pane)["titles"]
    swpy.obj.SwPyRunScript(str(titles.index("broken") - 2))
    out = pane("output", "")
    assert "ValueError: button error" in out and str(folder / "broken.py") in out
    assert json.loads(pane("tabs", ""))["titles"][-1] == "broken.py"
    assert pane("feature", "error_line") == "3"
    pane("forget", str(folder))


def test_out_of_range_button_is_ignored(swpy, pane):
    swpy.obj.SwPyRunScript("99")
    swpy.obj.SwPyRunScript("not a number")
    assert pane("output", "") == ""


def test_refresh_picks_up_new_scripts(swpy, pane, folder):
    (folder / "zz_new.py").write_bytes(b"print('new one')\n")
    try:
        swpy.obj.SwPyRefreshScripts()
        assert toolbar(pane)["titles"][-1] == "zz new"
    finally:
        (folder / "zz_new.py").unlink()
        swpy.obj.SwPyRefreshScripts()


def test_scripts_menu_in_pane(pane):
    items = pane("scripts_menu", "").split("|")
    assert items[:4] == ["broken", "helper mod", "say hello", "uses import"]
    assert items[-2:] == ["Open script folder", "Refresh SwPy toolbar"]


def test_startup_scripts(pane):
    pane("startup", "")
    assert "True" in pane("repl", "startup_ran")


# ---------------------------------------------------------------- swpy.ui

def test_progress_iterates_and_steps(swpy):
    assert swpy.ok("total = 0\nfor i in ui.progress(range(20), 'Counting'):\n    total += i\ntotal", "ui")["value"] == 190
    assert swpy.ok("with ui.progress(3, 'Steps') as p:\n    p.step(); p.step(title='two'); p.step()\np.position", "ui")["value"] == 3


def test_progress_cancel_raises(swpy):
    res = swpy.run(
        "class FakeBar:\n"
        "    def UpdateProgress(self, pos):\n"
        "        return swconst.swUpdateProgressError_e.swUpdateProgressError_UserCancel\n"
        "    def UpdateTitle(self, t): pass\n"
        "    def End(self): pass\n"
        "p = ui.progress(5, 'Cancel me')\np._bar = FakeBar()\np.step()", "ui")
    assert not res["ok"] and "Cancelled: Cancel me: cancelled by the user" in res["error"]


def test_status_bar(swpy):
    assert swpy.ok("ui.status('SwPy test status')", "ui")["ok"]


def _sw_pid():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq SLDWORKS.exe"],
                         capture_output=True, text=True).stdout
    return {int(line.split(",")[1].strip('"')) for line in out.splitlines() if "SLDWORKS" in line}


def _press(button_text, timeout=20):
    """Background: find a modal dialog of SOLIDWORKS showing a button with this text and click it."""
    import win32con
    import win32gui
    import win32process

    pids = _sw_pid()
    result = {"clicked": False}

    def find():
        t0 = time.time()
        while time.time() - t0 < timeout:
            dialogs = []
            win32gui.EnumWindows(lambda h, _: dialogs.append(h) if win32gui.IsWindowVisible(h)
                                 and win32process.GetWindowThreadProcessId(h)[1] in pids else None, None)
            for dialog in dialogs:
                buttons = []
                win32gui.EnumChildWindows(dialog, lambda c, _: buttons.append(c)
                                          if win32gui.GetWindowText(c).replace("&", "") == button_text else None, None)
                if buttons and dialog != harness_main_window():
                    win32gui.PostMessage(buttons[0], win32con.BM_CLICK, 0, 0)
                    result["clicked"] = True
                    return
            time.sleep(0.2)

    thread = threading.Thread(target=find, daemon=True)
    thread.start()
    return thread, result


def harness_main_window():
    import harness
    return harness.sw_window()


@pytest.mark.parametrize("code,button,expected", [
    ("ui.message('SwPy test message')", "OK", "ok"),
    ("ui.ask('SwPy test question?')", "Yes", True),
    ("ui.ask('SwPy test question?')", "No", False),
    ("ui.prompt('Name?', 'default text')", "OK", "default text"),
    ("ui.prompt('Name?', 'x')", "Cancel", None),
    ("ui.open_file('Python (*.py)|*.py', 'SwPy test open')", "Cancel", None),
])
def test_dialogs(swpy, code, button, expected):
    thread, clicked = _press(button)
    res = swpy.run(code, "ui")
    thread.join(5)
    assert clicked["clicked"], f"no dialog with a {button!r} button appeared"
    assert res["ok"], res["error"]
    assert res.get("value") == expected
