using System;
using System.IO;
using Microsoft.Win32;

namespace SwPy.Scripting
{
    internal sealed class PythonInstall
    {
        public string Home;
        public string Dll;
        public override string ToString() => Dll;
    }

    /// <summary>
    /// Finds a CPython to embed. Order: SWPY_PYTHON_HOME env var, bundled "python-runtime" folder
    /// next to the add-in, then registered installs (PEP 514) in preference order.
    /// </summary>
    internal static class PythonLocator
    {
        private static readonly string[] Preferred = { "3.12", "3.13", "3.11", "3.14" };

        public static PythonInstall Find()
        {
            var env = Environment.GetEnvironmentVariable("SWPY_PYTHON_HOME");
            if (!string.IsNullOrEmpty(env))
                return FromHome(env) ?? throw new InvalidOperationException($"SWPY_PYTHON_HOME has no python3XX.dll: {env}");

            var bundled = FromHome(Path.Combine(AssemblyResolver.AddInDir, "python-runtime"));
            if (bundled != null) return bundled;

            foreach (var version in Preferred)
            foreach (var hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
            {
                using (var key = hive.OpenSubKey($@"Software\Python\PythonCore\{version}\InstallPath"))
                {
                    var found = FromHome(key?.GetValue(null) as string);
                    if (found != null) return found;
                }
            }

            throw new InvalidOperationException(
                "No supported Python found (3.11-3.14). Install one or set SWPY_PYTHON_HOME.");
        }

        private static PythonInstall FromHome(string home)
        {
            if (string.IsNullOrEmpty(home) || !Directory.Exists(home)) return null;
            foreach (var dll in Directory.GetFiles(home, "python3*.dll"))
            {
                var name = Path.GetFileNameWithoutExtension(dll);
                if (name.Length > "python3".Length)   // python312.dll, not python3.dll
                    return new PythonInstall { Home = home.TrimEnd('\\'), Dll = dll };
            }
            return null;
        }
    }
}
