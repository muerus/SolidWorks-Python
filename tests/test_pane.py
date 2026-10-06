"""L4: task pane editor + REPL (driven through the add-in's Pane() automation hook)."""
import json
import os

import pytest


SCRATCH = os.path.join(os.environ["LOCALAPPDATA"], "SwPy", "scratch.py")


@pytest.fixture
def pane(swpy):
    """Editor pane driver; restores the user's editor text and scratch file afterwards."""
    p = swpy.obj.Pane
    p("reset", "")
    p("clear", "")
    saved_text = p("get_text", "")
    saved_file = open(SCRATCH, encoding="utf-8").read() if os.path.exists(SCRATCH) else None
    yield p
    p("set_text", saved_text)
    if saved_file is None:
        if os.path.exists(SCRATCH):
            os.remove(SCRATCH)
    else:
        with open(SCRATCH, "w", encoding="utf-8") as f:
            f.write(saved_file)


def test_pane_visible(pane):
    assert '"Visible":true' in pane("size", "")


def test_run_whole_script(pane):
    pane("set_text", "a = 6\nprint('hi from editor')\na * 7")
    out = pane("run", "")
    assert "hi from editor" in out
    assert "42" in out
    assert pane("status", "").startswith("Done in")


def test_repl_shares_editor_session(pane):
    pane("set_text", "shared = 'from script'")
    pane("run", "")
    out = pane("repl", "shared.upper()")
    assert ">>> shared.upper()" in out
    assert "'FROM SCRIPT'" in out


def test_run_selection_only(pane):
    pane("set_text", "x = 1\nx = 2\n")
    pane("select", "0,5")          # "x = 1"
    pane("run", "")
    assert "1" in pane("repl", "x")


def test_error_shown_and_status(pane):
    out = pane("repl", "undefined_name")
    assert "NameError" in out
    assert pane("status", "").startswith("Error in")


def test_reset_clears_variables(pane):
    pane("repl", "keep = 5")
    pane("reset", "")
    assert "NameError" in pane("repl", "keep")


def test_doc_and_sw_available(pane):
    out = pane("repl", "sw.RevisionNumber()")
    assert "28." in out or "29." in out or "3" in out


def test_scintilla_editor_loaded(pane):
    assert pane("editor", "") == "ScintillaEditor"


def test_streamed_output_appears_once(pane):
    pane("set_text", "for i in range(3):\n    print('line', i)\n")
    out = pane("run", "")
    assert out.count("line 0") == 1 and out.count("line 2") == 1


# ---------------------------------------------------------------- modern editor features

@pytest.fixture
def ed(pane):
    """Pane with Python started and a clean single active tab; extra tabs closed afterwards."""
    pane("repl", "1")
    first = pane("tabs", "")
    yield pane

    while len(json.loads(pane("tabs", ""))["titles"]) > len(json.loads(first)["titles"]):
        pane("close_tab", "force")


def type_at_end(pane, text):
    pane("set_text", text)
    pane("feature", "caret_end")


def test_completion_through_pane(ed):
    type_at_end(ed, "sw.RevisionNum")
    assert "RevisionNumber" in ed("feature", "complete")
    ed("feature", "cancel")


def test_signature_through_pane(ed):
    type_at_end(ed, "sw.SetUserPreferenceToggle(10, ")
    out = ed("feature", "signature")
    assert "SetUserPreferenceToggle(UserPreferenceValue: int, OnFlag: bool)" in out and "arg=1" in out
    ed("feature", "cancel")


def test_hover_through_pane(ed):
    type_at_end(ed, "sw.ActiveDoc")
    assert ed("feature", "hover").startswith("ISldWorks.ActiveDoc: object  (property)")


def test_syntax_check(ed):
    ed("set_text", "x = 1\ny = (\n")
    assert ed("feature", "check").startswith("2:")
    ed("set_text", "x = 1\n")
    assert ed("feature", "check") == "ok"


