"""Install AutoPulse Poetry projects into one shared root virtualenv."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    ROOT / "services" / "enrichment",
    ROOT / "services" / "pricer",
)


def run(args: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.check_call(args, cwd=cwd or ROOT, env=env)


def poetry_cmd() -> list[str]:
    return [sys.executable, "-m", "poetry"]


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
    root_venv = str(Path(root_python).resolve().parent.parent)
    scripts = Path(root_venv) / ("Scripts" if os.name == "nt" else "bin")

    service_env = base_env.copy()
    service_env["POETRY_VIRTUALENVS_CREATE"] = "false"
    service_env["POETRY_VIRTUALENVS_IN_PROJECT"] = "false"
    service_env["VIRTUAL_ENV"] = root_venv
    service_env["PATH"] = str(scripts) + os.pathsep + service_env.get("PATH", "")

    for service in SERVICES:
        run(
            [*poetry_cmd(), "install", "--no-interaction"],
            cwd=service,
            env=service_env,
        )

    print("Installed root + enrichment + pricer into:", root_python)


if __name__ == "__main__":
    main()
