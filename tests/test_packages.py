"""`# r:` requirements and the bundled runtime."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from swpy import packages  # noqa: E402  (pure Python, no SOLIDWORKS needed)


def test_requirement_parsing():
    code = "# r: numpy, pandas>=2\n#r:tabulate==0.9.0\nimport numpy\n# regular comment"
    assert packages.requirements(code) == ["numpy", "pandas>=2", "tabulate==0.9.0"]


def test_satisfied_checks_version():
    assert packages.satisfied("pytest")
    assert not packages.satisfied("pytest==0.0.1")
    assert not packages.satisfied("surely-not-a-real-package-xyz")


def test_runtime_has_python_and_pip(swpy):
    r = swpy.ok("import sys, swpy.packages as p; (sys.base_prefix, p.python_exe(), p.pip_command()[-1])", "pkg")
    assert "python" in r["result"].lower()


def test_r_header_installs_and_imports(swpy):
    code = "# r: tabulate\nimport tabulate\ntabulate.tabulate([[1, 2]])"
    r = swpy.ok(code, "pkg")
    assert "1" in r["result"]
    r2 = swpy.ok(code, "pkg")                      # second time: already satisfied, no install message
    assert "installing" not in r2["stdout"]
