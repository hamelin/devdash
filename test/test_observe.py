from contextlib import contextmanager
from copy import copy
from pathlib import Path
from shutil import rmtree
import sys
import time
from typing import *  # noqa

from watchdog.observers import Observer
import pytest

import devdash as dd
from test import tree_project


AccountPaths = Dict[Path, int]


class ObservationTest(dd.Tracker):

    def __init__(self, dir_observe: Path) -> None:
        super().__init__(self.record_event)
        self.tracked: AccountPaths = {}
        self.events: AccountPaths = {}
        self.observer = Observer()
        self.observer.schedule(self, dir_observe, recursive=True)
        self.observer.start()
        time.sleep(0.2)

    def track(self, account: AccountPaths) -> None:
        self.tracked = copy(account)
        if set(self.events.keys()) == set(self.tracked.keys()):
            self.observer.stop()

    def assert_events(self, account: AccountPaths, exact: bool = False) -> None:
        self.track(account)
        try:
            self.observer.join(timeout=5.0)
            if self.observer.is_alive():
                pytest.fail(f"Expected events {self.tracked}, but got {self.events}")

            if exact and account == self.events:
                return
                pytest.fail(
                    "Needed exact event correspondance to path accounting "
                    f"{self.tracked}, but got {self.events}."
                )
        finally:
            self.observer.stop()

    def record_event(self, path: Path) -> None:
        self.events[path] = self.events.get(path, 0) + 1
        if set(self.events.keys()) == set(self.tracked.keys()):
            self.observer.stop()


@contextmanager
def observation_test() -> Iterator[Tuple[Path, ObservationTest]]:
    with tree_project() as dir:
        ot = ObservationTest(dir)
        yield (dir, ot)


def test_observe_created_root() -> None:
    with observation_test() as (dir, ot):
        (dir / "new.py").write_text("import os\nimport sys\n")
        ot.assert_events({dir / "new.py": 1})


def test_observe_created_subdir() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "new.py").write_text("import sys\nprint(sys.argv)\n")
        ot.assert_events({dir / "dummy" / "new.py": 1})


def test_observe_created_subsubdir() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "sub").mkdir(parents=True)
        (dir / "dummy" / "sub" / "subsub.py").write_text("from subprocess import run\n")
        ot.assert_events({dir / "dummy" / "sub" / "subsub.py": 1})


def test_observe_deleted_environment() -> None:
    with observation_test() as (dir, ot):
        (dir / "environment.yml").unlink()
        ot.assert_events({dir / "environment.yml": 1})


def test_observe_deleted_subdir() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "data.json").touch()
        rmtree(dir / "dummy")
        ot.assert_events({
            dir / "dummy" / "data.json": 2,
            dir / "dummy" / "__init__.py": 1
        })


def test_observe_rename() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "__init__.py").replace(dir / "dummy.py")
        ot.assert_events({dir / "dummy" / "__init__.py": 1, dir / "dummy.py": 1})


def test_observe_move_from_observed() -> None:
    with observation_test() as (dir, ot):
        (dir / "setup.py").rename(dir / "setup.bak")
        ot.assert_events({dir / "setup.py": 1})


def test_observe_move_to_observed() -> None:
    with observation_test() as (dir, ot):
        (dir / "heyhey.txt").write_text("import inspect\n")
        (dir / "heyhey.txt").rename(dir / "dummy" / "heyhey.py")
        ot.assert_events({dir / "heyhey.txt": 1, dir / "dummy" / "heyhey.py": 1})


def test_observe_append() -> None:
    with observation_test() as (dir, ot):
        with (dir / "setup.py").open("w", encoding="utf-8") as file:
            print("setup()", file=file)
        ot.assert_events({dir / "setup.py": 1})


def test_observe_truncate() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "__init__.py").write_text("")
        ot.assert_events({dir / "dummy" / "__init__.py": 1})


def test_mypy_cache() -> None:
    with observation_test() as (dir, ot):
        mypy_cache = (
            dir / ".mypy_cache" / f"{sys.version_info.major}.{sys.version_info.minor}"
        )
        mypy_cache.mkdir(parents=True, exist_ok=True)
        (mypy_cache / "@plugins_snapshot.json").write_text("{}\n")
        (dir / "setup.py").write_text("")
        ot.assert_events({dir / "setup.py": 1}, exact=True)
