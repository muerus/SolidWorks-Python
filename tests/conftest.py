import pytest

import harness


@pytest.fixture(scope="session")
def swpy():
    """Live SwPy client. Starts SOLIDWORKS (dev env) and loads the add-in if needed."""
    return harness.SwPy()


@pytest.fixture
def session(request):
    """A fresh, test-specific session name."""
    return f"t-{request.node.name}"
