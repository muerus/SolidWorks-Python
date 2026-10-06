"""Editor services (swpy._editor via swpy._host.call): completion, signatures, hover, syntax check."""
import json

import pytest

from test_host import PART

SESSION = "editor-services"


@pytest.fixture(scope="module")
def call(swpy):
    swpy.ok("from swpy import _host", SESSION)
    swpy.ok(PART, SESSION)
    swpy.ok("model = Model(part)", SESSION)

    def call(method, **kwargs):
        kwargs["session"] = SESSION
        reply = json.loads(swpy.ok(f"_host.call({method!r}, {json.dumps(kwargs)!r})", SESSION)["value"])
        assert reply["ok"], reply.get("error")
        return reply["value"]

    yield call
    swpy.ok("sw.CloseDoc(part.GetTitle())", SESSION)


def names(call, before, source=""):
    return [n for n, _ in call("complete", before=before, source=source)["items"]]


def test_complete_com_members(call):
    assert "Extension" in names(call, "part.Ext")
    assert {"SelectByID2", "SelectAll"} <= set(names(call, "part.Extension.Sel"))


def test_complete_follows_api_return_types(call):
    # FeatureExtrusion2 returns Feature: completed from type info, nothing is executed
    assert "Name" in names(call, "part.FeatureManager.FeatureExtrusion2(1, 2).Na")


def test_complete_python_layer_chain(call):
    assert "GetArea" in names(call, "model.faces.planar().largest().GetAr")
    assert {"planar", "normal", "radius"} <= set(names(call, "model.faces."))
    assert "Select2" in names(call, "model.planes.top.Sel")


def test_complete_kinds(call):
    items = dict(map(tuple, call("complete", before="model.")["items"]))
    assert items["faces"] == "property" and items["batch"] == "method"


def test_complete_infers_buffer_assignments(call):
    src = "x = sldworks.IPartDoc(doc)\nx.GetBod"
    assert "GetBodies2" in names(call, src, src)
    src = "for f in model.faces:\n    f.GetSu"
    assert "GetSurface" in names(call, src, src)


def test_complete_globals_and_constants(call):
    assert {"model", "Model"} <= set(names(call, "mod"))
    assert "swDocPART" in names(call, "swconst.swDocumentTypes_e.swDocP")


def test_complete_parameterized_properties_as_accessors(call):
    found = names(call, "part.Extension.get_Cust")
    assert "get_CustomPropertyManager" in found
    assert "CustomPropertyManager" not in names(call, "part.Extension.Cust")
    assert "Get6" in names(call, "part.Extension.get_CustomPropertyManager('').Get")


def test_complete_nothing_for_unknown(call):
    assert names(call, "nope_unknown.") == []


def test_signature_net_method_and_arg_index(call):
    v = call("signature", before='part.Extension.SelectByID2("Top", "PLANE", ')
    assert v["arg"] == 2
    s = v["signatures"][0]
    assert s["label"].startswith("SelectByID2(Name: str, Type: str, X: float")
    a, b = s["params"][2]
    assert s["label"][a:b] == "X: float"


def test_signature_python(call):
    s = call("signature", before="model.faces.normal(")["signatures"][0]
    assert s["label"] == "normal(direction, tol=1e-06) -> Faces" and "outward normal" in s["doc"]
    assert call("signature", before="Model(")["signatures"][0]["label"] == "Model(doc)"
    s = call("signature", before="sldworks.IFace2(")["signatures"][0]
    assert s["label"] == "IFace2(obj) -> IFace2"


def test_signature_none_outside_call(call):
    assert call("signature", before="x = 1") is None


def test_hover(call):
    v = call("hover", before="part.Extension")
    assert v["text"].startswith("IModelDoc2.Extension: ModelDocExtension")
    assert v["help"].endswith("SolidWorks.Interop.sldworks.IModelDoc2~Extension.html")
    text = call("hover", before="model.faces")["text"]
    assert text.startswith("faces: Faces  (property)") and "All faces of all solid bodies" in text
    assert call("hover", before="mm")["text"] == "mm: float = 0.001"


def test_check(call):
    assert call("check", source="x = 1\n") is None
    d = call("check", source="x = 1\ny = (2,\n")
    assert d["line"] == 2 and "never closed" in d["msg"]


def test_unknown_service_reports_error(swpy, call):
    reply = json.loads(swpy.ok("_host.call('nope', '{}')", SESSION)["value"])
    assert reply["ok"] is False and "unknown editor service" in reply["error"]
