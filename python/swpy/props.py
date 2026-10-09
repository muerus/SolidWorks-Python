"""Custom properties of a document or configuration. Used through `model.props`.

    model.props["PartNo"] = "P-100"                 # str -> Text
    model.props["Qty"] = 4                          # int / float -> Number
    model.props["Purchased"] = True                 # bool -> Yes or no
    model.props["Released"] = datetime.date.today() # date -> Date
    model.props.link("Weight", "SW-Mass")           # linked to a system property or dimension
    model.props["Weight"]                           # '0.13' (resolved value, always str)
    model.props.config("Default")["Finish"] = "Anodized"
"""
import datetime
import math
import numbers
import os
from collections.abc import MutableMapping
from decimal import Decimal

from swpy import swconst as _c

_T = _c.swCustomInfoType_e
KINDS = {
    _T.swCustomInfoText: "text",
    _T.swCustomInfoNumber: "number",
    _T.swCustomInfoDouble: "number",
    _T.swCustomInfoYesOrNo: "yesno",
    _T.swCustomInfoDate: "date",
}
_ADD = _c.swCustomPropertyAddOption_e
_NOT_PRESENT = _c.swCustomInfoGetResult_e.swCustomInfoGetResult_NotPresent
_ADD_ERRORS = {v: k.replace("swCustomInfoAddResult_", "") for k, v in _c.swCustomInfoAddResult_e.items().items()}
_DELETE = _c.swCustomInfoDeleteResult_e
_FILE_EXT = {"IPartDoc": ".SLDPRT", "IAssemblyDoc": ".SLDASM", "IDrawingDoc": ".SLDDRW"}


def _number(value):
    """SOLIDWORKS Number properties: integers as Number, decimals as Double, never exponents ('1e-3'
    makes a broken property). Double keeps 6 decimals in the expression."""
    if isinstance(value, numbers.Integral):
        return _T.swCustomInfoNumber, str(int(value))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"custom property numbers must be finite, not {value}")
    if value == int(value) and abs(value) < 1e15:
        return _T.swCustomInfoNumber, str(int(value))
    return _T.swCustomInfoDouble, format(Decimal(repr(value)), "f")


def _encode(value, kind=None):
    """(swCustomInfoType_e, text) for a Python value, optionally forced to kind."""
    if kind is None:
        if isinstance(value, bool):
            kind = "yesno"
        elif isinstance(value, numbers.Real):
            kind = "number"
        elif isinstance(value, datetime.date):
            kind = "date"
        elif isinstance(value, str):
            kind = "text"
        else:
            raise TypeError(f"custom property values are str, int, float, bool or date, not {type(value).__name__}")
    if kind == "text":
        return _T.swCustomInfoText, str(value)
    if kind == "number":
        if isinstance(value, str):
            try:
                value = Decimal(value.strip())
            except ArithmeticError:
                raise ValueError(f"not a number: {value!r}") from None
            value = int(value) if value == value.to_integral_value() else float(value)
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"number property needs a number, not {value!r}")
        return _number(value)
    if kind == "yesno":
        if isinstance(value, str) and value.strip().lower() in ("yes", "no"):
            value = value.strip().lower() == "yes"
        if not isinstance(value, bool):
            raise TypeError(f"yes/no property needs True/False or 'Yes'/'No', not {value!r}")
        # SOLIDWORKS rejects the literal "No" for new properties; any non-yes text stores "No"
        return _T.swCustomInfoYesOrNo, "Yes" if value else "0"
    if kind == "date":
        if isinstance(value, datetime.datetime):
            value = value.date()
        if isinstance(value, str):
            value = datetime.date.fromisoformat(value.strip())
        if not isinstance(value, datetime.date):
            raise TypeError(f"date property needs a date or 'YYYY-MM-DD', not {value!r}")
        return _T.swCustomInfoDate, value.isoformat()
    raise ValueError(f"unknown property kind {kind!r} (use 'text', 'number', 'yesno' or 'date')")


