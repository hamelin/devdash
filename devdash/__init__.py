from abc import ABC, abstractmethod
from hashlib import md5
import io
from pathlib import Path
import re
from subprocess import run, PIPE, STDOUT, Popen
from typing import *  # noqa

from IPython import display
from ipywidgets import HTML, Accordion, HBox, VBox, Widget, Layout, IntProgress, Output
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent
# from watchdog.observers import Observer


def _event_path(event: FileSystemEvent) -> Path:
    return Path(event.src_path)


def _hash(path: Path) -> bytes:
    assert path.is_file()
    return md5(path.read_bytes()).digest()


class Checker(ABC, PatternMatchingEventHandler):

    def __init__(self):
        super().__init__(
            patterns=["*.py", "*.yml", "*.ini", "*.toml", "*.cfg", "*.json", ".flake8"],
            ignore_patterns=[
                "**/.ipynb_checkpoints/*",
                ".~*",
                "__pycache__",
                "*.pyc",
                "*.pyd"
            ],
            ignore_directories=False
        )
        self.hashes: Dict[Path, bytes] = {}
        self.ui = self.init_ui()

    def _ipython_display_(self) -> None:
        display(self.ui)

    def on_created(self, event: FileSystemEvent) -> None:
        p = _event_path(event)
        if p.is_file():
            self._run_update_on_distinct_hash(p, _hash(p))

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._run_update_on_distinct_hash(_event_path(event), b"")

    def on_moved(self, event: FileSystemEvent) -> None:
        self.hashes[Path(event.src_path)] = b""
        d = Path(event.dest_path)
        if d.is_file():
            self._run_update_on_distinct_hash(d, _hash(d))

    def on_modified(self, event: FileSystemEvent) -> None:
        p = _event_path(event)
        if p.is_file():
            self._run_update_on_distinct_hash(p, _hash(p))

    def _run_update_on_distinct_hash(self, path: Path, h: bytes) -> None:
        if h != self.hashes.get(path):
            self.hashes[path] = h
            self.run_update()

    @abstractmethod
    def init_ui(self) -> Widget:
        ...

    @abstractmethod
    def run_update(self) -> None:
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

    def run_update(self) -> None:
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
            'background: #404040;'
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
            self.container.index_selected = 0
        else:
            self.trafficlight.green()
            self.container.set_title(0, f"{self.title}: all good!")
            self.container.index_selected = None


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

    def run_update(self) -> None:
        pytest = Popen(
            ["pytest", "-v", "--color=yes", "--no-header"],
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

    def _capture_failures(self, stdout: io.TextIOBase, fails: List[str]) -> None:
        _expect_line(stdout, prefix="====", suffix="====", substr="FAILURES")
        children_new: List[Widget] = []
        for i, test in enumerate(fails):
            path_test, name_test = test.split("::")
            _expect_line(stdout, prefix="____", suffix="____", substr=name_test)
            _expect_empty(stdout)
            self.failures.set_title(i, f"{name_test} in {path_test}")
            out = Output()
            for line in stdout:
                out.append_stdout(line)
                if path_test in line.replace("\\", "/"):
                    break
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
