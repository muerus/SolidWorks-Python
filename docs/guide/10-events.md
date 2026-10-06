# 10. Events

Run Python automatically when something happens in SOLIDWORKS: a rebuild, a save, a new selection, a
document switch. `on(source, event, handler)` subscribes; it is predefined in scripts.

```python live
log = []

def rebuilt():
    log.append(doc.GetTitle())

handle = on(doc, "rebuild", rebuilt)       # doc rebuilds -> rebuilt() runs
doc.ForceRebuild3(False)
print(log, handle)
handle.remove()
```

Or as a decorator:

```python live
@on(doc, "save")
def saved():
    print("saved", doc.GetTitle())

off(saved)                                  # remove every handler that uses this function
```

## Sources and event names

A source is any SOLIDWORKS object with events: `sw` (the application), documents (parts, assemblies,
drawings), model views and objects from other API libraries such as motion studies. The event is
either an API event name, exactly as in the API help (`RegenPostNotify2`, `FileSavePostNotify` ...),
or one of these aliases:

| Alias | Source | API event |
|---|---|---|
| `rebuild` / `before_rebuild` | document | `RegenPostNotify2` (or `RegenPostNotify`) / `RegenNotify` |
| `save`, `save_as` | document | `FileSavePostNotify`, `FileSaveAsNotify2` |
| `selection`, `clear_selection` | document | `NewSelectionNotify`, `ClearSelectionsNotify` |
| `close` | document | `DestroyNotify2` |
| `dimension` | document | `DimensionChangeNotify` |
| `add_item`, `delete_item`, `rename_item` | document | `AddItemNotify`, `DeleteItemNotify`, `RenameItemNotify` |
| `config` | document | `ActiveConfigChangePostNotify` |
| `property` | document | `AddCustomPropertyNotify` (or `ChangeCustomPropertyNotify`) |
| `active_doc`, `open`, `new`, `close_doc` | `sw` | `ActiveDocChangeNotify`, `FileOpenPostNotify`, `FileNewNotify2`, `FileCloseNotify` |
| `idle` | `sw` | `OnIdleNotify` |

List everything a source supports:

```python live
from swpy import events
print(events.available(doc)[:12])
print(len(events.available(sw)), "application events")
```

## Handlers

* A handler may take **the event's arguments** (see the API help for each event) or **none** - SwPy
  calls it the way it accepts:

  ```python live
  @on(sw, "new")
  def created(new_doc, doc_type, template):
      print("new document of type", doc_type)

  off(created)
  ```

  Arguments that are SOLIDWORKS objects arrive as typed proxies.
* The return value goes back to SOLIDWORKS if it is an `int` (some *pre*-notifications let a non-zero
  value cancel the operation); anything else returns 0.
* `print` in a handler appears in the output of the run that caused the event, or in the editor output
  when the user caused it.

## Safety

Handlers can never take SOLIDWORKS down:

* Exceptions are caught and their traceback (your code only) is printed to the editor output. After 5
  failures in a row the handler is switched off (`swpy.events.MAX_ERRORS`).
* Handlers belong to the session that created them: **Reset** removes them. When a document closes, its
  handlers are removed with it. When SOLIDWORKS unloads SwPy, every handler is detached first.

Keep handlers short - they run on the SOLIDWORKS UI thread, inside the operation that raised the event.
`idle` fires very often: do as little as possible there.

## Managing handlers

| | |
|---|---|
| `handle = on(source, event, fn)` | Subscribe; returns a `Handler` |
| `handle.remove()` / `off(handle)` | Unsubscribe |
| `off(fn)` | Remove all handlers using `fn`; returns how many |
| `swpy.events.handlers()` | Active handlers (all, or `handlers(session)`) |
| `handle.calls`, `handle.errors`, `handle.active` | Statistics |

```python live
from swpy import events
h = on(doc, "rebuild", lambda: None)
print(events.handlers())
h.remove()
```

## Example: keep a property in sync

```python
from swpy import events

def update_mass():
    props = doc.Extension.get_CustomPropertyManager("")
    props.Add3("MassKg", swconst.swCustomInfoType_e.swCustomInfoText,
               f"{model.mass['mass']:.3f}",
               swconst.swCustomPropertyAddOption_e.swCustomPropertyReplaceValue)

on(doc, "rebuild", update_mass)
```

Every rebuild now refreshes the `MassKg` property of this document, until it closes or you press
**Reset**.
