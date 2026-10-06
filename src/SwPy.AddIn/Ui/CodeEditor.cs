using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using ScintillaNET;

namespace SwPy.Ui
{
    internal sealed class FindOptions
    {
        public bool MatchCase, WholeWord, Regex;
    }

    /// <summary>Editor surface the pane needs, so the Scintilla editor can fall back to plain text.</summary>
    internal interface ICodeEditor
    {
        Control Control { get; }
        string Text { get; set; }
        string SelectedText { get; }
        void Select(int start, int length);
        event KeyEventHandler KeyDown;
        /// <summary>User-visible text changed (edits, undo, Text=).</summary>
        event EventHandler TextChanged;
        event EventHandler CaretMoved;
        /// <summary>1-based caret line / column.</summary>
        int CaretLine { get; }
        int CaretColumn { get; }
        /// <summary>0-based line where the selection starts (to map tracebacks of a run selection).</summary>
        int SelectionStartLine { get; }
        bool Modified { get; }
        void SetSavePoint();
        void ResetUndo();
        EditorServices Services { get; set; }
        void ApplyTheme(Theme theme);
        int Zoom { get; set; }
        bool WordWrap { get; set; }
        void GotoLine(int line);
        void ShowRuntimeError(int line, string message);
        void ClearRuntimeError();
        /// <summary>Selects the next match; false when there is none.</summary>
        bool Find(string text, FindOptions options, bool backwards);
        int CountMatches(string text, FindOptions options);
        void HighlightMatches(string text, FindOptions options);
        bool Replace(string text, string replacement, FindOptions options);
        int ReplaceAll(string text, string replacement, FindOptions options);
        /// <summary>Run a named feature (tests): complete, signature, check ...; returns a description.</summary>
        string Feature(string name);
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
            "sw doc model swconst sldworks Model Vec X Y Z mm cm m inch ft deg rad kg g to on off";

        // Lexilla python f-string styles (SCE_P_FSTRING..SCE_P_FTRIPLEDOUBLE), not named by Scintilla.NET
        private const int FString = 16, FCharacter = 17, FTriple = 18, FTripleDouble = 19;

        // indicators
        private const int IndSyntax = 8, IndOccurrence = 9, IndFind = 10;
        // markers / margins
        private const int MarkError = 1;
        private const int MarginNumbers = 0, MarginMarkers = 1, MarginFold = 2;

        private static readonly Dictionary<string, int> KindImages = new Dictionary<string, int>
        {
            ["method"] = 1, ["function"] = 1, ["property"] = 2, ["field"] = 3, ["variable"] = 3,
            ["class"] = 4, ["module"] = 5, ["keyword"] = 6,
        };

        private readonly Scintilla _sci;
        private readonly Timer _checkTimer = new Timer { Interval = 600 };
        private Theme _theme = Theme.Light;
        private Diagnostic _syntax;
        private string _runtimeError;
        private int _runtimeErrorLine = -1;
        private bool _hoverTip;          // the visible calltip is a hover (closed on DwellEnd)
        private HoverInfo _lastHover;
        private string _lastFeature = "";

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
                TabIndents = true,
                BackspaceUnindents = true,
                WrapMode = WrapMode.None,
                IndentationGuides = IndentView.LookBoth,
                MultipleSelection = true,
                AdditionalSelectionTyping = true,
                MultiPaste = MultiPaste.Each,
                VirtualSpaceOptions = VirtualSpace.RectangularSelection,
                MouseDwellTime = 600,
                ScrollWidthTracking = true,
                ScrollWidth = 1,
            };

            _sci.SetKeywords(0, Keywords);
            _sci.SetKeywords(1, Builtins);

            // folding
            _sci.SetProperty("fold", "1");
            _sci.SetProperty("fold.compact", "0");
            _sci.SetProperty("fold.quotes.python", "1");
            _sci.Margins[MarginFold].Type = MarginType.Symbol;
            _sci.Margins[MarginFold].Mask = Marker.MaskFolders;
            _sci.Margins[MarginFold].Sensitive = true;
            _sci.Margins[MarginFold].Width = 14;
            _sci.Markers[Marker.Folder].Symbol = MarkerSymbol.BoxPlus;
            _sci.Markers[Marker.FolderOpen].Symbol = MarkerSymbol.BoxMinus;
            _sci.Markers[Marker.FolderEnd].Symbol = MarkerSymbol.BoxPlusConnected;
            _sci.Markers[Marker.FolderMidTail].Symbol = MarkerSymbol.TCorner;
            _sci.Markers[Marker.FolderOpenMid].Symbol = MarkerSymbol.BoxMinusConnected;
            _sci.Markers[Marker.FolderSub].Symbol = MarkerSymbol.VLine;
            _sci.Markers[Marker.FolderTail].Symbol = MarkerSymbol.LCorner;
            _sci.AutomaticFold = AutomaticFold.Show | AutomaticFold.Click | AutomaticFold.Change;

            // margins: line numbers, error marker
            _sci.Margins[MarginNumbers].Type = MarginType.Number;
            _sci.Margins[MarginNumbers].Width = 36;
            _sci.Margins[MarginMarkers].Type = MarginType.Symbol;
            _sci.Margins[MarginMarkers].Mask = 1u << MarkError;
            _sci.Margins[MarginMarkers].Width = 10;
            _sci.Markers[MarkError].Symbol = MarkerSymbol.Circle;

