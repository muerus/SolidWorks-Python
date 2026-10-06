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
        private static PythonInstall _engine;           // CPython started (once per process)
        private static Exception _engineError;          // start failure is permanent for this process
        private static readonly object Gate = new object();

        private readonly PyObject _host;   // the swpy._host module

        public PythonInstall Install => _engine;

        /// <summary>
        /// The engine starts once; importing swpy._host is retried on every call until it succeeds
        /// (a broken script package must not need a SOLIDWORKS restart once fixed).
        /// </summary>
        public static PythonHost Get(SwPyAddIn addin)
        {
            lock (Gate)
            {
                StartEngine();
                return _instance ?? (_instance = new PythonHost(addin));
            }
        }

        private static void StartEngine()
        {
            if (_engine != null) return;
            if (_engineError != null)
                throw new InvalidOperationException("Python failed to start earlier in this session: " + _engineError.Message, _engineError);
            try
            {
                var install = PythonLocator.Find();
                Log.Info($"Starting Python from {install.Dll}");
                Runtime.PythonDLL = install.Dll;
                PythonEngine.PythonHome = install.Home;
                PythonEngine.Initialize();
                PythonEngine.BeginAllowThreads();
                _engine = install;
            }
            catch (Exception ex)
            {
                _engineError = ex;
                Log.Error("Python engine start failed", ex);
                throw;
            }
        }

        private PythonHost(SwPyAddIn addin)
        {
            using (Py.GIL())
            {
                dynamic sys = Py.Import("sys");
                var dir = PackageDir();
                if (!(bool)sys.path.__contains__(dir)) sys.path.insert(0, dir);
                if (sys.modules.__contains__("swpy._host"))
                    _host = Py.Import("importlib").InvokeMethod("reload", (PyObject)sys.modules["swpy._host"]);
                else
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

        /// <param name="stream">Forward stdout/stderr live to SwPyAddIn.Write while the code runs.</param>
        public string Execute(string session, string code, bool stream = false)
        {
            using (Py.GIL())
            using (var s = new PyString(session ?? "default"))
            using (var c = new PyString(code ?? ""))
            using (var st = stream ? PyObject.FromManagedObject(true) : PyObject.FromManagedObject(false))
            using (var result = _host.InvokeMethod("run", s, c, st))
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
