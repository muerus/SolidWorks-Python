"""Checks that need no SOLIDWORKS."""
import glob
import os
import py_compile

import pytest

FILES = glob.glob(os.path.join(os.path.dirname(__file__), "..", "python", "swpy", "*.py"))


@pytest.mark.parametrize("path", FILES, ids=os.path.basename)
def test_compiles(path):
    py_compile.compile(path, doraise=True)


def test_library_constants_modules_import():
    """Generated swpy.libs.* constant modules import outside SOLIDWORKS and match the metadata."""
    import importlib
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
    libs = importlib.import_module("swpy.libs")
    for name, meta in libs.LIBRARIES.items():
        module = importlib.import_module(f"swpy.libs.{name}")
        enums = [n for n, v in vars(module).items() if isinstance(v, type) and not n.startswith("_")]
        assert len(enums) == meta["enums"], name
