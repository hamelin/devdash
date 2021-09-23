from typing import *  # noqa
import pytest

from devdash import deansi, _expect_line, _expect_empty


def test_deansi_empty():
    assert deansi("") == ""


def test_deansi_no_code():
    assert deansi("asdf qwer\nzxcv") == "asdf qwer\nzxcv"


def test_deansi_color():
    assert deansi(
        "default \x1b[33mgreen\x1b[0m \x1b[36mcyan\x1b[0m"
    ) == "default green cyan"


STDOUT_TEST = ["asdf qwer zxcv\n", "heyhey hoho\n"]


def run_test_expect_line_ok(
    prefix: str = "",
    suffix: str = "",
    substr: str = ""
) -> None:
    _expect_line(iter(STDOUT_TEST), prefix=prefix, suffix=suffix, substr=substr)


def run_test_expect_line_wrong(
    prefix: str = "",
    suffix: str = "",
    substr: str = ""
) -> None:
    with pytest.raises(ValueError):
        _expect_line(iter(STDOUT_TEST), prefix=prefix, suffix=suffix, substr=substr)


def test_expect_line_prefix_ok():
    run_test_expect_line_ok(prefix="asdf")


def test_expect_line_prefix_wrong():
    run_test_expect_line_wrong(prefix="qwer")
    run_test_expect_line_wrong(prefix="hey")


def test_expect_line_suffix_ok():
    run_test_expect_line_ok(suffix="zxcv")


def test_expect_line_suffix_wrong():
    run_test_expect_line_wrong(suffix="z")
    run_test_expect_line_wrong(suffix="hoho")


def test_expect_line_substr_ok():
    run_test_expect_line_ok(substr="qwer")
    run_test_expect_line_ok(substr="df qw")


def test_expect_line_substr_wrong():
    run_test_expect_line_wrong(substr="nope")
    run_test_expect_line_wrong(substr="hey ho")


def test_expect_line_all_ok():
    run_test_expect_line_ok(prefix="asdf", suffix="xcv", substr="qw")


def test_expect_line_all_wrong():
    run_test_expect_line_wrong(prefix="asdf", suffix="zxcv", substr="hey")
    run_test_expect_line_wrong(prefix="h", suffix="v", substr="qwer")
    run_test_expect_line_wrong(prefix="asdf", suffix="y", substr="qwer")


STDOUT_EMPTY = ["    \n", "asdf\n"]


def test_expect_empty():
    i = iter(STDOUT_EMPTY)
    _expect_empty(i)
    with pytest.raises(ValueError):
        _expect_empty(i)
