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

        // CommandManager callbacks (SOLIDWORKS calls them by name through IDispatch)

        /// <summary>Run script button number <paramref name="index"/> (ScriptCommands.Scripts).</summary>
        void SwPyRunScript(string index);

        void SwPyRefreshScripts();

        void SwPyOpenScriptsFolder();
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
        private ScriptCommands _commands;

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
                if (!Flag("SWPY_NO_PANE")) CreatePane();
                if (!Flag("SWPY_NO_COMMANDS")) CreateCommands();
                ScheduleStartupScripts();
                return true;
            }
            catch (Exception ex)
            {
                Log.Error("ConnectToSW failed", ex);
                return false;
            }
        }

        private static bool Flag(string name) => System.Environment.GetEnvironmentVariable(name) == "1";

        public bool DisconnectFromSW()
        {
            Log.Info("Disconnecting");
            try
            {
                if (PythonHost.IsStarted) PythonHost.Get(this).Shutdown();   // event handlers off first
            }
            catch (Exception ex)
            {
                Log.Error("Python shutdown failed", ex);
            }
            _commands?.Remove();   // toolbar, menu and CommandManager tabs (catches its own errors)
            _commands = null;
            try
            {
                if (!Flag("SWPY_SKIP_DELETEVIEW")) _taskpane?.DeleteView();
                if (_taskpane != null && !Flag("SWPY_SKIP_RELEASE")) Marshal.ReleaseComObject(_taskpane);
            }
            catch (Exception ex)
            {
                Log.Error("Removing task pane failed", ex);
            }
            _taskpane = null;
            _pane = null;
            if (!Flag("SWPY_SKIP_DISPOSE")) Main?.Dispose();
            Main = null;
            Instance = null;
            Sw = null;
            if (!Flag("SWPY_SKIP_GC"))
            {
                GC.Collect();
                GC.WaitForPendingFinalizers();
            }
            Log.Info("Disconnected");
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
                _pane.RefreshScriptCommands = SwPyRefreshScripts;
                _pane.Resetter = session => PythonHost.Get(this).Reset(session);
                _pane.Services = new EditorServices(() => PythonHost.Get(this), () => PythonHost.IsStarted);
                Log.Info("Task pane created");
            }
            catch (Exception ex)
            {
                Log.Error("Creating task pane failed", ex);
            }
        }

        private ExecResult Run(string session, string code, bool stream, string filename)
        {
            var watch = Stopwatch.StartNew();
            try
            {
                var json = PythonHost.Get(this).Execute(session, code, stream, filename);
                var r = ExecResult.Parse(json, watch.ElapsedMilliseconds);
                r.Streamed = stream;
                return r;
            }
            catch (Exception ex)
            {
                Log.Error("Run failed", ex);
                return ExecResult.HostError("Host error: " + ex, watch.ElapsedMilliseconds);
            }
        }

        /// <summary>Live output sink for streamed runs (called by swpy._host on the main thread).</summary>
        public void Write(string text, bool error) => _pane?.StreamWrite(text, error);

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
            switch (command)
            {
                case "toolbar":       // script commands state (tests)
                    return Main.Invoke(() => new System.Web.Script.Serialization.JavaScriptSerializer().Serialize(new
                    {
                        titles = _commands?.Titles.ToArray() ?? new string[0],
                        scripts = _commands?.Scripts.ToArray() ?? new string[0],
                        tabs = _commands?.TabsCreated ?? false,
                        folder = ScriptLibrary.Folder,
                        cookie = _cookie,
                        errors = _commands?.CreateErrors ?? -1,
                    }));
                case "scripts_folder":   // override the script folder for this session (tests), "" resets
                    return Main.Invoke(() =>
                    {
                        ScriptLibrary.Override = string.IsNullOrEmpty(arg) ? null : arg;
                        _commands?.Refresh();
                        return ScriptLibrary.Folder;
                    });
                case "startup":       // run the startup scripts now (tests)
                    return Main.Invoke(() => { RunStartupScripts(); return ""; });
            }
            if (_pane == null) throw new InvalidOperationException("Editor pane not created");
            if (command == "show") return Main.Invoke(() => { _taskpane?.ShowView(); return ""; });
            return Main.Invoke(() => _pane.Command(command, arg));
        }

        // ---------------------------------------------------------------- script buttons / startup scripts

        private void CreateCommands()
        {
            try
            {
                _commands = new ScriptCommands(Sw, _cookie);
                _commands.Create();
            }
            catch (Exception ex)
            {
                Log.Error("Creating script commands failed", ex);
            }
        }

        // Toolbar clicks arrive on the UI thread; COM clients (tests, other programs) call from an RPC
        // thread, so every callback is marshalled like Execute.
        public void SwPyRunScript(string index) => Main.Invoke(() =>
        {
            try
            {
                var scripts = _commands?.Scripts;
                if (scripts == null || !int.TryParse(index, out var i) || i < 0 || i >= scripts.Count) return 0;
                RunScriptFile(scripts[i]);
            }
            catch (Exception ex)
            {
                Log.Error("Script button failed", ex);
            }
            return 0;
        });

        public void SwPyRefreshScripts() => Main.Invoke(() => { _commands?.Refresh(); return 0; });

        public void SwPyOpenScriptsFolder() => Main.Invoke(() =>
        {
            ScriptLibrary.EnsureFolder();
            Process.Start("explorer.exe", "\"" + ScriptLibrary.Folder + "\"");
            return 0;
        });

        /// <summary>Run a .py file in the editor session; output goes to the pane, errors open the file.</summary>
        internal ExecResult RunScriptFile(string path)
        {
            if (_pane != null)
            {
                var r = _pane.RunFile(path);
                if (r != null && !r.Ok) _taskpane?.ShowView();
                return r;
            }
            var code = System.IO.File.ReadAllText(path);
            var result = Run(EditorPane.Session, code.Replace("\r\n", "\n"), false, path);
            if (!result.Ok) Log.Info($"Script {path} failed: {result.Error}");
            return result;
        }

        /// <summary>Startup scripts run once, when SOLIDWORKS is first idle (not during its own startup).</summary>
        private void ScheduleStartupScripts()
        {
            if (ScriptLibrary.StartupScripts().Count == 0) return;
            if (!(Sw is SldWorks app)) return;
            DSldWorksEvents_OnIdleNotifyEventHandler handler = null;
            handler = () =>
            {
                app.OnIdleNotify -= handler;
                RunStartupScripts();
                return 0;
            };
            app.OnIdleNotify += handler;
        }

        private void RunStartupScripts()
        {
            foreach (var path in ScriptLibrary.StartupScripts())
            {
                try
                {
                    Log.Info("Startup script " + path);
                    RunScriptFile(path);
                }
                catch (Exception ex)
                {
                    Log.Error("Startup script " + path + " failed", ex);
                }
            }
        }

        private static string JsonString(string s) =>
            "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "\\r").Replace("\n", "\\n") + "\"";
    }
}
