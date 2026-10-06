using System;
using System.IO;
using Python.Runtime;

namespace SwPy.Scripting
{
    /// <summary>
    /// Owns the embedded CPython for the lifetime of the SOLIDWORKS process.
    /// Initialized once, never shut down (finalizing CPython inside a host is unsafe).
    /// All script plumbing lives in Python: swpy._host.
    /// </summary>
    internal sealed class PythonHost
    {
        private static PythonHost _instance;
        private static readonly object Gate = new object();

        private readonly PyObject _host;   // the swpy._host module

        public PythonInstall Install { get; }

        public static PythonHost Get(SwPyAddIn addin)
        {
            lock (Gate)
            {
                return _instance ?? (_instance = new PythonHost(addin));
            }
        }

        private PythonHost(SwPyAddIn addin)
        {
            Install = PythonLocator.Find();
            Log.Info($"Starting Python from {Install.Dll}");

            Runtime.PythonDLL = Install.Dll;
            PythonEngine.PythonHome = Install.Home;
            PythonEngine.Initialize();
            PythonEngine.BeginAllowThreads();

            using (Py.GIL())
            {
                dynamic sys = Py.Import("sys");
                sys.path.insert(0, PackageDir());
                _host = Py.Import("swpy._host");
                using (var sw = addin.Sw.ToPython())
                using (var self = addin.ToPython())
                {
                    _host.InvokeMethod("attach", sw, self).Dispose();
                }
                Log.Info($"Python {sys.version} ready");
            }
        }

        /// <summary>Dev override SWPY_PACKAGE_DIR points at the repo's python/ folder.</summary>
        private static string PackageDir()
        {
            var dev = Environment.GetEnvironmentVariable("SWPY_PACKAGE_DIR");
            return !string.IsNullOrEmpty(dev) ? dev : Path.Combine(AssemblyResolver.AddInDir, "python");
        }

        public string Execute(string session, string code)
        {
            using (Py.GIL())
            using (var s = new PyString(session ?? "default"))
            using (var c = new PyString(code ?? ""))
            using (var result = _host.InvokeMethod("run", s, c))
            {
                return result.As<string>();
            }
        }

        public void Reset(string session)
        {
            using (Py.GIL())
            using (var s = new PyString(session ?? "default"))
            {
                _host.InvokeMethod("reset", s).Dispose();
            }
        }
    }
}
