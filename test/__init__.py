from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import *  # noqa


@contextmanager
def tree_project() -> Iterator[Path]:
    with TemporaryDirectory() as name_dir:
        dir = Path(name_dir)
        (dir / "environment.yml").write_text("name: dummy\n")
        (dir / "dummy").mkdir()
        (dir / "dummy" / "__init__.py").write_text("print('Hello world!')\n")
        (dir / "setup.py").write_text("import setuptools\n")
        yield dir
