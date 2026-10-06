using System;
using System.IO;
using System.Reflection;

namespace SwPy
{
    /// <summary>
    /// SOLIDWORKS probes for assemblies next to SLDWORKS.exe, not next to the add-in.
    /// Resolve our dependencies (Python.Runtime etc.) from the add-in folder.
    /// Must be installed before any method that touches those types is JIT-compiled.
    /// </summary>
    internal static class AssemblyResolver
    {
        private static bool _installed;

        public static string AddInDir { get; } =
            Path.GetDirectoryName(typeof(AssemblyResolver).Assembly.Location);

        public static void Install()
        {
            if (_installed) return;
            _installed = true;
            AppDomain.CurrentDomain.AssemblyResolve += OnResolve;
        }

        private static Assembly OnResolve(object sender, ResolveEventArgs args)
        {
            var name = new AssemblyName(args.Name).Name;
            var path = Path.Combine(AddInDir, name + ".dll");
            return File.Exists(path) ? Assembly.LoadFrom(path) : null;
        }
    }
}
