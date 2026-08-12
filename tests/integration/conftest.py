"""Shared helpers for Docker-backed integration tests."""

from __future__ import annotations

import pytest


def docker_available() -> bool:
    try:
        from testcontainers.core.docker_client import DockerClient

        DockerClient().client.ping()
        return True
    except Exception:
        return False


requires_docker = pytest.mark.skipif(
    not docker_available(),
    reason="Docker is required for integration tests",
)
