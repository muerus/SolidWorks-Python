"""`# r: package` requirements, Rhino-8 style.

    # r: numpy, pandas>=2
    import numpy as np

Missing packages are pip-installed into %LOCALAPPDATA%\\SwPy\\site-packages\\py3.X (never into the
Python install), using python.exe next to the embedded runtime and either its own pip or a bundled
pip wheel (python-runtime\\pip-*.whl).
"""
import glob
import importlib
import importlib.metadata as md
import os
import re
import subprocess
import sys

_HEADER = re.compile(r"^\s*#\s*r\s*:\s*(.+?)\s*$")
# PEP 508 subset: name, optional [extras], optional comma-separated version specifiers. No URLs/options.
_SPEC = r"\s*(==|!=|>=|<=|~=|>|<)\s*[A-Za-z0-9.*+!_-]+"
_REQUIREMENT = re.compile(rf"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9._,-]+\])?({_SPEC}(\s*,{_SPEC})*)?$")
_NAME = re.compile(r"^\s*([A-Za-z0-9_.\-\[\]]+)\s*(==\s*([^\s,;]+))?")
CREATE_NO_WINDOW = 0x08000000


def site_dir():
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SwPy", "site-packages",
                     f"py{sys.version_info[0]}.{sys.version_info[1]}")
    os.makedirs(d, exist_ok=True)
    if d not in sys.path:
        sys.path.insert(0, d)
    return d


def requirements(code):
    """Requirement specs from `# r:` comment lines (anywhere in the script, like Rhino).

    Only plain PyPI requirements are accepted (`name`, `name[extra]`, `name>=1,<2`). Anything else - pip
    options like `--index-url`, URLs, paths - raises ValueError, so a script header cannot point pip at
    another package source or pass it arbitrary options.
    """
    reqs = []
    for line in code.splitlines():
        m = _HEADER.match(line)
        if m:
            reqs += [r.strip() for r in re.split(r"[,\s]+(?=[A-Za-z-])", m.group(1)) if r.strip()]
    bad = [r for r in reqs if not _REQUIREMENT.match(r)]
    if bad:
        raise ValueError(f"# r: only accepts PyPI package names with optional versions, not {', '.join(bad)}")
    return reqs


def satisfied(req):
    m = _NAME.match(req)
    if not m:
        return False
    name = m.group(1).split("[")[0]
    try:
        version = md.version(name)
    except md.PackageNotFoundError:
        return False
    return m.group(3) is None or version == m.group(3)


def python_exe():
    exe = os.path.join(sys.base_prefix, "python.exe")
    if not os.path.exists(exe):
        raise RuntimeError(f"python.exe not found next to the embedded runtime ({sys.base_prefix})")
    return exe


def pip_command():
    if os.path.isdir(os.path.join(sys.base_prefix, "Lib", "site-packages", "pip")):
        return [python_exe(), "-m", "pip"]
    wheels = sorted(glob.glob(os.path.join(sys.base_prefix, "pip-*.whl")))
    if wheels:
        return [python_exe(), os.path.join(wheels[-1], "pip")]
    raise RuntimeError("No pip available: install pip into the runtime or bundle a pip wheel")


def ensure(reqs, log=print):
    """Install missing requirements. Returns the list that was installed."""
    target = site_dir()
    missing = [r for r in reqs if not satisfied(r)]
    if not missing:
        return []
    log(f"# r: installing {', '.join(missing)} ...\n")
    cmd = pip_command() + ["install", "--disable-pip-version-check", "--no-warn-script-location",
                           "--target", target, *missing]
    proc = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError(f"pip install failed:\n{proc.stdout}\n{proc.stderr}")
    importlib.invalidate_caches()
    log(f"# r: installed {', '.join(missing)}\n")
    return missing
