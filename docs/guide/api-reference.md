# API reference

All names below are SI-based. In editor scripts the most used ones are predefined (see
[Scripting basics](03-scripting-basics.md)); elsewhere import them from their module.

* [`swpy.units`](#swpyunits) - units and conversion
* [`swpy.model`](#swpymodel) - `Model`, queries, `Vec`, `Planes`, `Dims`, `Globals`
* [`swpy.com`](#swpycom) - auto-typed proxies over SOLIDWORKS objects
* [`swpy._interop`](#interop-sldworks-and-swconst) - `sldworks` casts and `swconst` enums
* [`swpy.events`](#swpyevents) - event handlers
* [`swpy.ui`](#swpyui) - progress bar, messages, dialogs
* [`swpy.packages`](#swpypackages) - `# r:` requirements
* [`swpy.client`](#swpyclient) - remote control from another Python

---

## swpy.units

Unit factors: multiply to convert **to** SI, divide (or use `to`) to convert **from** SI.

| Name | Value | | Name | Value |
|---|---|---|---|---|
| `m` | 1.0 | | `rad` | 1.0 |
| `cm` | 0.01 | | `deg` | π / 180 |
| `mm` | 0.001 | | `kg` | 1.0 |
| `um` | 1e-6 | | `g` | 0.001 |
| `inch` | 0.0254 | | `lb` | 0.45359237 |
| `ft` | 0.3048 | | | |

### `to(value, unit)`
Convert an SI value to `unit`: `to(0.05, mm) -> 50.0`. Works with derived units: `to(area, mm**2)`.

### `EQUATION_UNITS`
`{"mm": mm, "cm": cm, "m": m, "in": inch, "ft": ft, "deg": deg, "rad": rad, "um": um}` - unit suffixes
understood in equation-manager expressions.

---

## swpy.model

### `class Model(doc)`
Pythonic wrapper around an `IModelDoc2` (a proxy or a raw COM object). In scripts, `model` is
`Model(doc)` for the active document.

| Member | Description |
|---|---|
| `doc` | The wrapped document (auto-typed proxy) |
| `title` | Window title, e.g. `'Part1'` |
| `dims` | [`Dims`](#class-dims) - dimensions by full name |
| `globals` | [`Globals`](#class-globals) - equation-manager global variables |
| `mass` | `dict` with `mass` (kg), `volume` (m³), `area` (m²), `center` (`Vec`), `density` (kg/m³) |
| `bodies(solid=True)` | Solid bodies (or surface bodies with `solid=False`) of a part, as `IBody2` |
| `faces` | [`Faces`](#class-faces) query over all faces of all solid bodies |
| `edges` | [`Edges`](#class-edges) query over all edges of all solid bodies |
| `features()` | All features in tree order (`IFeature`), including hidden system features |
| `feature(name)` | Feature by name, or `None` |
| `planes` | [`Planes`](#class-planes) - the default Front/Top/Right planes by position |
| `rebuild(force=False)` | Rebuild changed features (`EditRebuild3`); `force=True` rebuilds all (`ForceRebuild3`) |
| `batch(rebuild=True)` | Context manager: freeze graphics and the feature tree, rebuild once at the end (if anything changed and `rebuild` is true). Nestable |

### `class Dims`
Returned by `model.dims`.

| Member | Description |
|---|---|
| `dims[name]` | SI value of a dimension (`"D1@Boss-Extrude1"`); `KeyError` if missing |
| `dims[name] = value` | Set the SI value and rebuild (deferred inside `model.batch()`) |
| `name in dims` | Whether the dimension exists |
| `names()` | Names of all displayed dimensions of all features |
| `items()` | `{name: SI value}` |

### `class Globals`
Returned by `model.globals`.

| Member | Description |
|---|---|
| `globals[name]` | SI value for "number + unit" expressions, else the evaluated number (`float`); `KeyError` if missing |
| `globals[name] = value` | `float`: a length in mm (or the variable's existing unit); `int`: a plain number; `str`: a raw expression. Creates the variable if needed, evaluates equations, rebuilds |
| `del globals[name]` | Delete the variable |
| `name in globals` | Whether it exists |
| `names()` | Variable names |
| `items()` | `{name: value}` |

Raises `ValueError` if SOLIDWORKS rejects an expression.

### `class Query(list)`
Base class of `Faces` and `Edges`: a list with chainable filters. Every filter returns a new query of
the same class.

| Member | Description |
|---|---|
| `where(predicate)` | Items for which `predicate(item)` is true; exceptions count as false |
| `largest()` / `smallest()` | Item with the largest / smallest size (area for faces, length for edges), or `None` |
| `sort(key=None, reverse=False)` | Sorted copy, by size by default |
| `select(append=False)` | Select all items in the viewport (clearing the selection first unless `append`). Returns the number selected |
| `ITEM` | Name of the item interface (`"IFace2"`, `"IEdge"`) - used by editor completion |

### `class Faces(Query)`
Items are `IFace2` proxies.

| Member | Description |
|---|---|
| `planar()` | Flat faces |
| `cylindrical()` | Cylindrical faces |
| `normal(direction, tol=1e-6)` | Planar faces whose outward normal points along `direction` (any 3-sequence) |
| `radius(r, tol=1e-9)` | Cylindrical faces with radius `r` |
| `area(lo=0.0, hi=inf)` | Faces with `lo <= area <= hi` |
| `edges` | [`Edges`](#class-edges) bounding these faces, each once |

### `class Edges(Query)`
Items are `IEdge` proxies.

| Member | Description |
|---|---|
| `linear()` | Straight edges |
| `circular()` | Circular edges (circles and arcs) |
| `parallel(direction, tol=1e-6)` | Straight edges parallel to `direction` (either sense) |
| `radius(r, tol=1e-9)` | Circular edges with radius `r` |
| `length(lo=0.0, hi=inf)` | Edges with `lo <= length <= hi` |

### `class Planes(tuple)`
Returned by `model.planes`: the three default reference planes (`IFeature`), found by position in the
feature tree (SOLIDWORKS keeps them first; they cannot be deleted or reordered), so it works with
templates that rename them. Raises `LookupError` if fewer than three planes exist.

| Member | Description |
|---|---|
| `front` / `planes[0]` | Front plane (XY in standard templates) |
| `top` / `planes[1]` | Top plane (XZ) |
| `right` / `planes[2]` | Right plane (YZ) |

### `class Vec(tuple)`
`Vec(x, y, z)` or `Vec(sequence)` - a 3D vector of floats.

| Member | Description |
|---|---|
| `-v` | Negated vector |
| `dot(o)` | Dot product with any 3-sequence |
| `length` | Euclidean length (property) |
| `unit()` | Normalised copy |
| `angle(o)` | Angle to `o` in radians |

### `X`, `Y`, `Z`
Unit vectors `Vec(1, 0, 0)`, `Vec(0, 1, 0)`, `Vec(0, 0, 1)`.

---

## swpy.com

Every SOLIDWORKS object returned to Python is wrapped in a `Com` proxy.

### `class Com(raw, prefer=None)`
Proxy over one COM object. It detects which of ~50 common SOLIDWORKS interfaces the object implements
and forwards attribute access to all of them (`prefer` is tried first). Results of calls and properties
are wrapped again with `auto`; arguments are converted with `unwrap`.

| Member | Description |
|---|---|
| `obj.<api member>` | Any property or method of the detected interfaces |
| `interfaces` | Tuple of detected interface names, in lookup order |
| `raw` | The underlying COM object |
| `as_(interface)` | Proxy that prefers `interface` (also interfaces outside the built-in list) |
| `==`, `hash()` | By COM identity: two proxies of the same SOLIDWORKS object are equal |
| `dir(obj)` | All member names (used by completion) |

### `auto(value)`
API result -> Python: COM objects become `Com`, .NET arrays become lists (primitive arrays become
`NetList`), tuples (out-parameters) are converted element-wise.

### `unwrap(value)`
Python argument -> API: `Com` -> raw object, `NetList` -> its original array type, lists/tuples -> a
typed .NET array inferred from the elements (objects, `bool`, `int`, `float`, `str`).

### `class NetList(list)`
A list from a primitive .NET array that remembers its `element_type`, so passing it back recreates
exactly that array (e.g. persistent reference IDs as `byte[]`).

### `is_com(value)`, `interfaces_of(raw, detect=True)`, `identity(raw)`
Low-level helpers: whether a value is a COM object; the interfaces it implements (curated list first,
then - with `detect` - every interface of every API library); its COM identity (an integer, equal for
all references to the same object).

### Interface names
Interfaces of the core library are named plainly (`"IFace2"`); interfaces of other API libraries are
qualified with the library (`"swmotionstudy.IMotionStudyManager"`). `Com.interfaces`, `as_()` and
`prefer=` all use these names.

| Function | Description |
|---|---|
| `detect_all(raw)` | Comma-separated interfaces from the full cross-library check (cached per COM class) |
| `caster(name)` | The typed-view function for an interface name |
| `net_type(name)` | The .NET interop type of an interface name, or `None` |
| `qualified_name(net_type)` | Interface name of a .NET interop type (`"IFace2"`, `"cosworks.ICWStudy"`), or `None` |
| `library_casts(library)` | The generated cast class of a library (loads its interop assembly) |

### `observed_returns`
`{(interface, member): interfaces}` - what API members declared as returning `object` actually returned
when code last ran. Used by editor completion.

### `CANDIDATES`
The interface names `Com` detects automatically, most specific first.

---

## Interop: `sldworks` and `swconst`

### `sldworks.<Interface>(obj)`
Typed cast for any interface of `SolidWorks.Interop.sldworks`: returns a `Com` proxy that prefers that
interface, or `None` for `None`. `dir(sldworks)` lists all ~930 interfaces.

### `swconst`
All SOLIDWORKS API enumerations as classes of integer constants, e.g.
`swconst.swDocumentTypes_e.swDocPART == 1`. Generated from the interop assembly
(`tools/gen_interop.py`). Every enum class also has `name(value)` (reverse lookup) and `items()`.

### Other API libraries: `cosworks`, `swmotionstudy`, `swdimxpert`, ...
One object per library ([list](05-solidworks-api.md#other-api-libraries)), predefined in scripts and in
`swpy._interop.libraries`. `<library>.<Interface>(obj)` casts (returns a `Com` preferring
`"<library>.<Interface>"`, `None` for `None`); `<library>.<Enum_e>` are its constants (generated into
`swpy.libs.<library>`). `swpy.libs.LIBRARIES` holds the metadata (title, namespace, counts).

---

## swpy.events

See [Events](10-events.md). `on` and `off` are predefined in scripts.

| Name | Description |
|---|---|
| `on(source, event, fn=None)` | Subscribe `fn` to `event` (API name or alias) of a SOLIDWORKS object; returns a `Handler`. Without `fn`: a decorator. Raises `ValueError` for unknown events or a `None` source |
| `off(handler_or_fn)` | Remove a `Handler`, or all handlers using a function; returns how many |
| `available(source)` | Aliases and API event names the source supports |
| `handlers(session=None)` | Active handlers |
| `remove_session(session)` | Remove a session's handlers (done by Reset) |
| `remove_all()` | Remove every handler (done when the add-in unloads) |
| `ALIASES` | `{alias: (API event names ...)}` |
| `MAX_ERRORS` | Consecutive failures after which a handler is switched off (5) |

### `class Handler`
Returned by `on`. Attributes: `source`, `event`, `api_event`, `fn`, `session`, `active`, `calls`,
`errors`; `remove()` unsubscribes (idempotent).

---

## swpy.ui

Predefined in scripts as `ui`. See [Script buttons and user interaction](11-scripts-and-ui.md).

| Name | Description |
|---|---|
| `progress(items_or_total=None, title="SwPy", total=None)` | SOLIDWORKS progress bar. Iterate over items, or use as a context manager with `step(n=1, title=None)`; `position` holds the progress. Esc raises `Cancelled` at the next step |
| `Cancelled` | Exception raised when the user pressed Esc |
| `message(text, icon="info", buttons="ok")` | Message box; icon `info`/`warning`/`error`/`question`, buttons `ok`/`ok_cancel`/`yes_no`/`yes_no_cancel`/`retry_cancel`; returns `'ok'`, `'cancel'`, `'yes'`, `'no'`, `'retry'` ... |
| `ask(text, cancel=False)` | Yes/No question -> `True`/`False` (`None` for Cancel with `cancel=True`) |
| `prompt(text, default="", title="SwPy")` | One line of text input; `None` if cancelled |
| `open_file(filter, title, folder)` / `open_files(...)` | File-open dialog -> path / list of paths |
| `save_file(filter, title, name, folder)` | File-save dialog -> path or `None` |
| `folder(title, start)` | Folder picker -> path or `None` |
| `status(text)` | Text in the SOLIDWORKS status bar |

---

## swpy.packages

| Function | Description |
|---|---|
| `requirements(code)` | Requirement strings from all `# r:` lines of a script |
| `ensure(reqs, log=print)` | Install the missing ones with pip into `site_dir()`; returns the list installed. Raises `RuntimeError` with pip's output on failure |
| `satisfied(req)` | Whether a requirement is installed (exact `==` pins are compared, other specifiers only check presence) |
| `site_dir()` | `%LOCALAPPDATA%\SwPy\site-packages\py3.X`, created and added to `sys.path` |
| `python_exe()` / `pip_command()` | The runtime's `python.exe` and the pip command used for installs |

---

## swpy.client

Remote control from another Python process (needs `pywin32`). See [Remote control](07-remote-control.md).

### `connect(session="client", start=False, timeout=300)`
Attach to the running SOLIDWORKS (`start=True`: launch it and wait up to `timeout` seconds), load the
SwPy add-in if needed, and return a `Client`.

### `class Client`

| Member | Description |
|---|---|
| `eval(expr, session=None)` / `client(expr)` | Evaluate; JSON-able values are returned as Python values, others as their `repr` |
| `exec(code, session=None)` | Run statements; returns captured stdout |
| `run(code, session=None)` | Raw result dict: `ok`, `stdout`, `result`, `value` (if JSON-able), `error` |
| `reset(session=None)` | Clear the session's variables |
| `version()` | Add-in version string |
| `sw` | The pywin32 `SldWorks.Application` object |
| `session` | Default session name |

### `class SwPyError(RuntimeError)`
Raised by `exec`/`eval` when the code failed inside SOLIDWORKS; the message is the remote traceback.

### `addin_dll()`
Path of the registered add-in DLL (per-user or per-machine registration).

### `PROGID`, `CLSID`
COM identifiers of the add-in: `"SwPy.AddIn"`, `"{10C1BD59-4D33-4878-BDDA-DE5D879D6213}"`.
