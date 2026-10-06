# 4. The model API

`model` wraps the active document with a small, Pythonic API for the things scripts do most:
dimensions, global variables, rebuild control, mass properties and finding faces and edges. For
everything else, `model.doc` is the full SOLIDWORKS API ([chapter 5](05-solidworks-api.md)).

The examples assume a part like the one the test suite uses: a 100 × 60 × 20 mm block
(`Boss-Extrude1`) with a Ø20 mm cylinder (`Boss-Extrude2`) standing on it.

```python live
model                     # <Model 'Part1'>
model.title               # 'Part1' - the window title
```

For a document that is not active, wrap it yourself: `Model(other_doc)`. To **create** geometry, assemblies
and drawings, see [Building models](12-building-models.md).

## Dimensions

Dimensions are addressed by their full name, `"<dimension>@<feature or sketch>"`, and values are SI:

```python live
depth = model.dims["D1@Boss-Extrude1"]          # 0.02
print(to(depth, mm), "mm")

model.dims["D1@Boss-Extrude1"] = 25 * mm        # updates and rebuilds
print(round(to(model.dims["D1@Boss-Extrude1"], mm), 6))
model.dims["D1@Boss-Extrude1"] = 20 * mm
```

| Expression | Result |
|---|---|
| `model.dims[name]` | Value in SI units (m, or rad for angles). `KeyError` if the name does not exist |
| `model.dims[name] = value` | Set (SI) and rebuild - unless inside `model.batch()` |
| `name in model.dims` | Whether the dimension exists |
| `model.dims.names()` | Names of all displayed dimensions |
| `model.dims.items()` | `{name: value}` for all of them |

```python live
for name, value in model.dims.items().items():
    print(f"{name:24} {to(value, mm):8.2f} mm")
```

**Finding a name:** in SOLIDWORKS, select a dimension and look at the *Primary Value* box of the
PropertyManager (e.g. `D1@Boss-Extrude1`), or print `model.dims.names()`.

## Global variables

`model.globals` reads and writes the global variables of the equation manager:

```python live
model.globals["Width"] = 120 * mm       # creates or updates "Width" = 120mm
print(model.globals["Width"])           # 0.12 (SI)
model.globals["Count"] = 4              # int -> unitless number
print(model.globals.items())
del model.globals["Count"]
```

| Write | Stored as |
|---|---|
| `float` (e.g. `120 * mm`) | A length in mm - or in the variable's existing unit (`in`, `deg` ...) |
| `int` | A plain number |
| `str` | A raw expression, e.g. `'"Width" / 2'` |

Reading returns SI when the expression is a number with a unit (`120mm` -> `0.12`), otherwise the
evaluated number (as `float`).

To let a global drive a dimension, add an equation through the API:

```python live
model.globals["Thick"] = 20 * mm
model.doc.GetEquationMgr().Add2(-1, '"D1@Boss-Extrude1" = "Thick"', True)
model.rebuild()
model.globals["Thick"] = 30 * mm        # the block follows
print(round(to(model.dims["D1@Boss-Extrude1"], mm), 6))   # 30.0
model.globals["Thick"] = 20 * mm
```

## Batch edits

Every `dims[...] = ` and `globals[...] = ` rebuilds immediately. When you change many values, wrap
them in `model.batch()`: graphics and the FeatureManager tree are frozen and the model rebuilds
**once** at the end. Batches can be nested.

```python live
with model.batch():
    model.globals["Width"] = 110 * mm
    model.globals["Thick"] = 22 * mm
model.globals["Thick"] = 20 * mm
```

`model.batch(rebuild=False)` skips the final rebuild. `model.rebuild()` rebuilds changed features;
`model.rebuild(force=True)` rebuilds everything.

## Mass properties

```python live
props = model.mass
print(props["mass"], "kg")
print(to(props["volume"], mm**3), "mm^3")
print(props["center"])                       # Vec(x, y, z) in metres
```

Keys: `mass` (kg), `volume` (m³), `area` (m²), `center` (`Vec`, m), `density` (kg/m³). The values
come from the material and density set in the document (or its template).

## Features and planes

```python live
for f in model.features():                   # tree order, including hidden system features
    print(f.GetTypeName2(), f.Name)
boss = model.feature("Boss-Extrude1")        # by name, None if missing
print(boss.Name, boss.GetTypeName2())
```

`model.planes` returns the three default planes **by position**, so scripts also work with templates
that rename them (`XY PLANE`, `Plan de face` ...):

```python live
front, top, right = model.planes
print(model.planes.front.Name, model.planes.top.Name, model.planes.right.Name)
model.planes.top.Select2(False, 0)
```

## Faces and edges

`model.faces` and `model.edges` return **queries**: lists you can filter with chainable methods.
Each item is an `IFace2` / `IEdge`, so the whole API is available on it.

```python live
faces = model.faces
print(len(faces), "faces,", len(faces.planar()), "planar,", len(faces.cylindrical()), "cylindrical")

top = faces.normal(Z)                        # planar faces whose outward normal is +Z
pin = faces.radius(10 * mm)                  # cylindrical faces of radius 10 mm
biggest = faces.planar().largest()
print(round(to(biggest.GetArea(), mm**2)), "mm^2")

vertical = model.edges.parallel(Z)           # straight edges along Z
print(len(vertical), "vertical edges")
```

| Query | Keeps |
|---|---|
| `faces.planar()` / `faces.cylindrical()` | Flat / cylindrical faces |
| `faces.normal(direction, tol=1e-6)` | Planar faces whose outward normal points along `direction` |
| `faces.radius(r, tol=1e-9)` | Cylindrical faces with radius `r` |
| `faces.area(lo, hi)` | Faces with `lo <= area <= hi` (m²) |
| `faces.edges` | All edges of these faces (each once) |
| `edges.linear()` / `edges.circular()` | Straight / circular edges |
| `edges.parallel(direction, tol=1e-6)` | Straight edges parallel to `direction` (either sense) |
| `edges.radius(r, tol=1e-9)` | Circular edges with radius `r` |
| `edges.length(lo, hi)` | Edges with `lo <= length <= hi` (m) |
| `q.where(predicate)` | Items for which `predicate(item)` is true |
| `q.largest()` / `q.smallest()` | Biggest / smallest item (area or length), `None` if empty |
| `q.sort(key=None, reverse=False)` | Sorted copy (default: by size) |
| `q.select(append=False)` | Select the items in the viewport; returns how many were selected |

Every filter returns a new query, so they chain:

```python live
model.faces.normal(Z).largest().Select4(False, None)     # one face, raw API
n = model.faces.cylindrical().edges.circular().select()  # all circular edges of the pin
print(n, "edges selected")
```

`where` takes any function - use the raw API inside:

```python live
small = model.faces.where(lambda f: f.GetArea() < 1000 * mm**2)
print(len(small), "faces smaller than 1000 mm^2")
```

## Vectors

`Vec` is a tuple of three floats with a little arithmetic: `-v`, `v.dot(w)`, `v.length`, `v.unit()`,
`v.angle(w)` (radians). `X`, `Y`, `Z` are the unit axes, and API arrays convert directly:

```python live
n = Vec(model.faces.normal(Z)[0].Normal)
print(n, n.length, to(Vec(1, 1, 0).angle(X), deg))
```

## Bodies

`model.bodies()` returns the solid bodies of a part (`IBody2`); `model.bodies(solid=False)` the
surface bodies.

```python live
for body in model.bodies():
    print(body.Name, len(body.GetFaces()), "faces")
```
