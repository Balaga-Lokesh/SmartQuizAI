import pytest

from app.core import security


def test_hash_and_verify_success():
    pw = "correct horse battery staple"
    hashed = security.hash_password(pw)
    assert isinstance(hashed, str)
    # verify should return True for correct password
    assert security.verify_password(pw, hashed) is True


def test_verify_wrong_password():
    pw = "shortpw"
    hashed = security.hash_password(pw)
    # wrong candidate must fail
    assert security.verify_password("not-the-right-one", hashed) is False
