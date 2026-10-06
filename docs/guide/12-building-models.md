# 12. Building models

Create parts, assemblies and drawings from Python with a few readable calls. Everything is in SI units,
works with any document template, and **raises `FeatureError` with a reason** where the raw API would
fail silently.

## Parts: sketch, then feature

```python live
import os, tempfile
out = os.path.join(tempfile.gettempdir(), "swpy-guide")

tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)
plate = Model(sw.NewDocument(tpl, 0, 0, 0))

with plate.sketch(plate.planes.front) as s:          # sketch on a plane ...
    s.rect((0, 0), 100 * mm, 60 * mm)
plate.extrude(s, 20 * mm)

with plate.sketch(plate.faces.normal(Z).largest()) as s:   # ... or on a planar face
    s.circle((0, 0), 10 * mm)
plate.cut(s)                                           # through all

plate.fillet(plate.edges.parallel(Z), 5 * mm)          # the four vertical edges
plate.chamfer(plate.faces.normal(Z).edges.circular(), 1 * mm)
print(round(to(plate.mass["volume"], mm**3)), "mm^3")
```

### Sketching

`with model.sketch(on) as s:` opens a sketch on a plane (`model.planes.front`, a reference plane
feature) or a planar face, and closes it at the end of the block. Coordinates are **sketch
coordinates** `(x, y)` in metres; entities are placed exactly (no snapping).

| Method | Draws |
|---|---|
| `s.line(start, end)` | Line |
| `s.centerline(start, end)` | Construction centerline (the axis for `revolve`) |
| `s.rect(center, width, height)` | Rectangle around a center |
| `s.corner_rect(corner1, corner2)` | Rectangle by two corners |
| `s.circle(center, radius)` | Circle |
| `s.arc(center, start, end, clockwise=False)` | Arc |
| `s.polyline(points, close=True)` | Connected lines |
| `s.point(p)` | Sketch point |

After the block, `s.feature` is the sketch feature; pass `s` (or any sketch feature) to the feature
methods.

### Features

| Method | Creates |
|---|---|
| `extrude(sketch, depth, reverse=False, both=False, merge=True, draft=0)` | Boss-extrude (`both`: mid-plane) |
| `cut(sketch, depth=None, reverse=False, both=False)` | Cut-extrude; `depth=None` cuts through all |
| `revolve(sketch, angle=None, cut=False)` | Revolve around the sketch's centerline (full turn by default) |
| `fillet(edges, radius)` | Constant-radius fillet |
| `chamfer(edges, distance, angle=None)` | Distance-angle chamfer (45° by default) |
| `shell(faces, thickness, outward=False)` | Hollow the part, removing the given faces |

`edges` and `faces` can be a single entity, a list or a [query](04-model-api.md#faces-and-edges)
(`model.edges.parallel(Z)`). Each method returns the new feature.

```python live
tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)
pin = Model(sw.NewDocument(tpl, 0, 0, 0))
with pin.sketch(pin.planes.front) as s:
    s.centerline((0, -50 * mm), (0, 50 * mm))
    s.polyline([(0, -40 * mm), (10 * mm, -40 * mm), (10 * mm, 40 * mm), (0, 40 * mm)])
pin.revolve(s)                                         # a 20 x 80 mm pin
print(round(to(pin.mass["volume"], mm**3)), "mm^3")
```

When SOLIDWORKS refuses a feature, you get an exception that says so:

```python live
try:
    plate.fillet(plate.edges.parallel(Z), 500 * mm)
except FeatureError as e:
    print(e)                                           # fillet failed: radius too large ...
```

## Saving and exporting

```python live
plate.save(os.path.join(out, "plate.SLDPRT"))          # save as; then plate.save() saves in place
pin.save(os.path.join(out, "pin.SLDPRT"))
for ext in (".step", ".x_t", ".stl"):
    print(plate.export(os.path.join(out, "plate" + ext)))
```

`export` writes a copy in the format given by the extension (`.step`, `.x_t`, `.igs`, `.stl`, `.3mf`,
`.pdf`, `.dxf`, `.dwg`, `.png`, `.jpg` ...) and leaves the document as it is. Drawings export **all
sheets** to PDF (`all_sheets=False` for the active sheet only). Failures raise `FeatureError` with
SOLIDWORKS' reasons (`swFileSaveAsInvalidFileExtension`, `swFileLockError` ...).

## Assemblies

```python live
atpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplateAssembly)
asm = Model(sw.NewDocument(atpl, 0, 0, 0))
base = asm.add_component(plate.path)                       # the first component is fixed
pin1 = asm.add_component(pin.path, at=(0.2, 0, 0))

pin_face = [f for f in asm.faces.radius(10 * mm) if f.GetComponent() == pin1][0]
hole_face = [f for f in asm.faces.radius(10 * mm) if f.GetComponent() == base][0]
asm.mate(pin_face, hole_face, "concentric")                # pin into the hole

for row in asm.bom():
    print(row["quantity"], "x", row["name"], f"({row['config']})")
print([m.GetTypeName2() for m in asm.mates()])
```

| Method | Does |
|---|---|
| `add_component(path, at=(x, y, z), config="")` | Insert a part/assembly file (opened silently if needed); returns the component |
| `components(top_level=True)` / `component(name)` | Components (`IComponent2`) / one by name (`"pin-1"`) |
| `mate(a, b, kind="coincident", align="closest", flip=False, distance=0, angle=0)` | Mate two entities; kinds: `coincident`, `concentric`, `parallel`, `perpendicular`, `tangent`, `distance`, `angle` |
| `mates()` | Mate features |
| `component_planes(component)` | The component's Front/Top/Right planes, for plane mates |
| `bom(top_level=True)` | `[{"path", "name", "config", "quantity"}]`, suppressed components excluded |

In assemblies, `model.faces` / `model.edges` cover **all components**, in assembly context: filter them
with the usual queries and `face.GetComponent()`, then mate or select them. A mate SOLIDWORKS rejects
raises `FeatureError` with its reason, e.g. `concentric mate failed: OverDefinedAssembly`.

## Drawings

```python live
drawing = plate.create_drawing()                           # front/top/right + isometric, third angle
print(drawing.sheets(), [v.Name for v in drawing.views()])
print(drawing.export(os.path.join(out, "plate.pdf")))
```

| Method | Does |
|---|---|
| `create_drawing(template=None, views="standard")` | New drawing of a **saved** part/assembly. `views`: `"standard"`, `"first_angle"`, a list like `["*Front", "*Isometric"]`, or `None`. Returns a `Model` |
| `add_view(model_path, view="*Front", at=(x, y))` | Add a named view at a sheet position (m) |
| `sheets()` / `views()` | Sheet names / views of the active sheet (`IView`) |

## Document type

`model.is_part`, `model.is_assembly`, `model.is_drawing` and `model.path` tell you what you are working
on; assembly and drawing methods raise `TypeError` on the wrong document type.
