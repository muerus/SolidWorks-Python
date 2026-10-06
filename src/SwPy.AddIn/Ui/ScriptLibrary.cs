using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace SwPy.Ui
{
    /// <summary>
    /// The user's script folder (default Documents\SwPy\Scripts): every *.py becomes a toolbar button;
    /// scripts in the "startup" subfolder run once after SOLIDWORKS starts.
    /// </summary>
    internal static class ScriptLibrary
    {
        /// <summary>Runtime override (tests); not persisted.</summary>
        internal static string Override { get; set; }

        internal static string DefaultFolder { get; } = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "SwPy", "Scripts");

        internal static string Folder
        {
            get
            {
                if (!string.IsNullOrEmpty(Override)) return Override;
                var configured = EditorSettings.Load().ScriptsFolder;
                return string.IsNullOrWhiteSpace(configured) ? DefaultFolder : configured;
            }
        }

        internal static string StartupFolder => Path.Combine(Folder, "startup");

        /// <summary>Toolbar scripts: *.py in the folder (not in subfolders), names starting with "_" skipped.</summary>
        internal static List<string> Scripts() => List(Folder);

        internal static List<string> StartupScripts() => List(StartupFolder);

        private static List<string> List(string folder)
        {
            try
            {
                if (!Directory.Exists(folder)) return new List<string>();
                return Directory.GetFiles(folder, "*.py")
                    .Where(p => !Path.GetFileName(p).StartsWith("_"))
                    .OrderBy(p => Path.GetFileName(p), StringComparer.OrdinalIgnoreCase)
                    .ToList();
            }
            catch (Exception ex)
            {
                Log.Error("Listing scripts in " + folder + " failed", ex);
                return new List<string>();
            }
        }

        /// <summary>Button text: the file name without extension, underscores as spaces.</summary>
        internal static string Title(string path) => Path.GetFileNameWithoutExtension(path).Replace('_', ' ');

        /// <summary>Tooltip: the first comment or docstring line of the script.</summary>
        internal static string Describe(string path)
        {
            try
            {
                foreach (var raw in File.ReadLines(path).Take(15))
                {
                    var line = raw.Trim();
                    if (line.StartsWith("# r:") || line.StartsWith("#!") || line.Length == 0) continue;
                    if (line.StartsWith("#")) return line.TrimStart('#').Trim();
                    if (line.StartsWith("\"\"\"") || line.StartsWith("'''"))
                    {
                        var text = line.Trim('"', '\'').Trim();
                        if (text.Length > 0) return text;
                        continue;
                    }
                    break;
                }
            }
            catch (Exception ex)
            {
                Log.Error("Reading " + path + " failed", ex);
            }
            return "Run " + Path.GetFileName(path);
        }

        /// <summary>Create the folder with an example script the first time.</summary>
        internal static void EnsureFolder()
        {
            var folder = Folder;
            if (Directory.Exists(folder)) return;
            try
            {
                Directory.CreateDirectory(folder);
                Directory.CreateDirectory(Path.Combine(folder, "startup"));
                File.WriteAllText(Path.Combine(folder, "List_features.py"),
                    "# List the features of the active document\n" +
                    "if doc is None:\n" +
                    "    ui.message(\"Open a document first.\", \"warning\")\n" +
                    "else:\n" +
                    "    for f in model.features():\n" +
                    "        print(f.GetTypeName2().ljust(20), f.Name)\n",
                    new UTF8Encoding(false));
            }
            catch (Exception ex)
            {
                Log.Error("Creating script folder " + folder + " failed", ex);
            }
        }
    }
}
