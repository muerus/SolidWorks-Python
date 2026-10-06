"""Other SOLIDWORKS API libraries (cosworks, swmotionstudy, swdimxpert, swcommands ...): typing, casts,
constants, cross-library detection and editor support."""
import json

import pytest

from test_host import PART

SESSION = "libraries"


@pytest.fixture(scope="module")
def r(swpy):
    swpy.ok(PART, SESSION)

    def run(expr):
        return swpy.ok(expr, SESSION)["result"]

    yield run
    swpy.ok("sw.CloseDoc(part.GetTitle())", SESSION)


def test_library_namespaces_in_scripts(r):
    assert r("cosworks").startswith("<SOLIDWORKS Simulation API (cosworks): ")
    assert r("all(n in globals() for n in ('swmotionstudy', 'swdimxpert', 'swcommands', 'EdmLib', 'SWRoutingLib'))") == "True"
    assert r("'IMotionStudyManager' in dir(swmotionstudy), 'swMotionStudyType_e' in dir(swmotionstudy)") == "(True, True)"
    assert r("[n for n in dir(swmotionstudy) if n.endswith('_Event') or n.startswith('_')]") == "[]"


def test_untyped_result_is_detected_across_libraries(r):
    # GetMotionStudyManager is declared as returning object: detected by the cross-library sweep
    assert r("msm = part.Extension.GetMotionStudyManager(); msm.interfaces") == "('swmotionstudy.IMotionStudyManager',)"
    assert r("msm.GetMotionStudyCount() >= 1") == "True"
    assert r("study = msm.GetMotionStudy(msm.GetMotionStudyNames()[0]); study.StudyType in "
             "swmotionstudy.swMotionStudyType_e.items().values()") == "True"


def test_typed_library_return(r):
    r("dx = part.Extension.get_DimXpertManager(part.ConfigurationManager.ActiveConfiguration.Name, True)")
    assert r("dx.DimXpertPart.interfaces") == "('swdimxpert.IDimXpertPart',)"
    assert r("dx.DimXpertPart.GetFeatureCount()") == "0"


def test_library_casts(r):
    assert r("swmotionstudy.IMotionStudyManager(part.Extension.GetMotionStudyManager())") == "<swmotionstudy.IMotionStudyManager>"
    assert r("swmotionstudy.IMotionStudyManager(None) is None") == "True"
    assert r("swmotionstudy.IMotionStudyManager.__swpy_interface__") == "'swmotionstudy.IMotionStudyManager'"


def test_constants(r):
    assert r("cosworks.swsAnalysisStudyType_e.swsAnalysisStudyTypeStatic") == "0"
    assert r("swcommands.swCommands_e.name(swcommands.swCommands_e.swCommands_ZoomToFit)") == "'swCommands_ZoomToFit'"


def test_run_command_with_command_ids(r):
    assert r("sw.RunCommand(swcommands.swCommands_e.swCommands_ZoomToFit, '')") == "True"


def test_detect_is_safe_on_application_object(r):
    # probing event interfaces on the application object used to kill SOLIDWORKS
    assert r("from SwPy.Scripting import ComInfo\nComInfo.Detect(sw.raw)") == "'ISldWorks'"
    assert r("ComInfo.Detect(part.GetBodies2(0, True)[0].GetFaces()[0].raw).split(',')[:2]") == "['IFace', 'IEntity']"


def test_detect_unknown_object_is_empty(r):
    assert r("from swpy.com import detect_all\ndetect_all(None)") == "''"


def test_editor_completes_library_types(r):
    r("from swpy import _host\nimport json\n"
      "def c(m, **kw):\n    kw['session'] = 'libraries'\n    v = json.loads(_host.call(m, json.dumps(kw)))\n"
      "    assert v['ok'], v\n    return v['value']\n"
      "names = lambda before: [n for n, k in c('complete', before=before)['items']]")
    assert r("names('x = swmotionstudy.IMotionStudyManager(None)\\nx.GetMo')") == \
        "['GetMotionStudy', 'GetMotionStudyCount', 'GetMotionStudyNames']"
    assert r("names('cosworks.swsAnalysisStudyType_e.swsAnalysisStudyTypeSt')") == "['swsAnalysisStudyTypeStatic']"


def test_editor_uses_observed_return_types(r):
    r("part.Extension.GetMotionStudyManager()")      # run once: the proxy records what came back
    assert "GetMotionStudyCount" in r("names('part.Extension.GetMotionStudyManager().GetMotion')")
    label = json.loads(r("json.dumps(c('signature', before='part.Extension.GetMotionStudyManager().GetMotionStudy(')"
                         "['signatures'][0]['label'])").strip("'"))
    assert label == "GetMotionStudy(MotionStudyName: str) -> MotionStudy"
