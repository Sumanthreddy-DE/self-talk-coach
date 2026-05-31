from pathlib import Path

from typer.testing import CliRunner

from self_talk_coach.cli import app


def test_cli_init_creates_workspace(tmp_path: Path) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"

    result = runner.invoke(app, ["init", "--data-root", str(data_root)])

    assert result.exit_code == 0
    assert "Initialized workspace" in result.stdout
    assert (data_root / "db" / "self_talk_coach.sqlite").exists()
    assert (data_root / "media" / "inbox").is_dir()


def test_cli_import_imports_inbox_file(tmp_path: Path) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    inbox = data_root / "media" / "inbox"

    init_result = runner.invoke(app, ["init", "--data-root", str(data_root)])
    assert init_result.exit_code == 0

    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "daily.mp4").write_bytes(b"video bytes")

    result = runner.invoke(app, ["import", "--data-root", str(data_root)])

    assert result.exit_code == 0
    assert "Imported: 1" in result.stdout
    assert "Duplicates: 0" in result.stdout
    assert "Failed: 0" in result.stdout
    assert not (inbox / "daily.mp4").exists()
