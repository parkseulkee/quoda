from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from typer.testing import CliRunner

from quada.cli.app import app


runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_init(tmp_path):
    result = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "quada.yaml").exists()
    assert (tmp_path / "models").is_dir()
    assert (tmp_path / "metrics").is_dir()
    assert (tmp_path / "glossary").is_dir()
    assert (tmp_path / "quality").is_dir()


def test_cli_validate_missing_config(tmp_path):
    result = runner.invoke(app, ["validate", "--path", str(tmp_path)])
    assert result.exit_code != 0 or "not found" in result.stdout.lower()
