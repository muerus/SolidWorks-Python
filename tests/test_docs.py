"""User guide stays correct: every ```python live block runs in SOLIDWORKS, and the API reference
mentions every public name of swpy."""
import ast
import os
import re

import pytest

from test_host import PART
from test_model import BOSS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GUIDE = os.path.join(ROOT, "docs", "guide")
LIVE = re.compile(r"^```python live\n(.*?)^```", re.M | re.S)


def _guides():
    out = []
    for name in sorted(os.listdir(GUIDE)):
        if name.endswith(".md"):
            with open(os.path.join(GUIDE, name), encoding="utf-8") as f:
                blocks = LIVE.findall(f.read())
            if blocks:
                out.append((name, blocks))
    return out


def _open_titles(swpy, session):
    return set(swpy.ok("[d.GetTitle() for d in (sw.GetDocuments() or [])]", session)["value"])


@pytest.mark.parametrize("name,blocks", _guides(), ids=[g[0] for g in _guides()])
def test_guide_examples_run(swpy, name, blocks):
    session = "docs-" + name
    swpy.ok(f"import swpy._host as _h\n_h.reset({session!r})", "docs-admin")
    before = _open_titles(swpy, "docs-admin")
    swpy.ok(PART + BOSS, session)            # sample part: block + cylinder, active
    try:
        for i, code in enumerate(blocks, 1):
            r = swpy.run(code, session)
            assert r["ok"], f"{name}, live block {i}:\n{code}\n{r['error']}"
    finally:
        for title in _open_titles(swpy, "docs-admin") - before:
            swpy.run(f"sw.CloseDoc({title!r})", "docs-admin")


# ---------------------------------------------------------------- API reference coverage (static)

MODULES = ["units", "model", "com", "packages", "client", "events", "ui", "build", "assembly", "drawing"]


def _public_names(module):
    with open(os.path.join(ROOT, "python", "swpy", module + ".py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            names.append(node.name)
            if isinstance(node, ast.ClassDef):
                names += [n.name for n in node.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name) and not t.id.startswith("_")]
            names += [e.id for t in node.targets if isinstance(t, ast.Tuple) for e in t.elts
                      if isinstance(e, ast.Name) and not e.id.startswith("_")]
    return names


@pytest.mark.parametrize("module", MODULES)
def test_api_reference_covers_module(module):
    with open(os.path.join(GUIDE, "api-reference.md"), encoding="utf-8") as f:
        text = f.read()
    ignore = {"CREATE_NO_WINDOW", "ASM", "TYPES", "KNOWN", "LABELS", "CANDIDATES_CSV", "GLOBAL", "VALUE_UNIT",
              "HEADER", "NAME", "call", "cast"}
    missing = [n for n in _public_names(module) if n not in ignore and not re.search(rf"\b{re.escape(n)}\b", text)]
    assert not missing, f"api-reference.md does not mention swpy.{module}: {missing}"
