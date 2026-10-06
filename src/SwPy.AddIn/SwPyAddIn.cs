using System;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swpublished;

namespace SwPy
{
    /// <summary>Automation surface returned by ISldWorks.GetAddInObject("SwPy.AddIn").</summary>
    [ComVisible(true)]
    [Guid("7a7a2eac-07eb-42ed-8a15-3fbb1750a600")]
    [InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
    public interface ISwPyAutomation
    {
        string Version();

        /// <summary>Run code in a named session. Returns JSON: ok, stdout, result, error.</summary>
        string Execute(string session, string code);
    }

    [ComVisible(true)]
    [Guid("10c1bd59-4d33-4878-bdda-de5d879d6213")]
    [ProgId("SwPy.AddIn")]
    [ClassInterface(ClassInterfaceType.None)]
    [ComDefaultInterface(typeof(ISwPyAutomation))]
    public class SwPyAddIn : ISwAddin, ISwPyAutomation
    {
        internal static SwPyAddIn Instance { get; private set; }

        internal ISldWorks Sw { get; private set; }

        internal MainThread Main { get; private set; }

        private int _cookie;

        public bool ConnectToSW(object ThisSW, int Cookie)
        {
            try
            {
                AssemblyResolver.Install();
                Sw = (ISldWorks)ThisSW;
                _cookie = Cookie;
                Sw.SetAddinCallbackInfo2(0, this, Cookie);
                Main = new MainThread();
                Instance = this;
                Log.Info($"Connected to SOLIDWORKS {Sw.RevisionNumber()} (add-in {Version()}, dir {AssemblyResolver.AddInDir})");
                return true;
            }
            catch (Exception ex)
            {
                Log.Error("ConnectToSW failed", ex);
                return false;
            }
        }

        public bool DisconnectFromSW()
        {
            Log.Info("Disconnecting");
            Main?.Dispose();
            Main = null;
            Instance = null;
            Sw = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            return true;
        }

        public string Version() => typeof(SwPyAddIn).Assembly.GetName().Version.ToString();

        public string Execute(string session, string code)
        {
            try
            {
                return Main.Invoke(() => Scripting.PythonHost.Get(this).Execute(session, code));
            }
            catch (Exception ex)
            {
                Log.Error("Execute failed", ex);
                return "{\"ok\": false, \"stdout\": \"\", \"result\": null, \"error\": "
                       + JsonString("Host error: " + ex) + "}";
            }
        }

        private static string JsonString(string s) =>
            "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "\\r").Replace("\n", "\\n") + "\"";
    }
}
