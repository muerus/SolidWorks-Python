using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using SwPy.Scripting;

namespace SwPy.Ui
{
    /// <summary>
    /// Task pane UI: tabbed script editor, output log and a REPL line sharing one Python session.
    /// COM-visible so SOLIDWORKS can host it through ITaskpaneView.AddControl, which gives proper
    /// keyboard routing (handle-hosted controls lose keys to SOLIDWORKS accelerators).
    /// </summary>
    [ComVisible(true)]
    [Guid("8278dec1-4a35-431c-9322-d96e5845272f")]
    [ProgId(ProgIdName)]
    public class EditorPane : UserControl
    {
        public const string ProgIdName = "SwPy.EditorPane";
        internal const string Session = "editor";

        private static readonly Font CodeFont = new Font("Consolas", 10f);
        private static readonly Regex TracebackLine = new Regex(@"File ""<swpy>"", line (\d+)");

        /// <summary>One editor tab: a file, or an untitled buffer auto-saved to a backup file (hot exit).</summary>
        private sealed class Doc
        {
            public ICodeEditor Editor;
            public TabPage Page;
            public string Path;      // null for untitled
            public string Backup;    // untitled only
            public bool Untitled => Path == null;
            public string Title => Untitled ? System.IO.Path.GetFileNameWithoutExtension(Backup) : System.IO.Path.GetFileName(Path);
        }

        private readonly EditorSettings _settings = EditorSettings.Load();
        private readonly List<Doc> _docs = new List<Doc>();
        private readonly TabControl _tabs;
        private readonly FindBar _findBar;
        private readonly RichTextBox _output;
        private readonly TextBox _repl;
        private readonly Label _prompt;
        private readonly ToolStripStatusLabel _status, _caret, _python;
        private readonly ToolStripSplitButton _open;
        private readonly ToolStripDropDownButton _scriptsMenu;
        private readonly ToolStrip _tools;
        private readonly StatusStrip _statusBar;
        private readonly List<string> _history = new List<string>();
        private readonly Timer _backupTimer = new Timer { Interval = 1500 };
        private int _historyIndex;
        private Theme _theme;
        private EditorServices _services;
        private bool _restoring;

        /// <summary>Runs code in a session (session, code, stream output live); set by the add-in.</summary>
        internal Func<string, string, bool, string, ExecResult> Runner { get; set; }

        /// <summary>Rebuild the SwPy toolbar after scripts changed; set by the add-in.</summary>
        internal Action RefreshScriptCommands { get; set; }

        /// <summary>Clears a session; set by the add-in.</summary>
        internal Action<string> Resetter { get; set; }

        /// <summary>Completion, signatures, hover, syntax check; set by the add-in.</summary>
        internal EditorServices Services
        {
            get => _services;
            set
            {
                _services = value;
                foreach (var d in _docs) d.Editor.Services = value;
            }
        }

        internal static string ScratchFile { get; } = Path.Combine(EditorSettings.Dir, "scratch.py");
        private static string ScratchDir { get; } = Path.Combine(EditorSettings.Dir, "scratch");

