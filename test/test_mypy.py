from textwrap import dedent
from typing import *  # noqa

from devdash import Issue, MyPy


def run_test_issue_parsing(stdout: str, issues_expected: List[Issue]) -> None:
    assert issues_expected == list(MyPy().iter_issues(dedent(stdout)))


def test_issues_empty() -> None:
    run_test_issue_parsing("", [])


def test_issues_oneliners_with_column() -> None:
    run_test_issue_parsing(
        """
        dummy\\__init__.py:29:19: error: Argument 1 to "foo" has incompatible type \
"int"; expected "str"
        dummy/heyhey.py:8:1: error: Missing return statement
        """,
        [
            (
                "dummy\\__init__.py",
                "29",
                "19",
                ['Argument 1 to "foo" has incompatible type "int"; expected "str"'],
                ""
            ),
            (
                "dummy/heyhey.py",
                "8",
                "1",
                ["Missing return statement"],
                ""
            )
        ]
    )


def test_issues_oneliners_missing_column() -> None:
    run_test_issue_parsing(
        """
        dummy\\__init__.py:29: error: Argument 1 to "foo" has incompatible type "int"; \
expected "str"
        dummy/heyhey.py:8:1: error: Missing return statement
        dummy/heyhey.py:139: error: Something something
        """,
        [
            (
                "dummy\\__init__.py",
                "29",
                "",
                ['Argument 1 to "foo" has incompatible type "int"; expected "str"'],
                ""
            ),
            (
                "dummy/heyhey.py",
                "8",
                "1",
                ["Missing return statement"],
                ""
            ),
            (
                "dummy/heyhey.py",
                "139",
                "",
                ["Something something"],
                ""
            )
        ]
    )


def test_issues_multiliners() -> None:
    run_test_issue_parsing(
        """
        dummy\\__init__.py:29: error: Argument 1 to "foo" has incompatible type "int"; \
expected "str"
        dummy\\__init__.py:29: note: Speak to the manager
                            note:    Or their direct supervisor
        dummy/heyhey.py:139:1: error: Missing return statement
        dummy/heyhey.py:139: note: You dimwit
        """,
        [
            (
                "dummy\\__init__.py",
                "29",
                "",
                [
                    'Argument 1 to "foo" has incompatible type "int"; expected "str"',
                    "Speak to the manager",
                    "Or their direct supervisor"
                ],
                ""
            ),
            (
                "dummy/heyhey.py",
                "139",
                "1",
                ["Missing return statement", "You dimwit"],
                ""
            )
        ]
    )


def test_issues_line_malformed() -> None:
    run_test_issue_parsing(
        """
        Malformed line
        dummy\\__init__.py:29: error: Argument 1 to "foo" has incompatible type "int"; \
expected "str"
        More weird output
        Two in a row actually
        dummy/heyhey.py:139:1: error: Missing return statement

        dummy/heyhey.py:139: note: Multiliner!
        """,
        [
            ("", "", "", [], "Malformed line"),
            (
                "dummy\\__init__.py",
                "29",
                "",
                ['Argument 1 to "foo" has incompatible type "int"; expected "str"'],
                ""
            ),
            ("", "", "", [], "More weird output"),
            ("", "", "", [], "Two in a row actually"),
            (
                "dummy/heyhey.py",
                "139",
                "1",
                ["Missing return statement", "Multiliner!"],
                ""
            )
        ]
    )
