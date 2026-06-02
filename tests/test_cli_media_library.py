from pathlib import Path

from typer.testing import CliRunner

from self_talk_coach.cli import app
from self_talk_coach.transcribe import TranscriptDraft, TranscriptSegmentDraft


class FakeCliTranscriber:
    model_name = "fake-cli-whisper"

    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: Path) -> TranscriptDraft:
        return TranscriptDraft(
            language="de",
            duration_seconds=1.5,
            segments=(
                TranscriptSegmentDraft(
                    start_seconds=0.0,
                    end_seconds=1.5,
                    text="Hallo CLI.",
                ),
            ),
        )


def fake_cli_audio_extractor(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(source_path.read_bytes() + b" wav")


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


def test_cli_transcribe_stores_imported_media_transcript(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    inbox = data_root / "media" / "inbox"

    init_result = runner.invoke(app, ["init", "--data-root", str(data_root)])
    assert init_result.exit_code == 0

    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "daily.mp4").write_bytes(b"video bytes")
    import_result = runner.invoke(app, ["import", "--data-root", str(data_root)])
    assert import_result.exit_code == 0

    monkeypatch.setattr(
        "self_talk_coach.cli.FasterWhisperTranscriber",
        FakeCliTranscriber,
        raising=False,
    )
    monkeypatch.setattr(
        "self_talk_coach.cli.extract_audio",
        fake_cli_audio_extractor,
        raising=False,
    )

    result = runner.invoke(
        app,
        ["transcribe", "--data-root", str(data_root), "--model-size", "tiny"],
    )

    assert result.exit_code == 0
    assert "Transcribed: 1" in result.stdout
    assert "Skipped: 0" in result.stdout
    assert "Failed: 0" in result.stdout


def test_cli_export_transcripts_writes_markdown_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    inbox = data_root / "media" / "inbox"

    init_result = runner.invoke(app, ["init", "--data-root", str(data_root)])
    assert init_result.exit_code == 0

    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "daily.mp4").write_bytes(b"video bytes")
    import_result = runner.invoke(app, ["import", "--data-root", str(data_root)])
    assert import_result.exit_code == 0

    monkeypatch.setattr(
        "self_talk_coach.cli.FasterWhisperTranscriber",
        FakeCliTranscriber,
        raising=False,
    )
    monkeypatch.setattr(
        "self_talk_coach.cli.extract_audio",
        fake_cli_audio_extractor,
        raising=False,
    )
    transcribe_result = runner.invoke(
        app,
        ["transcribe", "--data-root", str(data_root), "--model-size", "tiny"],
    )
    assert transcribe_result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "export",
            "transcripts",
            "--data-root",
            str(data_root),
            "--format",
            "markdown",
        ],
    )

    assert result.exit_code == 0
    assert "Exported transcripts: 1" in result.stdout
    markdown_exports = list((data_root / "exports" / "transcripts").glob("*.md"))
    assert len(markdown_exports) == 1
    assert "Hallo CLI." in markdown_exports[0].read_text(encoding="utf-8")
