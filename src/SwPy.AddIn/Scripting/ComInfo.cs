using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;

namespace SwPy.Scripting
{
    /// <summary>
    /// COM helpers for swpy.com. Probing interfaces from Python costs one pythonnet transition per
    /// check (~20 us); doing the whole QueryInterface sweep here is one call.
    /// </summary>
    public static class ComInfo
    {
        private static readonly ConcurrentDictionary<string, Type> Types = new ConcurrentDictionary<string, Type>();

        /// <summary>Comma-separated subset of <paramref name="candidatesCsv"/> that <paramref name="o"/> implements, in order.</summary>
        public static string Implemented(object o, string candidatesCsv)
        {
            if (o == null || !Marshal.IsComObject(o)) return "";
            var hits = new List<string>();
            foreach (var name in candidatesCsv.Split(','))
            {
                var type = Types.GetOrAdd(name, n => typeof(ISldWorks).Assembly.GetType("SolidWorks.Interop.sldworks." + n));
                if (type != null && type.IsInstanceOfType(o)) hits.Add(name);
            }
            return string.Join(",", hits);
        }

        // ---------------------------------------------------------------- detection across all libraries

        private const string LibrariesNamespace = "SwPy.Scripting.Libraries";
        private static readonly object SweepGate = new object();
        private static List<KeyValuePair<string, Type>> _all;
        private static readonly ConcurrentDictionary<long, string> ByClass = new ConcurrentDictionary<long, string>();
        private static readonly HashSet<string> Noise = new HashSet<string> { "ISldHotfix", "SldHotfix" };

        /// <summary>
        /// Every interface of every SOLIDWORKS API library the object implements: plain names for sldworks
        /// ("IFace2"), "library.Name" for the others ("swmotionstudy.IMotionStudyManager"). Used when the
        /// curated list finds nothing. A full sweep is ~2000 QueryInterface checks, so results are cached
        /// per COM class (all instances of a class share their IUnknown vtable) and re-validated on use.
        /// </summary>
        public static string Detect(object o)
        {
            if (o == null || !Marshal.IsComObject(o)) return "";
            long key;
            var unk = Marshal.GetIUnknownForObject(o);
            try { key = Marshal.ReadIntPtr(unk).ToInt64(); }
            finally { Marshal.Release(unk); }
            if (ByClass.TryGetValue(key, out var cached) && StillMatches(o, cached)) return cached;
            var found = Sweep(o);
            ByClass[key] = found;
            return found;
        }

        private static bool StillMatches(object o, string cached)
        {
            if (cached.Length == 0) return true;
            var first = cached.Split(',')[0];
            var type = AllInterfaces().FirstOrDefault(p => p.Key == first).Value;
            return type != null && type.IsInstanceOfType(o);
        }

        private static string Sweep(object o) =>
            string.Join(",", AllInterfaces().Where(p => p.Value.IsInstanceOfType(o)).Select(p => p.Key));



        /// <summary>
        /// Only plain API interfaces may be probed. IsInstanceOfType against an event interface
        /// (DSldWorksEvents_Event ...) or a coclass interface inheriting one (SldWorks, AssemblyDoc ...)
        /// makes the CLR set up COM event plumbing on the object; on the application object that
        /// kills SOLIDWORKS. Coclass interfaces only duplicate their I-interface anyway.
        /// </summary>
        private static bool Probeable(Type t)
        {
            if (!t.IsInterface || Noise.Contains(t.Name)) return false;
            if (t.IsDefined(typeof(ComEventInterfaceAttribute), false) || t.IsDefined(typeof(CoClassAttribute), false))
                return false;
            if (t.Name.EndsWith("_Event") || (t.Name.StartsWith("D") && t.Name.EndsWith("Events"))) return false;
            return !t.GetInterfaces().Any(i => i.IsDefined(typeof(ComEventInterfaceAttribute), false));
        }

        /// <summary>(qualified name, interface type) for sldworks and every generated library cast class.</summary>
        private static List<KeyValuePair<string, Type>> AllInterfaces()
        {
            if (_all != null) return _all;
            lock (SweepGate)
            {
                if (_all != null) return _all;
                var list = typeof(ISldWorks).Assembly.GetExportedTypes()
                    .Where(t => t.Namespace == "SolidWorks.Interop.sldworks" && Probeable(t))
                    .Select(t => new KeyValuePair<string, Type>(t.Name, t)).ToList();
                foreach (var cls in typeof(ComInfo).Assembly.GetTypes().Where(t => t.Namespace == LibrariesNamespace))
                {
                    var library = cls.Name.Substring("Cast_".Length);
                    try
                    {
                        list.AddRange(cls.GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static)
                            .Where(m => Probeable(m.ReturnType))
                            .Select(m => new KeyValuePair<string, Type>(library + "." + m.ReturnType.Name, m.ReturnType)));
                    }
                    catch (Exception ex)   // interop assembly missing on this machine: skip that library
                    {
                        Log.Info($"API library {library} unavailable: {ex.Message}");
                    }
                }
                return _all = list;
            }
        }

        /// <summary>COM identity: the IUnknown pointer, equal for all references to one object.</summary>
        public static long Identity(object o)
        {
            var ptr = Marshal.GetIUnknownForObject(o);
            try { return ptr.ToInt64(); }
            finally { Marshal.Release(ptr); }
        }
    }
}
