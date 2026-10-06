"""L3: Pythonic model API - units, dims, globals, batch, face/edge queries."""
import pytest

from test_host import PART

BOSS = """
part.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
part.SketchManager.InsertSketch(True)
part.SketchManager.CreateCircleByRadius(0, 0, 0, 0.01)
part.SketchManager.InsertSketch(True)
part.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, 0.04, 0, False, False, False, False,
                                      0, 0, False, False, False, False, True, True, True, 0, 0, False)
model = Model(part)
"""


@pytest.fixture(scope="module")
def s(swpy):
    name = "model-tests"
    swpy.ok(PART + BOSS, name)
    yield name
    swpy.ok("sw.CloseDoc(part.GetTitle())", name)


def r(swpy, s, expr):
    return swpy.ok(expr, s)["result"]


def test_units(swpy, s):
    assert r(swpy, s, "50 * mm, to(0.05, mm), round(90 * deg, 6)") == "(0.05, 50.0, 1.570796)"


def test_dims_read(swpy, s):
    assert r(swpy, s, "model.dims['D1@Boss-Extrude1']") == "0.02"
    assert r(swpy, s, "'D1@Boss-Extrude1' in model.dims, 'D9@Nope' in model.dims") == "(True, False)"


def test_dims_names(swpy, s):
    assert r(swpy, s, "'D1@Boss-Extrude1' in model.dims.names()") == "True"


def test_dims_write_rebuilds(swpy, s):
    v0 = float(r(swpy, s, "model.mass['volume']"))
    swpy.ok("model.dims['D1@Boss-Extrude1'] = 30 * mm", s)
    v1 = float(r(swpy, s, "model.mass['volume']"))
    assert v1 > v0
    swpy.ok("model.dims['D1@Boss-Extrude1'] = 20 * mm", s)
    assert abs(float(r(swpy, s, "model.mass['volume']")) - v0) < 1e-12


def test_globals_roundtrip(swpy, s):
    swpy.ok("model.globals['Width'] = 120 * mm", s)
    assert r(swpy, s, "round(model.globals['Width'], 9)") == "0.12"
    assert r(swpy, s, "'Width' in model.globals") == "True"
    swpy.ok("model.globals['Count'] = 5", s)
    assert r(swpy, s, "model.globals['Count']") == "5.0"
    swpy.ok("del model.globals['Count']", s)
    assert r(swpy, s, "'Count' in model.globals") == "False"


def test_global_drives_dimension(swpy, s):
    swpy.ok("model.globals['Thick'] = 25 * mm\n"
            "model.doc.GetEquationMgr().Add2(-1, '\"D1@Boss-Extrude1\" = \"Thick\"', True)\n"
            "model.rebuild()", s)
    assert r(swpy, s, "round(model.dims['D1@Boss-Extrude1'], 9)") == "0.025"
    swpy.ok("model.globals['Thick'] = 20 * mm", s)
    assert r(swpy, s, "round(model.dims['D1@Boss-Extrude1'], 9)") == "0.02"


def test_batch_single_rebuild(swpy, s):
    swpy.ok("""
calls = []
orig = model.rebuild
model.rebuild = lambda force=False: (calls.append(1), orig(force))[1]
with model.batch():
    model.dims['D1@Boss-Extrude1'] = 22 * mm
    model.dims['D1@Boss-Extrude1'] = 24 * mm
    model.globals['Thick'] = 24 * mm
model.rebuild = orig
""", s)
    assert r(swpy, s, "len(calls), round(model.dims['D1@Boss-Extrude1'], 9)") == "(1, 0.024)"
    swpy.ok("model.globals['Thick'] = 20 * mm", s)


def test_faces_planar_and_cylindrical(swpy, s):
    assert r(swpy, s, "len(model.faces.cylindrical())") == "1"
    assert r(swpy, s, "len(model.faces.radius(10 * mm)), len(model.faces.radius(11 * mm))") == "(1, 0)"
    assert r(swpy, s, "len(model.faces.planar()) >= 6") == "True"


def test_faces_normal(swpy, s):
    # block spans z 0..20 mm; the +Z face is the front face
    assert r(swpy, s, "len(model.faces.normal(Z))") == "1"
    assert r(swpy, s, "round(model.faces.normal(-Z)[0].Normal[2], 6)") == "-1.0"


def test_largest_face_and_select(swpy, s):
    assert r(swpy, s, "model.faces.planar().largest() in model.faces.normal(Z) + model.faces.normal(-Z)") == "True"
    assert r(swpy, s, "model.faces.normal(Z).select()") == "1"
    assert r(swpy, s, "model.doc.SelectionManager.GetSelectedObjectCount2(-1)") == "1"


def test_edges(swpy, s):
    assert r(swpy, s, "len(model.edges.parallel(Z))") == "4"
    assert r(swpy, s, "len(model.edges.radius(10 * mm)) >= 1") == "True"
    assert r(swpy, s, "round(model.edges.parallel(Z).largest() and model.edges._size(model.edges.parallel(Z)[0]), 6)") == "0.02"


def test_face_edges(swpy, s):
    assert r(swpy, s, "len(model.faces.normal(Z).edges)") == "4"


def test_vec(swpy, s):
    assert r(swpy, s, "-Z, round(Vec(1, 1, 0).angle(X) / deg, 6)") == "(Vec(-0, -0, -1), 45.0)"
