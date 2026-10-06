"""Run Python when something happens in SOLIDWORKS.

    @on(doc, "rebuild")
    def rebuilt():
        print("rebuilt", doc.GetTitle())

    handle = on(sw, "active_doc", lambda: print("switched to", sw.ActiveDoc.GetTitle()))
    handle.remove()                      # or off(handle)

Sources are SOLIDWORKS objects with events: `sw`, documents (part, assembly, drawing), model views,
motion studies ... Events are the API's own names (`RegenPostNotify2`, `FileSavePostNotify` ...; see
`available(source)`) or the friendly aliases in `ALIASES`.

Safety rules, so handlers can never take SOLIDWORKS down:
  * exceptions are caught and printed to the editor output; after `MAX_ERRORS` consecutive failures
    the handler is switched off,
  * handlers may take the event's arguments or none at all,
  * handlers are removed when their session is reset, when their document closes, and when the add-in
    unloads.
"""
import inspect
import traceback

import clr
from System.Runtime.InteropServices import ComEventInterfaceAttribute, CoClassAttribute

from swpy import com as _com

MAX_ERRORS = 5

# friendly name -> API event names, first one the source supports wins
ALIASES = {
    "rebuild": ("RegenPostNotify2", "RegenPostNotify"),
    "before_rebuild": ("RegenNotify",),
    "save": ("FileSavePostNotify",),
    "save_as": ("FileSaveAsNotify2", "FileSaveAsNotify"),
    "selection": ("NewSelectionNotify",),
    "clear_selection": ("ClearSelectionsNotify",),
    "close": ("DestroyNotify2", "DestroyNotify"),
    "dimension": ("DimensionChangeNotify",),
    "add_item": ("AddItemNotify",),
    "delete_item": ("DeleteItemNotify",),
    "rename_item": ("RenameItemNotify",),
    "config": ("ActiveConfigChangePostNotify",),
    "property": ("AddCustomPropertyNotify", "ChangeCustomPropertyNotify"),
    "active_doc": ("ActiveDocChangeNotify",),
    "open": ("FileOpenPostNotify",),
    "new": ("FileNewNotify2",),
    "close_doc": ("FileCloseNotify",),
    "idle": ("OnIdleNotify",),
}

# reload-safe registries: live subscriptions must survive `reload_package()`
_handlers = globals().get("_handlers", [])            # live Handler objects
_watchers = globals().get("_watchers", {})            # COM identity of a document -> internal close watcher


# ---------------------------------------------------------------- event discovery (cached reflection)

_EVENT_TYPES = {}         # interface name -> [(coclass name, {event name: EventInfo})]


def _coclasses_for(interface_name):
    """Coclass interfaces (e.g. PartDoc) that extend `interface_name` (e.g. IPartDoc) and carry events."""
    if interface_name in _EVENT_TYPES:
        return _EVENT_TYPES[interface_name]
    found = []
    net = _com.net_type(interface_name)
    if net is not None:
        for t in net.Assembly.GetExportedTypes():
            if not t.IsInterface or not t.IsDefined(clr.GetClrType(CoClassAttribute), False):
                continue
            bases = list(t.GetInterfaces())
            if not any(b == net for b in bases):
                continue
            events = {e.Name: e for b in bases if b.IsDefined(clr.GetClrType(ComEventInterfaceAttribute), False)
                      for e in b.GetEvents()}
            if events:
                found.append((_com.qualified_name(t), events))
    _EVENT_TYPES[interface_name] = found
    return found


def _resolve(source, event):
    """(coclass name, API event name) for an event on a Com source, or raise."""
    names = ALIASES.get(event, (event,))
    for interface in source.interfaces:
        for coclass, events in _coclasses_for(interface):
            for name in names:
                if name in events:
                    return coclass, name
    raise ValueError(f"{source!r} has no event {event!r}; see swpy.events.available(source)")


def available(source):
    """Event names (API names and the aliases that apply) a SOLIDWORKS object supports."""
    source = _com.Com(source) if type(source).__name__ != "Com" else source
    api = sorted({e for i in source.interfaces for _, events in _coclasses_for(i) for e in events})
    aliases = sorted(a for a, names in ALIASES.items() if any(n in api for n in names))
    return aliases + api


# ---------------------------------------------------------------- handlers

