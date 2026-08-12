"""Install AutoPulse Poetry projects into one shared root virtualenv.

Poetry ``virtualenvs.create=false`` targets the *base* interpreter,
not an existing ``.venv``, so service deps are installed with ``pip``
using locked versions from each service ``poetry.lock``.

Constraints:
- Service lockfiles must be Poetry **2.x** (``lock-version`` 2.* with
  ``groups = ["main"]``). Regenerate with Poetry 2 if install aborts.
- Docker images also expect Poetry 2 (see service Dockerfiles).
- Conflicting pins across enrichment/pricer fail the install (no silent
  overwrite).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.markers import Marker
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVICES = (
    ROOT / "services" / "enrichment",
    ROOT / "services" / "pricer",
    ROOT / "services" / "crawler",
)
DEFAULT_SHARED = ROOT / "shared"
_LOCK_VERSION_RE = re.compile(r"^2\.")


class Poetry2LockReader:
    """Parse Poetry 2 lockfiles into installable main-group pins."""

    def main_pins(self, lock_path: Path) -> dict[str, str]:
        """Map canonical name → version for installable main deps."""
        data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
        self._require_poetry2(lock_path, data)

        pins: dict[str, str] = {}
        for package in data.get("package", []):
            if not self._is_main(package):
                continue
            if not self._markers_apply(package):
                continue
            source = package.get("source") or {}
            if source.get("type") == "directory":
                continue
            name = canonicalize_name(package["name"])
            pins[name] = package["version"]

        if not pins:
            raise SystemExit(
                f"No main packages found in {lock_path}. "
                'Expected Poetry 2 lock entries with groups = ["main"].'
            )
        return pins

    @staticmethod
    def _require_poetry2(lock_path: Path, data: dict) -> None:
        meta = data.get("metadata") or {}
        lock_version = str(meta.get("lock-version", ""))
        if not _LOCK_VERSION_RE.match(lock_version):
            raise SystemExit(
                f"{lock_path}: require Poetry 2.x lockfiles "
                f"(metadata.lock-version 2.*), got {lock_version!r}. "
                "Regenerate with Poetry 2 (Docker/CI use Poetry 2.1.x)."
            )

    @staticmethod
    def _is_main(package: dict) -> bool:
        groups = package.get("groups") or []
        if groups:
            return "main" in groups
        return package.get("category") == "main"

    @staticmethod
    def _markers_apply(package: dict) -> bool:
        markers = package.get("markers")
        if not markers:
            return True
        return Marker(markers).evaluate()


class RootVenvInstaller:
    """Install root tooling and merged service pins into one venv."""

    def __init__(
        self,
        root: Path = ROOT,
        services: tuple[Path, ...] = DEFAULT_SERVICES,
        shared: Path = DEFAULT_SHARED,
        *,
        locks: Poetry2LockReader | None = None,
    ) -> None:
        self._root = root
        self._services = services
        self._shared = shared
        self._locks = locks or Poetry2LockReader()

    def run(self) -> None:
        self._remove_nested_service_venvs()
        specs = self.merge_service_pins()
        env = self._poetry_env()
        # Root pyproject: tooling + path shared only.
        self._run([*self._poetry_cmd(), "install", "--no-interaction"], env=env)
        root_python = self._root_venv_python(env)
        self._pip_install_shared_and_specs(root_python, specs)
        print(
            f"Installed root + shared + {len(specs)} locked service pins into:",
            root_python,
        )

    def merge_service_pins(self) -> list[str]:
        """Merge service pins; abort when the same package disagrees."""
        merged: dict[str, tuple[str, Path]] = {}
        for service in self._services:
            for name, version in self._locks.main_pins(service / "poetry.lock").items():
                prior = merged.get(name)
                if prior is not None and prior[0] != version:
                    raise SystemExit(
                        "Conflicting locked versions for "
                        f"{name!r}: {prior[1].name} has {prior[0]}, "
                        f"{service.name} has {version}. Align poetry.lock "
                        "files (or stop sharing one root .venv)."
                    )
                merged[name] = (version, service)
        return [f"{name}=={version}" for name, (version, _) in sorted(merged.items())]

    def _remove_nested_service_venvs(self) -> None:
        for service in self._services:
            nested = service / ".venv"
            if nested.exists():
                shutil.rmtree(nested, ignore_errors=True)

    def _poetry_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["POETRY_VIRTUALENVS_IN_PROJECT"] = "true"
        return env

    def _poetry_cmd(self) -> list[str]:
        return [sys.executable, "-m", "poetry"]

    def _root_venv_python(self, env: dict[str, str]) -> str:
        return subprocess.check_output(
            [*self._poetry_cmd(), "env", "info", "-e"],
            cwd=self._root,
            text=True,
            env=env,
        ).strip()

    def _pip_install_shared_and_specs(
        self,
        root_python: str,
        specs: list[str],
    ) -> None:
        # One pip resolve: editable shared + service pins.
        self._run(
            [
                root_python,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-e",
                str(self._shared),
                *specs,
            ]
        )

    def _run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        print("+", " ".join(args), flush=True)
        subprocess.check_call(args, cwd=cwd or self._root, env=env)


def main() -> None:
    RootVenvInstaller().run()


if __name__ == "__main__":
    main()
