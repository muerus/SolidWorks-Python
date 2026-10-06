using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
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

        /// <summary>COM identity: the IUnknown pointer, equal for all references to one object.</summary>
        public static long Identity(object o)
        {
            var ptr = Marshal.GetIUnknownForObject(o);
            try { return ptr.ToInt64(); }
            finally { Marshal.Release(ptr); }
        }
    }
}
