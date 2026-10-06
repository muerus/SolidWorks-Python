using System.Drawing;

namespace SwPy.Ui
{
    /// <summary>Editor colour scheme (VS Code Light+/Dark+ inspired).</summary>
    internal sealed class Theme
    {
        public string Name;
        public Color Back, Fore, Margin, LineNumber, CaretLine, Caret, Selection, IndentGuide;
        public Color Comment, Number, String, Keyword, Builtin, ClassName, DefName, Decorator, Operator;
        public Color BraceMatch, BraceBad, Occurrence, FindMatch, ErrorLine, Squiggle;
        public Color OutputBack, OutputFore, Error, Result, Echo;
        public Color AnnotationBack, AnnotationFore;

        public static Theme Light { get; } = new Theme
        {
            Name = "light",
            Back = Color.White, Fore = Rgb(0x1F1F1F), Margin = Rgb(0xF5F5F5), LineNumber = Rgb(0x8A8A8A),
            CaretLine = Color.FromArgb(40, 120, 160, 220), Caret = Color.Black, Selection = Rgb(0xADD6FF),
            IndentGuide = Rgb(0xD3D3D3),
            Comment = Rgb(0x008000), Number = Rgb(0x098658), String = Rgb(0xA31515), Keyword = Rgb(0x0000FF),
            Builtin = Rgb(0x267F99), ClassName = Rgb(0x267F99), DefName = Rgb(0x795E26), Decorator = Rgb(0xAF00DB),
            Operator = Rgb(0x333333),
            BraceMatch = Rgb(0xB9E0B0), BraceBad = Rgb(0xFF0000), Occurrence = Rgb(0x9BC8FF), FindMatch = Rgb(0xF0C040),
            ErrorLine = Rgb(0xFFE0E0), Squiggle = Rgb(0xE51400),
            OutputBack = Rgb(0xFAFAFA), OutputFore = Rgb(0x1F1F1F), Error = Rgb(0xC82828), Result = Rgb(0x1E5AAA),
            Echo = Color.Gray, AnnotationBack = Rgb(0xFFF0F0), AnnotationFore = Rgb(0xA01010),
        };

        public static Theme Dark { get; } = new Theme
        {
            Name = "dark",
            Back = Rgb(0x1E1E1E), Fore = Rgb(0xD4D4D4), Margin = Rgb(0x1E1E1E), LineNumber = Rgb(0x858585),
            CaretLine = Color.FromArgb(60, 70, 70, 70), Caret = Rgb(0xAEAFAD), Selection = Rgb(0x264F78),
            IndentGuide = Rgb(0x404040),
            Comment = Rgb(0x6A9955), Number = Rgb(0xB5CEA8), String = Rgb(0xCE9178), Keyword = Rgb(0x569CD6),
            Builtin = Rgb(0x4EC9B0), ClassName = Rgb(0x4EC9B0), DefName = Rgb(0xDCDCAA), Decorator = Rgb(0xC586C0),
            Operator = Rgb(0xD4D4D4),
            BraceMatch = Rgb(0x3A5A3A), BraceBad = Rgb(0xF44747), Occurrence = Rgb(0x3A4A60), FindMatch = Rgb(0x8A6A10),
            ErrorLine = Rgb(0x4B1818), Squiggle = Rgb(0xF44747),
            OutputBack = Rgb(0x181818), OutputFore = Rgb(0xCCCCCC), Error = Rgb(0xF48771), Result = Rgb(0x75BEFF),
            Echo = Rgb(0x8A8A8A), AnnotationBack = Rgb(0x3A1D1D), AnnotationFore = Rgb(0xF48771),
        };

        public static Theme Get(string name) => name == "dark" ? Dark : Light;

        private static Color Rgb(int rgb) => Color.FromArgb((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF);
    }
}
