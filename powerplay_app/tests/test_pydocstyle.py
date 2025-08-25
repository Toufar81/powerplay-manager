"""Lint project docstrings with pydocstyle."""

from __future__ import annotations

import shutil
import subprocess

import pytest


@pytest.mark.skipif(
    shutil.which("pydocstyle") is None, reason="pydocstyle is not installed"
)
def test_pydocstyle() -> None:
    """Run pydocstyle on selected modules."""
    result = subprocess.run(
        [
            "pydocstyle",
            "powerplay_app/admin.py",
            "powerplay_app/portal/views",
            "powerplay_app/services",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

