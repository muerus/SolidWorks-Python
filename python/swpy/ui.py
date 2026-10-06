"""Talk to the user from scripts: progress bar (Esc cancels), messages, questions, text input, file and
folder dialogs, status bar. Predefined in scripts as `ui`.

    for part in ui.progress(paths, "Exporting"):     # Esc in SOLIDWORKS stops the loop
        export(part)
    if ui.ask("Overwrite existing files?"):
        ...
    name = ui.prompt("Feature name", "Boss-Extrude1")
    path = ui.open_file("Parts (*.sldprt)|*.sldprt")
"""
import clr as _clr

_clr.AddReference("System.Windows.Forms")
_clr.AddReference("System.Drawing")
import System as _System  # noqa: E402
from System.Windows import Forms as _Forms  # noqa: E402

from swpy import swconst as _swconst  # noqa: E402


class Cancelled(Exception):
    """Raised by `progress` when the user presses Esc."""


def _sw():
    from swpy import _host
    if _host._sw is None:
        raise RuntimeError("not running inside SOLIDWORKS")
    return _host._sw


# ---------------------------------------------------------------- progress

class progress:
    """SOLIDWORKS progress bar. Iterate (`for x in progress(items, "Title")`) or use as a context manager
    with `step()`. Pressing Esc raises `Cancelled` at the next step."""

    def __init__(self, items_or_total=None, title="SwPy", total=None):
        if isinstance(items_or_total, int):
            self.items, self.total = None, items_or_total
        else:
            self.items = items_or_total
            self.total = total if total is not None else (len(items_or_total) if hasattr(items_or_total, "__len__") else 0)
        self.title = title
        self.position = 0
        self._bar = None

    def __enter__(self):
        ok, bar = _sw().GetUserProgressBar(None)
        if ok and bar is not None:
            self._bar = bar
            bar.Start(0, max(1, self.total), self.title)
        return self

    def __exit__(self, *exc):
        if self._bar is not None:
            self._bar.End()
            self._bar = None
        return False

    def step(self, n=1, title=None):
        """Advance by n (and optionally change the title). Raises Cancelled if the user pressed Esc."""
        self.position += n
        if self._bar is None:
            return
        if title is not None:
            self._bar.UpdateTitle(title)
        result = self._bar.UpdateProgress(min(self.position, max(1, self.total)))
        if result == _swconst.swUpdateProgressError_e.swUpdateProgressError_UserCancel:
            raise Cancelled(f"{self.title}: cancelled by the user")

    def __iter__(self):
        if self.items is None:
            raise TypeError("progress(total) is not iterable; pass the items or use step()")
        with self:
            for item in self.items:
                yield item
                self.step()


# ---------------------------------------------------------------- messages

_ICONS = {"info": _swconst.swMessageBoxIcon_e.swMbInformation, "warning": _swconst.swMessageBoxIcon_e.swMbWarning,
          "error": _swconst.swMessageBoxIcon_e.swMbStop, "question": _swconst.swMessageBoxIcon_e.swMbQuestion}
_BUTTONS = {"ok": _swconst.swMessageBoxBtn_e.swMbOk, "ok_cancel": _swconst.swMessageBoxBtn_e.swMbOkCancel,
            "yes_no": _swconst.swMessageBoxBtn_e.swMbYesNo, "yes_no_cancel": _swconst.swMessageBoxBtn_e.swMbYesNoCancel,
            "retry_cancel": _swconst.swMessageBoxBtn_e.swMbRetryCancel}
_RESULTS = {v: k[len("swMbHit"):].lower() for k, v in _swconst.swMessageBoxResult_e.items().items()}


def message(text, icon="info", buttons="ok"):
    """SOLIDWORKS message box. icon: info/warning/error/question; buttons: ok/ok_cancel/yes_no/
    yes_no_cancel/retry_cancel. Returns the button pressed: 'ok', 'cancel', 'yes', 'no', 'retry'."""
    result = _sw().SendMsgToUser2(str(text), _ICONS[icon], _BUTTONS[buttons])
    return _RESULTS.get(result, str(result))