class Handler:
    """A subscription returned by `on`. `remove()` unsubscribes (idempotent)."""

    def __init__(self, source, event, api_event, coclass, fn, session):
        self.source, self.event, self.api_event, self.fn, self.session = source, event, api_event, fn, session
        self.errors = 0
        self.calls = 0
        self.active = False
        self._view = _com.caster(coclass)(source.raw)   # typed view whose events we subscribe
        self._delegate = self._invoke                    # keep the bound method alive while subscribed

    def __repr__(self):
        state = "active" if self.active else "removed"
        return f"<Handler {self.event!r} on {self.source!r} ({state}, {self.calls} calls)>"

    def _subscribe(self):
        binding = getattr(self._view, self.api_event)
        binding += self._delegate
        self.active = True

    def remove(self):
        if not self.active:
            return
        self.active = False
        try:
            binding = getattr(self._view, self.api_event)
            binding -= self._delegate
        except Exception:
            pass                                          # the object may already be gone
        if self in _handlers:
            _handlers.remove(self)

    def _invoke(self, *args):
        if not self.active:
            return 0
        self.calls += 1
        from swpy import _host
        try:
            with _host.event_output():
                result = _call_flexibly(self.fn, [_com.auto(a) for a in args])
            self.errors = 0
            return result if isinstance(result, int) and not isinstance(result, bool) else 0
        except BaseException as e:   # never let an exception reach SOLIDWORKS
            self.errors += 1
            message = f"# event {self.event!r} handler {getattr(self.fn, '__name__', self.fn)!r} failed:\n" \
                      + _user_traceback(e)
            if self.errors >= MAX_ERRORS:
                message += f"# handler switched off after {MAX_ERRORS} consecutive errors\n"
                self.remove()
            _host.report_error(message)
            return 0


def _call_flexibly(fn, args):
    """Call with the event's arguments if the handler accepts them, else without."""
    try:
        inspect.signature(fn).bind(*args)
        accepts = True
    except TypeError:
        accepts = False
    except ValueError:                                   # no signature (builtins): pass them
        accepts = True
    return fn(*args) if accepts else fn()


def _user_traceback(e):
    """Traceback of a handler error without SwPy's own frames."""
    from swpy import _host
    internal = (__file__, _host.__file__)
    tb = e.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename in internal:
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(e), e, tb, chain=False))


def on(source, event, fn=None):
    """Subscribe `fn` to `event` of `source`; returns a Handler. Without `fn`, returns a decorator."""
    if fn is None:
        return lambda f: (on(source, event, f), f)[1]
    if source is None:
        raise ValueError("on(): source is None (no active document?)")
    source = source if type(source).__name__ == "Com" else _com.Com(source)
    coclass, api_event = _resolve(source, event)
    from swpy import _host
    handler = Handler(source, event, api_event, coclass, fn, _host.current_session())
    handler._subscribe()
    _handlers.append(handler)
    if api_event not in ALIASES["close"]:
        _watch_close(source)
    return handler


def off(handler_or_fn):
    """Remove a Handler, or every handler registered with this function."""
    if isinstance(handler_or_fn, Handler):
        handler_or_fn.remove()
        return 1
    matches = [h for h in list(_handlers) if h.fn is handler_or_fn]
    for h in matches:
        h.remove()
    return len(matches)


def handlers(session=None):
    """Active handlers (of one session, or all)."""
    return [h for h in _handlers if session is None or h.session == session]


def _watch_close(source):
    """Drop a document's handlers when it closes (one internal watcher per document)."""
    key = _com.identity(source.raw)
    if key in _watchers:
        return
    try:
        coclass, api_event = _resolve(source, "close")
    except ValueError:
        return                                            # not a document: nothing to watch
    watcher = Handler(source, "close", api_event, coclass, lambda: _closed(key), session=None)
    watcher._subscribe()
    _watchers[key] = watcher


def _closed(key):
    for h in [h for h in _handlers if _com.identity(h.source.raw) == key]:
        h.remove()
    watcher = _watchers.pop(key, None)
    if watcher is not None:
        watcher.remove()


def remove_session(session):
    """Remove all handlers registered from a session (called by Reset)."""
    for h in [h for h in _handlers if h.session == session]:
        h.remove()


def remove_all():
    """Remove every handler and watcher (add-in unload). Returns how many handlers were active."""
    count = len(_handlers)
    for h in list(_handlers):
        h.remove()
    for key in list(_watchers):
        _watchers.pop(key).remove()
    return count