            // indicators
            _sci.Indicators[IndSyntax].Style = IndicatorStyle.Squiggle;
            _sci.Indicators[IndOccurrence].Style = IndicatorStyle.FullBox;
            _sci.Indicators[IndOccurrence].Under = true;
            _sci.Indicators[IndOccurrence].Alpha = 90;
            _sci.Indicators[IndOccurrence].OutlineAlpha = 0;
            _sci.Indicators[IndFind].Style = IndicatorStyle.FullBox;
            _sci.Indicators[IndFind].Under = true;
            _sci.Indicators[IndFind].Alpha = 120;
            _sci.Indicators[IndFind].OutlineAlpha = 200;

            _sci.AnnotationVisible = Annotation.Boxed;

            // autocomplete
            _sci.AutoCIgnoreCase = true;
            _sci.AutoCOrder = Order.PerformSort;
            _sci.AutoCMaxHeight = 12;
            _sci.AutoCSeparator = ' ';
            _sci.AutoCTypeSeparator = '?';
            _sci.AutoCAutoHide = true;
            _sci.AutoCCancelAtStart = true;
            _sci.AutoCDropRestOfWord = false;
            _sci.AutoCChooseSingle = false;
            RegisterKindImages();

            // our shortcuts replace these defaults
            _sci.ClearCmdKey(Keys.Control | Keys.D);
            _sci.ClearCmdKey(Keys.Control | Keys.L);
            _sci.ClearCmdKey(Keys.Control | Keys.Shift | Keys.L);

            ApplyTheme(Theme.Light);

