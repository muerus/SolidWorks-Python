# 8. Recipes

Complete scripts for common jobs, written with the raw API so you can see what happens underneath;
[Building models](12-building-models.md) shows shorter versions of several of them. They build on each other in order (the first one creates and saves
`plate.SLDPRT`, later ones work on the active document), and each can be adapted on its own. Files
go to `%TEMP%\swpy-recipes`.

## Create a part from scratch

Sketch a rectangle on the Front plane, extrude it and save. `model.planes` makes it work with any
part template, also ones that rename the default planes.

```python live
import os, tempfile
folder = os.path.join(tempfile.gettempdir(), "swpy-recipes")
os.makedirs(folder, exist_ok=True)

tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)
part = sw.NewDocument(tpl, 0, 0, 0)
plate = Model(part)

def extrude(doc, depth):
    """Close the open sketch and extrude it (blind)."""
    doc.SketchManager.InsertSketch(True)
    doc.FeatureByPositionReverse(0).Select2(False, 0)   # closing a sketch can leave nothing selected
    feat = doc.FeatureManager.FeatureExtrusion2(
        True, False, False, 0, 0, depth, 0, False, False, False, False,
        0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is None:
        raise RuntimeError("extrusion failed")       # the API fails silently - check results
    return feat

plate.planes.front.Select2(False, 0)
part.SketchManager.InsertSketch(True)
part.SketchManager.CreateCenterRectangle(0, 0, 0, 40 * mm, 25 * mm, 0)   # 80 x 50 mm
extrude(part, 15 * mm)

ok, errors, warnings = part.Extension.SaveAs(os.path.join(folder, "plate.SLDPRT"), 0, 1, None, 0, 0)
print("saved" if ok else f"save failed ({errors})", part.GetPathName())
```

## Parameter study to CSV

Vary a dimension, record the mass, restore the original value.

```python live
import csv, os, tempfile
path = os.path.join(tempfile.gettempdir(), "swpy-recipes", "study.csv")

original = model.dims["D1@Boss-Extrude1"]
rows = []
for t in [5, 10, 15, 20]:
    model.dims["D1@Boss-Extrude1"] = t * mm
    rows.append((t, round(model.mass["mass"], 6)))
model.dims["D1@Boss-Extrude1"] = original

with open(path, "w", newline="") as f:
    csv.writer(f).writerows([("thickness_mm", "mass_kg"), *rows])
rows
```

## Export to STEP, Parasolid and STL

```python live
import os
base = os.path.splitext(doc.GetPathName())[0]          # the document must be saved once
for ext in (".step", ".x_t", ".stl"):
    ok, errors, warnings = doc.Extension.SaveAs(
        base + ext, swconst.swSaveAsVersion_e.swSaveAsCurrentVersion,
        swconst.swSaveAsOptions_e.swSaveAsOptions_Silent, None, 0, 0)
    print(f"{ext:6} {'ok' if ok else f'failed (error {errors})'}")
```

## Custom properties

```python live
props = doc.Extension.get_CustomPropertyManager("")    # "" = file properties; or a configuration name
TEXT = swconst.swCustomInfoType_e.swCustomInfoText
REPLACE = swconst.swCustomPropertyAddOption_e.swCustomPropertyReplaceValue

props.Add3("PartNo", TEXT, "P-1001", REPLACE)
props.Add3("Description", TEXT, "Base plate", REPLACE)

for name in props.GetNames() or []:
    status, value, resolved, was_resolved, linked = props.Get6(name, False)
    print(f"{name:12} {resolved}")

ok, errors, warnings = doc.Save3(swconst.swSaveAsOptions_e.swSaveAsOptions_Silent, 0, 0)
```

## Features by type, rename

```python live
from collections import Counter
print(Counter(f.GetTypeName2() for f in model.features()))

extrusions = [f for f in model.features() if f.GetTypeName2() == "Extrusion"]
first = extrusions[0]
first.Name = "Plate body"                 # property assignment works like in VBA
print([f.Name for f in extrusions])
first.Name = "Boss-Extrude1"
```

