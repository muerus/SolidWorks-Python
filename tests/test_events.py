"""swpy.events: subscribe Python handlers to SOLIDWORKS events, safely."""
import pytest

from test_host import PART

SESSION = "events"


@pytest.fixture(scope="module")
def r(swpy):
    swpy.ok(f"import swpy._host as _h\n_h.reset({SESSION!r})\n_h.reset('events-reset')", "events-admin")
    swpy.ok(PART + "\nfrom swpy import events\nlog = []", SESSION)

    def run(code):
        res = swpy.run(code, SESSION)
        assert res["ok"], res["error"]
        return res

    yield run
    swpy.ok("for h in events.handlers('events'): h.remove()\nsw.CloseDoc(part.GetTitle())", SESSION)


@pytest.fixture(autouse=True)
def clean(r):
    r("log.clear()")
    yield
    r("for h in events.handlers('events'): h.remove()")


def test_available_lists_aliases_and_api_names(r):
    names = r("events.available(part)")["value"]
    assert {"rebuild", "save", "selection", "close"} <= set(names)
    assert {"RegenPostNotify2", "FileSavePostNotify"} <= set(names)
    assert "active_doc" in r("events.available(sw)")["value"]


def test_rebuild_alias_without_arguments(r):
    r("h = on(part, 'rebuild', lambda: log.append('rebuilt'))")
    r("part.ForceRebuild3(False)")
    assert r("log")["value"] == ["rebuilt"]
    assert r("(h.active, h.calls, h.api_event)")["result"] == "(True, 1, 'RegenPostNotify2')"


def test_decorator_and_event_arguments(r):
    r("@on(part, 'RegenPostNotify2')\ndef rebuilt(stop_feature):\n    log.append(stop_feature is None)")
    assert r("callable(rebuilt)")["value"] is True          # decorator returns the function
    r("part.ForceRebuild3(False)")
    assert r("log")["value"] == [True]


def test_off_by_function_and_handle(r):
    r("def f():\n    log.append(1)\nh1 = on(part, 'rebuild', f)\nh2 = on(part, 'before_rebuild', f)")
    assert r("off(f)")["value"] == 2
    r("part.ForceRebuild3(False)")
    assert r("log")["value"] == []
    assert r("(h1.active, h2.active, off(h1))")["result"] == "(False, False, 1)"


def test_handler_errors_are_isolated_and_switched_off(r):
    res = r("def bad():\n    raise ValueError('boom')\nhb = on(part, 'rebuild', bad)\n"
            "ok = on(part, 'rebuild', lambda: log.append('still runs'))\n"
            "for _ in range(events.MAX_ERRORS + 1):\n    part.ForceRebuild3(False)\n"
            "(hb.active, hb.errors, len(log))")
    assert res["result"] == "(False, 5, 6)"
    assert "ValueError: boom" in res["stdout"] and 'File "<swpy>", line 2, in bad' in res["stdout"]
    assert "events.py" not in res["stdout"]                 # only the user's frames
    assert "switched off after 5 consecutive errors" in res["stdout"]


def test_print_inside_handler_reaches_output(r):
    res = r("on(part, 'rebuild', lambda: print('hello from handler'))\npart.ForceRebuild3(False)")
    assert "hello from handler" in res["stdout"]


def test_handler_return_value_passed_through(r):
    r("h = on(part, 'rebuild', lambda: 7)")
    assert r("h._invoke()")["value"] == 7
    r("h2 = on(part, 'rebuild', lambda: 'not an int')")
    assert r("h2._invoke()")["value"] == 0


def test_unknown_event_and_missing_source(r):
    res = r("try:\n    on(part, 'no_such_event', print)\n    msg = 'no error'\nexcept ValueError as e:\n    msg = str(e)\nmsg")
    assert "has no event 'no_such_event'" in res["value"]
    res = r("try:\n    on(None, 'rebuild', print)\n    msg = 'no error'\nexcept ValueError as e:\n    msg = str(e)\nmsg")
    assert "source is None" in res["value"]


def test_application_event(r):
    r("h = on(sw, 'new', lambda new_doc, doc_type, template: log.append(doc_type))\n"
      "tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)\n"
      "d2 = sw.NewDocument(tpl, 0, 0, 0)\nsw.CloseDoc(d2.GetTitle())")
    assert r("log")["value"] == [swpy_part_type()]


def swpy_part_type():
    return 1   # swconst.swDocumentTypes_e.swDocPART


def test_closing_a_document_removes_its_handlers(r):
    r("tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)\n"
      "d3 = sw.NewDocument(tpl, 0, 0, 0)\nh3 = on(d3, 'rebuild', lambda: None)\nkey = events._com.identity(d3.raw)")
    assert r("(h3.active, key in events._watchers)")["result"] == "(True, True)"
    r("sw.CloseDoc(d3.GetTitle())")
    assert r("(h3.active, key in events._watchers)")["result"] == "(False, False)"


def test_reset_removes_session_handlers(swpy, r):
    swpy.ok("h = on(doc, 'rebuild', lambda: None)", "events-reset")   # doc: the active part
    assert r("len(events.handlers('events-reset'))")["value"] == 1
    swpy.ok("import swpy._host as _h\n_h.reset('events-reset')", "events-admin")
    assert r("len(events.handlers('events-reset'))")["value"] == 0


def test_shutdown_detaches_everything(r):
    # what the add-in calls on unload; the application's own DestroyNotify also removes its handlers
    r("h = on(sw, 'active_doc', lambda: None)\nh2 = on(part, 'rebuild', lambda: None)")
    res = r("import swpy._host as _h\n(_h.shutdown(), h.active, h2.active, len(events.handlers()), len(events._watchers))")
    assert res["result"] == "(2, False, False, 0, 0)"
