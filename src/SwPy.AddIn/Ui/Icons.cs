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
            using (var blue = new SolidBrush(Color.FromArgb(55, 118, 171)))
            using (var yellow = new SolidBrush(Color.FromArgb(255, 212, 59)))
            using (var font = new Font("Segoe UI", size * 0.42f, FontStyle.Bold, GraphicsUnit.Pixel))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                var r = size * 0.22f;
                using (var path = RoundedRect(new RectangleF(0, 0, size - 1, size - 1), r))
                    g.FillPath(blue, path);
                var fmt = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
                g.DrawString("Py", font, yellow, new RectangleF(0, size * 0.04f, size, size), fmt);
            }
            return bmp;
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
