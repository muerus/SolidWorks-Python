"""Build part geometry: sketches and features, in SI units, with clear errors instead of silent failures.

    with model.sketch(model.planes.front) as s:
        s.rect((0, 0), 100 * mm, 60 * mm)
    block = model.extrude(s, 20 * mm)
    with model.sketch(model.faces.normal(Z).largest()) as s:
        s.circle((0, 0), 10 * mm)
    model.cut(s)                                  # through all
    model.fillet(model.edges.parallel(Z), 3 * mm)

Used through `Model` methods; see docs/guide/12-building-models.md.
"""
from swpy import swconst as _c


class FeatureError(RuntimeError):
    """SOLIDWORKS refused to create a feature (most API calls fail silently - SwPy raises instead)."""


def _check(feature, what, hint=""):
    if feature is None:
        raise FeatureError(f"{what} failed" + (f": {hint}" if hint else ""))
    return feature


def _select(doc, items, append=False, mark=0):
    """Select SOLIDWORKS entities/features (faces, edges, planes, sketches ...)."""
    if not append:
        doc.ClearSelection2(True)
    count = 0
    for item in items:
        item = item.feature if isinstance(item, Sketch) else item
        if item is None:
            continue
        if "IFeature" in item.interfaces:
            ok = item.Select2(True, mark)
        else:
            data = doc.SelectionManager.CreateSelectData()
            data.Mark = mark
            ok = item.Select4(True, data)
        count += 1 if ok else 0
    return count


def _as_list(items):
    if items is None:
        return []
    if hasattr(items, "interfaces") or isinstance(items, Sketch):
        return [items]
    return list(items)


# ---------------------------------------------------------------- sketches

class Sketch:
    """A 2D sketch being drawn (inside `with model.sketch(plane_or_face) as s:`).

    Coordinates are sketch coordinates (x, y) in metres; `feature` is the sketch feature once the
    `with` block ends.
    """

    def __init__(self, model, on):
        self.model = model
        self.on = on
        self.feature = None
        self.segments = []

    @property
    def _sm(self):
        return self.model.doc.SketchManager

    def __enter__(self):
        doc = self.model.doc
        if self.on is not None and _select(doc, [self.on]) == 0:
            raise FeatureError("could not select the sketch plane/face")
        self._sm.InsertSketch(True)
        sketch = doc.GetActiveSketch2()
        if sketch is None:
            raise FeatureError("could not start a sketch (select a plane or a planar face)")
        self._sketch = sketch
        self._sm.AddToDB = True                 # exact coordinates: no snapping or inferencing
        self._sm.DisplayWhenAdded = False
        return self

    def __exit__(self, *exc):
        self._sm.AddToDB = False
        self._sm.DisplayWhenAdded = True
        from swpy._interop import sldworks
        self.feature = sldworks.IFeature(self._sketch)
        self._sm.InsertSketch(True)              # leave the sketch
        self.model.doc.ClearSelection2(True)
        return False

    def __repr__(self):
        return f"<Sketch {self.feature.Name if self.feature else '(open)'}: {len(self.segments)} segments>"

    def _add(self, segment, what):
        if segment is None:
            raise FeatureError(f"sketch {what} failed")
        self.segments.append(segment)
        return segment

    def line(self, start, end):
        """Line from start (x, y) to end (x, y)."""
        return self._add(self._sm.CreateLine(start[0], start[1], 0, end[0], end[1], 0), "line")

    def centerline(self, start, end):
        """Construction centerline (the axis of a revolve)."""
        return self._add(self._sm.CreateCenterLine(start[0], start[1], 0, end[0], end[1], 0), "centerline")

    def circle(self, center, radius):
        """Circle by center and radius."""
        return self._add(self._sm.CreateCircleByRadius(center[0], center[1], 0, radius), "circle")

    def arc(self, center, start, end, clockwise=False):
        """Arc around center from start to end (counter-clockwise unless clockwise=True)."""
        return self._add(self._sm.CreateArc(center[0], center[1], 0, start[0], start[1], 0, end[0], end[1], 0,
                                            -1 if clockwise else 1), "arc")

    def rect(self, center, width, height):
        """Rectangle centred on center."""
        lines = self._sm.CreateCenterRectangle(center[0], center[1], 0,
                                               center[0] + width / 2, center[1] + height / 2, 0)
        if not lines:
            raise FeatureError("sketch rectangle failed")
        self.segments.extend(lines)
        return lines

    def corner_rect(self, corner1, corner2):
        """Rectangle by two opposite corners."""
        lines = self._sm.CreateCornerRectangle(corner1[0], corner1[1], 0, corner2[0], corner2[1], 0)
        if not lines:
            raise FeatureError("sketch rectangle failed")
        self.segments.extend(lines)
        return lines

    def polyline(self, points, close=True):
        """Connected lines through points; closed back to the first point by default."""
        pts = list(points)
        pairs = list(zip(pts, pts[1:] + pts[:1] if close else pts[1:]))
        return [self.line(a, b) for a, b in pairs]

    def point(self, p):
        """Sketch point."""
        return self._add(self._sm.CreatePoint(p[0], p[1], 0), "point")


