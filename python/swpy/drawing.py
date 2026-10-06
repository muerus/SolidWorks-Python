"""Drawings and file export. Used through `Model` methods.

    drawing = model.create_drawing()              # standard 3 views of a saved part/assembly
    drawing.export(r"C:\\out\\bracket.pdf")       # all sheets
    model.export(r"C:\\out\\bracket.step")        # format from the extension
"""
import os

from swpy import swconst as _c
from swpy.build import FeatureError

_SAVE_ERRORS = _c.swFileSaveError_e.items()


def _drawing(model):
    if "IDrawingDoc" not in model.doc.interfaces:
        raise TypeError(f"{model!r} is not a drawing")
    return model.doc.as_("IDrawingDoc")


def create_drawing(model, template=None, views="standard"):
    """New drawing of this (saved) part or assembly. views: 'standard' (front/top/right, third angle),
    'first_angle', a list of named views like ['*Front', '*Isometric'], or None. Returns a Model."""
    from swpy import _host
    from swpy.model import Model
    path = model.doc.GetPathName()
    if not path:
        raise FeatureError("save the model before creating a drawing of it")
    sw = _host._sw
    template = template or sw.GetUserPreferenceStringValue(
        _c.swUserPreferenceStringValue_e.swDefaultTemplateDrawing)
    doc = sw.NewDocument(template, 0, 0, 0)
    if doc is None:
        raise FeatureError(f"cannot create a drawing from template {template!r}")
    drawing = Model(doc)
    drw = _drawing(drawing)
    if views == "standard":
        ok = drw.Create3rdAngleViews2(path)
    elif views == "first_angle":
        ok = drw.Create1stAngleViews2(path)
    elif views:
        ok = all(add_view(drawing, path, name, (0.1 + 0.12 * i, 0.15)) for i, name in enumerate(views))
    else:
        ok = True
    if not ok:
        raise FeatureError(f"creating drawing views of {os.path.basename(path)} failed")
    return drawing


def add_view(model, model_path, view="*Front", at=(0.1, 0.1)):
    """Insert a named model view ('*Front', '*Top', '*Isometric' ...) at a sheet position (m)."""
    v = _drawing(model).CreateDrawViewFromModelView3(model_path, view, at[0], at[1], 0)
    if v is None:
        raise FeatureError(f"inserting view {view!r} failed")
    return v


def sheets(model):
    """Sheet names of a drawing."""
    return list(_drawing(model).GetSheetNames() or [])


def views(model):
    """Drawing views (IView) of the active sheet, without the sheet itself."""
    view = _drawing(model).GetFirstView()          # the sheet
    out = []
    view = view.GetNextView() if view is not None else None
    while view is not None:
        out.append(view)
        view = view.GetNextView()
    return out


def export(model, path, all_sheets=True):
    """Save a copy in the format given by the extension (.step .x_t .igs .stl .pdf .dxf .dwg .png .jpg
    .3mf .sldprt ...). Drawings export all sheets to PDF by default. Returns the path."""
    from swpy import _host
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = None
    if path.lower().endswith(".pdf") and "IDrawingDoc" in model.doc.interfaces:
        data = _host._sw.GetExportFileData(_c.swExportDataFileType_e.swExportPdfData)
        which = _c.swExportDataSheetsToExport_e
        data.SetSheets(which.swExportData_ExportAllSheets if all_sheets else which.swExportData_ExportCurrentSheet, None)
    options = _c.swSaveAsOptions_e.swSaveAsOptions_Silent | _c.swSaveAsOptions_e.swSaveAsOptions_Copy
    ok, errors, _ = model.doc.Extension.SaveAs(path, _c.swSaveAsVersion_e.swSaveAsCurrentVersion, options, data, 0, 0)
    if not ok:
        reasons = [k for k, v in _SAVE_ERRORS.items() if errors & v] or [str(errors)]
        raise FeatureError(f"export to {os.path.basename(path)} failed: {', '.join(reasons)}")
    return path


def save(model, path=None):
    """Save the document (to path: save as, the document then refers to that file). Returns the path."""
    options = _c.swSaveAsOptions_e.swSaveAsOptions_Silent
    if path:
        path = os.path.abspath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ok, errors, _ = model.doc.Extension.SaveAs(path, _c.swSaveAsVersion_e.swSaveAsCurrentVersion, options, None, 0, 0)
    else:
        if not model.doc.GetPathName():
            raise FeatureError("the document was never saved: pass a path")
        ok, errors, _ = model.doc.Save3(options, 0, 0)
    if not ok:
        reasons = [k for k, v in _SAVE_ERRORS.items() if errors & v] or [str(errors)]
        raise FeatureError(f"save failed: {', '.join(reasons)}")
    return model.doc.GetPathName()
