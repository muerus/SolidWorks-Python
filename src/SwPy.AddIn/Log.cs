using System;
using System.IO;

namespace SwPy
{
    /// <summary>Append-only file log. SOLIDWORKS swallows add-in exceptions, so this is our eyes.</summary>
    internal static class Log
    {
        private static readonly object Gate = new object();

        public static string Dir { get; } = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SwPy", "logs");

        public static string FilePath { get; } = Path.Combine(Dir, "swpy.log");

        public static void Info(string message) => Write("INFO ", message);

        public static void Error(string message, Exception ex = null) =>
            Write("ERROR", ex == null ? message : message + Environment.NewLine + ex);

        private static void Write(string level, string message)
        {
            try
            {
                lock (Gate)
                {
                    Directory.CreateDirectory(Dir);
                    File.AppendAllText(FilePath,
                        $"{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff} {level} {message}{Environment.NewLine}");
                }
            }
            catch
            {
                // logging must never take SOLIDWORKS down
            }
        }
    }
}
