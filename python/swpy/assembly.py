"""Assembly helpers: components, insertion, bill of materials, mates. Used through `Model` methods.

    bolt = model.add_component(r"C:\\parts\\bolt.sldprt", at=(0, 0, 50 * mm))
    model.mate(model.component_planes(bolt).front, model.planes.front)       # coincident
    model.bom()     # [{'path': ..., 'config': 'Default', 'quantity': 4}, ...]
"""
import os
from collections import Counter

from swpy import swconst as _c
from swpy.build import FeatureError, _select

MATES = {
    "coincident": _c.swMateType_e.swMateCOINCIDENT,
    "concentric": _c.swMateType_e.swMateCONCENTRIC,
    "perpendicular": _c.swMateType_e.swMatePERPENDICULAR,
    "parallel": _c.swMateType_e.swMatePARALLEL,
    "tangent": _c.swMateType_e.swMateTANGENT,
    "distance": _c.swMateType_e.swMateDISTANCE,
    "angle": _c.swMateType_e.swMateANGLE,
}
ALIGN = {
    "closest": _c.swMateAlign_e.swMateAlignCLOSEST,
    "aligned": _c.swMateAlign_e.swMateAlignALIGNED,
    "anti_aligned": _c.swMateAlign_e.swMateAlignANTI_ALIGNED,
}
_MATE_ERRORS = {v: k.replace("swAddMateError_", "") for k, v in _c.swAddMateError_e.items().items()}


def _assembly(model):
    if "IAssemblyDoc" not in model.doc.interfaces:
        raise TypeError(f"{model!r} is not an assembly")
    return model.doc.as_("IAssemblyDoc")


def components(model, top_level=True):
    """Components (IComponent2), top level only by default."""
    return list(_assembly(model).GetComponents(top_level) or [])


def component(model, name):
    """Component by name ('bolt-1'), or None."""
    return _assembly(model).GetComponentByName(name)


def add_component(model, path, at=(0.0, 0.0, 0.0), config=""):
    """Insert a part or assembly file at a position (SI). The file is opened silently if needed."""
    from swpy import _host
    sw = _host._sw
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    opened = None
    if sw.GetOpenDocumentByName(path) is None:
        kind = _c.swDocumentTypes_e.swDocASSEMBLY if path.lower().endswith(".sldasm") else _c.swDocumentTypes_e.swDocPART
        opened, errors, _ = sw.OpenDoc6(path, kind, _c.swOpenDocOptions_e.swOpenDocOptions_Silent, config, 0, 0)
        if opened is None:
            raise FeatureError(f"cannot open {path} (error {errors})")
        model.doc.Visible = True
        sw.ActivateDoc3(model.doc.GetTitle(), False, 0, 0)
    use_config = 1 if config else 0       # swAddComponentConfigOptions_e: 0 current, 1 specific config
    comp = _assembly(model).AddComponent5(path, use_config, "", False, config, at[0], at[1], at[2])
    if opened is not None and opened != model.doc:
        sw.CloseDoc(opened.GetTitle())
    if comp is None:
        raise FeatureError(f"adding {os.path.basename(path)} failed")
    return comp


def bom(model, top_level=True):
    """Bill of materials: [{'path', 'name', 'config', 'quantity'}] (suppressed components excluded)."""
    counts = Counter()
    for comp in components(model, top_level):
        if comp.IsSuppressed():
            continue
        counts[(comp.GetPathName(), comp.ReferencedConfiguration)] += 1
    return [{"path": p, "name": os.path.splitext(os.path.basename(p))[0], "config": cfg, "quantity": n}
            for (p, cfg), n in sorted(counts.items())]


def component_planes(component):
    """Front/Top/Right planes of a component (by position, in assembly context) - for mates."""
    from swpy.model import Planes
    planes, feature = [], component.FirstFeature()
    while feature is not None and len(planes) < 3:
        if feature.GetTypeName2() == "RefPlane":
            planes.append(feature)
        feature = feature.GetNextFeature()
    return Planes(planes)


def mates(model):
    """Mate features of the assembly (inside its Mates folder), in tree order."""
    _assembly(model)
    out = []
    for feature in model.features():
        if feature.GetTypeName2() == "MateGroup":
            sub = feature.GetFirstSubFeature()
            while sub is not None:
                out.append(sub)
                sub = sub.GetNextSubFeature()
    return out


def mate(model, a, b, kind="coincident", align="closest", flip=False, distance=0.0, angle=0.0):
    """Mate two entities (faces, edges, planes ...): coincident, concentric, parallel, perpendicular,
    tangent, distance (distance=...), angle (angle=...)."""
    asm = _assembly(model)
    if kind not in MATES:
        raise ValueError(f"unknown mate {kind!r}; one of {', '.join(MATES)}")
    if _select(model.doc, [a, b]) < 2:
        raise FeatureError("mate: could not select both entities")
    result = asm.AddMate5(MATES[kind], ALIGN[align], flip, distance, distance, distance, 1, 1,
                          angle, angle, angle, False, False, 0, 0)
    mate_feature, error = result if isinstance(result, tuple) else (result, 1)
    model.doc.ClearSelection2(True)
    if mate_feature is None or error != _c.swAddMateError_e.swAddMateError_NoError:
        raise FeatureError(f"{kind} mate failed: {_MATE_ERRORS.get(error, error)}")
    model.doc.EditRebuild3()
    return mate_feature