class Props(MutableMapping):
    """Custom properties of a document (file level) or of one configuration (`props.config(name)`).

    Reading gives the resolved value as str (links such as "SW-Mass@part.SLDPRT" evaluated); `raw()`
    gives the expression. Writing picks the property type from the value: str -> Text,
    int/float -> Number, bool -> Yes or no, date -> Date. Names are case-insensitive, as in SOLIDWORKS.
    """

    def __init__(self, model, config=""):
        self._m = model
        self.config_name = config
        self._mgr()                      # fail early on unknown configurations

    def _mgr(self) -> "ICustomPropertyManager":
        doc = self._m.doc
        if not self.config_name:
            return doc.Extension.get_CustomPropertyManager("")
        cfg = doc.GetConfigurationByName(self.config_name)
        if cfg is None:
            raise KeyError(f"{self._m.title} has no configuration {self.config_name!r}")
        return cfg.CustomPropertyManager

    def _get(self, name):
        rc, raw, resolved, _, _ = self._mgr().Get6(name, False)
        if rc == _NOT_PRESENT:
            raise KeyError(name)
        return raw, resolved

    # -- mapping --------------------------------------------------------------
    def __getitem__(self, name):
        return self._get(name)[1]

    def __setitem__(self, name, value):
        self.set(name, value)

    def __delitem__(self, name):
        rc = self._mgr().Delete2(name)
        if rc == _DELETE.swCustomInfoDeleteResult_NotPresent:
            raise KeyError(name)
        if rc != _DELETE.swCustomInfoDeleteResult_OK:
            raise ValueError(f"SOLIDWORKS cannot delete custom property {name!r} (linked property)")

    def __iter__(self):
        return iter(self.names())

    def __len__(self):
        return self._mgr().Count

    def __contains__(self, name):
        return isinstance(name, str) and self._mgr().Get6(name, False)[0] != _NOT_PRESENT

    # -- extras ---------------------------------------------------------------
    def set(self, name, value, kind=None):
        """Create or update a property. kind forces the type: 'text', 'number', 'yesno' or 'date'
        (default: from the value). Changing the type of an existing property moves it to the end."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"invalid custom property name {name!r}")
        code, text = _encode(value, kind)
        mgr = self._mgr()
        if mgr.Get6(name, False)[0] == _NOT_PRESENT:
            option = _ADD.swCustomPropertyOnlyIfNew
        elif KINDS.get(mgr.GetType2(name)) == KINDS[code]:
            option = _ADD.swCustomPropertyReplaceValue
        else:
            option = _ADD.swCustomPropertyDeleteAndAdd
        rc = mgr.Add3(name, code, text, option)
        if rc != 0:
            raise ValueError(f"SOLIDWORKS rejected custom property {name!r} = {text!r} "
                             f"({_ADD_ERRORS.get(rc, rc)})")

    def link(self, name, source):
        """Text property linked to a system property ('SW-Mass', 'SW-Material', 'SW-File Name' ...) or a
        dimension ('D1@Boss-Extrude1'); reading it gives the current value."""
        if source.upper().startswith("SW-") and "@" not in source:
            path = self._m.path
            source += "@" + (os.path.basename(path) if path else self._m.title + self._file_ext())
        self.set(name, f'"{source}"', "text")

    def _file_ext(self):
        return next((ext for i, ext in _FILE_EXT.items() if i in self._m.doc.interfaces), "")

    def raw(self, name) -> str:
        """The stored expression ('"SW-Mass@part.SLDPRT"' for a link); KeyError if missing."""
        return self._get(name)[0]

    def kind(self, name) -> str:
        """'text', 'number', 'yesno' or 'date'; KeyError if missing."""
        mgr = self._mgr()
        if mgr.Get6(name, False)[0] == _NOT_PRESENT:
            raise KeyError(name)
        return KINDS.get(mgr.GetType2(name), "unknown")

    def names(self) -> list:
        """Property names in SOLIDWORKS order."""
        return list(self._mgr().GetNames() or [])

    def items(self) -> dict:
        """{name: resolved value} for every property."""
        return {n: self[n] for n in self.names()}

    def config(self, name) -> "Props":
        """Properties of a configuration (part or assembly); KeyError if it does not exist."""
        return Props(self._m, name)

    def __repr__(self):
        where = f"[{self.config_name}]" if self.config_name else ""
        return f"Props{where}({self.items()})"
