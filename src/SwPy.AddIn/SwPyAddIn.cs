using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swpublished;
using SwPy.Scripting;
using SwPy.Ui;

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

        /// <summary>Drive the editor pane (tests): see EditorPane.Command.</summary>
        string Pane(string command, string arg);
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
        private TaskpaneView _taskpane;
        private EditorPane _pane;

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
                CreatePane();
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
            try
            {
                _taskpane?.DeleteView();
                if (_taskpane != null) Marshal.ReleaseComObject(_taskpane);
            }
            catch (Exception ex)
            {
                Log.Error("Removing task pane failed", ex);
            }
            _taskpane = null;
            _pane = null;
            Main?.Dispose();
            Main = null;
            Instance = null;
            Sw = null;
            GC.Collect();
            GC.WaitForPendingFinalizers();
            return true;
        }

        // ---------------------------------------------------------------- task pane

        private void CreatePane()
        {
            try
            {
                _taskpane = Sw.CreateTaskpaneView3(Icons.TaskPaneIcons(), "SwPy - Python");
                _pane = _taskpane.AddControl(EditorPane.ProgIdName, "") as EditorPane;
                if (_pane == null)
                {
                    // Fallback when the control's COM class is not registered: host by window handle.
                    Log.Info("AddControl returned no EditorPane; hosting by window handle");
                    _pane = new EditorPane();
                    _taskpane.DisplayWindowFromHandlex64(_pane.Handle.ToInt64());
                }
                _pane.Runner = Run;
                _pane.Resetter = session => PythonHost.Get(this).Reset(session);
                Log.Info("Task pane created");
            }
            catch (Exception ex)
            {
                Log.Error("Creating task pane failed", ex);
            }
        }

        private ExecResult Run(string session, string code)
        {
            var watch = Stopwatch.StartNew();
            try
            {
                var json = PythonHost.Get(this).Execute(session, code);
                return ExecResult.Parse(json, watch.ElapsedMilliseconds);
            }
            catch (Exception ex)
            {
                Log.Error("Run failed", ex);
                return ExecResult.HostError("Host error: " + ex, watch.ElapsedMilliseconds);
            }
        }

        // ---------------------------------------------------------------- automation

        public string Version() => typeof(SwPyAddIn).Assembly.GetName().Version.ToString();

        public string Execute(string session, string code)
        {
            try
            {
                return Main.Invoke(() => PythonHost.Get(this).Execute(session, code));
            }
            catch (Exception ex)
            {
                Log.Error("Execute failed", ex);
                return "{\"ok\": false, \"stdout\": \"\", \"result\": null, \"error\": "
                       + JsonString("Host error: " + ex) + "}";
            }
        }

        public string Pane(string command, string arg)
        {
            if (_pane == null) throw new InvalidOperationException("Editor pane not created");
            return Main.Invoke(() => _pane.Command(command, arg));
        }

        private static string JsonString(string s) =>
            "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "\\r").Replace("\n", "\\n") + "\"";
    }
}
