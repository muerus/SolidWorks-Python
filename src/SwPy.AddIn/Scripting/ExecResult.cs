using System.Collections.Generic;
using System.Web.Script.Serialization;

namespace SwPy.Scripting
{
    /// <summary>Outcome of one script run (parsed from swpy._host.run's JSON).</summary>
    internal sealed class ExecResult
    {
        public bool Ok;
        public string Stdout = "";
        public string Result;
        public string Error;
        public long ElapsedMs;
        public bool Streamed;

        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        public static ExecResult Parse(string json, long elapsedMs)
        {
            var d = Json.Deserialize<Dictionary<string, object>>(json);
            return new ExecResult
            {
                Ok = d.TryGetValue("ok", out var ok) && ok is bool b && b,
                Stdout = d.TryGetValue("stdout", out var o) ? o as string ?? "" : "",
                Result = d.TryGetValue("result", out var r) ? r as string : null,
                Error = d.TryGetValue("error", out var e) ? e as string : null,
                ElapsedMs = elapsedMs,
            };
        }

        public static ExecResult HostError(string message, long elapsedMs) =>
            new ExecResult { Ok = false, Error = message, ElapsedMs = elapsedMs };
    }
}
