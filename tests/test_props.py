"""L3: custom properties (model.props) - types, links, configurations, errors."""
import json

import pytest

from test_host import PART
from test_model import BOSS


@pytest.fixture(scope="module")
def s(swpy):
    name = "props-tests"
    swpy.ok(PART + BOSS + "import datetime\nprops = model.props", name)
    yield name
    swpy.ok("sw.CloseDoc(part.GetTitle())", name)


def r(swpy, s, expr):
    return swpy.ok(expr, s)["result"]


def err(swpy, s, code):
    res = swpy.run(code, s)
    assert not res["ok"], f"expected an error from {code!r}"
    return res["error"].strip().splitlines()[-1]


def test_text_roundtrip(swpy, s):
    swpy.ok("props['PartNo'] = 'P-100'", s)
    assert r(swpy, s, "props['PartNo'], props.raw('PartNo'), props.kind('PartNo')") == "('P-100', 'P-100', 'text')"


def test_names_are_case_insensitive_and_update_in_place(swpy, s):
    swpy.ok("props['First'] = 'a'\nprops['Second'] = 'b'\nprops['first'] = 'A'", s)
    assert r(swpy, s, "props['FIRST'], 'fIrSt' in props") == "('A', True)"
    names = r(swpy, s, "[n for n in props.names() if n in ('First', 'Second')]")
    assert names == "['First', 'Second']"            # updating keeps the position


def test_unicode_quotes_and_newlines(swpy, s):
    swpy.ok("props['Note'] = 'Ünïcode ✓ \"quoted\"\\nline 2'", s)
    assert r(swpy, s, "props['Note'] == 'Ünïcode ✓ \"quoted\"\\nline 2'") == "True"


def test_numbers(swpy, s):
    swpy.ok("props['Qty'] = 4\nprops['Neg'] = -7\nprops['Whole'] = 5.0\nprops['Pi'] = 3.14159\nprops['Tiny'] = 0.001",
            s)
    assert r(swpy, s, "props['Qty'], props['Neg'], props['Whole']") == "('4', '-7', '5')"
    assert r(swpy, s, "props['Pi'], props['Tiny']") == "('3.14159', '0.001')"
    assert r(swpy, s, "{props.kind(n) for n in ('Qty', 'Neg', 'Whole', 'Pi', 'Tiny')}") == "{'number'}"


def test_float_never_written_with_exponent(swpy, s):
    # repr(1e-05) is '1e-05', which SOLIDWORKS stores as a broken property
    swpy.ok("props['Small'] = 1e-05\nprops['Big'] = 1.5e20", s)
    assert r(swpy, s, "float(props['Small']), props.kind('Small')") == "(1e-05, 'number')"
    assert r(swpy, s, "float(props['Big'])") == "1.5e+20"


def test_yes_no(swpy, s):
    swpy.ok("props['Bought'] = True", s)
    assert r(swpy, s, "props['Bought'], props.kind('Bought')") == "('Yes', 'yesno')"
    swpy.ok("props['Bought'] = False", s)
    assert r(swpy, s, "props['Bought']") == "'No'"
    swpy.ok("props['NewNo'] = False", s)                 # the literal "No" is rejected for new ones
    assert r(swpy, s, "props['NewNo']") == "'No'"
    swpy.ok("props.set('Str', 'yes', 'yesno')", s)
    assert r(swpy, s, "props['Str']") == "'Yes'"


def test_dates(swpy, s):
    swpy.ok("props['Released'] = datetime.date(2026, 10, 8)\nprops['Stamp'] = datetime.datetime(2026, 1, 2, 3, 4)",
            s)
    assert r(swpy, s, "props['Released'], props.kind('Released'), props['Stamp']") == \
        "('2026-10-08', 'date', '2026-01-02')"
    swpy.ok("props.set('Iso', '2025-12-31', 'date')", s)
    assert r(swpy, s, "props['Iso']") == "'2025-12-31'"


def test_type_change(swpy, s):
    swpy.ok("props['Changing'] = 'text'\nprops['After'] = 'x'\nprops['Changing'] = 12", s)
    assert r(swpy, s, "props['Changing'], props.kind('Changing')") == "('12', 'number')"
    assert r(swpy, s, "props.names()[-1]") == "'Changing'"     # SOLIDWORKS re-adds it at the end
    swpy.ok("props.set('Changing', 12, 'text')", s)
    assert r(swpy, s, "props['Changing'], props.kind('Changing')") == "('12', 'text')"


def test_link_system_property(swpy, s):
    swpy.ok("props.link('Weight', 'SW-Mass')", s)
    raw = r(swpy, s, "props.raw('Weight')")
    assert raw.startswith("'\"SW-Mass@") and raw.endswith(".SLDPRT\"'")
    # SW-Mass is in document units (grams for the default template); compare against model.mass (kg)
    assert r(swpy, s, "abs(float(props['Weight']) - model.mass['mass'] * 1000) < 0.01") == "True"


