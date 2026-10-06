using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace SwPy.Launcher
{
    /// <summary>
    /// Starts SOLIDWORKS (or attaches to a running one) and loads the SwPy add-in.
    /// SOLIDWORKS only auto-loads add-ins registered under HKLM (admin); this gives per-user installs
    /// the same experience via a "SOLIDWORKS + SwPy" shortcut.
    /// </summary>
    internal static class Program
    {
        private const string ProgId = "SldWorks.Application";

        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                var dll = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "SwPy.AddIn.dll");
                var sw = Attach() ?? Start(TimeSpan.FromMinutes(5));
                var type = sw.GetType();
                if (type.InvokeMember("GetAddInObject", BindingFlags.InvokeMethod, null, sw, new object[] { "SwPy.AddIn" }) == null)
                {
                    var rc = (int)type.InvokeMember("LoadAddIn", BindingFlags.InvokeMethod, null, sw, new object[] { dll });
                    if (rc != 0) throw new InvalidOperationException($"LoadAddIn returned {rc} for {dll}");
                }
                Marshal.ReleaseComObject(sw);
                LogLine("SwPy loaded");
                return 0;
            }
            catch (Exception ex)
            {
                LogLine("FAILED " + ex);
                if (Array.IndexOf(args, "--quiet") >= 0) return 1;
                MessageBox.Show("SwPy could not be loaded into SOLIDWORKS:\n\n" + ex.Message, "SwPy",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }

        private static void LogLine(string text)
        {
            try
            {
                var dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SwPy", "logs");
                Directory.CreateDirectory(dir);
                File.AppendAllText(Path.Combine(dir, "launcher.log"), $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {text}{Environment.NewLine}");
            }
            catch { }
        }

        private static object Attach()
        {
            try { return Marshal.GetActiveObject(ProgId); }
            catch (COMException) { return null; }
        }

        private static object Start(TimeSpan timeout)
        {
            var exe = SolidWorksExe();
            LogLine("starting " + exe);
            Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true });
            var until = DateTime.UtcNow + timeout;
            while (DateTime.UtcNow < until)
            {
                Thread.Sleep(1000);
                var sw = Attach();
                if (sw == null) continue;
                try
                {
                    if ((bool)sw.GetType().InvokeMember("StartupProcessCompleted", BindingFlags.GetProperty, null, sw, null))
                        return sw;
                }
                catch (COMException) { }
                Marshal.ReleaseComObject(sw);
            }
            throw new TimeoutException("SOLIDWORKS did not finish starting.");
        }

        /// <summary>SLDWORKS.exe from the COM server registration of SldWorks.Application.</summary>
        private static string SolidWorksExe()
        {
            var clsid = Type.GetTypeFromProgID(ProgId)?.GUID ?? throw new InvalidOperationException("SOLIDWORKS is not installed.");
            using (var key = Registry.ClassesRoot.OpenSubKey($@"CLSID\{{{clsid}}}\LocalServer32"))
            {
                var cmd = (key?.GetValue(null) as string)?.Trim() ?? throw new InvalidOperationException("SOLIDWORKS COM server not registered.");
                // value may be unquoted with spaces and arguments: C:\Program Files\...\SLDWORKS.exe /automation
                cmd = cmd.Trim('"');
                var end = cmd.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
                return end > 0 ? cmd.Substring(0, end + 4) : cmd;
            }
        }
    }
}
