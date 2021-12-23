from abc import ABC, abstractmethod
from hashlib import md5
import io
from itertools import chain
import logging as lg
from pathlib import Path
import re
from subprocess import run, PIPE, STDOUT, Popen
from threading import Lock, Thread
from typing import *  # noqa

from IPython.display import display
from ipywidgets import HTML, Accordion, HBox, VBox, Widget, Layout, IntProgress,\
    Output, Button
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent
from watchdog.observers import Observer


LOG = lg.getLogger(__name__)


def _event_path(event: FileSystemEvent) -> Path:
    return Path(event.src_path)


def _hash(path: Path) -> bytes:
    try:
        return md5(path.read_bytes()).digest()
    except IOError:
        return b""


Update = Callable[[Path], None]


class Tracker(PatternMatchingEventHandler):

    def __init__(self, update: Update) -> None:
        super().__init__(
            patterns=["*.py", "*.yml", "*.ini", "*.toml", "*.cfg", "*.json", ".flake8"],
            ignore_patterns=[
                "**/.ipynb_checkpoints/*",
                ".~*",
                "**/__pycache__/*",
                "*.pyc",
                "*.pyd",
                "**/.mypy_cache/**/*"
            ],
            ignore_directories=False
        )
        self._update = update
        self.hashes: Dict[Path, bytes] = {}

    def on_created(self, event: FileSystemEvent) -> None:
        p = _event_path(event)
        LOG.debug(f"Created {p}")
        if p.is_file():
            self._run_update_on_distinct_hash(p, _hash(p))

    def on_deleted(self, event: FileSystemEvent) -> None:
        p = _event_path(event)
        LOG.debug(f"Deleted {p}")
        self._run_update_on_distinct_hash(p, b"")

    def on_moved(self, event: FileSystemEvent) -> None:
        s = Path(event.src_path)
        d = Path(event.dest_path)
        LOG.debug(f"Moved {s} to {d}")
        if d.is_file():
            self._run_update_on_distinct_hash(s, b"")
            self._run_update_on_distinct_hash(d, _hash(d))

    def on_modified(self, event: FileSystemEvent) -> None:
        p = _event_path(event)
        LOG.debug(f"Modified {p}")
        if p.is_file():
            self._run_update_on_distinct_hash(p, _hash(p))

    def _run_update_on_distinct_hash(self, path: Path, h: bytes) -> None:
        if h != self.hashes.get(path):
            self.hashes[path] = h
            LOG.info(f"Update {path}")
            self._update(path)


class Checker(ABC):

    def __init__(self):
        super().__init__
        self.ui = self.init_ui()
        self._lock = Lock()
        self._thread_ = None

    def _ipython_display_(self) -> None:
        display(self.ui)

    @abstractmethod
    def init_ui(self) -> Widget:
        ...

    def update(self) -> None:
        with self._lock:
            if self._thread_ is None or not self._thread_.is_alive():
                self._thread_ = Thread(target=self._update)
                self._thread_.start()

    @abstractmethod
    def _update(self) -> None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...


