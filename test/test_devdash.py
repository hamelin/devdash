from contextlib import contextmanager
from copy import copy
from enum import Enum, auto
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory
import time
from typing import *  # noqa

from ipywidgets import Widget, Label
from watchdog.events import FileSystemEvent
from watchdog.observers import Observer
import pytest

import devdash as dd


class NameEvent(Enum):
    NONE = auto()
    CREATED = auto()
    DELETED = auto()
    MOVED = auto()
    MODIFIED = auto()


Event = Tuple[NameEvent, Path, Optional[Path]]


class ObservationTest(dd.Checker):

    def __init__(self, dir_observe: Path) -> None:
        super().__init__()
        self.tracked: List[Set[Event]] = []
        self.events: Set[Event] = set()
        self.observer = Observer()
        self.observer.schedule(self, dir_observe, recursive=True)
        self.observer.start()
        time.sleep(0.2)

    def track(self, events: List[Set[Event]]) -> None:
        self.tracked = copy(events)
        for s in self.tracked:
            if s <= self.events:
                self.observer.stop()

    def assert_events(self, *possibilities: Set[Event]) -> None:
        self.track(list(possibilities))
        try:
            self.observer.join(timeout=5.0)
            if self.observer.is_alive():
                pytest.fail(
                    f"Expected events from either set {self.tracked}, but got "
                    f"{self.events}."
                )
        finally:
            self.observer.stop()

    def init_ui(self) -> Widget:
        return Label(value="")

    def run_update(self) -> None:
        raise NotImplementedError()

    def record_event(
        self,
        name_event: NameEvent,
        src_path: Path,
        dest_path: Optional[Path] = None
    ) -> None:
        self.events.add(
            (name_event, Path(src_path), Path(dest_path) if dest_path else None)
        )
        for s in self.tracked:
            if s <= self.events:
                self.observer.stop()

    def on_created(self, event: FileSystemEvent) -> None:
        self.record_event(NameEvent.CREATED, event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self.record_event(NameEvent.DELETED, event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        self.record_event(NameEvent.MOVED, event.src_path, event.dest_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        self.record_event(NameEvent.MODIFIED, event.src_path)


@contextmanager
def tree_project() -> Iterator[Path]:
    with TemporaryDirectory() as name_dir:
        dir = Path(name_dir)
        (dir / "environment.yml").write_text("name: dummy\n")
        (dir / "dummy").mkdir()
        (dir / "dummy" / "__init__.py").write_text("print('Hello world!')\n")
        (dir / "setup.py").write_text("import setuptools\n")
        yield dir


@contextmanager
def observation_test() -> Iterator[Tuple[Path, ObservationTest]]:
    with tree_project() as dir:
        ot = ObservationTest(dir)
        yield (dir, ot)


def test_observe_created_root() -> None:
    with observation_test() as (dir, ot):
        (dir / "new.py").write_text("import os\nimport sys\n")
        ot.assert_events({(NameEvent.CREATED, dir / "new.py", None)})


def test_observe_created_subdir() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "new.py").write_text("import sys\nprint(sys.argv)\n")
        ot.assert_events({(NameEvent.CREATED, dir / "dummy" / "new.py", None)})


def test_observe_created_subsubdir() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "sub").mkdir(parents=True)
        (dir / "dummy" / "sub" / "subsub.py").write_text("from subprocess import run\n")
        ot.assert_events({
            (NameEvent.CREATED, dir / "dummy" / "sub" / "subsub.py", None)
        })


def test_observe_deleted_environment() -> None:
    with observation_test() as (dir, ot):
        (dir / "environment.yml").unlink()
        ot.assert_events({(NameEvent.DELETED, dir / "environment.yml", None)})


def test_observe_deleted_subdir() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "data.json").touch()
        rmtree(dir / "dummy")
        ot.assert_events({
            (NameEvent.CREATED, dir / "dummy" / "data.json", None),
            (NameEvent.DELETED, dir / "dummy" / "__init__.py", None),
            (NameEvent.DELETED, dir / "dummy" / "data.json", None)
        })


def test_observe_rename() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "__init__.py").replace(dir / "dummy.py")
        ot.assert_events(
            {(NameEvent.MOVED, dir / "dummy" / "__init__.py", dir / "dummy.py")},
            {
                (NameEvent.DELETED, dir / "dummy" / "__init__.py", None),
                (NameEvent.CREATED, dir / "dummy.py", None)
            }
        )


def test_observe_move_from_observed() -> None:
    with observation_test() as (dir, ot):
        (dir / "setup.py").rename(dir / "setup.bak")
        ot.assert_events(
            {(NameEvent.MOVED, dir / "setup.py", dir / "setup.bak")},
            {(NameEvent.DELETED, dir / "setup.py", None)}
        )


def test_observe_move_to_observed() -> None:
    with observation_test() as (dir, ot):
        (dir / "heyhey.txt").write_text("import inspect\n")
        (dir / "heyhey.txt").rename(dir / "dummy" / "heyhey.py")
        ot.assert_events(
            {(NameEvent.MOVED, dir / "heyhey.txt", dir / "dummy" / "heyhey.py")},
            {(NameEvent.CREATED, dir / "dummy" / "heyhey.py", None)}
        )


def test_observe_append() -> None:
    with observation_test() as (dir, ot):
        with (dir / "setup.py").open("w", encoding="utf-8") as file:
            print("setup()", file=file)
        ot.assert_events({(NameEvent.MODIFIED, dir / "setup.py", None)})


def test_observe_truncate() -> None:
    with observation_test() as (dir, ot):
        (dir / "dummy" / "__init__.py").write_text("")
        ot.assert_events({(NameEvent.MODIFIED, dir / "dummy" / "__init__.py", None)})
