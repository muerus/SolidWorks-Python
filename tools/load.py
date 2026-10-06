"""Load SwPy into the SOLIDWORKS you already have open (until startup auto-load is packaged).

    .venv\\Scripts\\python tools\\load.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))
import harness  # noqa: E402

sw = harness.get_sw(start=False)
if sw is None:
    sys.exit("SOLIDWORKS is not running - start it first.")
client = harness.SwPy(sw)
print(f"SwPy {client.version()} loaded - open the 'Py' tab in the Task Pane.")
