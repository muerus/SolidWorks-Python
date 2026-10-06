using System;
using System.Drawing;
using System.Windows.Forms;
using ScintillaNET;

namespace SwPy.Ui
{
    /// <summary>Minimal editor surface the pane needs, so the Scintilla editor can fall back to plain text.</summary>
    internal interface ICodeEditor
    {
        Control Control { get; }
        string Text { get; set; }
        string SelectedText { get; }
        void Select(int start, int length);
        event KeyEventHandler KeyDown;
    }

    internal static class CodeEditors
    {
        /// <summary>Scintilla with Python highlighting; plain RichTextBox if the native control cannot load.</summary>
        public static ICodeEditor Create()
        {
            try
            {
                return new ScintillaEditor();
            }
            catch (Exception ex)
            {
                Log.Error("Scintilla editor unavailable, using plain editor", ex);
                return new PlainEditor();
            }
        }
    }

    // ------------------------------------------------------------------ Scintilla

    internal sealed class ScintillaEditor : ICodeEditor
    {
        private const string Keywords =
            "False None True and as assert async await break class continue def del elif else except finally for " +
            "from global if import in is lambda nonlocal not or pass raise return try while with yield match case";

        private const string Builtins =
            "abs all any bool dict dir enumerate filter float format getattr hasattr int isinstance len list map max " +
            "min next object open print range repr reversed round set sorted str sum super tuple type zip " +
            "sw doc model swconst sldworks Model Vec X Y Z mm cm m inch ft deg rad kg g to";

        private readonly Scintilla _sci;

        public ScintillaEditor()
        {
            _sci = new Scintilla
            {
                Dock = DockStyle.Fill,
                BorderStyle = ScintillaNET.BorderStyle.None,
                LexerName = "python",
                TabWidth = 4,
                IndentWidth = 4,
                UseTabs = false,
                WrapMode = WrapMode.None,
                IndentationGuides = IndentView.LookBoth,
            };

            _sci.StyleResetDefault();
            _sci.Styles[Style.Default].Font = "Consolas";
            _sci.Styles[Style.Default].SizeF = 10f;
            _sci.StyleClearAll();
            Color(Style.Python.CommentLine, 0x6A9955);
            Color(Style.Python.CommentBlock, 0x6A9955);
            Color(Style.Python.Number, 0x098658);
            Color(Style.Python.String, 0xA31515);
            Color(Style.Python.Character, 0xA31515);
            Color(Style.Python.Triple, 0xA31515);
            Color(Style.Python.TripleDouble, 0xA31515);
            Color(Style.Python.StringEol, 0xA31515);
            Color(Style.Python.Word, 0x0000FF);
            Color(Style.Python.Word2, 0x267F99);
            Color(Style.Python.ClassName, 0x267F99);
            Color(Style.Python.DefName, 0x795E26);
            Color(Style.Python.Decorator, 0xAF00DB);
            Color(Style.Python.Operator, 0x333333);
            _sci.SetKeywords(0, Keywords);
            _sci.SetKeywords(1, Builtins);

            _sci.Margins[0].Type = MarginType.Number;
            _sci.Margins[0].Width = 32;
            _sci.Styles[Style.LineNumber].ForeColor = System.Drawing.Color.Gray;

            _sci.CaretLineBackColor = System.Drawing.Color.FromArgb(40, 120, 160, 220);   // alpha => visible caret line

            _sci.CharAdded += OnCharAdded;
            _ = _sci.Handle;   // create the native window now so failures surface here (and we fall back)
        }

        private void Color(int style, int rgb) =>
            _sci.Styles[style].ForeColor = System.Drawing.Color.FromArgb((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF);

        /// <summary>Auto-indent: keep the previous line's indentation, one level deeper after ':'.</summary>
        private void OnCharAdded(object sender, CharAddedEventArgs e)
        {
            if (e.Char != '\n') return;
            var line = _sci.CurrentLine;
            if (line == 0) return;
            var prev = _sci.Lines[line - 1];
            var indent = prev.Indentation;
            if (prev.Text.TrimEnd().EndsWith(":")) indent += _sci.IndentWidth;
            _sci.Lines[line].Indentation = indent;
            _sci.GotoPosition(_sci.Lines[line].IndentPosition);
        }

        public Control Control => _sci;

        public string Text
        {
            get => _sci.Text;
            set => _sci.Text = value;
        }

        public string SelectedText => _sci.SelectedText;

        public void Select(int start, int length) => _sci.SetSelection(start + length, start);

        public event KeyEventHandler KeyDown
        {
            add => _sci.KeyDown += value;
            remove => _sci.KeyDown -= value;
        }
    }

    // ------------------------------------------------------------------ plain fallback

    internal sealed class PlainEditor : ICodeEditor
    {
        private readonly RichTextBox _box;

        public PlainEditor()
        {
            _box = new RichTextBox
            {
                Dock = DockStyle.Fill,
                Font = new Font("Consolas", 10f),
                AcceptsTab = true,
                WordWrap = false,
                DetectUrls = false,
                BorderStyle = System.Windows.Forms.BorderStyle.None,
                ScrollBars = RichTextBoxScrollBars.Both,
            };
            _box.KeyDown += OnKeyDown;
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Control && e.KeyCode == Keys.V)
            {
                Handled(e);
                if (Clipboard.ContainsText()) _box.SelectedText = Clipboard.GetText().Replace("\t", "    ");
            }
            else if (e.KeyCode == Keys.Tab && !e.Shift && !e.Control) { Handled(e); _box.SelectedText = "    "; }
            else if (e.KeyCode == Keys.Enter && !e.Control) { Handled(e); NewLineWithIndent(); }
        }

        private static void Handled(KeyEventArgs e)
        {
            e.Handled = true;
            e.SuppressKeyPress = true;
        }

        private void NewLineWithIndent()
        {
            var line = _box.GetLineFromCharIndex(_box.SelectionStart);
            var lineStart = _box.GetFirstCharIndexFromLine(line);
            var current = _box.Text.Substring(lineStart, _box.SelectionStart - lineStart);
            var indent = current.Substring(0, current.Length - current.TrimStart(' ').Length);
            if (current.TrimEnd().EndsWith(":")) indent += "    ";
            _box.SelectedText = "\n" + indent;
        }

        public Control Control => _box;

        public string Text
        {
            get => _box.Text;
            set => _box.Text = value;
        }

        public string SelectedText => _box.SelectedText;

        public void Select(int start, int length) => _box.Select(start, length);

        public event KeyEventHandler KeyDown
        {
            add => _box.KeyDown += value;
            remove => _box.KeyDown -= value;
        }
    }
}
