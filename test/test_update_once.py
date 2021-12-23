from contextlib import contextmanager
from pathlib import Path
from typing import *  # noqa

from ipywidgets import Label, Widget
from watchdog.events import FileSystemEvent, FileSystemMovedEvent

from test import tree_project
import devdash as dd


class CheckerTestUpdateOnce:

    def __init__(self) -> None:
        super().__init__()
        self.updates: Dict[Path, int] = {}

    def init_ui(self) -> Widget:
        return Label(value="Dummy")

    def update(self, path: Path) -> None:
        self.updates[path] = self.updates.get(path, 0) + 1

    @property
    def num_updates(self) -> int:
        return sum(list(self.updates.values()))


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
def testing_num_updates(n: int = 1) -> Iterator[Tuple[Path, dd.Tracker]]:
    checker = CheckerTestUpdateOnce()
    tracker = dd.Tracker(checker.update)
    with tree_project() as dir:
        yield (dir, tracker)
        assert n == checker.num_updates


def test_creates() -> None:
    with testing_num_updates() as (dir, tracker):
        for _ in range(2):
            tracker.on_created(event_x(dir))


def test_deletes() -> None:
    with testing_num_updates() as (dir, tracker):
        for _ in range(2):
            tracker.on_deleted(event_nx(dir))


def test_moves() -> None:
    with testing_num_updates(2) as (dir, tracker):
        for _ in range(2):
            tracker.on_moved(event_bin(dir))


def test_mods() -> None:
    with testing_num_updates() as (dir, tracker):
        for _ in range(2):
            tracker.on_modified(event_x(dir))


def test_create_mod() -> None:
    with testing_num_updates() as (dir, tracker):
        tracker.on_created(event_x(dir))
        tracker.on_modified(event_x(dir))


def test_mod_create() -> None:
    with testing_num_updates() as (dir, tracker):
        tracker.on_modified(event_x(dir))
        tracker.on_created(event_x(dir))


def test_move_mod() -> None:
    with testing_num_updates(2) as (dir, tracker):
        tracker.on_moved(event_bin(dir))
        tracker.on_modified(event_x(dir))


def test_move_create() -> None:
    with testing_num_updates(2) as (dir, tracker):
        tracker.on_moved(event_bin(dir))
        tracker.on_created(event_x(dir))


def test_move_delete() -> None:
    with testing_num_updates(2) as (dir, tracker):
        tracker.on_moved(event_bin(dir))
        tracker.on_deleted(event_bin(dir))
