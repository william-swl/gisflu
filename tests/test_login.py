import pytest
import gisflu


@pytest.mark.parametrize("passwd", ["12345678", "abcdefdfs", "as52345fasdf4"])
def test_passwd_length(passwd):
    assert len(passwd) >= 8


def test_login():
    cred = gisflu.login()
    assert cred.sessionId is not None, "Failed to fetch GISAID"
    assert cred.browseParamsCeid["type"] is not None, "Failed to fetch browse page"
