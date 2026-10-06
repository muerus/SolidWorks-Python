"""L2: auto-typed Com proxies over SOLIDWORKS objects."""
import pytest

from test_host import PART


@pytest.fixture(scope="module")
def part(swpy):
    s = "com-tests"
    swpy.ok(PART, s)
    swpy.ok("faces = part.GetBodies2(0, True)[0].GetFaces()", s)
    yield s
    swpy.ok("sw.CloseDoc(part.GetTitle())", s)


def res(swpy, s, expr):
    return swpy.ok(expr, s)["result"]


def test_new_document_is_typed(swpy, part):
    assert res(swpy, part, "part.interfaces") == "('IModelDoc2', 'IPartDoc')"


def test_object_returning_member_is_auto_typed(swpy, part):
    # FirstFeature is declared as `object` in the interop
    assert res(swpy, part, "part.FirstFeature().interfaces[0]") == "'IFeature'"
    assert res(swpy, part, "type(part.FirstFeature().Name).__name__") == "'str'"


def test_arrays_become_lists_of_com(swpy, part):
    assert res(swpy, part, "type(faces).__name__, len(faces)") == "('list', 6)"
    assert res(swpy, part, "faces[0].interfaces") == "('IFace2', 'IEntity')"


def test_secondary_interface_members_reachable(swpy, part):
    # Select4 lives on IEntity, GetArea on IFace2 - one object reaches both
    assert res(swpy, part, "part.ClearSelection2(True); faces[0].Select4(False, None)") == "True"
    assert res(swpy, part, "abs(faces[0].GetArea()) > 0") == "True"


def test_com_identity(swpy, part):
    assert res(swpy, part, "faces[0] == part.GetBodies2(0, True)[0].GetFaces()[0]") == "True"
    assert res(swpy, part, "faces[0] == faces[1]") == "False"
    assert res(swpy, part, "len(set(faces + part.GetBodies2(0, True)[0].GetFaces()))") == "6"


def test_repr_has_label(swpy, part):
    assert res(swpy, part, "repr(part.FeatureByName('Boss-Extrude1'))") == "\"<IFeature+IEntity 'Boss-Extrude1'>\""


def test_property_set_roundtrip(swpy, part):
    swpy.ok("f = part.FeatureByName('Boss-Extrude1'); f.Name = 'Block'", part)
    assert res(swpy, part, "part.FeatureByName('Block').Name") == "'Block'"
    swpy.ok("part.FeatureByName('Block').Name = 'Boss-Extrude1'", part)


def test_cast_prefers_interface(swpy, part):
    assert res(swpy, part, "sldworks.IPartDoc(part).interfaces[0]") == "'IPartDoc'"


def test_unknown_attribute_error_names_interfaces(swpy, part):
    r = swpy.run("part.NoSuchThing", part)
    assert not r["ok"] and "IModelDoc2/IPartDoc has no attribute 'NoSuchThing'" in r["error"]


def test_com_args_are_unwrapped(swpy, part):
    # Com proxies passed back into the API: persistent reference round trip returns the same face
    swpy.ok("ref = part.Extension.GetPersistReference3(faces[2])", part)
    assert res(swpy, part, "isinstance(ref, list), len(ref) > 0") == "(True, True)"
    assert res(swpy, part, "part.Extension.GetObjectByPersistReference3(ref)[0] == faces[2]") == "True"


def test_wrap_cost(swpy, part):
    cost = float(res(swpy, part, """
import time
from swpy.com import Com
t0 = time.perf_counter()
for _ in range(200): Com(faces[0].raw)
(time.perf_counter() - t0) / 200 * 1e6"""))
    assert cost < 300, f"{cost:.0f} us per wrap"


def test_primitive_arrays_roundtrip_types(swpy, part):
    assert res(swpy, part, "type(ref).__name__, str(ref.element_type)") == "('NetList', 'System.Byte')"
    assert res(swpy, part, "box = part.GetBodies2(0, True)[0].GetBodyBox(); str(box.element_type), len(box)") \
        == "('System.Double', 6)"


def test_plain_lists_become_typed_arrays(swpy, part):
    assert res(swpy, part, """
from swpy.com import unwrap
[str(unwrap(v).GetType()) for v in ([1, 2], [1, 2.5], ['a'], [True], faces[:2], [1, 'a'])]""") == (
        "['System.Int32[]', 'System.Double[]', 'System.String[]', 'System.Boolean[]', "
        "'System.Object[]', 'System.Object[]']")