        public EditorPane()
        {
            Dock = DockStyle.Fill;
            Font = SystemFonts.MessageBoxFont;
            _theme = Theme.Get(_settings.Theme);

            var tools = _tools = new ToolStrip { GripStyle = ToolStripGripStyle.Hidden, RenderMode = ToolStripRenderMode.System };
            tools.Items.Add(Button("▶ Run", "Run selection or whole script (F5 / Ctrl+Enter)", (s, e) => RunEditor()));
            tools.Items.Add(new ToolStripSeparator());
            tools.Items.Add(Button("New", "New script tab (Ctrl+N)", (s, e) => NewTab()));
            _open = new ToolStripSplitButton("Open") { ToolTipText = "Open a .py file (Ctrl+O); arrow: recent files" };
            _open.ButtonClick += (s, e) => OpenFile();
            _open.DropDownOpening += (s, e) => FillRecent();
            _open.DropDownItems.Add("(none)");
            tools.Items.Add(_open);
            tools.Items.Add(Button("Save", "Save (Ctrl+S), Save As (Ctrl+Shift+S)", (s, e) => SaveFile(Active, false)));
            tools.Items.Add(Button("Find", "Find (Ctrl+F), Replace (Ctrl+H), Go to line (Ctrl+G)", (s, e) => _findBar.Open(false)));
            _scriptsMenu = new ToolStripDropDownButton("Scripts") { ToolTipText = "Run a script from the script folder" };
            _scriptsMenu.DropDownOpening += (s, e) => FillScripts();
            _scriptsMenu.DropDownItems.Add("(none)");
            tools.Items.Add(_scriptsMenu);
            tools.Items.Add(new ToolStripSeparator());
            tools.Items.Add(Button("Clear", "Clear output", (s, e) => _output.Clear()));
            tools.Items.Add(Button("Reset", "Forget all variables of this session", (s, e) => ResetSession()));
            tools.Items.Add(new ToolStripSeparator());
            tools.Items.Add(Button("Theme", "Toggle light / dark theme", (s, e) => SetTheme(_theme == Theme.Dark ? "light" : "dark")));
            tools.Items.Add(Button("?", "Keyboard shortcuts", (s, e) => ShowShortcuts()));

            _tabs = new TabControl { Dock = DockStyle.Fill, Padding = new Point(8, 3) };
            _tabs.SelectedIndexChanged += (s, e) => OnActiveTabChanged();
            _tabs.MouseUp += OnTabMouseUp;
            _findBar = new FindBar(() => Active?.Editor);
            var editorArea = new Panel { Dock = DockStyle.Fill };
            editorArea.Controls.Add(_tabs);
            editorArea.Controls.Add(_findBar);

            _output = new RichTextBox
            {
                Dock = DockStyle.Fill,
                Font = CodeFont,
                ReadOnly = true,
                WordWrap = true,
                DetectUrls = false,
                BorderStyle = BorderStyle.None,
            };
            _output.DoubleClick += OnOutputDoubleClick;

            _repl = new TextBox { Dock = DockStyle.Fill, Font = CodeFont, BorderStyle = BorderStyle.FixedSingle };
            _repl.KeyDown += ReplKeyDown;
            _repl.PreviewKeyDown += (s, e) => { if (e.KeyCode == Keys.Tab) e.IsInputKey = true; };
            _prompt = new Label { Text = ">>>", Dock = DockStyle.Left, AutoSize = true, Font = CodeFont, Padding = new Padding(2, 3, 0, 0) };
            var replRow = new Panel { Dock = DockStyle.Bottom, Height = _repl.PreferredHeight };
            replRow.Controls.Add(_repl);
            replRow.Controls.Add(_prompt);

            var bottom = new Panel { Dock = DockStyle.Fill };
            bottom.Controls.Add(_output);
            bottom.Controls.Add(replRow);

            var split = new SplitContainer { Dock = DockStyle.Fill, Orientation = Orientation.Horizontal, SplitterWidth = 5 };
            split.Panel1.Controls.Add(editorArea);
            split.Panel2.Controls.Add(bottom);

            var statusBar = _statusBar = new StatusStrip { SizingGrip = false };
            _status = new ToolStripStatusLabel("Ready") { Spring = true, TextAlign = ContentAlignment.MiddleLeft };
            _caret = new ToolStripStatusLabel("Ln 1, Col 1");
            _python = new ToolStripStatusLabel("Python: starts on first run") { ForeColor = Color.DimGray };
            statusBar.Items.AddRange(new ToolStripItem[] { _status, _caret, _python });

            Controls.Add(split);
            Controls.Add(tools);
            Controls.Add(statusBar);

            _backupTimer.Tick += (s, e) => { _backupTimer.Stop(); SaveBackups(); };
            Load += (s, e) => split.SplitterDistance = Math.Max(80, (int)(split.Height * 0.55));
            RestoreTabs();
            ApplyTheme();
        }

        private static ToolStripButton Button(string text, string tip, EventHandler click) =>
            new ToolStripButton(text, null, click) { ToolTipText = tip, DisplayStyle = ToolStripItemDisplayStyle.Text };

        private Doc Active => _tabs.SelectedIndex >= 0 && _tabs.SelectedIndex < _docs.Count ? _docs[_tabs.SelectedIndex] : null;
        private ICodeEditor ActiveEditor => Active?.Editor;

        // ---------------------------------------------------------------- tabs