# ---------------------------------------------------------------- features

def _sketch_feature(sketch):
    feature = sketch.feature if isinstance(sketch, Sketch) else sketch
    if feature is None:
        raise FeatureError("the sketch is still open - use the feature after the `with` block")
    return feature


def extrude(model, sketch, depth, reverse=False, both=False, merge=True, draft=0.0):
    """Boss-extrude a sketch by depth (both=True: symmetric, mid-plane)."""
    doc = model.doc
    _select(doc, [_sketch_feature(sketch)])
    end = _c.swEndConditions_e.swEndCondMidPlane if both else _c.swEndConditions_e.swEndCondBlind
    feature = doc.FeatureManager.FeatureExtrusion3(
        True, reverse, False, end, 0, depth, 0, draft > 0, False, False, False, draft, 0,
        False, False, False, False, merge, True, True, 0, 0, False)
    return _check(feature, "extrude", "is the sketch a closed profile?")


def cut(model, sketch, depth=None, reverse=False, both=False):
    """Cut-extrude a sketch: through all (depth=None) or by depth."""
    doc = model.doc
    _select(doc, [_sketch_feature(sketch)])
    e = _c.swEndConditions_e
    if depth is None:
        end = e.swEndCondThroughAllBoth if both else e.swEndCondThroughAll
    else:
        end = e.swEndCondMidPlane if both else e.swEndCondBlind
    feature = doc.FeatureManager.FeatureCut4(
        True, reverse, False, end, 0, depth or 0.0, 0, False, False, False, False, 0, 0,
        False, False, False, False, False, True, True, True, True, False, 0, 0, False, False)
    return _check(feature, "cut", "is the sketch closed and does it overlap the part? try reverse=True")


def revolve(model, sketch, angle=None, cut=False, merge=True):
    """Revolve a sketch around its centerline by angle (default full turn)."""
    import math
    doc = model.doc
    _select(doc, [_sketch_feature(sketch)])
    feature = doc.FeatureManager.FeatureRevolve2(
        True, True, False, cut, False, False, 0, 0, angle if angle is not None else 2 * math.pi, 0,
        False, False, 0, 0, 0, 0, 0, merge, True, True)
    return _check(feature, "revolve", "the sketch needs exactly one centerline and a closed profile on one side")


def fillet(model, items, radius):
    """Constant-radius fillet on edges (or all edges of faces)."""
    doc = model.doc
    items = _as_list(items)
    if _select(doc, items) == 0:
        raise FeatureError("fillet: nothing to fillet (no edges selected)")
    o = _c.swFeatureFilletOptions_e
    feature = doc.FeatureManager.FeatureFillet3(
        o.swFeatureFilletUniformRadius | o.swFeatureFilletPropagate, radius, 0, 0,
        _c.swFeatureFilletType_e.swFeatureFilletType_Simple, 0, 0, None, None, None, None, None, None, None)
    return _check(feature, "fillet", "radius too large for the selected edges?")


def chamfer(model, items, distance, angle=None):
    """Distance-angle chamfer on edges (default 45 degrees)."""
    import math
    doc = model.doc
    items = _as_list(items)
    if _select(doc, items) == 0:
        raise FeatureError("chamfer: nothing to chamfer (no edges selected)")
    feature = doc.FeatureManager.InsertFeatureChamfer(
        _c.swFeatureChamferOption_e.swFeatureChamferTangentPropagation,
        _c.swChamferType_e.swChamferAngleDistance, distance, angle if angle is not None else math.pi / 4, 0, 0, 0, 0)
    return _check(feature, "chamfer", "distance too large for the selected edges?")


def shell(model, faces, thickness, outward=False):
    """Hollow the part, removing the given faces (may be empty for a closed shell)."""
    doc = model.doc
    before = doc.FeatureByPositionReverse(0)
    _select(doc, _as_list(faces))
    doc.InsertFeatureShell(thickness, outward)
    feature = doc.FeatureByPositionReverse(0)
    if feature is None or feature == before or feature.GetTypeName2() != "Shell":
        raise FeatureError("shell failed: thickness too large for the part?")
    doc.ClearSelection2(True)
    return feature
