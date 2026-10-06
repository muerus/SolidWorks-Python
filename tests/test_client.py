"""L5: out-of-process client (swpy.client) over the COM bridge."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import swpy.client as swc  # noqa: E402


@pytest.fixture(scope="module")
def client(swpy):   # swpy fixture guarantees SOLIDWORKS + add-in are up
    c = swc.connect(session="client-tests")
    c.reset()
    return c


def test_version(client):
    assert client.version().startswith("0.")


def test_eval_returns_python_values(client):
    assert client.eval("1 + 1") == 2
    assert client.eval("{'a': [1, 2.5, 'x']}") == {"a": [1, 2.5, "x"]}


def test_eval_non_json_returns_repr(client):
    assert client.eval("sw").startswith("<ISldWorks")


def test_exec_returns_stdout_and_state_persists(client):
    assert client.exec("v = 41\nprint('hello')") == "hello\n"
    assert client("v + 1") == 42


def test_errors_raise(client):
    with pytest.raises(swc.SwPyError, match="ZeroDivisionError"):
        client.eval("1/0")


def test_reset(client):
    client.exec("gone = 1")
    client.reset()
    with pytest.raises(swc.SwPyError, match="NameError"):
        client.eval("gone")


def test_addin_dll_registered():
    assert os.path.exists(swc.addin_dll())
