using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace SwPy.Ui
{
    /// <summary>Editor preferences and open tabs, persisted in %LOCALAPPDATA%\SwPy\editor.json.</summary>
    public sealed class EditorSettings
    {
        public const int MaxRecent = 12;

        public string Theme { get; set; } = "light";
        public int Zoom { get; set; }
        public bool WordWrap { get; set; }
        /// <summary>Folder of toolbar scripts (empty: Documents\SwPy\Scripts).</summary>
        public string ScriptsFolder { get; set; } = "";
        public List<string> Recent { get; set; } = new List<string>();
        /// <summary>Open tabs: file paths, or untitled buffers' backup files under the scratch folder.</summary>
        public List<string> OpenTabs { get; set; } = new List<string>();
        public int ActiveTab { get; set; }

        internal static string Dir { get; } =
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SwPy");

        internal static string FilePath => Path.Combine(Dir, "editor.json");

        internal static EditorSettings Load()
        {
            try
            {
                if (File.Exists(FilePath))
                    return new JavaScriptSerializer().Deserialize<EditorSettings>(File.ReadAllText(FilePath)) ?? new EditorSettings();
            }
            catch (Exception ex)
            {
                Log.Error("Loading editor settings failed", ex);
            }
            return new EditorSettings();
        }

        internal void Save()
        {
            try
            {
                Directory.CreateDirectory(Dir);
                File.WriteAllText(FilePath, new JavaScriptSerializer().Serialize(this), new UTF8Encoding(false));
            }
            catch (Exception ex)
            {
                Log.Error("Saving editor settings failed", ex);
            }
        }

        internal void AddRecent(string path)
        {
            Recent.RemoveAll(p => string.Equals(p, path, StringComparison.OrdinalIgnoreCase));
            Recent.Insert(0, path);
            if (Recent.Count > MaxRecent) Recent.RemoveRange(MaxRecent, Recent.Count - MaxRecent);
        }
    }
}
