# 5. The SOLIDWORKS API from Python

Everything in the official SOLIDWORKS API (thousands of methods on `ISldWorks`, `IModelDoc2`,
`IFeature` ...) is available from Python, with the same names and arguments as in the VBA/C# help.
SwPy removes the usual friction: no casting, no `ByRef` juggling, Python lists instead of arrays.

## Objects are typed automatically

In VBA or C# many API calls return a plain `Object` that you must cast (`Dim f As SldWorks.Feature`).
In SwPy every object returned by the API is wrapped in a proxy that knows which interfaces it
implements, so members of all of them just work:

```python live
print(doc)                         # <IModelDoc2+IPartDoc 'Part1'>
feat = doc.FirstFeature()          # declared as Object in the API - typed anyway
print(feat, feat.Name)
print(doc.interfaces)              # every interface this object implements
bodies = doc.GetBodies2(swconst.swBodyType_e.swSolidBody, True)   # IPartDoc member on the same object
print(len(bodies), bodies[0])
```

* Proxies compare equal when they refer to the same SOLIDWORKS object (`face_a == face_b`) and can be
  used in sets and as dictionary keys.
* `obj.interfaces` lists the interfaces, `obj.raw` is the underlying COM object (rarely needed).
* `obj.as_("IFoo")` views an object primarily as another interface, also for interfaces outside the
  built-in list.

### Casts

When you want to be explicit, or the object implements an interface SwPy does not detect, cast with
`sldworks.<Interface>`. It returns a proxy that prefers that interface (or `None` for `None`):

```python live
part = sldworks.IPartDoc(doc)
print(part, len(part.GetBodies2(0, True)))
```

Casting also helps the editor: after `x = sldworks.IPartDoc(...)`, completion on `x.` lists `IPartDoc`
members even before the script ran.

> **Never import `SolidWorks.Interop.*`** in scripts (`from SolidWorks.Interop.sldworks import ...`).
> Other add-ins (e.g. McMaster-Carr) embed trimmed copies of those types, and Python may bind to the
> wrong one. Use `sldworks.IFoo(...)` and `swconst` instead.

## Enumerations: `swconst`

All API enums are in `swconst`, with the names from the API help:

```python live
print(swconst.swDocumentTypes_e.swDocPART)                          # 1
print(doc.GetType() == swconst.swDocumentTypes_e.swDocPART)         # True
print(swconst.swUserPreferenceToggle_e.swInputDimValOnCreate)
```

Enum values are plain integers, so you can also pass numbers, but names document intent.

## Arrays

API methods that return arrays give you **Python lists** (of proxies, numbers or strings). Methods
that take arrays accept lists and tuples:

```python live
box = doc.GetPartBox(True)          # [x1, y1, z1, x2, y2, z2] in metres
print([round(to(v, mm), 1) for v in box])
faces = doc.GetBodies2(0, True)[0].GetFaces()
print(len(faces), type(faces).__name__)
```

Lists of proxies become object arrays, lists of `int`/`float`/`bool`/`str` become typed arrays. A
numeric array returned by the API (e.g. a persistent reference ID as `byte[]`) remembers its exact type
when you pass it back.

## Out-parameters

C#/VBA methods with `out`/`ByRef` parameters return a **tuple**: the return value first, then the
out-parameters in order. You can omit trailing out-parameters, or pass placeholders:

```python live
import os, tempfile
step = os.path.join(tempfile.gettempdir(), "swpy_demo.step")
ok, errors, warnings = doc.Extension.SaveAs(
    step,
    swconst.swSaveAsVersion_e.swSaveAsCurrentVersion,
    swconst.swSaveAsOptions_e.swSaveAsOptions_Silent, None, 0, 0)
print(ok, errors, warnings)

props = doc.Extension.get_CustomPropertyManager("")
props.Add3("Material", swconst.swCustomInfoType_e.swCustomInfoText, "Steel",
           swconst.swCustomPropertyAddOption_e.swCustomPropertyReplaceValue)
status, value, resolved, was_resolved, linked = props.Get6("Material", False)
print(value, resolved)
```

The signature help shows which parameters are `out`.

## Indexed properties: `get_X(...)` / `set_X(...)`

A few API properties take arguments (in VBA `ext.CustomPropertyManager("")`). In Python call their
accessor methods instead, `get_<Name>(args)` and `set_<Name>(args, value)` - completion lists them that
way:

```python live
cpm = doc.Extension.get_CustomPropertyManager("")      # "" = document-level properties
print(cpm.GetNames())
```

## Translating VBA and C# examples

The API help is full of VBA and C# samples. They translate almost line by line:

| VBA / C# | Python (SwPy) |
|---|---|
| `Set swApp = Application.SldWorks` / `(SldWorks)swApp` | `sw` |
| `Set swModel = swApp.ActiveDoc` | `doc` (or `sw.ActiveDoc`) |
| `Dim swPart As SldWorks.PartDoc: Set swPart = swModel` | not needed - or `sldworks.IPartDoc(doc)` |
| `swModel.Extension.SelectByID2 "Top Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0` | `doc.Extension.SelectByID2("Top Plane", "PLANE", 0, 0, 0, False, 0, None, 0)` |
| `Nothing` / `null` | `None` |
| `swDocPART` / `(int)swDocumentTypes_e.swDocPART` | `swconst.swDocumentTypes_e.swDocPART` |
| `vFaces = swBody.GetFaces` then `For i = 0 To UBound(vFaces)` | `for face in body.GetFaces():` |
| `bRet = swModel.Extension.SaveAs(path, 0, 1, Nothing, lErrors, lWarnings)` | `ok, errors, warnings = doc.Extension.SaveAs(path, 0, 1, None, 0, 0)` |
| `swExt.CustomPropertyManager("")` | `ext.get_CustomPropertyManager("")` |
| `Debug.Print x` / `Console.WriteLine(x)` | `print(x)` |
| Values in metres/radians | the same - multiply by `mm`, `deg` for readability |

### Example: a VBA macro, ported

VBA (from the API help, shortened):

```vb
Set swModel = swApp.ActiveDoc
Set swFeat = swModel.FirstFeature
Do While Not swFeat Is Nothing
    Debug.Print swFeat.Name & " [" & swFeat.GetTypeName2 & "]"
    Set swFeat = swFeat.GetNextFeature
Loop
```

Python:

```python live
feat = doc.FirstFeature()
while feat is not None:
    print(f"{feat.Name} [{feat.GetTypeName2()}]")
    feat = feat.GetNextFeature()
```

or simply `for f in model.features(): ...`.

## Finding the right API call

* **Completion** (`doc.` + Ctrl+Space) lists every member with its kind; hover shows types.
* **F1** on a member opens its page in the online API help, with remarks and examples.
* The help's *Accessors* section tells you how to get an interface (e.g. `IFeatureManager` from
  `IModelDoc2.FeatureManager`).
* Record a VBA macro in SOLIDWORKS (*Tools > Macro > Record*), then translate it with the table above.

## Performance

API calls from scripts are direct in-process calls on the SOLIDWORKS thread: typically **tens of
microseconds** each, so loops over thousands of faces are fine. What costs time is SOLIDWORKS work
itself - rebuilds and graphics. Use [`model.batch()`](04-model-api.md#batch-edits) when changing many
values, and avoid selecting in loops when you can work with the objects directly.
