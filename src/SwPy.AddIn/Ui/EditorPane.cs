using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using SwPy.Scripting;

namespace SwPy.Ui
{
    /// <summary>
    /// Task pane UI: script editor, output log and a REPL line sharing one Python session.
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
        private static readonly Color ErrorColor = Color.FromArgb(200, 40, 40);
        private static readonly Color ResultColor = Color.FromArgb(30, 90, 170);
        private static readonly Color EchoColor = Color.Gray;

        private readonly ICodeEditor _editor;
        private readonly RichTextBox _output;
        private readonly TextBox _repl;
        private readonly ToolStripLabel _status;
        private readonly ToolStripLabel _file;
        private readonly List<string> _history = new List<string>();
        private int _historyIndex;
        private string _currentFile;

        /// <summary>Runs code in a session (session, code, stream output live); set by the add-in.</summary>
        internal Func<string, string, bool, ExecResult> Runner { get; set; }

        /// <summary>Clears a session; set by the add-in.</summary>
        internal Action<string> Resetter { get; set; }

        internal static string ScratchFile { get; } = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SwPy", "scratch.py");

        public EditorPane()
        {
            Dock = DockStyle.Fill;
            Font = SystemFonts.MessageBoxFont;

            var tools = new ToolStrip { GripStyle = ToolStripGripStyle.Hidden, RenderMode = ToolStripRenderMode.System };
            tools.Items.Add(Button("Run", "Run selection or whole script (Ctrl+Enter)", (s, e) => RunEditor()));
            tools.Items.Add(new ToolStripSeparator());
            tools.Items.Add(Button("Open", "Open a .py file (Ctrl+O)", (s, e) => OpenFile()));
            tools.Items.Add(Button("Save", "Save (Ctrl+S)", (s, e) => SaveFile(false)));
            tools.Items.Add(new ToolStripSeparator());
            tools.Items.Add(Button("Clear", "Clear output", (s, e) => _output.Clear()));
            tools.Items.Add(Button("Reset", "Forget all variables of this session", (s, e) => ResetSession()));
            _file = new ToolStripLabel("scratch") { ForeColor = Color.DimGray };
            tools.Items.Add(new ToolStripSeparator());
            tools.Items.Add(_file);

            _editor = CodeEditors.Create();
            _editor.KeyDown += EditorKeyDown;

            _output = new RichTextBox
            {
                Dock = DockStyle.Fill,
                Font = CodeFont,
                ReadOnly = true,
                WordWrap = true,
                DetectUrls = false,
                BorderStyle = BorderStyle.None,
                BackColor = Color.FromArgb(250, 250, 250),
            };

            _repl = new TextBox { Dock = DockStyle.Bottom, Font = CodeFont, BorderStyle = BorderStyle.FixedSingle };
            _repl.KeyDown += ReplKeyDown;
            var prompt = new Label { Text = ">>>", Dock = DockStyle.Left, AutoSize = true, Font = CodeFont, ForeColor = EchoColor, Padding = new Padding(2, 3, 0, 0) };
            var replRow = new Panel { Dock = DockStyle.Bottom, Height = _repl.PreferredHeight };
            replRow.Controls.Add(_repl);
            _repl.Dock = DockStyle.Fill;
            replRow.Controls.Add(prompt);

            var bottom = new Panel { Dock = DockStyle.Fill };
            bottom.Controls.Add(_output);
            bottom.Controls.Add(replRow);

            var split = new SplitContainer { Dock = DockStyle.Fill, Orientation = Orientation.Horizontal, SplitterWidth = 5 };
            split.Panel1.Controls.Add(_editor.Control);
            split.Panel2.Controls.Add(bottom);

            var statusBar = new StatusStrip { SizingGrip = false };
            _status = new ToolStripLabel("Python starts on first run");
            statusBar.Items.Add(_status);

            Controls.Add(split);
            Controls.Add(tools);
            Controls.Add(statusBar);

            Load += (s, e) => split.SplitterDistance = Math.Max(80, (int)(split.Height * 0.55));
            LoadScratch();
        }

        private static ToolStripButton Button(string text, string tip, EventHandler click) =>
            new ToolStripButton(text, null, click) { ToolTipText = tip, DisplayStyle = ToolStripItemDisplayStyle.Text };

        // ---------------------------------------------------------------- running

        internal void RunEditor()
        {
            var selection = _editor.SelectedText;
            var code = string.IsNullOrEmpty(selection) ? _editor.Text : selection;
            if (string.IsNullOrWhiteSpace(code)) return;
            var lines = code.Split('\n').Length;
            Append($"# run {(string.IsNullOrEmpty(selection) ? _file.Text : "selection")} ({lines} line{(lines == 1 ? "" : "s")})\n", EchoColor);
            Execute(code);
            SaveScratch();
        }

