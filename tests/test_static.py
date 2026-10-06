"""Checks that need no SOLIDWORKS."""
import glob
import os
import py_compile

import pytest

FILES = glob.glob(os.path.join(os.path.dirname(__file__), "..", "python", "swpy", "*.py"))


@pytest.mark.parametrize("path", FILES, ids=os.path.basename)
def test_compiles(path):
    py_compile.compile(path, doraise=True)
