"""Typer CLI entry point for self-talk-coach."""

from __future__ import annotations

from pathlib import Path

import typer

from self_talk_coach.db import connect, init_db
from self_talk_coach.domain import ImportOutcome, TranscriptionOutcome
from self_talk_coach.ingest import import_inbox
from self_talk_coach.paths import AppPaths
from self_talk_coach.transcribe import (
    FasterWhisperTranscriber,
    extract_audio,
    transcribe_pending,
)
from self_talk_coach.transcript_export import (
    TranscriptExportFormat,
    export_all_transcripts,
)

app = typer.Typer(help="self-talk-coach: German self-talk learning system")
export_app = typer.Typer(help="Export stored learning artifacts.")
app.add_typer(export_app, name="export")


@app.command()
def version() -> None:
    """Print version."""
    from self_talk_coach import __version__

    typer.echo(__version__)


@app.command()
def info() -> None:
    """Print project info."""
    typer.echo("self-talk-coach - local-first German self-talk learning system")


@app.command("init")
def init_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
) -> None:
    """Initialize local database and managed media folders."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
    typer.echo(f"Initialized workspace at {paths.data_root}")


@app.command("import")
def import_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
) -> None:
    """Import videos from the managed inbox into the local media library."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
        results = import_inbox(conn, paths)

    imported = sum(1 for result in results if result.outcome == ImportOutcome.IMPORTED)
    duplicates = sum(1 for result in results if result.outcome == ImportOutcome.DUPLICATE)
    failed = sum(1 for result in results if result.outcome == ImportOutcome.FAILED)

    typer.echo(f"Imported: {imported}")
    typer.echo(f"Duplicates: {duplicates}")
    typer.echo(f"Failed: {failed}")


@app.command("transcribe")
def transcribe_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
    model_size: str = typer.Option("medium", "--model-size", help="Faster Whisper model size."),
    device: str = typer.Option("cpu", "--device", help="Transcription device."),
    compute_type: str = typer.Option("int8", "--compute-type", help="Transcription compute type."),
) -> None:
    """Transcribe imported media files into stored transcripts."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    transcriber = FasterWhisperTranscriber(
        model_size=model_size,
        device=device,
        compute_type=compute_type,
    )
    with connect(paths.db_path) as conn:
        init_db(conn)
        results = transcribe_pending(
            conn,
            paths,
            transcriber=transcriber,
            audio_extractor=extract_audio,
        )

    transcribed = sum(
        1 for result in results if result.outcome == TranscriptionOutcome.TRANSCRIBED
    )
    skipped = sum(
        1 for result in results if result.outcome == TranscriptionOutcome.SKIPPED
    )
    failed = sum(
        1 for result in results if result.outcome == TranscriptionOutcome.FAILED
    )

    typer.echo(f"Transcribed: {transcribed}")
    typer.echo(f"Skipped: {skipped}")
    typer.echo(f"Failed: {failed}")


@export_app.command("transcripts")
def export_transcripts_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
    export_format: TranscriptExportFormat = typer.Option(
        TranscriptExportFormat.JSON,
        "--format",
        help="Transcript export format.",
    ),
) -> None:
    """Export stored transcripts."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
        exported_paths = export_all_transcripts(
            conn,
            paths,
            export_format=export_format,
        )

    typer.echo(f"Exported transcripts: {len(exported_paths)}")