        internal void RunRepl(string code)
        {
            if (string.IsNullOrWhiteSpace(code)) return;
            _history.Add(code);
            _historyIndex = _history.Count;
            Append(">>> " + code + "\n", EchoColor);
            Execute(code);
        }

        private void Execute(string code)
        {
            if (Runner == null)
            {
                Append("Not connected to SOLIDWORKS.\n", ErrorColor);
                return;
            }
            SetStatus("Running...");
            UseWaitCursor = true;
            ExecResult r;
            try
            {
                r = Runner(Session, code.Replace("\r\n", "\n"), true);
            }
            finally
            {
                UseWaitCursor = false;
            }
            if (!r.Streamed && !string.IsNullOrEmpty(r.Stdout)) Append(r.Stdout, ForeColor);
            if (r.Result != null) Append(r.Result + "\n", ResultColor);
            if (!r.Ok) Append(r.Error ?? "Unknown error\n", ErrorColor);
            SetStatus((r.Ok ? "Done" : "Error") + $" in {r.ElapsedMs} ms");
        }

        private void ResetSession()
        {
            Resetter?.Invoke(Session);
            Append("# session reset\n", EchoColor);
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
            Append(text, error ? ErrorColor : ForeColor);
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

        // ---------------------------------------------------------------- editor keys

        private void EditorKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Control && e.KeyCode == Keys.Enter) { Handled(e); RunEditor(); }
            else if (e.Control && e.KeyCode == Keys.S) { Handled(e); SaveFile(false); }
            else if (e.Control && e.KeyCode == Keys.O) { Handled(e); OpenFile(); }
        }

        private static void Handled(KeyEventArgs e)
        {
            e.Handled = true;
            e.SuppressKeyPress = true;
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

        // ---------------------------------------------------------------- files

        private void LoadScratch()
        {
            try
            {
                _editor.Text = File.Exists(ScratchFile)
                    ? File.ReadAllText(ScratchFile)
                    : "# SwPy - Python inside SOLIDWORKS. Ctrl+Enter runs the script or the selection.\n"
                      + "# sw = ISldWorks, doc = active IModelDoc2, swconst = API constants.\n\n"
                      + "print(sw.RevisionNumber())\n"
                      + "doc.GetTitle() if doc else 'no document open'\n";
            }
            catch (Exception ex)
            {
                Log.Error("Loading scratch failed", ex);
            }
        }

        private void SaveScratch()
        {
            if (_currentFile != null) return;
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(ScratchFile));
                File.WriteAllText(ScratchFile, _editor.Text, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Log.Error("Saving scratch failed", ex);
            }
        }

        private void OpenFile()
        {
            using (var dlg = new OpenFileDialog { Filter = "Python (*.py)|*.py|All files|*.*" })
            {
                if (dlg.ShowDialog(this) != DialogResult.OK) return;
                _editor.Text = File.ReadAllText(dlg.FileName);
                SetCurrentFile(dlg.FileName);
            }
        }

        private void SaveFile(bool saveAs)
        {
            if (_currentFile == null || saveAs)
            {
                using (var dlg = new SaveFileDialog { Filter = "Python (*.py)|*.py", DefaultExt = "py" })
                {
                    if (dlg.ShowDialog(this) != DialogResult.OK) return;
                    SetCurrentFile(dlg.FileName);
                }
            }
            File.WriteAllText(_currentFile, _editor.Text, new UTF8Encoding(false));
            SetStatus("Saved " + Path.GetFileName(_currentFile));
        }

        private void SetCurrentFile(string path)
        {
            _currentFile = path;
            _file.Text = Path.GetFileName(path);
            _file.ToolTipText = path;
        }

        // ---------------------------------------------------------------- automation (tests)

        /// <summary>Drive the pane from tests: set_text, get_text, run, repl, output, clear, reset, status.</summary>
        internal string Command(string command, string arg)
        {
            switch (command)
            {
                case "set_text": _editor.Text = arg ?? ""; return "";
                case "get_text": return _editor.Text;
                case "select": { var p = arg.Split(','); _editor.Select(int.Parse(p[0]), int.Parse(p[1])); return ""; }
                case "editor": return _editor.GetType().Name;
                case "run": RunEditor(); return _output.Text;
                case "repl": RunRepl(arg); return _output.Text;
                case "output": return _output.Text;
                case "clear": _output.Clear(); return "";
                case "reset": ResetSession(); return "";
                case "status": return _status.Text;
                case "size": return new JavaScriptSerializer().Serialize(new { Width, Height, Visible });
                default: throw new ArgumentException("Unknown pane command: " + command);
            }
        }
    }
}
