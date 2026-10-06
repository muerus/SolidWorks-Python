"""Pythonic layer over a SOLIDWORKS document (L3).

    model = Model(doc)
    model.dims["D1@Boss-Extrude1"] = 30 * mm      # rebuilds (unless inside batch)
    model.globals["Width"] = 120 * mm
    with model.batch():                            # many edits, one rebuild
        ...
    model.faces.planar().normal(Z).largest().select()
    model.mass["volume"]
All values are SI (see swpy.units).
"""
import contextlib
import math
import re

from swpy.com import Com
from swpy.units import EQUATION_UNITS, mm


# ---------------------------------------------------------------- vectors
class Vec(tuple):
    """3D vector with the little arithmetic queries need: -Z, dot, angle."""

    def __new__(cls, x, y=None, z=None):
        if y is None:
            x, y, z = x
        return super().__new__(cls, (float(x), float(y), float(z)))

    def __neg__(self):
        return Vec(-self[0], -self[1], -self[2])

    def dot(self, o):
        return self[0] * o[0] + self[1] * o[1] + self[2] * o[2]

    @property
    def length(self):
        return math.sqrt(self.dot(self))

    def unit(self):
        n = self.length
        return Vec(self[0] / n, self[1] / n, self[2] / n)

    def angle(self, o):
        c = self.unit().dot(Vec(o).unit())
        return math.acos(max(-1.0, min(1.0, c)))

    def __repr__(self):
        return f"Vec({self[0]:g}, {self[1]:g}, {self[2]:g})"


X, Y, Z = Vec(1, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1)


# ---------------------------------------------------------------- queries
class Query(list):
    """A list of faces/edges with chainable filters. Every filter returns a new Query."""

    ITEM = None   # SOLIDWORKS interface of the items (editor completion)

    def where(self, predicate) -> "SELF":
        """Items for which predicate(item) is true (exceptions count as false)."""
        return type(self)(e for e in self if _safe(predicate, e))

    def largest(self) -> "ITEM":
        """Biggest item (area for faces, length for edges), or None if empty."""
        return max(self, key=self._size) if self else None

    def smallest(self) -> "ITEM":
        """Smallest item (area for faces, length for edges), or None if empty."""
        return min(self, key=self._size) if self else None

    def sort(self, key=None, reverse=False) -> "SELF":
        """New query sorted by key (default: size, ascending)."""
        return type(self)(sorted(self, key=key or self._size, reverse=reverse))

    def select(self, append=False):
        """Select all items in the viewport. Returns how many were selected."""
        if not self:
            return 0
        if not append:
            _doc_of(self[0]).ClearSelection2(True)
        return sum(1 for e in self if e.Select4(True, None))

    @staticmethod
    def _size(e):
        return 0.0


def _safe(fn, e):
    try:
        return fn(e)
    except Exception:
        return False


def _doc_of(entity):
    return Model._current_doc


class Faces(Query):
    """Faces of a model (IFace2 proxies). Get one from `model.faces`."""

    ITEM = "IFace2"

    @staticmethod
    def _size(f):
        return f.GetArea()

    def planar(self) -> "Faces":
        """Flat faces."""
        return self.where(lambda f: f.GetSurface().IsPlane())

    def cylindrical(self) -> "Faces":
        """Cylindrical faces (holes, bosses, fillets on straight edges)."""
        return self.where(lambda f: f.GetSurface().IsCylinder())

    def normal(self, direction, tol=1e-6) -> "Faces":
        """Planar faces whose outward normal points along `direction`."""
        d = Vec(direction).unit()
        return self.planar().where(lambda f: Vec(f.Normal).unit().dot(d) > 1 - tol)

    def radius(self, r, tol=1e-9) -> "Faces":
        """Cylindrical faces with radius r (SI)."""
        return self.cylindrical().where(lambda f: abs(f.GetSurface().CylinderParams[6] - r) <= tol)

    def area(self, lo=0.0, hi=float("inf")) -> "Faces":
        """Faces with lo <= area <= hi (m^2)."""
        return self.where(lambda f: lo <= f.GetArea() <= hi)

    @property
    def edges(self) -> "Edges":
        """All edges bounding these faces (each edge once)."""
        seen, out = set(), Edges()
        for f in self:
            for e in f.GetEdges() or []:
                if e not in seen:
                    seen.add(e)
                    out.append(e)
        return out