def test_link_dimension_follows_changes(swpy, s):
    swpy.ok("props.link('Thickness', 'D1@Boss-Extrude1')", s)
    assert r(swpy, s, "float(props['Thickness'])") == "20.0"
    swpy.ok("model.dims['D1@Boss-Extrude1'] = 25 * mm", s)
    try:
        assert r(swpy, s, "float(props['Thickness'])") == "25.0"
    finally:
        swpy.ok("model.dims['D1@Boss-Extrude1'] = 20 * mm", s)


def test_mapping_protocol(swpy, s):
    swpy.ok("props.update({'U1': 'one', 'U2': 2})", s)
    assert r(swpy, s, "props.get('U1'), props.get('Missing', 'dflt'), dict(props)['U2']") == "('one', 'dflt', '2')"
    assert r(swpy, s, "len(props) == len(props.names()) == len(list(props))") == "True"
    assert r(swpy, s, "props.items()['U1'], 'U1' in props.keys(), 'one' in props.values()") == "('one', True, True)"
    assert r(swpy, s, "props.pop('U1'), 'U1' in props") == "('one', False)"


def test_delete(swpy, s):
    swpy.ok("props['Temp'] = 'x'\ndel props['temp']", s)
    assert r(swpy, s, "'Temp' in props") == "False"
    assert "KeyError" in err(swpy, s, "del props['Temp']")


def test_missing_property(swpy, s):
    assert "KeyError" in err(swpy, s, "props['NoSuchProperty']")
    assert "KeyError" in err(swpy, s, "props.raw('NoSuchProperty')")
    assert "KeyError" in err(swpy, s, "props.kind('NoSuchProperty')")
    assert r(swpy, s, "'NoSuchProperty' in props, 42 in props") == "(False, False)"


def test_invalid_values(swpy, s):
    assert "TypeError" in err(swpy, s, "props['Bad'] = [1, 2]")
    assert "TypeError" in err(swpy, s, "props['Bad'] = None")
    assert "ValueError" in err(swpy, s, "props['Bad'] = float('nan')")
    assert "ValueError" in err(swpy, s, "props[''] = 'x'")
    assert "ValueError" in err(swpy, s, "props.set('Bad', 'abc', 'number')")
    assert "ValueError" in err(swpy, s, "props.set('Bad', 'x', 'colour')")
    assert "TypeError" in err(swpy, s, "props.set('Bad', 'maybe', 'yesno')")
    assert "ValueError" in err(swpy, s, "props.set('Bad', '08/10/2026', 'date')")
    assert r(swpy, s, "'Bad' in props") == "False"


def test_failed_write_keeps_existing_value(swpy, s):
    swpy.ok("props['Keep'] = 7", s)
    err(swpy, s, "props.set('Keep', 'abc', 'number')")
    assert r(swpy, s, "props['Keep'], props.kind('Keep')") == "('7', 'number')"


def test_number_given_as_text(swpy, s):
    swpy.ok("props.set('AsText', ' 12.50 ', 'number')\nprops.set('AsInt', '3', 'number')", s)
    assert r(swpy, s, "props['AsText'], props['AsInt']") == "('12.5', '3')"


def test_configuration_properties(swpy, s):
    cfg = r(swpy, s, "part.ConfigurationManager.ActiveConfiguration.Name")[1:-1]
    swpy.ok(f"cp = props.config({cfg!r})\ncp['Finish'] = 'Anodized'", s)
    assert r(swpy, s, "cp['Finish'], 'Finish' in props, cp.config_name") == f"('Anodized', False, {cfg!r})"
    assert r(swpy, s, "repr(cp).startswith(f'Props[{cp.config_name}]')") == "True"
    assert "KeyError" in err(swpy, s, "props.config('NoSuchConfig')")


def test_second_configuration(swpy, s):
    swpy.ok("part.AddConfiguration3('Alt', '', '', 0)\nprops.config('Alt')['Finish'] = 'Painted'", s)
    try:
        assert r(swpy, s, "props.config('Alt')['Finish'], props.config('alt')['finish']") == "('Painted', 'Painted')"
        assert r(swpy, s, "'Finish' in props") == "False"
    finally:
        cfg = r(swpy, s, "part.GetConfigurationNames()[0]")
        swpy.ok(f"part.ShowConfiguration2({cfg})\npart.DeleteConfiguration2('Alt')", s)


def test_drawing_has_file_properties_only(swpy, s):
    swpy.ok("tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplateDrawing)\n"
            "drw = Model(sldworks.IModelDoc2(sw.NewDocument(tpl, 12, 0.2, 0.2)))", s)
    try:
        swpy.ok("drw.props['Checked'] = 'MR'", s)
        assert r(swpy, s, "drw.props['Checked']") == "'MR'"
        assert "KeyError" in err(swpy, s, "drw.props.config('Default')")
    finally:
        swpy.ok("sw.CloseDoc(drw.title)\nModel(part)", s)


def test_editor_completion(swpy, s):
    args = json.dumps({"before": "model.props.", "session": s})
    reply = json.loads(swpy.ok(f"from swpy import _host\n_host.call('complete', {args!r})", s)["value"])
    assert reply["ok"], reply.get("error")
    names = {n for n, _ in reply["value"]["items"]}
    assert {"link", "raw", "kind", "config", "names", "items", "set"} <= names
