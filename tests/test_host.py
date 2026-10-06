"""L0-L2: add-in host, embedded Python runtime, raw API surface."""
import time


def test_version(swpy):
    assert swpy.version().startswith("0.")


def test_python_version(swpy, session):
    r = swpy.ok("import sys; sys.version_info[:2]", session)
    assert r["result"] in ("(3, 11)", "(3, 12)", "(3, 13)", "(3, 14)")


def test_trailing_expression_is_result(swpy, session):
    assert swpy.ok("x = 20\nx + 1", session)["result"] == "21"


def test_statement_has_no_result(swpy, session):
    assert swpy.ok("y = 1", session)["result"] is None


def test_none_result_is_null(swpy, session):
    assert swpy.ok("None", session)["result"] is None


def test_session_state_persists(swpy, session):
    swpy.ok("counter = 41", session)
    assert swpy.ok("counter + 1", session)["result"] == "42"


def test_sessions_are_isolated(swpy, session):
    swpy.ok("secret = 1", session)
    r = swpy.run("secret", session + "-other")
    assert not r["ok"] and "NameError" in r["error"]


def test_stdout_captured(swpy, session):
    r = swpy.ok("print('hello'); print('world')", session)
    assert r["stdout"] == "hello\nworld\n"


def test_stdout_kept_on_error(swpy, session):
    r = swpy.run("print('before'); 1/0", session)
    assert not r["ok"]
    assert r["stdout"] == "before\n"


def test_error_traceback_hides_host_frames(swpy, session):
    r = swpy.run("def f():\n    raise ValueError('boom')\nf()", session)
    assert not r["ok"]
    assert "ValueError: boom" in r["error"]
    assert "_host.py" not in r["error"]
    assert 'File "<swpy>", line 3' in r["error"]


def test_syntax_error_reported(swpy, session):
    r = swpy.run("def (", session)
    assert not r["ok"] and "SyntaxError" in r["error"]


def test_system_exit_does_not_escape(swpy, session):
    r = swpy.run("raise SystemExit(3)", session)
    assert not r["ok"] and "SystemExit" in r["error"]
    assert swpy.ok("1 + 1", session)["result"] == "2"   # host still alive


def test_sw_is_full_typed_interface(swpy, session):
    assert swpy.ok("type(sw).__name__", session)["result"] == "'ISldWorks'"
    assert int(swpy.ok("len(dir(sw))", session)["result"]) > 300   # not an embedded trimmed copy


def test_swconst_values(swpy, session):
    assert swpy.ok("swconst.swDocumentTypes_e.swDocPART", session)["result"] == "1"
    assert swpy.ok("swconst.swDocumentTypes_e.name(2)", session)["result"] == "'swDocASSEMBLY'"


def test_cast_none_passes_through(swpy, session):
    assert swpy.ok("sldworks.IModelDoc2(None)", session)["result"] is None


def test_unknown_interface_is_attribute_error(swpy, session):
    r = swpy.run("sldworks.INotAThing", session)
    assert not r["ok"] and "AttributeError" in r["error"]


def test_call_overhead_is_small(swpy, session):
    swpy.ok("1", session)
    t0 = time.perf_counter()
    for _ in range(20):
        swpy.ok("1", session)
    per_call = (time.perf_counter() - t0) / 20
    assert per_call < 0.1, f"{per_call * 1000:.1f} ms per round trip"


PART = """
tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)
part = sldworks.IModelDoc2(sw.NewDocument(tpl, 0, 0, 0))
part.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
part.SketchManager.InsertSketch(True)
part.SketchManager.CreateCenterRectangle(0, 0, 0, 0.05, 0.03, 0)
part.SketchManager.InsertSketch(True)
feat = part.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, 0.02, 0, False, False, False, False,
                                             0, 0, False, False, False, False, True, True, True, 0, 0, False)
"""


def test_build_part_and_measure(swpy, session):
    swpy.ok(PART, session)
    assert swpy.ok("feat.Name", session)["result"] == "'Boss-Extrude1'"
    vol = float(swpy.ok("part.Extension.CreateMassProperty().Volume", session)["result"])
    assert abs(vol - 100e-3 * 60e-3 * 20e-3) < 1e-12
    # `doc` follows the active document on every run
    assert swpy.ok("doc.GetTitle() == part.GetTitle()", session)["result"] == "True"
    swpy.ok("sw.CloseDoc(part.GetTitle())", session)