class Edges(Query):
    """Edges of a model (IEdge proxies). Get one from `model.edges` or `faces.edges`."""

    ITEM = "IEdge"

    @staticmethod
    def _size(e):
        c = e.GetCurve()
        lo, hi = c.GetEndParams()[1:3]
        return c.GetLength3(lo, hi)

    def linear(self) -> "Edges":
        """Straight edges."""
        return self.where(lambda e: e.GetCurve().IsLine())

    def circular(self) -> "Edges":
        """Circular edges (full circles and arcs)."""
        return self.where(lambda e: e.GetCurve().IsCircle())

    def parallel(self, direction, tol=1e-6) -> "Edges":
        """Straight edges parallel (either sense) to `direction`."""
        d = Vec(direction).unit()
        return self.linear().where(lambda e: abs(Vec(e.GetCurve().LineParams[3:6]).unit().dot(d)) > 1 - tol)

    def radius(self, r, tol=1e-9) -> "Edges":
        """Circular edges with radius r (SI)."""
        return self.circular().where(lambda e: abs(e.GetCurve().CircleParams[6] - r) <= tol)

    def length(self, lo=0.0, hi=float("inf")) -> "Edges":
        """Edges with lo <= length <= hi (m)."""
        return self.where(lambda e: lo <= self._size(e) <= hi)


class Planes(tuple):
    """The three default reference planes. SOLIDWORKS keeps them first in the tree and they
    cannot be deleted or reordered, so position is stable while names are template-defined."""

    ITEM = "IFeature"

    def __new__(cls, ref_planes):
        planes = tuple(ref_planes)[:3]
        if len(planes) < 3:
            raise LookupError(f"expected 3 default planes, found {len(planes)}")
        return super().__new__(cls, planes)

    @property
    def front(self) -> "IFeature":
        """Front plane (XY in standard templates)."""
        return self[0]

    @property
    def top(self) -> "IFeature":
        """Top plane (XZ in standard templates)."""
        return self[1]

    @property
    def right(self) -> "IFeature":
        """Right plane (YZ in standard templates)."""
        return self[2]

    def __repr__(self):
        return "<Planes " + ", ".join(p.Name for p in self) + ">"


# ---------------------------------------------------------------- dimensions / globals

class Dims:
    """model.dims["D1@Boss-Extrude1"] -> SI float; assignment updates and rebuilds."""

    def __init__(self, model):
        self._m = model

    def _dim(self, name):
        d = self._m.doc.Parameter(name)
        if d is None:
            raise KeyError(name)
        return d

    def __getitem__(self, name):
        return self._dim(name).SystemValue

    def __setitem__(self, name, value):
        self._dim(name).SystemValue = float(value)
        self._m._changed()

    def __contains__(self, name):
        return self._m.doc.Parameter(name) is not None

    def names(self):
        """Names of all displayed dimensions, e.g. ['D1@Sketch1', 'D1@Boss-Extrude1']."""
        out = []
        for f in self._m.features():
            dd = f.GetFirstDisplayDimension()
            while dd is not None:
                full = dd.GetDimension2(0).FullName          # D1@Boss-Extrude1@Part1.Part
                out.append(full.rsplit("@", 1)[0] if full.count("@") > 1 else full)
                dd = f.GetNextDisplayDimension(dd)
        return out

    def items(self):
        """{name: SI value} for every dimension."""
        return {n: self[n] for n in self.names()}

    def __repr__(self):
        return f"Dims({ {n: round(v / mm, 6) for n, v in self.items().items()} } mm)"


_GLOBAL = re.compile(r'^\s*"([^"]+)"\s*=\s*(.+?)\s*$')
_VALUE_UNIT = re.compile(r"^\s*(-?[\d.]+(?:e-?\d+)?)\s*([a-z]*)\s*$", re.I)


class Globals:
    """Global variables of the equation manager.

    Read: SI float when the expression is "number + unit", else the evaluated number.
    Write: float -> length in mm (or the variable's existing unit); int -> plain number;
    str -> raw expression (e.g. '"Width" * 2').
    """

    def __init__(self, model):
        self._m = model

    @property
    def _eq(self):
        return self._m.doc.GetEquationMgr()

    def _index(self):
        eq = self._eq
        out = {}
        for i in range(eq.GetCount()):
            if eq.get_GlobalVariable(i):
                mt = _GLOBAL.match(eq.get_Equation(i))
                if mt:
                    out[mt.group(1)] = (i, mt.group(2))
        return out

    def __getitem__(self, name):
        i, expr = self._index()[name]
        value = self._eq.get_Value(i)
        mt = _VALUE_UNIT.match(expr)
        if mt and mt.group(2).lower() in EQUATION_UNITS:
            return value * EQUATION_UNITS[mt.group(2).lower()]
        return value

    def __setitem__(self, name, value):
        idx = self._index()
        if isinstance(value, str):
            expr = value
        elif isinstance(value, int) and not isinstance(value, bool):
            expr = str(value)
        else:
            unit = "mm"
            if name in idx:
                mt = _VALUE_UNIT.match(idx[name][1])
                if mt and mt.group(2).lower() in EQUATION_UNITS:
                    unit = mt.group(2)
            expr = f"{float(value) / EQUATION_UNITS[unit.lower()]:.10g}{unit}"
        text = f'"{name}" = {expr}'
        eq = self._eq
        if name in idx:
            eq.set_Equation(idx[name][0], text)
        elif eq.Add2(-1, text, True) < 0:
            raise ValueError(f"SOLIDWORKS rejected equation {text!r}")
        eq.EvaluateAll()
        self._m._changed()

    def __delitem__(self, name):
        self._eq.Delete(self._index()[name][0])
        self._m._changed()

    def __contains__(self, name):
        return name in self._index()

    def names(self):
        """Names of the global variables."""
        return list(self._index())

    def items(self):
        """{name: value} for every global variable."""
        return {n: self[n] for n in self.names()}

    def __repr__(self):
        return f"Globals({self.items()})"