class TrafficLight(HTML):
    TEMPLATE = '<span style="font-size: xx-large;">{}</style>'
    LIGHTS = {
        "green": "🟢",
        "red": "🔴",
        "yellow": "🟡",
        "white": "⚪"
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_value("white")

    def update_value(self, color: str) -> None:
        self.value = TrafficLight.TEMPLATE.format(TrafficLight.LIGHTS[color])

    def green(self) -> None:
        self.update_value("green")

    def yellow(self) -> None:
        self.update_value("yellow")

    def red(self) -> None:
        self.update_value("red")


Issue = Tuple[str, str, str, List[str], str]


class CheckerLinewise(Checker):

    def init_ui(self) -> None:
        self.trafficlight = TrafficLight(layout=Layout(width="0.5in"))
        self.issues = HTML(value="")
        self.container = Accordion(children=[self.issues])
        self.container.set_title(0, "Yet to update")
        self.container.selected_index = None
        return HBox(children=[self.trafficlight, self.container])

    @property
    @abstractmethod
    def title(self) -> str:
        ...

    @property
    @abstractmethod
    def command(self) -> List[str]:
        ...

    @abstractmethod
    def iter_issues(self, stdout: str) -> Iterator[Issue]:
        ...

    def _update(self) -> None:
        self.trafficlight.yellow()
        cp = run(self.command, stdout=PIPE, stderr=STDOUT, encoding="utf-8")
        rows_issues = []
        for path, lineno, column, issue, oops in self.iter_issues(cp.stdout):
            row = ""
            if issue:
                row = (
                    f'<td class="db-cell">{path}</td>'
                    f'<td class="db-cell db-cell-alt at-right"">{lineno}</td>'
                    f'<td class="db-cell at-right">{column}</td>'
                    f'<td class="db-cell db-cell-alt">'
                    f'{"".join(f"<div>{x}</div>" for x in issue)}'
                    '</td>'
                )
            elif oops:
                row = f"<td colspan=4>{oops.strip()}</td>"

            if row:
                rows_issues.append(f'<tr>{row}</tr>')

        self.issues.value = (
            '<table cellspacing="0">'
            '<style>'
            '.at-right {'
            'text-align: right;'
            '}'
            '.db-cell {'
            'padding: 0pt 4pt 0pt 4pt;'
            '}'
            '.db-cell-alt {'
            'background: #dc8787;'
            '}'
            '</style>'
            '<thead>'
            '<tr>'
            '<th><div class="db-cell">File</div></th>'
            '<th><div class="db-cell db-cell-alt at-right">Line</div></th>'
            '<th><div class="db-cell at-right">Column</div></th>'
            '<th><div class="db-cell db-cell-alt">Issue</div></th>'
            '</tr>'
            '</thead>'
            '<tbody>'
            f"{''.join(rows_issues)}"
            '</tbody>'
            "</table>"
        )

        if rows_issues:
            self.trafficlight.red()
            self.container.set_title(0, f"{self.title}: {len(rows_issues)} issues")
            self.container.selected_index = 0
        else:
            self.trafficlight.green()
            self.container.set_title(0, f"{self.title}: all good!")
            self.container.selected_index = None

    def clear(self) -> None:
        self.trafficlight.white()


class Flake8(CheckerLinewise):

    @property
    def command(self) -> List[str]:
        return ["flake8"]

    @property
    def title(self) -> str:
        return "PEP8 compliance"

    def iter_issues(self, stdout: str) -> Iterator[Issue]:
        for line in stdout.split("\n"):
            try:
                path, lineno, column, issue = line.split(":", maxsplit=3)
                issue = issue.strip()
                if any([path, lineno, column, issue]):
                    yield (path, lineno, column, [issue], "")
            except ValueError:
                line = line.strip()
                if line:
                    yield ("", "", "", [], line)


class MyPy(CheckerLinewise):

    @property
    def command(self) -> List[str]:
        return ["mypy", "--ignore-missing-imports", "--show-column-numbers", "."]

    @property
    def title(self) -> str:
        return "Type coherence"

    def iter_issues(self, stdout: str) -> Iterator[Issue]:
        path = ""
        lineno = ""
        column = ""
        lines_issue: List[str] = []
        for line in stdout.split("\n"):
            if line.startswith("Found "):
                continue
            elif "error:" in line:
                if path:
                    yield (path, lineno, column, lines_issue, "")
                head, tail = line.split("error:")
                lines_issue = [tail.strip()]
                parts_head = head.split(":")
                while len(parts_head) < 3:
                    parts_head.append("")
                path, lineno, column = [part.strip() for part in parts_head[:3]]
            elif ": " in line:
                parts = line.split(": ")
                lines_issue.append(parts[-1].strip())
            else:
                if path:
                    yield (path, lineno, column, lines_issue, "")
                path = ""
                if line:
                    yield ("", "", "", [], line)
        if path:
            yield (path, lineno, column, lines_issue, "")


class Pytest(Checker):

    def init_ui(self) -> Widget:
        self.progress = IntProgress(
            value=0,
            max=100,
            description="<strong>Unit tests</strong>",
            bar_style="info"
        )
        self.failures = Accordion(children=[])
        return VBox(children=[self.progress, self.failures])

    def clear(self) -> None:
        self.progress.value = 0

    def _update(self) -> None:
        pytest = Popen(
            ["pytest", "-vv", "--color=yes", "--no-header"],
            encoding="utf-8",
            stdout=PIPE,
            stderr=STDOUT
        )
        fails = self._track_progress(cast(io.TextIOBase, pytest.stdout))
        if fails:
            self._capture_failures(cast(io.TextIOBase, pytest.stdout), fails)
        else:
            self.failures.children = [HTML(value="")]
            self.failures.set_title(0, "All tests passed")
        pytest.communicate()

    def _track_progress(self, stdout: io.TextIOBase) -> List[str]:
        self.progress.value = 0
        self.progress.bar_style = "success"
        self.failures.children = [
            HTML(value="Failures will be reported once pytest terminates.")
        ]
        self.failures.set_title(0, "Running pytest")
        self.failures.selected_index = None
        fails: List[str] = []
        _expect_line(stdout, prefix="====", suffix="====", substr="test session starts")
        _expect_line(stdout, prefix="collecting")
        _expect_empty(stdout)

        for line in stdout:
            line = deansi(line.strip())
            if not line:
                break
            self.progress.value = int(line[-5:-2].strip())
            if "FAILED" in line:
                self.progress.bar_style = "danger"
                test, *_ = line.split()
                fails.append(test)

        return fails

    def _capture_failures(self, stdout: Iterator[str], fails: List[str]) -> None:
        _expect_line(stdout, prefix="====", suffix="====", substr="FAILURES")
        children_new: List[Widget] = []
        for i, test in enumerate(fails):
            path_test, name_test = test.split("::")
            _expect_line(stdout, prefix="____", suffix="____", substr=name_test)
            _expect_empty(stdout)
            self.failures.set_title(i, f"{name_test} in {path_test}")
            out = Output()
            for line in stdout:
                line_no_code = deansi(line).strip()
                if any(
                    line_no_code.startswith(sep * 8) and line_no_code.endswith(sep * 8)
                    for sep in ["_", "="]
                ):
                    # Found the header to the next failure or to the final summary.
                    stdout = chain([line], cast(Iterator[str], stdout))
                    break
                out.append_stdout(line)
            children_new.append(out)
        self.failures.children = children_new
        self.failures.selected_index = 0


def deansi(s: str) -> str:
    return re.sub("\x1b\\[.+?m", "", s)


def _expect_line(
    stdout: Iterator[str],
    prefix: str = "",
    suffix: str = "",
    substr: str = ""
) -> None:
    line = deansi(next(stdout).rstrip())
    if not line.startswith(prefix):
        raise ValueError(f"Line [{line[:-1]}] does not start with prefix [{prefix}]")
    if not line.endswith(suffix):
        raise ValueError(f"Line [{line[:-1]}] does not end with suffix [{suffix}]")
    if substr not in line:
        raise ValueError(f"Line [{line[:-1]}] does not contain substring [{substr}]")


def _expect_empty(stdout) -> None:
    line = next(stdout).strip()
    if line:
        raise ValueError(f"Line [{line[:-1]}] is not empty as expected.")


class Dashboard:

    def __init__(self, dir_project: Union[Path, str] = ""):
        self._checkers = [Flake8(), MyPy(), Pytest()]
        self._button_auto = Button(description="Auto", button_style="")
        self._button_auto.on_click(self.on_auto)
        self._button_run_now = Button(description="Run checks now")
        self._button_run_now.on_click(self.on_run_now)
        self._ui = VBox(
            children=[
                HBox(children=[self._button_auto, self._button_run_now]),
                *[ch.ui for ch in self._checkers]
            ]
        )
        tracker = Tracker(self.on_file_changed)
        self._observer = Observer()
        self._observer.schedule(
            tracker,
            Path(dir_project or Path.cwd()),
            recursive=True
        )
        self._observer.start()

    def _ipython_display_(self) -> None:
        display(self._ui)

    def on_auto(self, _) -> None:
        if self._button_auto.button_style:
            self._button_auto.button_style = ""
        else:
            self._button_auto.button_style = "info"

    def on_run_now(self, _) -> None:
        self._update_checkers()

    def on_file_changed(self, path: Path) -> None:
        if self._button_auto.button_style:
            self._update_checkers()

    def _update_checkers(self) -> None:
        for checker in self._checkers:
            checker.update()
