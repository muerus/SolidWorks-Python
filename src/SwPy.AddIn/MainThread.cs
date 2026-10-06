using System;
using System.Threading;
using System.Windows.Forms;

namespace SwPy
{
    /// <summary>
    /// Runs work on SOLIDWORKS' main (STA UI) thread.
    /// External COM clients call the add-in on MTA RPC threads; every SOLIDWORKS API call made from
    /// there is marshalled back to the UI thread (~300 ms each). Hopping once to the UI thread and
    /// running the whole script there makes API calls direct in-process calls.
    /// Must be constructed on the main thread (ConnectToSW).
    /// </summary>
    internal sealed class MainThread : IDisposable
    {
        private readonly Control _control;

        public int ThreadId { get; }

        public MainThread()
        {
            ThreadId = Thread.CurrentThread.ManagedThreadId;
            _control = new Control();
            _control.CreateControl();
            _ = _control.Handle;   // force window creation on this thread
        }

        public bool IsCurrent => Thread.CurrentThread.ManagedThreadId == ThreadId;

        public T Invoke<T>(Func<T> work) => IsCurrent ? work() : (T)_control.Invoke(work);

        public void Dispose() => _control.Dispose();
    }
}