## Bounding box and largest face

```python live
x1, y1, z1, x2, y2, z2 = doc.GetPartBox(True)
size = [round(to(b - a, mm), 3) for a, b in ((x1, x2), (y1, y2), (z1, z2))]
print("bounding box (mm):", size)

face = model.faces.planar().largest()
face.Select4(False, None)                  # highlight it in the viewport
print("largest face:", round(to(face.GetArea(), mm**2)), "mm^2, normal", Vec(face.Normal))
```

## Sketch from a list of points

```python live
points = [(0, 0), (60, 0), (60, 20), (30, 35), (0, 20)]      # mm, closed outline

tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplatePart)
profile = sw.NewDocument(tpl, 0, 0, 0)
Model(profile).planes.front.Select2(False, 0)
sketch = profile.SketchManager
sketch.InsertSketch(True)
sketch.AddToDB = True                     # draw directly: no snapping, much faster
for (xa, ya), (xb, yb) in zip(points, points[1:] + points[:1]):
    sketch.CreateLine(xa * mm, ya * mm, 0, xb * mm, yb * mm, 0)
sketch.AddToDB = False

profile.SketchManager.InsertSketch(True)
profile.FeatureByPositionReverse(0).Select2(False, 0)
feat = profile.FeatureManager.FeatureExtrusion2(
    True, False, False, 0, 0, 10 * mm, 0, False, False, False, False,
    0, 0, False, False, False, False, True, True, True, 0, 0, False)
print(feat.Name, round(to(Model(profile).mass["volume"], mm**3)), "mm^3")
sw.CloseDoc(profile.GetTitle())           # closes without saving
```

## Build an assembly and count components

```python live
import os, tempfile
from collections import Counter

plate_path = os.path.join(tempfile.gettempdir(), "swpy-recipes", "plate.SLDPRT")   # saved above
tpl = sw.GetUserPreferenceStringValue(swconst.swUserPreferenceStringValue_e.swDefaultTemplateAssembly)
asm = sw.NewDocument(tpl, 0, 0, 0)
for i in range(3):
    asm.AddComponent5(plate_path, 0, "", False, "", i * 100 * mm, 0, 0)

components = asm.GetComponents(True)      # True = top level only
for path, n in Counter(c.GetPathName() for c in components).items():
    print(n, "x", os.path.basename(path))
for c in components:
    x, y, z = c.Transform2.ArrayData[9:12]   # translation part of the 4x4 transform
    print(f"{c.Name2:10} at {to(x, mm):6.1f} {to(y, mm):6.1f} {to(z, mm):6.1f} mm")
print("total mass:", round(Model(asm).mass["mass"], 3), "kg")
sw.CloseDoc(asm.GetTitle())
```

## Process every part in a folder

Open each file silently, read something, close the ones that were not open before.

```python live
import glob, os, tempfile
folder = os.path.join(tempfile.gettempdir(), "swpy-recipes")

for path in sorted(glob.glob(os.path.join(folder, "*.SLDPRT"))):
    was_open = sw.GetOpenDocumentByName(path) is not None
    part, errors, warnings = sw.OpenDoc6(
        path, swconst.swDocumentTypes_e.swDocPART,
        swconst.swOpenDocOptions_e.swOpenDocOptions_Silent, "", 0, 0)
    if part is None:
        print("cannot open", path, "error", errors)
        continue
    print(f"{os.path.basename(path):20} {Model(part).mass['mass']:.3f} kg")
    if not was_open:
        sw.CloseDoc(part.GetTitle())
```

## Clean up

```python live
import os, tempfile
plate = sw.GetOpenDocumentByName(os.path.join(tempfile.gettempdir(), "swpy-recipes", "plate.SLDPRT"))
if plate is not None:
    sw.CloseDoc(plate.GetTitle())
```