        private Doc AddTab(string path, string backup, string text)
        {
            var doc = new Doc { Path = path, Backup = backup, Editor = CodeEditors.Create() };
            doc.Editor.Text = text ?? "";
            doc.Editor.ResetUndo();
            doc.Editor.SetSavePoint();
            doc.Editor.Services = _services;
            doc.Editor.ApplyTheme(_theme);
            doc.Editor.Zoom = _settings.Zoom;
            doc.Editor.WordWrap = _settings.WordWrap;
            doc.Editor.KeyDown += EditorKeyDown;
            doc.Editor.TextChanged += (s, e) => OnDocChanged(doc);
            doc.Editor.CaretMoved += (s, e) => { if (doc == Active) UpdateCaret(); };
            doc.Page = new TabPage(doc.Title) { ToolTipText = path ?? "Untitled (kept automatically)" };
            doc.Page.Controls.Add(doc.Editor.Control);
            _docs.Add(doc);
            _tabs.TabPages.Add(doc.Page);
            _tabs.SelectedTab = doc.Page;
            return doc;
        }

        private void OnDocChanged(Doc doc)
        {
            UpdateTabTitle(doc);
            if (doc.Untitled && !_restoring) { _backupTimer.Stop(); _backupTimer.Start(); }
        }

        private void UpdateTabTitle(Doc doc)
        {
            var title = doc.Title + (!doc.Untitled && doc.Editor.Modified ? " ●" : "");
            if (doc.Page.Text != title) doc.Page.Text = title;
        }

        private void OnActiveTabChanged()
        {
            UpdateCaret();
            if (_findBar.Visible) _findBar.Open(false);
            if (!_restoring) SaveSettings();
        }

        private void UpdateCaret()
        {
            var ed = ActiveEditor;
            if (ed != null) _caret.Text = $"Ln {ed.CaretLine}, Col {ed.CaretColumn}";
        }

        internal void NewTab()
        {
            Directory.CreateDirectory(ScratchDir);
            var n = 1;
            string backup;
            do backup = Path.Combine(ScratchDir, $"untitled-{n++}.py");
            while (File.Exists(backup) || _docs.Any(d => string.Equals(d.Backup, backup, StringComparison.OrdinalIgnoreCase)));
            AddTab(null, backup, "");
            SaveSettings();
            ActiveEditor?.Control.Focus();
        }

        private Doc FindDoc(string path) =>
            _docs.FirstOrDefault(d => d.Path != null && string.Equals(d.Path, path, StringComparison.OrdinalIgnoreCase));

        internal void OpenPath(string path)
        {
            var existing = FindDoc(path);
            if (existing != null)
            {
                _tabs.SelectedTab = existing.Page;
                return;
            }
            try
            {
                var text = File.ReadAllText(path);
                var active = Active;   // replace an empty, untouched untitled tab
                var reuse = active != null && active.Untitled && active.Backup != ScratchFile && active.Editor.Text.Length == 0;
                AddTab(path, null, text);
                if (reuse) CloseTab(active, true);
                _settings.AddRecent(path);
                SaveSettings();
                SetStatus("Opened " + Path.GetFileName(path));
            }
            catch (Exception ex)
            {
                Append($"Cannot open {path}: {ex.Message}\n", _theme.Error);
            }
        }

