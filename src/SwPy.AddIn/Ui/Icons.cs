using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;
using System.Linq;

namespace SwPy.Ui
{
    /// <summary>Draws the task pane tab icons at runtime so no image files have to ship.</summary>
    internal static class Icons
    {
        private static readonly int[] TaskPaneSizes = { 20, 32, 40, 64, 96, 128 };

        public static string[] TaskPaneIcons()
        {
            var dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SwPy", "icons");
            Directory.CreateDirectory(dir);
            return TaskPaneSizes.Select(size =>
            {
                var path = Path.Combine(dir, $"taskpane_{size}.png");
                if (!File.Exists(path)) Draw(size).Save(path, ImageFormat.Png);
                return path;
            }).ToArray();
        }

        private static Bitmap Draw(int size)
        {
            var bmp = new Bitmap(size, size, PixelFormat.Format32bppArgb);
            using (var g = Graphics.FromImage(bmp))
                Tile(g, 0, size, "Py", Color.FromArgb(55, 118, 171));
            return bmp;
        }

        /// <summary>
        /// CommandManager image strips (one per size), one tile per command: glyphs like "↻" or script
        /// initials. File names carry a hash of the glyphs, so a changed script list gets new files.
        /// </summary>
        public static string[] CommandStrips(string[] glyphs)
        {
            var dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SwPy", "icons");
            Directory.CreateDirectory(dir);
            var hash = (uint)string.Join("|", glyphs).GetHashCode();
            return TaskPaneSizes.Select(size =>
            {
                var path = Path.Combine(dir, $"commands_{hash:x8}_{size}.png");
                if (File.Exists(path)) return path;
                using (var bmp = new Bitmap(size * Math.Max(1, glyphs.Length), size, PixelFormat.Format32bppArgb))
                {
                    using (var g = Graphics.FromImage(bmp))
                    {
                        for (var i = 0; i < glyphs.Length; i++)
                        {
                            var tool = i < 2;   // Refresh / Open folder
                            Tile(g, i * size, size, glyphs[i], tool ? Color.FromArgb(96, 96, 96) : Color.FromArgb(55, 118, 171));
                        }
                    }
                    bmp.Save(path, ImageFormat.Png);
                }
                return path;
            }).ToArray();
        }

        private static void Tile(Graphics g, float x, int size, string text, Color back)
        {
            using (var fill = new SolidBrush(back))
            using (var yellow = new SolidBrush(Color.FromArgb(255, 212, 59)))
            using (var font = new Font("Segoe UI", size * (text.Length > 1 ? 0.42f : 0.6f), FontStyle.Bold, GraphicsUnit.Pixel))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                using (var path = RoundedRect(new RectangleF(x, 0, size - 1, size - 1), size * 0.22f))
                    g.FillPath(fill, path);
                var fmt = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
                g.DrawString(text, font, yellow, new RectangleF(x, size * 0.04f, size, size), fmt);
            }
        }

        private static GraphicsPath RoundedRect(RectangleF b, float r)
        {
            var p = new GraphicsPath();
            var d = r * 2;
            p.AddArc(b.X, b.Y, d, d, 180, 90);
            p.AddArc(b.Right - d, b.Y, d, d, 270, 90);
            p.AddArc(b.Right - d, b.Bottom - d, d, d, 0, 90);
            p.AddArc(b.X, b.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }
    }
}
