using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

namespace SwPy
{
    /// <summary>
    /// SOLIDWORKS probes for assemblies next to SLDWORKS.exe, not next to the add-in.
    /// Resolve our dependencies (Python.Runtime etc.) from the add-in folder, and the SOLIDWORKS interop
    /// assemblies (not shipped with SwPy) from the running SOLIDWORKS installation - by name, whatever
    /// their version, so one build works with every SOLIDWORKS release.
    /// Must be installed before any method that touches those types is JIT-compiled.
    /// </summary>
    internal static class AssemblyResolver
    {
        private static bool _installed;

        public static string AddInDir { get; } =
            Path.GetDirectoryName(typeof(AssemblyResolver).Assembly.Location);

        /// <summary>Folder of the SLDWORKS.exe hosting the add-in (null outside SOLIDWORKS).</summary>
        public static string SolidWorksDir { get; } = FindSolidWorksDir();

        public static void Install()
        {
            if (_installed) return;
            _installed = true;
            AppDomain.CurrentDomain.AssemblyResolve += OnResolve;
        }

        private static string FindSolidWorksDir()
        {
            try
            {
                var exe = Process.GetCurrentProcess().MainModule?.FileName;
                return exe != null && Path.GetFileName(exe).Equals("SLDWORKS.exe", StringComparison.OrdinalIgnoreCase)
                    ? Path.GetDirectoryName(exe)
                    : null;
            }
            catch
            {
                return null;
            }
        }

        private static Assembly OnResolve(object sender, ResolveEventArgs args)
        {
            var name = new AssemblyName(args.Name).Name;
            foreach (var dir in new[] { AddInDir, SolidWorksDir, SolidWorksDir == null ? null : Path.Combine(SolidWorksDir, "api", "redist") })
            {
                if (dir == null) continue;
                var path = Path.Combine(dir, name + ".dll");
                if (File.Exists(path)) return Assembly.LoadFrom(path);
            }
            return null;
        }
    }
}