        /// <returns>false when the user cancelled.</returns>
        private bool CloseTab(Doc doc, bool force)
        {
            if (doc == null) return false;
            if (!force)
            {
                if (!doc.Untitled && doc.Editor.Modified)
                {
                    var answer = MessageBox.Show(this, $"Save changes to {doc.Title}?", "SwPy",
                        MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
                    if (answer == DialogResult.Cancel) return false;
                    if (answer == DialogResult.Yes && !SaveFile(doc, false)) return false;
                }
                else if (doc.Untitled && doc.Editor.Text.Trim().Length > 0 && doc.Backup != ScratchFile)
                {
                    var answer = MessageBox.Show(this, $"Discard {doc.Title}? It has not been saved to a file.", "SwPy",
                        MessageBoxButtons.OKCancel, MessageBoxIcon.Question);
                    if (answer != DialogResult.OK) return false;
                }
            }
            if (doc.Untitled && doc.Backup != ScratchFile)
            {
                try { File.Delete(doc.Backup); } catch (Exception ex) { Log.Error("Deleting backup failed", ex); }
            }
            var index = _docs.IndexOf(doc);
            _docs.RemoveAt(index);
            _tabs.TabPages.Remove(doc.Page);
            doc.Page.Dispose();
            if (_docs.Count == 0) AddTab(null, ScratchFile, File.Exists(ScratchFile) ? SafeRead(ScratchFile) : "");
            if (!_restoring) SaveSettings();
            return true;
        }

        private void OnTabMouseUp(object sender, MouseEventArgs e)
        {
            var index = -1;
            for (var i = 0; i < _tabs.TabCount; i++)
                if (_tabs.GetTabRect(i).Contains(e.Location)) index = i;
            if (index < 0) return;
            var doc = _docs[index];
            if (e.Button == MouseButtons.Middle) CloseTab(doc, false);
            else if (e.Button == MouseButtons.Right)
            {
                var menu = new ContextMenuStrip();
                menu.Items.Add("Close", null, (s, a) => CloseTab(doc, false));
                menu.Items.Add("Close others", null, (s, a) =>
                {
                    foreach (var other in _docs.Where(d => d != doc).ToList())
                        if (!CloseTab(other, false)) break;
                });
                if (doc.Path != null)
                {
                    menu.Items.Add(new ToolStripSeparator());
                    menu.Items.Add("Copy path", null, (s, a) => Clipboard.SetText(doc.Path));
                    menu.Items.Add("Show in Explorer", null, (s, a) => Process.Start("explorer.exe", $"/select,\"{doc.Path}\""));
                }
                menu.Show(_tabs, e.Location);
            }
        }

        private static string SafeRead(string path)
        {
            try { return File.ReadAllText(path); }
            catch (Exception ex) { Log.Error("Reading " + path + " failed", ex); return ""; }
        }

        private const string Welcome =
            "# SwPy - Python inside SOLIDWORKS. F5 / Ctrl+Enter runs the script or the selection.\n"
            + "# sw = ISldWorks, doc = active document, model = Pythonic wrapper, swconst = API constants.\n"
            + "# Ctrl+Space completes, F1 opens API help for the word under the caret, ? lists shortcuts.\n\n"
            + "print(sw.RevisionNumber())\n"
            + "doc.GetTitle() if doc else 'no document open'\n";

        private void RestoreTabs()
        {
            _restoring = true;
            try
            {
                foreach (var entry in _settings.OpenTabs.ToList())
                {
                    if (string.Equals(entry, ScratchFile, StringComparison.OrdinalIgnoreCase) || IsBackup(entry))
                    {
                        if (File.Exists(entry) || entry == ScratchFile) AddTab(null, entry, File.Exists(entry) ? SafeRead(entry) : "");
                    }
                    else if (File.Exists(entry)) AddTab(entry, null, SafeRead(entry));
                }
                if (_docs.Count == 0)
                    AddTab(null, ScratchFile, File.Exists(ScratchFile) ? SafeRead(ScratchFile) : Welcome);
                _tabs.SelectedIndex = Math.Max(0, Math.Min(_settings.ActiveTab, _docs.Count - 1));
            }
            finally
            {
                _restoring = false;
            }
            UpdateCaret();
        }

        private static bool IsBackup(string path) =>
            path.StartsWith(ScratchDir + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);

        private void SaveBackups()
        {
            foreach (var d in _docs.Where(x => x.Untitled))
            {
                try
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(d.Backup));
                    File.WriteAllText(d.Backup, d.Editor.Text, Encoding.UTF8);
                }
                catch (Exception ex)
                {
                    Log.Error("Saving " + d.Backup + " failed", ex);
                }
            }
        }

