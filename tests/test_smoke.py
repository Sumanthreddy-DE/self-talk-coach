def test_import_package() -> None:
    import self_talk_coach

    assert self_talk_coach.__version__


def test_import_stubs() -> None:
    from self_talk_coach import anki, cli, db, domain, enrich, ingest, mine, paths, transcribe  # noqa: F401


def test_cli_version(capsys) -> None:
    from typer.testing import CliRunner

    from self_talk_coach.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout
