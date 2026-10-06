"""L4: task pane editor + REPL (driven through the add-in's Pane() automation hook)."""
import pytest


@pytest.fixture
def pane(swpy):
    p = swpy.obj.Pane
    p("reset", "")
    p("clear", "")
    saved = p("get_text", "")
    yield p
    p("set_text", saved)   # leave the user's scratch script as it was


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
