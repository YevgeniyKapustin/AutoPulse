"""Install AutoPulse Poetry projects into one shared root virtualenv.

Poetry's ``virtualenvs.create=false`` mode targets the *base* interpreter, not
an existing ``.venv``, so service deps are installed with ``pip`` using locked
versions from each service ``poetry.lock``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    ROOT / "services" / "enrichment",
    ROOT / "services" / "pricer",
)
SHARED = ROOT / "shared"


def run(args: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.check_call(args, cwd=cwd or ROOT, env=env)


def poetry_cmd() -> list[str]:
    return [sys.executable, "-m", "poetry"]


def locked_main_specs(lock_path: Path) -> list[str]:
    """Build ``name==version`` pins for main-group packages (skip path deps)."""
    data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    specs: list[str] = []
    for package in data.get("package", []):
        groups = package.get("groups") or []
        if "main" not in groups:
            continue
        source = package.get("source") or {}
        if source.get("type") == "directory":
            continue
        name = package["name"]
        version = package["version"]
        specs.append(f"{name}=={version}")
    return specs


def install_service(root_python: str, service: Path) -> None:
    run([root_python, "-m", "pip", "install", "--disable-pip-version-check", "-e", str(SHARED)])
    specs = locked_main_specs(service / "poetry.lock")
    if not specs:
        raise SystemExit(f"No main packages found in {service / 'poetry.lock'}")
    run(
        [
            root_python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *specs,
        ]
    )


def main() -> None:
    base_env = os.environ.copy()
    base_env["POETRY_VIRTUALENVS_IN_PROJECT"] = "true"

    for service in SERVICES:
        nested = service / ".venv"
        if nested.exists():
            shutil.rmtree(nested, ignore_errors=True)

    run([*poetry_cmd(), "install", "--no-interaction"], env=base_env)

    root_python = subprocess.check_output(
        [*poetry_cmd(), "env", "info", "-e"],
        cwd=ROOT,
        text=True,
        env=base_env,
    ).strip()

    for service in SERVICES:
        install_service(root_python, service)

    print("Installed root + enrichment + pricer into:", root_python)


if __name__ == "__main__":
    main()
