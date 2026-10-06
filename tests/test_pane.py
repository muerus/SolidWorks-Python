"""L4: task pane editor + REPL (driven through the add-in's Pane() automation hook)."""
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