def test_runtime_error_marks_line(ed):
    ed("set_text", "a = 1\nb = undefined_thing\n")
    assert "NameError" in ed("run", "")
    assert ed("feature", "error_line") == "2"
    ed("set_text", "a = 2\n")                       # editing clears the marker
    assert ed("feature", "error_line") == ""


def test_runtime_error_line_offset_for_selection(ed):
    ed("set_text", "a = 1\nb = 2\nc = missing_name\n")
    ed("select", "12,16")                           # line 3 only: "c = missing_name"
    ed("run", "")
    assert ed("feature", "error_line") == "3"


def test_toggle_comment(ed):
    ed("set_text", "a = 1\nif a:\n    b = 2\n")
    ed("select", "0,22")
    assert ed("feature", "toggle_comment") == "# a = 1\n# if a:\n#     b = 2\n"
    ed("select", "0,28")
    assert ed("feature", "toggle_comment") == "a = 1\nif a:\n    b = 2\n"


def test_find_and_replace_all(ed):
    ed("set_text", "foo = 1\nbar = foo + foo\n")
    assert ed("find", "foo") == "3:True"
    assert ed("replace_all", "foo|baz") == "3"
    assert ed("get_text", "") == "baz = 1\nbar = baz + baz\n"


def test_goto_and_caret(ed):
    ed("set_text", "a\nb\nc\nd\n")
    assert ed("goto", "3") == "3"
    assert ed("caret", "") == "3,1"


def test_tabs_new_save_close(ed, tmp_path):

    before = json.loads(ed("tabs", ""))
    ed("new_tab", "")
    ed("set_text", "print('tab two')")
    tabs = json.loads(ed("tabs", ""))
    assert len(tabs["titles"]) == len(before["titles"]) + 1 and tabs["titles"][-1].startswith("untitled")
    target = str(tmp_path / "saved_script.py")
    assert ed("save_as", target) == "True"
    assert open(target, encoding="utf-8").read() == "print('tab two')"
    assert json.loads(ed("tabs", ""))["titles"][-1] == "saved_script.py"
    ed("set_text", "print('changed')")
    assert ed("modified", "") == "True"
    assert json.loads(ed("tabs", ""))["titles"][-1] == "saved_script.py ●"
    ed("close_tab", "force")
    assert len(json.loads(ed("tabs", ""))["titles"]) == len(before["titles"])


def test_open_existing_file_once(ed, tmp_path):

    p = tmp_path / "opened.py"
    p.write_bytes(b"x = 41\n")
    ed("open", str(p))
    ed("open", str(p))                              # second open focuses the same tab
    titles = json.loads(ed("tabs", ""))["titles"]
    assert titles.count("opened.py") == 1
    assert ed("get_text", "") == "x = 41\n"


def test_theme_toggle(ed):
    original = ed("theme", "")
    try:
        assert ed("theme", "dark") == "dark"
        assert ed("theme", "light") == "light"
    finally:
        ed("theme", original)


def test_repl_tab_completion(ed):
    names, text = ed("repl_complete", "swconst.swDocumentTypes_e.swDocPA").split("|")
    assert names == "swDocPART" and text == "swconst.swDocumentTypes_e.swDocPART"


def error_dialogs():
    """Visible 'Error' message boxes owned by SOLIDWORKS (unhandled UI exceptions in the add-in)."""
    import subprocess
    import win32gui
    import win32process
    pids = {int(line.split(",")[1].strip('"')) for line in subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq SLDWORKS.exe"],
        capture_output=True, text=True).stdout.splitlines() if "SLDWORKS" in line}
    found = []
    win32gui.EnumWindows(lambda h, _: found.append(h) if win32gui.IsWindowVisible(h)
                         and win32process.GetWindowThreadProcessId(h)[1] in pids
                         and win32gui.GetWindowText(h) == "Error" else None, None)
    return found


def test_closing_tab_right_after_edit_is_safe(ed):
    import time
    ed("new_tab", "")
    ed("set_text", "x = (")          # starts the delayed syntax check
    ed("close_tab", "force")
    time.sleep(1.2)                  # past the check delay
    ed("status", "")                 # pump the UI thread
    assert error_dialogs() == []