            _sci.CharAdded += OnCharAdded;
            _sci.KeyDown += OnKeyDown;
            _sci.UpdateUI += OnUpdateUI;
            _sci.DwellStart += OnDwellStart;
            _sci.DwellEnd += (s, e) => { if (_hoverTip) { _sci.CallTipCancel(); _hoverTip = false; } };
            _sci.TextChanged += OnTextChanged;
            _checkTimer.Tick += (s, e) => { _checkTimer.Stop(); RunSyntaxCheck(); };
            _sci.Disposed += (s, e) => _checkTimer.Dispose();   // a closed tab must not tick into a disposed control
            _ = _sci.Handle;   // create the native window now so failures surface here (and we fall back)
        }

        // ---------------------------------------------------------------- appearance

        public void ApplyTheme(Theme t)
        {
            _theme = t;
            _sci.StyleResetDefault();
            _sci.Styles[Style.Default].Font = "Consolas";
            _sci.Styles[Style.Default].SizeF = 10f;
            _sci.Styles[Style.Default].BackColor = t.Back;
            _sci.Styles[Style.Default].ForeColor = t.Fore;
            _sci.StyleClearAll();
            Fore(Style.Python.CommentLine, t.Comment);
            Fore(Style.Python.CommentBlock, t.Comment);
            Fore(Style.Python.Number, t.Number);
            foreach (var s in new[] { Style.Python.String, Style.Python.Character, Style.Python.Triple,
                         Style.Python.TripleDouble, Style.Python.StringEol, FString,
                         FCharacter, FTriple, FTripleDouble })
                Fore(s, t.String);
            Fore(Style.Python.Word, t.Keyword);
            Fore(Style.Python.Word2, t.Builtin);
            Fore(Style.Python.ClassName, t.ClassName);
            Fore(Style.Python.DefName, t.DefName);
            Fore(Style.Python.Decorator, t.Decorator);
            Fore(Style.Python.Operator, t.Operator);
            _sci.Styles[Style.LineNumber].ForeColor = t.LineNumber;
            _sci.Styles[Style.LineNumber].BackColor = t.Margin;
            _sci.Styles[Style.IndentGuide].ForeColor = t.IndentGuide;
            _sci.Styles[Style.BraceLight].BackColor = t.BraceMatch;
            _sci.Styles[Style.BraceLight].Bold = true;
            _sci.Styles[Style.BraceBad].ForeColor = t.BraceBad;
            _sci.Styles[Style.CallTip].Font = "Consolas";
            _sci.Styles[Style.CallTip].SizeF = 9.5f;
            _sci.CallTipTabSize(4);   // SCI_CALLTIPUSESTYLE: calltips use Style.CallTip (themed)
            _sci.Styles[Style.CallTip].BackColor = t.Margin;
            _sci.Styles[Style.CallTip].ForeColor = t.Fore;
            _sci.CallTipSetForeHlt(t.Keyword);
            _sci.SelectionBackColor = t.Selection;
            _sci.CaretForeColor = t.Caret;
            _sci.CaretLineBackColor = t.CaretLine;
            _sci.SetFoldMarginColor(true, t.Margin);
            _sci.SetFoldMarginHighlightColor(true, t.Margin);
            for (var i = Marker.FolderEnd; i <= Marker.FolderOpen; i++)
            {
                _sci.Markers[i].SetForeColor(t.Margin);
                _sci.Markers[i].SetBackColor(t.LineNumber);
            }
            _sci.Margins[MarginMarkers].BackColor = t.Margin;
            _sci.Markers[MarkError].SetBackColor(t.Squiggle);
            _sci.Markers[MarkError].SetForeColor(t.Squiggle);
            _sci.Indicators[IndSyntax].ForeColor = t.Squiggle;
            _sci.Indicators[IndOccurrence].ForeColor = t.Occurrence;
            _sci.Indicators[IndFind].ForeColor = t.FindMatch;
            // annotation style for runtime errors: a spare style slot after the predefined ones
            _sci.Styles[AnnotationStyle].BackColor = t.AnnotationBack;
            _sci.Styles[AnnotationStyle].ForeColor = t.AnnotationFore;
            _sci.Styles[AnnotationStyle].Font = "Consolas";
            _sci.Styles[AnnotationStyle].SizeF = 9f;
            _sci.AutocompleteListBackColor = t.Back;
            _sci.AutocompleteListTextColor = t.Fore;
            _sci.AutocompleteListSelectedBackColor = t.Selection;
            _sci.AutocompleteListSelectedTextColor = t.Fore;
        }

        private const int AnnotationStyle = 60;

        private void Fore(int style, Color c) => _sci.Styles[style].ForeColor = c;

        private void RegisterKindImages()
        {
            var specs = new (int id, string letter, Color color)[]
            {
                (1, "m", Color.FromArgb(0x9B, 0x4D, 0xCA)), (2, "p", Color.FromArgb(0x1E, 0x88, 0xE5)),
                (3, "v", Color.FromArgb(0x00, 0x89, 0x7B)), (4, "C", Color.FromArgb(0xE6, 0x7E, 0x22)),
                (5, "M", Color.FromArgb(0x75, 0x75, 0x75)), (6, "k", Color.FromArgb(0x42, 0x42, 0xC0)),
            };
            foreach (var (id, letter, color) in specs)
            {
                var bmp = new Bitmap(14, 14);
                using (var g = Graphics.FromImage(bmp))
                using (var brush = new SolidBrush(color))
                using (var font = new Font("Segoe UI", 7.5f, FontStyle.Bold))
                {
                    g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
                    g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
                    g.FillEllipse(brush, 0, 0, 13, 13);
                    var size = g.MeasureString(letter, font);
                    g.DrawString(letter, font, Brushes.White, (14 - size.Width) / 2, (14 - size.Height) / 2);
                }
                _sci.RegisterRgbaImage(id, bmp);
            }
        }

        public int Zoom
        {
            get => _sci.Zoom;
            set => _sci.Zoom = Math.Max(-8, Math.Min(20, value));
        }

        public bool WordWrap
        {
            get => _sci.WrapMode != WrapMode.None;
            set => _sci.WrapMode = value ? WrapMode.Word : WrapMode.None;
        }

        // ---------------------------------------------------------------- basic surface

        public Control Control => _sci;
        public EditorServices Services { get; set; }

        public string Text
        {
            get => _sci.Text;
            set => _sci.Text = value;
        }

        public string SelectedText => _sci.SelectedText;
        public void Select(int start, int length) => _sci.SetSelection(start + length, start);
        public int CaretLine => _sci.CurrentLine + 1;
        public int CaretColumn => _sci.GetColumn(_sci.CurrentPosition) + 1;
        public int SelectionStartLine => _sci.LineFromPosition(_sci.SelectionStart);
        public bool Modified => _sci.Modified;
        public void SetSavePoint() => _sci.SetSavePoint();
        public void ResetUndo() => _sci.EmptyUndoBuffer();

        public event KeyEventHandler KeyDown
        {
            add => _sci.KeyDown += value;
            remove => _sci.KeyDown -= value;
        }

        public event EventHandler TextChanged;
        public event EventHandler CaretMoved;

        public void GotoLine(int line)
        {
            var index = Math.Max(0, Math.Min(_sci.Lines.Count - 1, line - 1));
            _sci.Lines[index].EnsureVisible();
            _sci.Lines[index].Goto();
            _sci.FirstVisibleLine = Math.Max(0, index - _sci.LinesOnScreen / 3);
            _sci.Focus();
        }

        private string TextBefore(int pos) => _sci.GetTextRange(0, pos);

        private bool InStringOrComment(int pos)
        {
            if (pos <= 0) return false;
            switch (_sci.GetStyleAt(pos - 1))
            {
                case Style.Python.CommentLine:
                case Style.Python.CommentBlock:
                case Style.Python.String:
                case Style.Python.Character:
                case Style.Python.Triple:
                case Style.Python.TripleDouble:
                case Style.Python.StringEol:
                case FString:
                case FCharacter:
                case FTriple:
                case FTripleDouble:
                case Style.Python.Number:
                    return true;
                default:
                    return false;
            }
        }

        // ---------------------------------------------------------------- typing

        private void OnTextChanged(object sender, EventArgs e)
        {
            ClearRuntimeError();
            _checkTimer.Stop();
            _checkTimer.Start();
            TextChanged?.Invoke(this, EventArgs.Empty);
        }

        private void OnCharAdded(object sender, CharAddedEventArgs e)
        {
            var c = (char)e.Char;
            var pos = _sci.CurrentPosition;
            if (c == '\n')
            {
                AutoIndent();
                return;
            }
            if (_sci.Selections.Count > 1) return;   // keep multi-caret typing simple
            if (AutoClose(c, pos)) return;

            if (c == '.')
            {
                if (!InStringOrComment(pos - 1)) ShowCompletion(true);
            }
            else if (char.IsLetterOrDigit(c) || c == '_')
            {
                if (!_sci.AutoCActive && !InStringOrComment(pos - 1))
                {
                    var start = _sci.WordStartPosition(pos, true);
                    if (pos - start >= 2 && !char.IsDigit(_sci.GetTextRange(start, 1)[0])) ShowCompletion(false);
                }
            }
            else if (c == '(' || c == ',')
            {
                if (!InStringOrComment(pos - 1)) ShowSignature(c == '(');
            }
            else if (c == ')')
            {
                if (_sci.CallTipActive && !_hoverTip) ShowSignature(false);
            }
        }

        private static readonly Dictionary<char, char> Pairs = new Dictionary<char, char>
        {
            ['('] = ')', ['['] = ']', ['{'] = '}', ['"'] = '"', ['\''] = '\'',
        };

        /// <summary>Auto-close brackets/quotes and type over closers. True when the character was consumed.</summary>
        private bool AutoClose(char c, int pos)
        {
            var next = pos < _sci.TextLength ? (char)_sci.GetCharAt(pos) : '\0';
            var prev = pos >= 2 ? (char)_sci.GetCharAt(pos - 2) : '\0';
            if ((c == ')' || c == ']' || c == '}' || c == '"' || c == '\'') && next == c)
            {
                _sci.DeleteRange(pos, 1);   // type over the auto-inserted closer
                if (c == ')' && _sci.CallTipActive && !_hoverTip) ShowSignature(false);
                return true;
            }
            if (!Pairs.TryGetValue(c, out var closer)) return false;
            var nextOk = next == '\0' || char.IsWhiteSpace(next) || ")]},:".IndexOf(next) >= 0;
            if (!nextOk) return false;
            if (c == '"' || c == '\'')
            {
                if (char.IsLetterOrDigit(prev) || prev == '_' || prev == c) return false;   // f'..., don't, '''
                if (InStringOrComment(pos - 1)) return false;
            }
            _sci.InsertText(pos, closer.ToString());
            return false;
        }

        private void AutoIndent()
        {
            var line = _sci.CurrentLine;
            if (line == 0) return;
            var prev = _sci.Lines[line - 1];
            var indent = prev.Indentation;
            var text = prev.Text.Split('#')[0].TrimEnd();
            if (text.EndsWith(":")) indent += _sci.IndentWidth;
            else
            {
                var first = text.TrimStart().Split(' ', '(')[0];
                if (first == "return" || first == "pass" || first == "break" || first == "continue" || first == "raise")
                    indent = Math.Max(0, indent - _sci.IndentWidth);
            }
            _sci.Lines[line].Indentation = indent;
            _sci.GotoPosition(_sci.Lines[line].IndentPosition);
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            if (e.Control && e.KeyCode == Keys.Space && !e.Shift) { Handled(e); ShowCompletion(true); }
            else if (e.Control && e.Shift && e.KeyCode == Keys.Space) { Handled(e); ShowSignature(true); }
            else if (e.KeyCode == Keys.F1) { Handled(e); OpenHelp(); }
            else if (e.Control && (e.KeyCode == Keys.OemQuestion || e.KeyCode == Keys.Divide)) { Handled(e); ToggleComment(); }
            else if (e.Control && !e.Shift && e.KeyCode == Keys.D) { Handled(e); AddNextOccurrence(); }
            else if (e.Control && e.Shift && e.KeyCode == Keys.L) { Handled(e); SelectAllOccurrences(); }
            else if (e.Alt && e.Shift && e.KeyCode == Keys.Down) { Handled(e); _sci.ExecuteCmd(Command.SelectionDuplicate); }
            else if (e.Alt && !e.Shift && e.KeyCode == Keys.Up) { Handled(e); _sci.ExecuteCmd(Command.MoveSelectedLinesUp); }
            else if (e.Alt && !e.Shift && e.KeyCode == Keys.Down) { Handled(e); _sci.ExecuteCmd(Command.MoveSelectedLinesDown); }
            else if (e.Control && e.Shift && e.KeyCode == Keys.K) { Handled(e); _sci.ExecuteCmd(Command.LineDelete); }
            else if (e.Control && (e.KeyCode == Keys.Oemplus || e.KeyCode == Keys.Add)) { Handled(e); Zoom++; }
            else if (e.Control && (e.KeyCode == Keys.OemMinus || e.KeyCode == Keys.Subtract)) { Handled(e); Zoom--; }
            else if (e.Control && (e.KeyCode == Keys.D0 || e.KeyCode == Keys.NumPad0)) { Handled(e); Zoom = 0; }
            else if (e.KeyCode == Keys.Back && !e.Control && _sci.Selections.Count == 1 && _sci.SelectionStart == _sci.SelectionEnd)
            {
                var pos = _sci.CurrentPosition;   // delete an empty pair: (|) -> |
                if (pos > 0 && pos < _sci.TextLength && Pairs.TryGetValue((char)_sci.GetCharAt(pos - 1), out var closer)
                    && (char)_sci.GetCharAt(pos) == closer)
                {
                    Handled(e);
                    _sci.DeleteRange(pos - 1, 2);
                }
            }
        }

        private static void Handled(KeyEventArgs e)
        {
            e.Handled = true;
            e.SuppressKeyPress = true;
        }

        private void ToggleComment()
        {
            var first = _sci.LineFromPosition(_sci.SelectionStart);
            var last = _sci.LineFromPosition(_sci.SelectionEnd);
            if (last > first && _sci.SelectionEnd == _sci.Lines[last].Position) last--;   // selection ends at line start
            var lines = Enumerable.Range(first, last - first + 1).Select(i => _sci.Lines[i]).ToList();
            var code = lines.Where(l => l.Text.Trim().Length > 0).ToList();
            if (code.Count == 0) return;
            var uncomment = code.All(l => l.Text.TrimStart().StartsWith("#"));
            var indent = code.Min(l => l.Indentation);
            _sci.BeginUndoAction();
            try
            {
                foreach (var l in code)
                {
                    if (uncomment)
                    {
                        var hash = l.Position + l.Text.IndexOf('#');
                        var len = _sci.GetTextRange(hash, Math.Min(2, l.EndPosition - hash)) == "# " ? 2 : 1;
                        _sci.DeleteRange(hash, len);
                    }
                    else
                    {
                        _sci.InsertText(_sci.Lines[l.Index].Position + PositionOfColumn(l, indent), "# ");
                    }
                }
            }
            finally
            {
                _sci.EndUndoAction();
            }
        }

        private int PositionOfColumn(Line line, int column)
        {
            var text = line.Text;
            int col = 0, i = 0;
            while (i < text.Length && col < column) { col += text[i] == '\t' ? _sci.TabWidth : 1; i++; }
            return i;
        }

        private void AddNextOccurrence()
        {
            if (_sci.SelectionStart == _sci.SelectionEnd)
            {
                var pos = _sci.CurrentPosition;
                _sci.SetSelection(_sci.WordEndPosition(pos, true), _sci.WordStartPosition(pos, true));
                return;
            }
            _sci.TargetWholeDocument();
            _sci.SearchFlags = SearchFlags.MatchCase;
            _sci.MultipleSelectAddNext();
        }

        private void SelectAllOccurrences()
        {
            if (_sci.SelectionStart == _sci.SelectionEnd)
            {
                var pos = _sci.CurrentPosition;
                _sci.SetSelection(_sci.WordEndPosition(pos, true), _sci.WordStartPosition(pos, true));
            }
            _sci.TargetWholeDocument();
            _sci.SearchFlags = SearchFlags.MatchCase;
            _sci.MultipleSelectAddEach();
        }

        // ---------------------------------------------------------------- brace match + occurrences

        private void OnUpdateUI(object sender, UpdateUIEventArgs e)
        {
            if ((e.Change & UpdateChange.Selection) == 0 && (e.Change & UpdateChange.Content) == 0) return;
            HighlightBraces();
            HighlightOccurrences();
            CaretMoved?.Invoke(this, EventArgs.Empty);
        }

        private void HighlightBraces()
        {
            var pos = _sci.CurrentPosition;
            int brace = -1;
            if (pos > 0 && IsBrace(_sci.GetCharAt(pos - 1))) brace = pos - 1;
            else if (pos < _sci.TextLength && IsBrace(_sci.GetCharAt(pos))) brace = pos;
            if (brace < 0 || InStringOrComment(brace + 1))
            {
                _sci.BraceHighlight(Scintilla.InvalidPosition, Scintilla.InvalidPosition);
                return;
            }
            var match = _sci.BraceMatch(brace);
            if (match == Scintilla.InvalidPosition) _sci.BraceBadLight(brace);
            else _sci.BraceHighlight(brace, match);
        }

        private static bool IsBrace(int c) => c == '(' || c == ')' || c == '[' || c == ']' || c == '{' || c == '}';

        private string _occurrenceWord;

        private void HighlightOccurrences()
        {
            string word = null;
            var selStart = _sci.SelectionStart;
            var selEnd = _sci.SelectionEnd;
            if (selStart == selEnd)
            {
                var start = _sci.WordStartPosition(selStart, true);
                var end = _sci.WordEndPosition(selStart, true);
                if (end > start) word = _sci.GetTextRange(start, end - start);
            }
            else if (_sci.Selections.Count == 1 && selEnd - selStart < 100)
            {
                var sel = _sci.GetTextRange(selStart, selEnd - selStart);
                if (sel.All(ch => char.IsLetterOrDigit(ch) || ch == '_')) word = sel;
            }
            if (word != null && (word.Length < 2 || char.IsDigit(word[0]) || Keywords.Split(' ').Contains(word))) word = null;
            if (word == _occurrenceWord) return;
            _occurrenceWord = word;
            _sci.IndicatorCurrent = IndOccurrence;
            _sci.IndicatorClearRange(0, _sci.TextLength);
            if (word == null || _sci.TextLength > 500_000) return;
            var hits = FindAll(word, new FindOptions { MatchCase = true, WholeWord = true });
            if (hits.Count < 2) return;
            foreach (var (s, l) in hits) _sci.IndicatorFillRange(s, l);
        }

        // ---------------------------------------------------------------- completion / signatures / hover

        private void ShowCompletion(bool explicitRequest)
        {
            if (Services == null) return;
            var pos = _sci.CurrentPosition;
            var c = Services.Complete(TextBefore(pos), _sci.Text, explicitRequest);
            if (c == null || c.Items.Count == 0)
            {
                _lastFeature = "complete: none";
                return;
            }
            var list = string.Join(" ", c.Items.Select(i => i.Key + (KindImages.TryGetValue(i.Value, out var img) ? "?" + img : "")));
            _lastFeature = "complete: " + string.Join(",", c.Items.Select(i => i.Key));
            _hoverTip = false;
            _sci.AutoCShow(c.Start, list);
        }

        private void ShowSignature(bool mayStartPython)
        {
            if (Services == null) return;
            var pos = _sci.CurrentPosition;
            var help = Services.Signature(TextBefore(pos), mayStartPython);
            if (help == null || help.Signatures.Count == 0)
            {
                if (_sci.CallTipActive && !_hoverTip) _sci.CallTipCancel();
                _lastFeature = "signature: none";
                return;
            }
            var sig = help.Signatures[0];
            var text = help.Signatures.Count > 1 ? $"(1 of {help.Signatures.Count}) " : "";
            var offset = text.Length;
            var (label, spans) = LayoutSignature(sig);
            text += label;
            if (!string.IsNullOrEmpty(sig.Doc)) text += "\n\n" + sig.Doc;
            _hoverTip = false;
            _sci.CallTipShow(OpenParenPosition(pos), text);
            if (help.Arg < spans.Count)
                _sci.CallTipSetHlt(offset + spans[help.Arg][0], offset + spans[help.Arg][1]);
            _lastFeature = "signature: " + sig.Label + " arg=" + help.Arg;
        }

        /// <summary>Long signatures get one parameter per line (the task pane is narrow); spans follow.</summary>
        private static (string label, List<int[]> spans) LayoutSignature(Signature sig)
        {
            if (sig.Label.Length <= 56 || sig.Params.Count < 2) return (sig.Label, sig.Params);
            var label = sig.Label;
            var text = new System.Text.StringBuilder(label.Substring(0, sig.Params[0][0]));
            var spans = new List<int[]>();
            for (var i = 0; i < sig.Params.Count; i++)
            {
                var p = sig.Params[i];
                text.Append("\n    ");
                var start = text.Length;
                text.Append(label, p[0], p[1] - p[0]);
                spans.Add(new[] { start, text.Length });
                if (i < sig.Params.Count - 1) text.Append(',');
            }
            text.Append('\n').Append(label.Substring(sig.Params[sig.Params.Count - 1][1]));
            return (text.ToString(), spans);
        }

        /// <summary>Position just after the '(' of the call being typed (keeps the tip anchored while typing).</summary>
        private int OpenParenPosition(int pos)
        {
            var depth = 0;
            for (var i = pos - 1; i >= 0 && i > pos - 2000; i--)
            {
                var ch = _sci.GetCharAt(i);
                if (ch == ')') depth++;
                else if (ch == '(')
                {
                    if (depth == 0) return i + 1;
                    depth--;
                }
            }
            return pos;
        }

        private void OnDwellStart(object sender, DwellEventArgs e)
        {
            if (e.Position < 0 || _sci.AutoCActive || (_sci.CallTipActive && !_hoverTip)) return;
            var text = HoverText(e.Position);
            if (string.IsNullOrEmpty(text)) return;
            _hoverTip = true;
            _sci.CallTipShow(e.Position, text);
        }

        private string HoverText(int position)
        {
            if (_syntax != null && _sci.IndicatorAllOnFor(position) is uint mask && (mask & (1u << IndSyntax)) != 0)
                return _syntax.Message;
            if (_runtimeError != null && _sci.LineFromPosition(position) == _runtimeErrorLine)
                return _runtimeError;
            if (Services == null || InStringOrComment(position + 1)) return null;
            var end = _sci.WordEndPosition(position, true);
            var start = _sci.WordStartPosition(position, true);
            if (end <= start) return null;
            _lastHover = Services.Hover(TextBefore(end));
            if (_lastHover?.Text == null) return null;
            return _lastHover.Text + (_lastHover.Help != null ? "\n(F1: SOLIDWORKS API help)" : "");
        }

        private void OpenHelp()
        {
            if (Services == null) return;
            var pos = _sci.CurrentPosition;
            var end = _sci.WordEndPosition(pos, true);
            var info = Services.Hover(TextBefore(end));
            var url = info?.Help ?? "https://help.solidworks.com/";
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Log.Error("Opening help failed", ex);
            }
        }

        // ---------------------------------------------------------------- diagnostics

        private void RunSyntaxCheck()
        {
            if (_sci.IsDisposed || Services == null || !Services.IsStarted) return;
            try
            {
                ShowSyntax(Services.Check(_sci.Text));
            }
            catch (Exception ex)   // never surface a dialog from a background check
            {
                Log.Error("Syntax check failed", ex);
            }
        }

        private void ShowSyntax(Diagnostic d)
        {
            _syntax = d;
            _sci.IndicatorCurrent = IndSyntax;
            _sci.IndicatorClearRange(0, _sci.TextLength);
            if (d == null || d.Line < 1 || d.Line > _sci.Lines.Count) return;
            var line = _sci.Lines[d.Line - 1];
            var lineLen = Math.Max(0, line.EndPosition - line.Position - EolLength(line));
            var start = line.Position + Math.Min(d.Col, lineLen);
            var length = Math.Max(1, Math.Min(d.EndCol, lineLen) - Math.Min(d.Col, lineLen));
            if (start >= _sci.TextLength) { start = Math.Max(0, _sci.TextLength - 1); length = 1; }
            _sci.IndicatorFillRange(start, Math.Min(length, _sci.TextLength - start));
        }

        private static int EolLength(Line line)
        {
            var t = line.Text;
            return t.EndsWith("\r\n") ? 2 : t.EndsWith("\n") || t.EndsWith("\r") ? 1 : 0;
        }

        public void ShowRuntimeError(int line, string message)
        {
            ClearRuntimeError();
            if (line < 1 || line > _sci.Lines.Count) return;
            _runtimeErrorLine = line - 1;
            _runtimeError = message;
            _sci.Lines[_runtimeErrorLine].MarkerAdd(MarkError);
            _sci.Lines[_runtimeErrorLine].AnnotationText = message;
            _sci.Lines[_runtimeErrorLine].AnnotationStyle = AnnotationStyle;
            GotoLine(line);
        }

        public void ClearRuntimeError()
        {
            if (_runtimeErrorLine < 0) return;
            _sci.MarkerDeleteAll(MarkError);
            _sci.AnnotationClearAll();
            _runtimeErrorLine = -1;
            _runtimeError = null;
        }

        // ---------------------------------------------------------------- find / replace

        private void SetSearch(FindOptions o)
        {
            var flags = SearchFlags.None;
            if (o.MatchCase) flags |= SearchFlags.MatchCase;
            if (o.WholeWord) flags |= SearchFlags.WholeWord;
            if (o.Regex) flags |= SearchFlags.Regex | SearchFlags.Cxx11Regex;
            _sci.SearchFlags = flags;
        }

        private List<(int start, int length)> FindAll(string text, FindOptions o)
        {
            var hits = new List<(int, int)>();
            if (string.IsNullOrEmpty(text)) return hits;
            SetSearch(o);
            var pos = 0;
            while (pos <= _sci.TextLength && hits.Count < 10000)
            {
                _sci.TargetStart = pos;
                _sci.TargetEnd = _sci.TextLength;
                if (_sci.SearchInTarget(text) < 0) break;
                var len = _sci.TargetEnd - _sci.TargetStart;
                hits.Add((_sci.TargetStart, len));
                pos = _sci.TargetEnd + (len == 0 ? 1 : 0);
            }
            return hits;
        }

        public bool Find(string text, FindOptions o, bool backwards)
        {
            if (string.IsNullOrEmpty(text)) return false;
            SetSearch(o);
            int Search(int from, int to)
            {
                _sci.TargetStart = from;
                _sci.TargetEnd = to;
                return _sci.SearchInTarget(text);
            }
            int found;
            if (!backwards)
            {
                found = Search(_sci.SelectionEnd, _sci.TextLength);
                if (found < 0) found = Search(0, _sci.SelectionEnd);   // wrap
            }
            else
            {
                found = Search(_sci.SelectionStart, 0);
                if (found < 0) found = Search(_sci.TextLength, _sci.SelectionStart);
            }
            if (found < 0) return false;
            _sci.SetSelection(_sci.TargetEnd, _sci.TargetStart);
            _sci.ScrollCaret();
            return true;
        }

        public int CountMatches(string text, FindOptions o) => FindAll(text, o).Count;

        public void HighlightMatches(string text, FindOptions o)
        {
            _sci.IndicatorCurrent = IndFind;
            _sci.IndicatorClearRange(0, _sci.TextLength);
            if (string.IsNullOrEmpty(text)) return;
            foreach (var (s, l) in FindAll(text, o)) _sci.IndicatorFillRange(s, Math.Max(1, l));
        }

        public bool Replace(string text, string replacement, FindOptions o)
        {
            if (string.IsNullOrEmpty(text)) return false;
            // replace the current selection if it is a match, then move to the next one
            SetSearch(o);
            _sci.TargetStart = _sci.SelectionStart;
            _sci.TargetEnd = _sci.SelectionEnd;
            if (_sci.SelectionStart != _sci.SelectionEnd && _sci.SearchInTarget(text) == _sci.SelectionStart
                && _sci.TargetEnd == _sci.SelectionEnd)
            {
                if (o.Regex) _sci.ReplaceTargetRe(replacement); else _sci.ReplaceTarget(replacement);
                _sci.SetSelection(_sci.TargetEnd, _sci.TargetEnd);
            }
            return Find(text, o, false);
        }

        public int ReplaceAll(string text, string replacement, FindOptions o)
        {
            if (string.IsNullOrEmpty(text)) return 0;
            SetSearch(o);
            var count = 0;
            _sci.BeginUndoAction();
            try
            {
                var pos = 0;
                while (count < 100000)
                {
                    _sci.TargetStart = pos;
                    _sci.TargetEnd = _sci.TextLength;
                    if (_sci.SearchInTarget(text) < 0) break;
                    var matchLength = _sci.TargetEnd - _sci.TargetStart;
                    var written = o.Regex ? _sci.ReplaceTargetRe(replacement) : _sci.ReplaceTarget(replacement);
                    pos = _sci.TargetStart + written + (matchLength == 0 ? 1 : 0);
                    count++;
                    if (pos > _sci.TextLength) break;
                }
            }
            finally
            {
                _sci.EndUndoAction();
            }
            return count;
        }

        // ---------------------------------------------------------------- automation (tests)

        public string Feature(string name)
        {
            switch (name)
            {
                case "complete": ShowCompletion(true); return _lastFeature + (_sci.AutoCActive ? " [shown]" : "");
                case "signature": ShowSignature(true); return _lastFeature + (_sci.CallTipActive ? " [shown]" : "");
                case "check":
                    if (Services == null) return "no services";
                    ShowSyntax(Services.Check(_sci.Text));
                    return _syntax == null ? "ok" : $"{_syntax.Line}:{_syntax.Col} {_syntax.Message}";
                case "hover":
                    return HoverText(Math.Max(0, _sci.CurrentPosition - 1)) ?? "";
                case "error_line": return _runtimeErrorLine < 0 ? "" : (_runtimeErrorLine + 1).ToString();
                case "occurrences":
                    return FindAll(_occurrenceWord ?? "", new FindOptions { MatchCase = true, WholeWord = true }).Count.ToString();
                case "cancel": _sci.AutoCCancel(); _sci.CallTipCancel(); return "";
                case "toggle_comment": ToggleComment(); return _sci.Text;
                case "caret_end": _sci.GotoPosition(_sci.TextLength); return "";
                default: throw new ArgumentException("Unknown editor feature: " + name);
            }
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
            _box.TextChanged += (s, e) => { _modified = true; TextChanged?.Invoke(this, EventArgs.Empty); };
            _box.SelectionChanged += (s, e) => CaretMoved?.Invoke(this, EventArgs.Empty);
        }

        private bool _modified;

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
        public EditorServices Services { get; set; }

        public string Text
        {
            get => _box.Text;
            set => _box.Text = value;
        }

        public string SelectedText => _box.SelectedText;
        public void Select(int start, int length) => _box.Select(start, length);
        public int CaretLine => _box.GetLineFromCharIndex(_box.SelectionStart) + 1;
        public int CaretColumn => _box.SelectionStart - _box.GetFirstCharIndexOfCurrentLine() + 1;
        public int SelectionStartLine => _box.GetLineFromCharIndex(_box.SelectionStart);
        public bool Modified => _modified;
        public void SetSavePoint() => _modified = false;
        public void ResetUndo() => _box.ClearUndo();

        public event KeyEventHandler KeyDown
        {
            add => _box.KeyDown += value;
            remove => _box.KeyDown -= value;
        }

        public event EventHandler TextChanged;
        public event EventHandler CaretMoved;

        public void ApplyTheme(Theme theme)
        {
            _box.BackColor = theme.Back;
            _box.ForeColor = theme.Fore;
        }

        public int Zoom { get; set; }

        public bool WordWrap
        {
            get => _box.WordWrap;
            set => _box.WordWrap = value;
        }

        public void GotoLine(int line)
        {
            var i = _box.GetFirstCharIndexFromLine(Math.Max(0, line - 1));
            if (i >= 0) { _box.Select(i, 0); _box.ScrollToCaret(); }
        }

        public void ShowRuntimeError(int line, string message) => GotoLine(line);
        public void ClearRuntimeError() { }

        private StringComparison Cmp(FindOptions o) => o.MatchCase ? StringComparison.Ordinal : StringComparison.OrdinalIgnoreCase;

        public bool Find(string text, FindOptions o, bool backwards)
        {
            if (string.IsNullOrEmpty(text)) return false;
            var i = backwards
                ? _box.Text.LastIndexOf(text, Math.Max(0, _box.SelectionStart - 1), Cmp(o))
                : _box.Text.IndexOf(text, _box.SelectionStart + _box.SelectionLength, Cmp(o));
            if (i < 0) i = backwards ? _box.Text.LastIndexOf(text, Cmp(o)) : _box.Text.IndexOf(text, Cmp(o));
            if (i < 0) return false;
            _box.Select(i, text.Length);
            return true;
        }

        public int CountMatches(string text, FindOptions o)
        {
            if (string.IsNullOrEmpty(text)) return 0;
            int n = 0, i = 0;
            while ((i = _box.Text.IndexOf(text, i, Cmp(o))) >= 0) { n++; i += text.Length; }
            return n;
        }

        public void HighlightMatches(string text, FindOptions o) { }

        public bool Replace(string text, string replacement, FindOptions o)
        {
            if (string.Equals(_box.SelectedText, text, Cmp(o))) _box.SelectedText = replacement;
            return Find(text, o, false);
        }

        public int ReplaceAll(string text, string replacement, FindOptions o)
        {
            var n = CountMatches(text, o);
            if (n > 0) _box.Text = System.Text.RegularExpressions.Regex.Replace(_box.Text,
                System.Text.RegularExpressions.Regex.Escape(text), replacement.Replace("$", "$$"),
                o.MatchCase ? System.Text.RegularExpressions.RegexOptions.None : System.Text.RegularExpressions.RegexOptions.IgnoreCase);
            return n;
        }

        public string Feature(string name) => "";
    }
}