        private void SaveSettings()
        {
            _settings.OpenTabs = _docs.Select(d => d.Path ?? d.Backup).ToList();
            _settings.ActiveTab = Math.Max(0, _tabs.SelectedIndex);
            _settings.Theme = _theme.Name;
            if (ActiveEditor != null) _settings.Zoom = ActiveEditor.Zoom;
            _settings.Save();
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                try
                {
                    SaveBackups();
                    SaveSettings();
                }
                catch (Exception ex)
                {
                    Log.Error("Saving editor state failed", ex);
                }
                _backupTimer.Dispose();
            }
            base.Dispose(disposing);
        }

        // ---------------------------------------------------------------- appearance

        private void SetTheme(string name)
        {
            _theme = Theme.Get(name);
            ApplyTheme();
            SaveSettings();
        }

        private void ApplyTheme()
        {
            foreach (var d in _docs) d.Editor.ApplyTheme(_theme);
            _output.BackColor = _theme.OutputBack;
            _output.ForeColor = _theme.OutputFore;
            _repl.BackColor = _theme.Back;
            _repl.ForeColor = _theme.Fore;
            _prompt.BackColor = _theme.Back;
            _prompt.ForeColor = _theme.Echo;
            foreach (var strip in new ToolStrip[] { _tools, _statusBar })
            {
                strip.BackColor = _theme == Theme.Dark ? _theme.Margin : SystemColors.Control;
                strip.ForeColor = _theme == Theme.Dark ? _theme.Fore : SystemColors.ControlText;
            }
            _python.ForeColor = _theme.Echo;
        }

        private void ShowShortcuts()
        {
            Append(string.Join("\n", new[]
            {
                "# Keyboard shortcuts",
                "  F5 / Ctrl+Enter     run script (or selection)      Ctrl+N / Ctrl+W   new / close tab",
                "  Ctrl+Space          complete                       Ctrl+Tab          next tab",
                "  Ctrl+Shift+Space    parameter hints                Ctrl+O / Ctrl+S   open / save (Ctrl+Shift+S: save as)",
                "  F1                  SOLIDWORKS API help for word   Ctrl+F / Ctrl+H   find / replace (F3, Shift+F3)",
                "  Ctrl+/              toggle comment                 Ctrl+G            go to line",
                "  Ctrl+D              add next occurrence            Ctrl+Shift+L      select all occurrences",
                "  Alt+Up / Alt+Down   move line(s)                   Shift+Alt+Down    duplicate line(s)",
                "  Ctrl+Shift+K        delete line                    Ctrl+Click        add caret",
                "  Tab / Shift+Tab     indent / dedent selection      Alt+Drag          column selection",
                "  Ctrl+= / Ctrl+- / Ctrl+0  zoom                     Double-click a traceback line in output: jump to it",
                "  REPL: Enter runs, Up/Down history, Tab completes",
            }) + "\n", _theme.Echo);
        }

        // ---------------------------------------------------------------- running

        internal void RunEditor()
        {
            var ed = ActiveEditor;
            if (ed == null) return;
            var selection = ed.SelectedText;
            var code = string.IsNullOrEmpty(selection) ? ed.Text : selection;
            if (string.IsNullOrWhiteSpace(code)) return;
            var lineOffset = string.IsNullOrEmpty(selection) ? 0 : ed.SelectionStartLine;
            var lines = code.Split('\n').Length;
            Append($"# run {(string.IsNullOrEmpty(selection) ? Active.Title : "selection")} ({lines} line{(lines == 1 ? "" : "s")})\n", _theme.Echo);
            if (Active.Untitled) SaveBackups();
            var r = Execute(code);
            if (r != null && !r.Ok && r.Error != null)
            {
                var matches = TracebackLine.Matches(r.Error);
                if (matches.Count > 0)
                {
                    var line = int.Parse(matches[matches.Count - 1].Groups[1].Value) + lineOffset;
                    var message = r.Error.TrimEnd().Split('\n').Last().Trim();
                    ed.ShowRuntimeError(line, message);
                }
            }
        }

        internal void RunRepl(string code)
        {
            if (string.IsNullOrWhiteSpace(code)) return;
            _history.Add(code);
            _historyIndex = _history.Count;
            Append(">>> " + code + "\n", _theme.Echo);
            Execute(code);
        }

        /// <summary>Run a script file (toolbar button, Scripts menu, startup). On error the file opens in a
        /// tab with the failing line marked.</summary>
        internal ExecResult RunFile(string path)
        {
            string code;
            try
            {
                code = File.ReadAllText(path);
            }
            catch (Exception ex)
            {
                Append($"Cannot read {path}: {ex.Message}\n", _theme.Error);
                return null;
            }
            Append($"# run {Path.GetFileName(path)}\n", _theme.Echo);
            var r = Execute(code, path);
            if (r != null && !r.Ok && r.Error != null)
            {
                var pattern = new Regex("File \"" + Regex.Escape(path) + "\", line (\\d+)", RegexOptions.IgnoreCase);
                var matches = pattern.Matches(r.Error);
                if (matches.Count > 0)
                {
                    OpenPath(path);
                    ActiveEditor?.ShowRuntimeError(int.Parse(matches[matches.Count - 1].Groups[1].Value),
                        r.Error.TrimEnd().Split('\n').Last().Trim());
                }
            }
            return r;
        }

        private void FillScripts()
        {
            _scriptsMenu.DropDownItems.Clear();
            var scripts = ScriptLibrary.Scripts();
            if (scripts.Count == 0) _scriptsMenu.DropDownItems.Add(new ToolStripMenuItem("(no scripts yet)") { Enabled = false });
            foreach (var path in scripts)
                _scriptsMenu.DropDownItems.Add(new ToolStripMenuItem(ScriptLibrary.Title(path), null, (s, e) => RunFile(path))
                    { ToolTipText = ScriptLibrary.Describe(path) });
            _scriptsMenu.DropDownItems.Add(new ToolStripSeparator());
            _scriptsMenu.DropDownItems.Add(new ToolStripMenuItem("Open script folder", null, (s, e) =>
            {
                ScriptLibrary.EnsureFolder();
                Process.Start("explorer.exe", "\"" + ScriptLibrary.Folder + "\"");
            }));
            _scriptsMenu.DropDownItems.Add(new ToolStripMenuItem("Refresh SwPy toolbar", null, (s, e) => RefreshScriptCommands?.Invoke()));
        }

        private ExecResult Execute(string code, string filename = null)
        {
            if (Runner == null)
            {
                Append("Not connected to SOLIDWORKS.\n", _theme.Error);
                return null;
            }
            SetStatus("Running...");
            UseWaitCursor = true;
            ExecResult r;
            try
            {
                r = Runner(Session, code.Replace("\r\n", "\n"), true, filename);
            }
            finally
            {
                UseWaitCursor = false;
            }
            if (!r.Streamed && !string.IsNullOrEmpty(r.Stdout)) Append(r.Stdout, _theme.OutputFore);
            if (r.Result != null) Append(r.Result + "\n", _theme.Result);
            if (!r.Ok) Append(r.Error ?? "Unknown error\n", _theme.Error);
            SetStatus((r.Ok ? "Done" : "Error") + $" in {r.ElapsedMs} ms");
            UpdatePythonStatus();
            return r;
        }

        private void UpdatePythonStatus()
        {
            if (_services != null && _services.IsStarted) _python.Text = "Python: ready";
        }

        private void ResetSession()
        {
            Resetter?.Invoke(Session);
            Append("# session reset\n", _theme.Echo);
            SetStatus("Session reset");
        }

        private void SetStatus(string text)
        {
            _status.Text = text;
            _status.Owner?.Refresh();
        }

        /// <summary>Live script output (called from Python while the script runs on this thread).</summary>
        internal void StreamWrite(string text, bool error)
        {
            Append(text, error ? _theme.Error : _theme.OutputFore);
            _output.Update();   // repaint now without pumping messages (no re-entrancy)
        }

        private void Append(string text, Color color)
        {
            _output.SelectionStart = _output.TextLength;
            _output.SelectionLength = 0;
            _output.SelectionColor = color;
            _output.AppendText(text);
            _output.SelectionColor = _output.ForeColor;
            _output.ScrollToCaret();
        }

        private void OnOutputDoubleClick(object sender, EventArgs e)
        {
            var line = _output.GetLineFromCharIndex(_output.SelectionStart);
            if (line < 0 || line >= _output.Lines.Length) return;
            var m = TracebackLine.Match(_output.Lines[line]);
            if (m.Success) ActiveEditor?.GotoLine(int.Parse(m.Groups[1].Value));
        }

        // ---------------------------------------------------------------- keys

        private void EditorKeyDown(object sender, KeyEventArgs e)
        {
            var handled = true;
            if ((e.Control && e.KeyCode == Keys.Enter) || (e.KeyCode == Keys.F5 && !e.Control)) RunEditor();
            else if (e.Control && e.Shift && e.KeyCode == Keys.S) SaveFile(Active, true);
            else if (e.Control && e.KeyCode == Keys.S) SaveFile(Active, false);
            else if (e.Control && e.KeyCode == Keys.O) OpenFile();
            else if (e.Control && e.KeyCode == Keys.N) NewTab();
            else if (e.Control && e.KeyCode == Keys.W) CloseTab(Active, false);
            else if (e.Control && e.KeyCode == Keys.Tab)
                _tabs.SelectedIndex = (_tabs.SelectedIndex + (e.Shift ? _tabs.TabCount - 1 : 1)) % _tabs.TabCount;
            else if (e.Control && e.KeyCode == Keys.F) _findBar.Open(false);
            else if (e.Control && e.KeyCode == Keys.H) _findBar.Open(true);
            else if (e.KeyCode == Keys.F3) _findBar.Next(e.Shift);
            else if (e.Control && e.KeyCode == Keys.G) GoToLinePrompt();
            else if (e.KeyCode == Keys.Escape && _findBar.Visible) _findBar.Close();
            else handled = false;
            if (handled) Handled(e);
        }

        private static void Handled(KeyEventArgs e)
        {
            e.Handled = true;
            e.SuppressKeyPress = true;
        }

        private void GoToLinePrompt()
        {
            var ed = ActiveEditor;
            if (ed == null) return;
            using (var form = new Form
            {
                Text = "Go to line", FormBorderStyle = FormBorderStyle.FixedToolWindow, StartPosition = FormStartPosition.CenterParent,
                ClientSize = new Size(220, 36), KeyPreview = true, ShowInTaskbar = false,
            })
            {
                var box = new TextBox { Location = new Point(8, 8), Width = 140, Text = ed.CaretLine.ToString() };
                var ok = new Button { Text = "Go", Location = new Point(154, 6), Width = 58, DialogResult = DialogResult.OK };
                form.Controls.Add(box);
                form.Controls.Add(ok);
                form.AcceptButton = ok;
                box.SelectAll();
                if (form.ShowDialog(this) == DialogResult.OK && int.TryParse(box.Text.Trim(), out var line))
                    ed.GotoLine(line);
            }
        }

        private void ReplKeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Enter)
            {
                Handled(e);
                var code = _repl.Text;
                _repl.Clear();
                RunRepl(code);
            }
            else if (e.KeyCode == Keys.Tab)
            {
                Handled(e);
                CompleteRepl();
            }
            else if (e.KeyCode == Keys.Up && _history.Count > 0)
            {
                Handled(e);
                _historyIndex = Math.Max(0, _historyIndex - 1);
                _repl.Text = _history[_historyIndex];
                _repl.SelectionStart = _repl.TextLength;
            }
            else if (e.KeyCode == Keys.Down && _history.Count > 0)
            {
                Handled(e);
                _historyIndex = Math.Min(_history.Count, _historyIndex + 1);
                _repl.Text = _historyIndex < _history.Count ? _history[_historyIndex] : "";
                _repl.SelectionStart = _repl.TextLength;
            }
        }

        /// <summary>Tab in the REPL: insert the unique completion / common prefix, else list candidates.</summary>
        private string CompleteRepl()
        {
            var caret = _repl.SelectionStart;
            var before = _repl.Text.Substring(0, caret);
            var c = _services?.Complete(before, _repl.Text, true);
            if (c == null || c.Items.Count == 0) return "";
            var names = c.Items.Select(i => i.Key).ToList();
            var prefix = before.Substring(before.Length - c.Start);
            var common = names.Aggregate((a, b) =>
            {
                var n = 0;
                while (n < a.Length && n < b.Length && char.ToLowerInvariant(a[n]) == char.ToLowerInvariant(b[n])) n++;
                return a.Substring(0, n);
            });
            if (common.Length > prefix.Length || names.Count == 1)
            {
                var insert = names.Count == 1 ? names[0] : common;
                _repl.Text = before.Substring(0, before.Length - c.Start) + insert + _repl.Text.Substring(caret);
                _repl.SelectionStart = caret - c.Start + insert.Length;
            }
            else
            {
                Append(string.Join("  ", names.Take(80)) + (names.Count > 80 ? $"  ... ({names.Count})" : "") + "\n", _theme.Echo);
            }
            return string.Join(",", names);
        }

        // ---------------------------------------------------------------- files

        private void OpenFile()
        {
            using (var dlg = new OpenFileDialog { Filter = "Python (*.py)|*.py|All files|*.*", Multiselect = true })
            {
                var current = Active?.Path;
                if (current != null) dlg.InitialDirectory = Path.GetDirectoryName(current);
                if (dlg.ShowDialog(this) != DialogResult.OK) return;
                foreach (var f in dlg.FileNames) OpenPath(f);
            }
        }

        private void FillRecent()
        {
            _open.DropDownItems.Clear();
            var recent = _settings.Recent.Where(File.Exists).ToList();
            if (recent.Count == 0) _open.DropDownItems.Add(new ToolStripMenuItem("(no recent files)") { Enabled = false });
            foreach (var path in recent)
                _open.DropDownItems.Add(new ToolStripMenuItem(Path.GetFileName(path), null, (s, e) => OpenPath(path)) { ToolTipText = path });
        }

        /// <returns>false when cancelled or failed.</returns>
        private bool SaveFile(Doc doc, bool saveAs)
        {
            if (doc == null) return false;
            var path = doc.Path;
            if (path == null || saveAs)
            {
                using (var dlg = new SaveFileDialog { Filter = "Python (*.py)|*.py", DefaultExt = "py", FileName = doc.Title + ".py" })
                {
                    if (dlg.ShowDialog(this) != DialogResult.OK) return false;
                    path = dlg.FileName;
                }
            }
            return SaveTo(doc, path);
        }

        private bool SaveTo(Doc doc, string path)
        {
            try
            {
                File.WriteAllText(path, doc.Editor.Text, new UTF8Encoding(false));
            }
            catch (Exception ex)
            {
                Append($"Cannot save {path}: {ex.Message}\n", _theme.Error);
                return false;
            }
            if (doc.Untitled && doc.Backup != ScratchFile)
            {
                try { File.Delete(doc.Backup); } catch (Exception ex) { Log.Error("Deleting backup failed", ex); }
            }
            doc.Path = path;
            doc.Backup = null;
            doc.Page.ToolTipText = path;
            doc.Editor.SetSavePoint();
            UpdateTabTitle(doc);
            _settings.AddRecent(path);
            SaveSettings();
            SetStatus("Saved " + Path.GetFileName(path));
            return true;
        }

        // ---------------------------------------------------------------- automation (tests)

        /// <summary>Drive the pane from tests. See the switch for commands; editor features via "feature".</summary>
        internal string Command(string command, string arg)
        {
            var ed = ActiveEditor;
            switch (command)
            {
                case "set_text": ed.Text = arg ?? ""; return "";
                case "get_text": return ed.Text;
                case "select": { var p = arg.Split(','); ed.Select(int.Parse(p[0]), int.Parse(p[1])); return ""; }
                case "editor": return ed.GetType().Name;
                case "run": RunEditor(); return _output.Text;
                case "repl": RunRepl(arg); return _output.Text;
                case "repl_complete": _repl.Text = arg ?? ""; _repl.SelectionStart = _repl.TextLength; return CompleteRepl() + "|" + _repl.Text;
                case "output": return _output.Text;
                case "clear": _output.Clear(); return "";
                case "reset": ResetSession(); return "";
                case "status": return _status.Text;
                case "size": return new JavaScriptSerializer().Serialize(new { Width, Height, Visible });
                case "feature": return ed.Feature(arg);
                case "service":
                {
                    var bar = arg.IndexOf('|');
                    return _services?.CallJson(arg.Substring(0, bar), arg.Substring(bar + 1)) ?? "null";
                }
                case "tabs":
                    return new JavaScriptSerializer().Serialize(new
                    {
                        titles = _docs.Select(d => d.Page.Text).ToArray(),
                        active = _tabs.SelectedIndex,
                        paths = _docs.Select(d => d.Path ?? d.Backup).ToArray(),
                    });
                case "new_tab": NewTab(); return _tabs.SelectedIndex.ToString();
                case "open": OpenPath(arg); return _tabs.SelectedIndex.ToString();
                case "close_tab": CloseTab(Active, arg == "force"); return _docs.Count.ToString();
                case "select_tab": _tabs.SelectedIndex = int.Parse(arg); return "";
                case "save_as": return SaveTo(Active, arg).ToString();
                case "modified": return ed.Modified.ToString();
                case "find": return ed.CountMatches(arg, new FindOptions()) + ":" + ed.Find(arg, new FindOptions(), false);
                case "replace_all":
                {
                    var bar = arg.IndexOf('|');
                    return ed.ReplaceAll(arg.Substring(0, bar), arg.Substring(bar + 1), new FindOptions()).ToString();
                }
                case "goto": ed.GotoLine(int.Parse(arg)); return ed.CaretLine.ToString();
                case "caret": return $"{ed.CaretLine},{ed.CaretColumn}";
                case "theme": if (!string.IsNullOrEmpty(arg)) SetTheme(arg); return _theme.Name;
                case "run_file": RunFile(arg); return _output.Text;
                case "forget":   // tests: close tabs and drop recent files under a folder, so the user's state stays clean
                {
                    foreach (var d in _docs.Where(d => d.Path != null && d.Path.StartsWith(arg, StringComparison.OrdinalIgnoreCase)).ToList())
                        CloseTab(d, true);
                    var removed = _settings.Recent.RemoveAll(p => p.StartsWith(arg, StringComparison.OrdinalIgnoreCase));
                    SaveSettings();
                    return removed.ToString();
                }
                case "scripts_menu":
                    FillScripts();
                    return string.Join("|", _scriptsMenu.DropDownItems.Cast<ToolStripItem>().Select(i => i.Text));
                default: throw new ArgumentException("Unknown pane command: " + command);
            }
        }
    }
}
