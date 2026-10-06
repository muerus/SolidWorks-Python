using System;
using System.Drawing;
using System.Windows.Forms;

namespace SwPy.Ui
{
    /// <summary>Inline find/replace bar (Ctrl+F / Ctrl+H) acting on the active editor.</summary>
    internal sealed class FindBar : Panel
    {
        private readonly Func<ICodeEditor> _editor;
        private readonly TextBox _find, _replace;
        private readonly CheckBox _case, _word, _regex;
        private readonly Label _count;
        private readonly Panel _replaceRow;

        public FindBar(Func<ICodeEditor> editor)
        {
            _editor = editor;
            Dock = DockStyle.Top;
            Visible = false;
            Padding = new Padding(2);

            _find = new TextBox { Width = 160 };
            _replace = new TextBox { Width = 160 };
            _case = Toggle("Aa", "Match case");
            _word = Toggle("W", "Whole word");
            _regex = Toggle(".*", "Regular expression");
            _count = new Label { AutoSize = true, ForeColor = Color.DimGray, Padding = new Padding(4, 5, 0, 0) };

            var findRow = Row();
            findRow.Controls.AddRange(new Control[]
            {
                _find, Btn("↑", "Previous match (Shift+F3)", (s, e) => Next(true)),
                Btn("↓", "Next match (F3)", (s, e) => Next(false)), _case, _word, _regex, _count,
                Btn("✕", "Close (Esc)", (s, e) => Close()),
            });
            _replaceRow = Row();
            _replaceRow.Controls.AddRange(new Control[]
            {
                _replace, Btn("Replace", "Replace and find next", (s, e) => ReplaceOne()),
                Btn("All", "Replace all", (s, e) => ReplaceAll()),
            });
            Controls.Add(_replaceRow);
            Controls.Add(findRow);

            _find.TextChanged += (s, e) => Recount(true);
            _find.KeyDown += OnKey;
            _replace.KeyDown += OnKey;
            foreach (var c in new[] { _case, _word, _regex }) c.CheckedChanged += (s, e) => Recount(true);
            UpdateHeight();
        }

        private static FlowLayoutPanel Row() =>
            new FlowLayoutPanel { Dock = DockStyle.Top, AutoSize = true, WrapContents = false, Margin = Padding.Empty };

        private static Button Btn(string text, string tip, EventHandler click)
        {
            var b = new Button { Text = text, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, FlatStyle = FlatStyle.System };
            b.Click += click;
            new ToolTip().SetToolTip(b, tip);
            return b;
        }

        private static CheckBox Toggle(string text, string tip)
        {
            var c = new CheckBox { Text = text, Appearance = Appearance.Button, AutoSize = true, FlatStyle = FlatStyle.System };
            new ToolTip().SetToolTip(c, tip);
            return c;
        }

        private FindOptions Options => new FindOptions { MatchCase = _case.Checked, WholeWord = _word.Checked, Regex = _regex.Checked };

        public string Query => _find.Text;

        public void Open(bool replace)
        {
            var sel = _editor()?.SelectedText;
            if (!string.IsNullOrEmpty(sel) && !sel.Contains("\n")) _find.Text = sel;
            _replaceRow.Visible = replace;
            UpdateHeight();
            Visible = true;
            _find.Focus();
            _find.SelectAll();
            Recount(false);
        }

        public void Close()
        {
            Visible = false;
            _editor()?.HighlightMatches(null, Options);
            _editor()?.Control.Focus();
        }

        private void UpdateHeight() => Height = (_replaceRow.Visible ? 2 : 1) * (_find.PreferredHeight + 10) + 4;

        public void Next(bool backwards)
        {
            var ed = _editor();
            if (ed == null) return;
            var found = ed.Find(_find.Text, Options, backwards);
            _find.BackColor = found || _find.Text.Length == 0 ? SystemColors.Window : Color.FromArgb(255, 220, 220);
        }

        private void ReplaceOne()
        {
            _editor()?.Replace(_find.Text, _replace.Text, Options);
            Recount(false);
        }

        private void ReplaceAll()
        {
            var n = _editor()?.ReplaceAll(_find.Text, _replace.Text, Options) ?? 0;
            Recount(false);
            _count.Text = $"replaced {n}";
        }

        private void Recount(bool jump)
        {
            var ed = _editor();
            if (ed == null) return;
            var n = ed.CountMatches(_find.Text, Options);
            _count.Text = _find.Text.Length == 0 ? "" : n == 0 ? "no results" : $"{n} match{(n == 1 ? "" : "es")}";
            ed.HighlightMatches(_find.Text, Options);
            if (jump && n > 0) Next(false);
            _find.BackColor = n > 0 || _find.Text.Length == 0 ? SystemColors.Window : Color.FromArgb(255, 220, 220);
        }

        private void OnKey(object sender, KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape) { Handled(e); Close(); }
            else if (e.KeyCode == Keys.Enter && sender == _find) { Handled(e); Next(e.Shift); }
            else if (e.KeyCode == Keys.Enter && sender == _replace) { Handled(e); ReplaceOne(); }
            else if (e.KeyCode == Keys.F3) { Handled(e); Next(e.Shift); }
        }

        private static void Handled(KeyEventArgs e)
        {
            e.Handled = true;
            e.SuppressKeyPress = true;
        }
    }
}