# ---------------------------------------------------------------- model
class Model:
    """Pythonic wrapper around an IModelDoc2. In scripts, `model` is the active document."""

    doc: "IModelDoc2"   # the wrapped document (auto-typed Com proxy)
    _current_doc = None

    def __init__(self, doc):
        self.doc = doc if type(doc).__name__ == "Com" else Com(doc)
        self._batch_depth = 0
        self._dirty = False
        Model._current_doc = self.doc

    # -- info ---------------------------------------------------------------
    @property
    def title(self) -> str:
        """Document title as shown in the window ('Part1', 'bracket.SLDPRT')."""
        return self.doc.GetTitle()

    @property
    def dims(self) -> "Dims":
        """Dimensions by full name: model.dims["D1@Boss-Extrude1"] = 30 * mm."""
        return Dims(self)

    @property
    def globals(self) -> "Globals":
        """Global variables: model.globals["Width"] = 120 * mm."""
        return Globals(self)

    @property
    def mass(self) -> dict:
        """Mass properties in SI: {'mass', 'volume', 'area', 'center', 'density'}."""
        mp = self.doc.Extension.CreateMassProperty()
        return {"mass": mp.Mass, "volume": mp.Volume, "area": mp.SurfaceArea,
                "center": Vec(mp.CenterOfMass), "density": mp.Density}

    def bodies(self, solid=True) -> list:
        """Solid (or surface, solid=False) bodies of a part, as IBody2 proxies."""
        part = self.doc.as_("IPartDoc")
        return list(part.GetBodies2(0 if solid else 1, True) or [])

    @property
    def faces(self) -> "Faces":
        """All faces of all solid bodies, as a chainable Faces query."""
        return Faces(f for b in self.bodies() for f in (b.GetFaces() or []))

    @property
    def edges(self) -> "Edges":
        """All edges of all solid bodies, as a chainable Edges query."""
        return Edges(e for b in self.bodies() for e in (b.GetEdges() or []))

    def features(self) -> list:
        """All features in tree order (IFeature proxies), including hidden system features."""
        return list(self.doc.FeatureManager.GetFeatures(True) or [])

    def feature(self, name) -> "IFeature":
        """Feature by name ('Boss-Extrude1'), or None."""
        return self.doc.FeatureByName(name)

    @property
    def planes(self) -> "Planes":
        """Default Front/Top/Right planes (also `[0]`, `[1]`, `[2]`), found by position so
        templates that rename them (e.g. "XY PLANE") still work."""
        return Planes(f for f in self.features() if f.GetTypeName2() == "RefPlane")

    # -- rebuild control ------------------------------------------------------
    def rebuild(self, force=False):
        """Rebuild changed features (force=True: rebuild everything)."""
        return self.doc.ForceRebuild3(False) if force else self.doc.EditRebuild3()

    def _changed(self):
        if self._batch_depth:
            self._dirty = True
        else:
            self.rebuild()

    @contextlib.contextmanager
    def batch(self, rebuild=True):
        """Group edits: no graphics/tree updates and a single rebuild at the end."""
        view = self.doc.ActiveView
        fm = self.doc.FeatureManager
        self._batch_depth += 1
        outer = self._batch_depth == 1
        if outer:
            if view is not None:
                view.EnableGraphicsUpdate = False
            fm.EnableFeatureTree = False
        try:
            yield self
        finally:
            self._batch_depth -= 1
            if outer:
                fm.EnableFeatureTree = True
                if view is not None:
                    view.EnableGraphicsUpdate = True
                if rebuild and self._dirty:
                    self.rebuild()
                self._dirty = False
                self.doc.GraphicsRedraw2()

    def __repr__(self):
        return f"<Model {self.title!r}>"
