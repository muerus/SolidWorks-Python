"""Building models: sketches, features, save/export, assemblies (components, mates, BOM), drawings."""
import math
import os

import pytest

SESSION = "build"

NEW_PART = """
tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)
{name} = Model(sw.NewDocument(tpl, 0, 0, 0))
"""


@pytest.fixture(scope="module")
def r(swpy, tmp_path_factory):
    out = tmp_path_factory.mktemp("build")
    swpy.ok(f"import swpy._host as _h\n_h.reset({SESSION!r})", "build-admin")
    swpy.ok(f"import os, math\nout = {str(out)!r}\nopened = []", SESSION)

    def run(code):
        res = swpy.run(code, SESSION)
        assert res["ok"], res["error"]
        return res.get("value", res["result"])

    yield run
    swpy.run("for d in reversed(opened):\n    sw.CloseDoc(d.title)", SESSION)


def volume_mm3(r, name):
    return r(f"round(to({name}.mass['volume'], mm**3))")


def test_sketch_and_extrude(r):
    r(NEW_PART.format(name="plate") + "opened.append(plate)\n"
      "with plate.sketch(plate.planes.front) as s:\n    s.rect((0, 0), 100 * mm, 60 * mm)\n"
      "block = plate.extrude(s, 20 * mm)")
    assert r("(s.feature.GetTypeName2(), len(s.segments) >= 4, block.GetTypeName2())") == ["ProfileFeature", True, "Extrusion"]
    assert volume_mm3(r, "plate") == 120000


def test_cut_through_all_on_a_face(r):
    r("with plate.sketch(plate.faces.normal(Z).largest()) as h:\n    h.circle((0, 0), 10 * mm)\nplate.cut(h)")
    assert volume_mm3(r, "plate") == round(120000 - math.pi * 10 ** 2 * 20)
    assert r("len(plate.faces.cylindrical())") == 1


def test_fillet_and_chamfer(r):
    assert r("plate.fillet(plate.edges.parallel(Z), 5 * mm).GetTypeName2()") == "Fillet"
    assert r("plate.chamfer(plate.faces.normal(Z).edges.circular(), 1 * mm).GetTypeName2()") == "Chamfer"


def test_feature_errors_are_raised(r):
    msg = r("try:\n    plate.fillet(plate.edges.parallel(Z), 500 * mm)\n    m = 'no error'\n"
            "except FeatureError as e:\n    m = str(e)\nm")
    assert msg.startswith("fillet failed")
    msg = r("try:\n    plate.fillet([], 1 * mm)\n    m = 'no error'\nexcept FeatureError as e:\n    m = str(e)\nm")
    assert "nothing to fillet" in msg


def test_shell(r):
    before = volume_mm3(r, "plate")
    assert r("plate.shell(plate.faces.normal(-Z), 2 * mm).GetTypeName2()") == "Shell"
    assert volume_mm3(r, "plate") < before / 2


def test_save_and_export(r, tmp_path_factory):
    path = r("plate.save(os.path.join(out, 'plate.SLDPRT'))")
    assert path.endswith("plate.SLDPRT") and r("plate.path") == path
    names = r("[os.path.basename(plate.export(os.path.join(out, 'plate' + e))) for e in ('.step', '.x_t', '.stl')]")
    assert names == ["plate.step", "plate.x_t", "plate.stl"]
    assert all(os.path.getsize(os.path.join(os.path.dirname(path), n)) > 0 for n in names)
    msg = r("try:\n    plate.export(os.path.join(out, 'plate.nope'))\n    m = 'no error'\n"
            "except FeatureError as e:\n    m = str(e)\nm")
    assert msg.startswith("export to plate.nope failed")


def test_revolve(r):
    r(NEW_PART.format(name="pin") + "opened.append(pin)\n"
      "with pin.sketch(pin.planes.front) as p:\n    p.centerline((0, -0.05), (0, 0.05))\n"
      "    p.polyline([(0, -0.04), (0.01, -0.04), (0.01, 0.04), (0, 0.04)])\npin.revolve(p)\n"
      "pin.save(os.path.join(out, 'pin.SLDPRT'))")
    assert volume_mm3(r, "pin") == round(math.pi * 10 ** 2 * 80)


def test_assembly_components_and_bom(r):
    r("atpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplateAssembly)\n"
      "asm = Model(sw.NewDocument(atpl, 0, 0, 0))\nopened.append(asm)\n"
      "c1 = asm.add_component(plate.path)\nc2 = asm.add_component(pin.path, at=(0.2, 0, 0))\n"
      "c3 = asm.add_component(pin.path, at=(0.3, 0, 0))")
    assert r("asm.is_assembly, sorted(c.Name2 for c in asm.components())") == [True, ["pin-1", "pin-2", "plate-1"]]
    assert r("[(row['name'], row['quantity']) for row in asm.bom()]") == [["pin", 2], ["plate", 1]]
    assert r("asm.component('plate-1') == c1")


def test_assembly_faces_and_mates(r):
    assert r("len(asm.faces) > 20 and len(asm.faces.cylindrical()) >= 3")
    r("asm.mate(asm.component_planes(c2).right, asm.component_planes(c1).right)\n"
      "asm.mate(asm.component_planes(c2).top, asm.component_planes(c1).top)")
    # faces of an assembly know their component: mate the free pin into the plate's hole
    r("pin_face = [f for f in asm.faces.radius(10 * mm) if f.GetComponent() == c3][0]\n"   # c3: still free
      "hole_face = [f for f in asm.faces.radius(10 * mm) if f.GetComponent() == c1][0]\n"
      "asm.mate(pin_face, hole_face, 'concentric')")
    kinds = r("[m.GetTypeName2() for m in asm.mates()]")
    assert kinds.count("MateCoincident") == 2 and kinds.count("MateConcentric") == 1
    msg = r("try:\n    asm.mate(c1, c2, 'spiral')\n    m = 'no error'\nexcept ValueError as e:\n    m = str(e)\nm")
    assert "unknown mate 'spiral'" in msg


def test_drawing_views_and_pdf(r):
    r("drw = plate.create_drawing()\nopened.append(drw)")
    assert r("drw.is_drawing, drw.sheets(), len(drw.views()) >= 3") == [True, ["Sheet1"], True]
    pdf = r("drw.export(os.path.join(out, 'plate.pdf'))")
    assert os.path.getsize(pdf) > 1000
    assert r("os.path.basename(drw.export(os.path.join(out, 'plate.dxf')))") == "plate.dxf"


def test_drawing_requires_saved_model(r):
    r(NEW_PART.format(name="unsaved") + "opened.append(unsaved)")
    msg = r("try:\n    unsaved.create_drawing()\n    m = 'no error'\nexcept FeatureError as e:\n    m = str(e)\nm")
    assert "save the model" in msg


def test_type_checks(r):
    assert r("plate.is_part, plate.is_assembly, plate.is_drawing") == [True, False, False]
    msg = r("try:\n    plate.components()\n    m = 'no error'\nexcept TypeError as e:\n    m = str(e)\nm")
    assert "is not an assembly" in msg
