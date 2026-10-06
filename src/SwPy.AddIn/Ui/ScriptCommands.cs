using System;
using System.Collections.Generic;
using System.Linq;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace SwPy.Ui
{
    /// <summary>
    /// The SwPy command group: a toolbar, a "SwPy" menu and a "SwPy" CommandManager tab (parts, assemblies,
    /// drawings) with one button per script of the ScriptLibrary, plus Refresh and Open folder.
    /// Callbacks are methods of ISwPyAutomation (SOLIDWORKS calls them by name through IDispatch).
    /// </summary>
    internal sealed class ScriptCommands
    {
        public const int GroupId = 7701;
        private const string TabName = "SwPy";
        private static readonly int[] DocTypes =
        {
            (int)swDocumentTypes_e.swDocPART, (int)swDocumentTypes_e.swDocASSEMBLY, (int)swDocumentTypes_e.swDocDRAWING,
        };

        private readonly ISldWorks _sw;
        private readonly int _cookie;
        private CommandGroup _group;

        public ScriptCommands(ISldWorks sw, int cookie)
        {
            _sw = sw;
            _cookie = cookie;
        }

        /// <summary>Scripts behind the buttons, in button order (index = SwPyRunScript argument).</summary>
        public List<string> Scripts { get; private set; } = new List<string>();

        public List<string> Titles { get; } = new List<string>();
        public bool TabsCreated { get; private set; }
        public int CreateErrors { get; private set; }
        public int Cookie => _cookie;

        public void Create()
        {
            ScriptLibrary.EnsureFolder();
            Scripts = ScriptLibrary.Scripts();
            var mgr = _sw.GetCommandManager(_cookie);
            var errors = 0;
            _group = mgr.CreateCommandGroup2(GroupId, "SwPy", "Python scripts", "Run Python scripts", -1, true, ref errors);
            CreateErrors = errors;
            if (_group == null)
            {
                Log.Info($"CreateCommandGroup2 failed (error {errors})");
                return;
            }

            var labels = new List<(string title, string tip, string glyph)>
            {
                ("Refresh scripts", "Rescan the script folder", "↻"),
                ("Script folder", "Open the script folder in Explorer", "…"),
            };
            labels.AddRange(Scripts.Select(p => (ScriptLibrary.Title(p), ScriptLibrary.Describe(p), Initials(p))));
            _group.IconList = Icons.CommandStrips(labels.Select(l => l.glyph).ToArray());
            _group.MainIconList = Icons.TaskPaneIcons();

            const int both = (int)(swCommandItemType_e.swMenuItem | swCommandItemType_e.swToolbarItem);
            var indexes = new List<int>
            {
                _group.AddCommandItem2(labels[0].title, -1, labels[0].tip, labels[0].tip, 0, "SwPyRefreshScripts", "", 1, both),
                _group.AddCommandItem2(labels[1].title, -1, labels[1].tip, labels[1].tip, 1, "SwPyOpenScriptsFolder", "", 2, both),
            };
            for (var i = 0; i < Scripts.Count; i++)
            {
                var (title, tip, _) = labels[i + 2];
                indexes.Add(_group.AddCommandItem2(title, -1, tip, tip, i + 2, $"SwPyRunScript({i})", "", 100 + i, both));
            }
            _group.HasToolbar = true;
            _group.HasMenu = true;
            _group.Activate();
            Titles.Clear();
            Titles.AddRange(labels.Select(l => l.title));
            CreateTabs(mgr, indexes);
            Log.Info($"Script commands: {Scripts.Count} script(s) from {ScriptLibrary.Folder}");
        }

        private void CreateTabs(ICommandManager mgr, List<int> indexes)
        {
            var ids = indexes.Select(i => _group.get_CommandID(i)).ToArray();
            var styles = ids.Select(_ => (int)swCommandTabButtonTextDisplay_e.swCommandTabButton_TextBelow).ToArray();
            foreach (var type in DocTypes)
            {
                var tab = mgr.GetCommandTab(type, TabName);
                if (tab != null) mgr.RemoveCommandTab(tab);
                tab = mgr.AddCommandTab(type, TabName);
                tab?.AddCommandTabBox()?.AddCommands(ids, styles);
            }
            TabsCreated = true;
        }

        public void Remove()
        {
            try
            {
                var mgr = _sw.GetCommandManager(_cookie);
                foreach (var type in DocTypes)
                {
                    var tab = mgr.GetCommandTab(type, TabName);
                    if (tab != null) mgr.RemoveCommandTab(tab);
                }
                mgr.RemoveCommandGroup2(GroupId, true);
            }
            catch (Exception ex)
            {
                Log.Error("Removing script commands failed", ex);
            }
            _group = null;
            TabsCreated = false;
        }

        public void Refresh()
        {
            Remove();
            Create();
        }

        /// <summary>Two letters for the button icon: "export_step" -> "ES".</summary>
        private static string Initials(string path)
        {
            var words = ScriptLibrary.Title(path).Split(new[] { ' ', '-' }, StringSplitOptions.RemoveEmptyEntries);
            var s = words.Length >= 2 ? $"{words[0][0]}{words[1][0]}" : (words.FirstOrDefault() ?? "Py");
            return s.Substring(0, Math.Min(2, s.Length)).ToUpperInvariant();
        }
    }
}
