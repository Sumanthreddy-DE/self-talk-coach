"""Typer CLI entry point for self-talk-coach."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

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
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
) -> None:
    """Initialize local database and managed media folders."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
    typer.echo(f"Initialized workspace at {paths.data_root}")


@app.command("import")
def import_command(
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
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
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
    model_size: Annotated[
        str, typer.Option("--model-size", help="Faster Whisper model size.")
    ] = "medium",
    device: Annotated[
        str, typer.Option("--device", help="Transcription device.")
    ] = "cpu",
    compute_type: Annotated[
        str, typer.Option("--compute-type", help="Transcription compute type.")
    ] = "int8",
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
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
    export_format: Annotated[
        TranscriptExportFormat,
        typer.Option("--format", help="Transcript export format."),
    ] = TranscriptExportFormat.JSON,
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


@app.command("talk")
def talk_command(
    scenario: Annotated[
        str | None,
        typer.Option("--scenario", help="Section name (substring) from the question banks."),
    ] = None,
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
) -> None:
    """Start a spoken German conversation with the AI partner."""
    import os
    import random
    from datetime import UTC, datetime

    from dotenv import load_dotenv

    from self_talk_coach.conversation.audio_io import (
        ConsoleKeys,
        MicRecorder,
        RealClock,
        SpeakerPlayer,
    )
    from self_talk_coach.conversation.config import ConfigError, TalkConfig
    from self_talk_coach.conversation.partner import (
        OpenAIChatClient,
        Partner,
        build_system_prompt,
    )
    from self_talk_coach.conversation.question_bank import (
        SeedPicker,
        filter_scenario,
        load_banks,
    )
    from self_talk_coach.conversation.session import ConversationSession, SessionDeps
    from self_talk_coach.conversation.stt import DeepgramTranscriber
    from self_talk_coach.conversation.tts import EdgeVoice
    from self_talk_coach.db import list_turns

    load_dotenv()
    try:
        cfg = TalkConfig.from_env(os.environ)
        seeds = filter_scenario(load_banks(cfg.question_banks), scenario)
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    profile_path = paths.learner_profile_path
    profile = profile_path.read_text(encoding="utf-8") if profile_path.is_file() else None
    rng = random.Random()
    partner = Partner(
        OpenAIChatClient(cfg.gateway_base_url, cfg.gateway_api_key),
        cfg.partner_model,
        cfg.fallback_model,
        build_system_prompt(profile),
    )
    typer.echo("SPACE = sprechen/stoppen · r = nochmal · s = langsamer · t = Text zeigen · q = Ende")
    with connect(paths.db_path) as conn:
        init_db(conn)
        deps = SessionDeps(
            partner=partner,
            transcriber=DeepgramTranscriber(cfg.deepgram_api_key),
            voice=EdgeVoice(cfg.tts_voice),
            player=SpeakerPlayer(),
            recorder=MicRecorder(),
            keys=ConsoleKeys(),
            clock=RealClock(),
            picker=SeedPicker(seeds, rng),
            conn=conn,
            paths=paths,
            ladder=cfg.ladder,
            rng=rng,
            now_iso=lambda: datetime.now(UTC).isoformat(timespec="seconds"),
        )
        cid = ConversationSession(deps, scenario=scenario, llm_label=cfg.partner_model).run()
        turns = list_turns(conn, cid)
    freezes = sorted(t["freeze_seconds"] for t in turns if t["freeze_seconds"] is not None)
    median = freezes[len(freezes) // 2] if freezes else None
    typer.echo(f"Gespräch {cid} gespeichert: {len(turns)} Turns, Median-Freeze {median} s")
