using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using SwPy.Scripting;

namespace SwPy.Ui
{
    internal sealed class Completion
    {
        public int Start;                                   // length of the typed prefix
        public List<KeyValuePair<string, string>> Items;    // name, kind
    }

    internal sealed class Signature
    {
        public string Label, Doc;
        public List<int[]> Params;
    }

    internal sealed class SignatureHelp
    {
        public List<Signature> Signatures;
        public int Arg;
    }

    internal sealed class HoverInfo
    {
        public string Text, Help;
    }

    internal sealed class Diagnostic
    {
        public int Line, Col, EndCol;   // 1-based line, 0-based columns
        public string Message;
    }

    /// <summary>
    /// Typed client for swpy._editor (completion, signatures, hover, syntax check) in the editor session.
    /// Calls never throw; null means "nothing to show". While typing we never start Python
    /// (that takes a second); explicit requests (Ctrl+Space, '.') may.
    /// </summary>
    internal sealed class EditorServices
    {
        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        private readonly Func<PythonHost> _host;
        private readonly Func<bool> _started;

        public EditorServices(Func<PythonHost> host, Func<bool> started)
        {
            _host = host;
            _started = started;
        }

        public string Session { get; set; } = EditorPane.Session;
        public bool IsStarted => _started();

        /// <summary>Raw call: returns the JSON-decoded value, or null.</summary>
        public object Call(string method, Dictionary<string, object> args, bool mayStartPython)
        {
            if (!mayStartPython && !_started()) return null;
            try
            {
                args["session"] = Session;
                var reply = Json.DeserializeObject(_host().Call(method, Json.Serialize(args))) as Dictionary<string, object>;
                if (reply == null) return null;
                if (!(reply.TryGetValue("ok", out var ok) && ok is bool b && b))
                {
                    Log.Info($"editor service {method}: {(reply.TryGetValue("error", out var e) ? e : "?")}");
                    return null;
                }
                return reply.TryGetValue("value", out var v) ? v : null;
            }
            catch (Exception ex)
            {
                Log.Error("Editor service " + method + " failed", ex);
                return null;
            }
        }

        /// <summary>Raw JSON of a call (tests / pane automation).</summary>
        public string CallJson(string method, string argsJson)
        {
            var args = Json.DeserializeObject(string.IsNullOrEmpty(argsJson) ? "{}" : argsJson) as Dictionary<string, object>
                       ?? new Dictionary<string, object>();
            return Json.Serialize(Call(method, args, true));
        }

        public Completion Complete(string before, string source, bool mayStartPython)
        {
            if (!(Call("complete", new Dictionary<string, object> { ["before"] = before, ["source"] = source }, mayStartPython)
                    is Dictionary<string, object> d)) return null;
            return new Completion
            {
                Start = Convert.ToInt32(d["start"]),
                Items = ((IEnumerable)d["items"]).Cast<object[]>()
                    .Select(i => new KeyValuePair<string, string>((string)i[0], (string)i[1])).ToList(),
            };
        }

        public SignatureHelp Signature(string before, bool mayStartPython)
        {
            if (!(Call("signature", new Dictionary<string, object> { ["before"] = before }, mayStartPython)
                    is Dictionary<string, object> d)) return null;
            return new SignatureHelp
            {
                Arg = Convert.ToInt32(d["arg"]),
                Signatures = ((IEnumerable)d["signatures"]).Cast<Dictionary<string, object>>().Select(s => new Signature
                {
                    Label = (string)s["label"],
                    Doc = s.TryGetValue("doc", out var doc) ? doc as string : null,
                    Params = ((IEnumerable)s["params"]).Cast<object[]>()
                        .Select(p => new[] { Convert.ToInt32(p[0]), Convert.ToInt32(p[1]) }).ToList(),
                }).ToList(),
            };
        }

        public HoverInfo Hover(string before)
        {
            if (!(Call("hover", new Dictionary<string, object> { ["before"] = before }, false)
                    is Dictionary<string, object> d)) return null;
            return new HoverInfo { Text = d["text"] as string, Help = d.TryGetValue("help", out var h) ? h as string : null };
        }

        public Diagnostic Check(string source)
        {
            if (!(Call("check", new Dictionary<string, object> { ["source"] = source }, false)
                    is Dictionary<string, object> d)) return null;
            return new Diagnostic
            {
                Line = Convert.ToInt32(d["line"]),
                Col = Convert.ToInt32(d["col"]),
                EndCol = Convert.ToInt32(d["end_col"]),
                Message = d["msg"] as string,
            };
        }
    }
}
