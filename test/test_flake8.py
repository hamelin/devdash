from textwrap import dedent
from typing import *  # noqa

import devdash as dd


def issue_parsing_test(stdout: str, expected: List[dd.Issue]) -> None:
    assert expected == list(dd.Flake8().iter_issues(dedent(stdout)))


def test_no_issue():
    issue_parsing_test("", [])


def test_posix_paths():
    issue_parsing_test(
        """\
        ./dummy/__init__.py:28:19: Wxxx something something
        ./heyhey.py:234:1: W391 blank line at end of file
        """,
        [
            ("./dummy/__init__.py", "28", "19", ["Wxxx something something"], ""),
            ("./heyhey.py", "234", "1", ["W391 blank line at end of file"], "")
        ]
    )


def test_windows_paths():
    issue_parsing_test(
        """\
        .\\dummy\\__init__.py:28:19: Wxxx something something
        .\\heyhey.py:234:1: W391 blank line at end of file
        """,
        [
            (".\\dummy\\__init__.py", "28", "19", ["Wxxx something something"], ""),
            (".\\heyhey.py", "234", "1", ["W391 blank line at end of file"], "")
        ]
    )


def test_malformed_line():
    issue_parsing_test(
        """\
        .\\dummy\\__init__.py:28:19: Wxxx something something
        ./heyhey.py: Some malformed line

        ./heyhey.py:234:1: W391 blank line at end of file
        """,
        [
            (".\\dummy\\__init__.py", "28", "19", ["Wxxx something something"], ""),
            ("", "", "", [], "./heyhey.py: Some malformed line"),
            ("./heyhey.py", "234", "1", ["W391 blank line at end of file"], "")
        ]
    )
