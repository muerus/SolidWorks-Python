using System;
using System.Windows.Forms;

namespace SwPy.Ui
{
    /// <summary>Owner window for dialogs shown from Python (swpy.ui): wraps the SOLIDWORKS frame handle.</summary>
    public sealed class WindowHandle : IWin32Window
    {
        public WindowHandle(long handle) => Handle = new IntPtr(handle);

        public IntPtr Handle { get; }
    }
}