def ask(text, cancel=False):
    """Yes/No question -> True/False (None for Cancel when cancel=True)."""
    answer = message(text, "question", "yes_no_cancel" if cancel else "yes_no")
    return {"yes": True, "no": False}.get(answer)


def status(text):
    """Show text in the SOLIDWORKS status bar."""
    _sw().Frame().SetStatusBarText(str(text))


# ---------------------------------------------------------------- dialogs (WinForms, owned by SOLIDWORKS)

def _owner():
    """The SOLIDWORKS main window, so dialogs are modal to it and stay on top."""
    try:
        from SwPy.Ui import WindowHandle
        return WindowHandle(int(_sw().Frame().GetHWndx64()))
    except Exception:
        return None


def _show(dialog):
    owner = _owner()
    return dialog.ShowDialog(owner) if owner is not None else dialog.ShowDialog()


def prompt(text, default="", title="SwPy"):
    """Ask for a line of text. Returns the text, or None if cancelled."""
    form = _Forms.Form()
    form.Text = title
    form.FormBorderStyle = _Forms.FormBorderStyle.FixedDialog
    form.StartPosition = _Forms.FormStartPosition.CenterParent
    form.MinimizeBox = form.MaximizeBox = form.ShowInTaskbar = False
    form.ClientSize = _System.Drawing.Size(360, 96)
    label = _Forms.Label()
    label.Text, label.AutoSize, label.Location = str(text), True, _System.Drawing.Point(10, 10)
    box = _Forms.TextBox()
    box.Text, box.Location, box.Width = str(default), _System.Drawing.Point(10, 32), 340
    ok, cancel = _Forms.Button(), _Forms.Button()
    ok.Text, ok.DialogResult, ok.Location = "OK", _Forms.DialogResult.OK, _System.Drawing.Point(194, 62)
    cancel.Text, cancel.DialogResult, cancel.Location = "Cancel", _Forms.DialogResult.Cancel, _System.Drawing.Point(275, 62)
    for c in (label, box, ok, cancel):
        form.Controls.Add(c)
    form.AcceptButton, form.CancelButton = ok, cancel
    box.SelectAll()
    try:
        return box.Text if _show(form) == _Forms.DialogResult.OK else None
    finally:
        form.Dispose()


def open_file(filter="All files (*.*)|*.*", title="Open", folder=None):
    """File-open dialog. filter: 'Parts (*.sldprt)|*.sldprt|All files|*.*'. Returns a path or None."""
    paths = _open(filter, title, folder, False)
    return paths[0] if paths else None


def open_files(filter="All files (*.*)|*.*", title="Open", folder=None):
    """Multi-select file-open dialog. Returns a list of paths (empty if cancelled)."""
    return _open(filter, title, folder, True)


def _open(filter, title, folder, multi):
    dialog = _Forms.OpenFileDialog()
    dialog.Filter, dialog.Title, dialog.Multiselect = filter, title, multi
    if folder:
        dialog.InitialDirectory = folder
    try:
        return list(dialog.FileNames) if _show(dialog) == _Forms.DialogResult.OK else []
    finally:
        dialog.Dispose()


def save_file(filter="All files (*.*)|*.*", title="Save as", name="", folder=None):
    """File-save dialog (asks before overwriting). Returns a path or None."""
    dialog = _Forms.SaveFileDialog()
    dialog.Filter, dialog.Title, dialog.FileName = filter, title, name
    if folder:
        dialog.InitialDirectory = folder
    try:
        return dialog.FileName if _show(dialog) == _Forms.DialogResult.OK else None
    finally:
        dialog.Dispose()


def folder(title="Select a folder", start=None):
    """Folder picker. Returns a path or None."""
    dialog = _Forms.FolderBrowserDialog()
    dialog.Description = title
    if start:
        dialog.SelectedPath = start
    try:
        return dialog.SelectedPath if _show(dialog) == _Forms.DialogResult.OK else None
    finally:
        dialog.Dispose()
