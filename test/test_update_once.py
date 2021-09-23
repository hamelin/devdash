from contextlib import contextmanager
from pathlib import Path
from typing import *  # noqa

from ipywidgets import Label, Widget
from watchdog.events import FileSystemEvent, FileSystemMovedEvent

from test import tree_project
import devdash as dd


class CheckerTestUpdateOnce(dd.Checker):

    def __init__(self) -> None:
        super().__init__()
        self.num_updates = 0

    def init_ui(self) -> Widget:
        return Label(value="Dummy")

    def run_update(self) -> None:
        self.num_updates += 1


def event(src_path: Path, dest_path: Optional[Path] = None) -> FileSystemEvent:
    if dest_path:
        return FileSystemMovedEvent(src_path=str(src_path), dest_path=str(dest_path))
    return FileSystemEvent(str(src_path))


path_x = Path("dummy") / "__init__.py"
path_nx = Path("dummy.py")


def event_x(dir: Path) -> FileSystemEvent:
    return event(dir / path_x)


def event_nx(dir: Path) -> FileSystemEvent:
    return event(dir / path_nx)


def event_bin(dir: Path) -> FileSystemEvent:
    return event(dir / path_nx, dir / path_x)


@contextmanager
def testing_num_updates(
    num_expected: int = 1
) -> Iterator[Tuple[Path, CheckerTestUpdateOnce]]:
    checker = CheckerTestUpdateOnce()
    with tree_project() as dir:
        yield (dir, checker)
        assert num_expected == checker.num_updates


def test_creates() -> None:
    with testing_num_updates() as (dir, checker):
        for _ in range(2):
            checker.on_created(event_x(dir))


def test_deletes() -> None:
    with testing_num_updates() as (dir, checker):
        for _ in range(2):
            checker.on_deleted(event_nx(dir))


def test_moves() -> None:
    with testing_num_updates() as (dir, checker):
        for _ in range(2):
            checker.on_moved(event_bin(dir))


def test_mods() -> None:
    with testing_num_updates() as (dir, checker):
        for _ in range(2):
            checker.on_modified(event_x(dir))


def test_create_mod() -> None:
    with testing_num_updates() as (dir, checker):
        checker.on_created(event_x(dir))
        checker.on_modified(event_x(dir))


def test_mod_create() -> None:
    with testing_num_updates() as (dir, checker):
        checker.on_modified(event_x(dir))
        checker.on_created(event_x(dir))


def test_move_mod() -> None:
    with testing_num_updates() as (dir, checker):
        checker.on_moved(event_bin(dir))
        checker.on_modified(event_x(dir))


def test_move_create() -> None:
    with testing_num_updates() as (dir, checker):
        checker.on_moved(event_bin(dir))
        checker.on_created(event_x(dir))


def test_move_delete() -> None:
    with testing_num_updates() as (dir, checker):
        checker.on_moved(event_bin(dir))
        checker.on_deleted(event_bin(dir))
