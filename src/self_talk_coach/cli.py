"""Typer CLI entry point for self-talk-coach."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from self_talk_coach.conversation.mein_tag import MEIN_TAG
from self_talk_coach.conversation.report_metrics import median_freeze
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

REPORT_MAX_TOKENS = 3000


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
    mein_tag: Annotated[
        bool, typer.Option("--mein-tag", help="Talk freely about your day; partner only asks follow-ups.")
    ] = False,
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
    from self_talk_coach.conversation.mein_tag import MEIN_TAG_MAX_RECORD_SECONDS, MeinTagDeck
    from self_talk_coach.conversation.partner import (
        OpenAIChatClient,
        Partner,
        build_mein_tag_prompt,
        build_system_prompt,
    )
    from self_talk_coach.conversation.question_bank import (
        ScenarioDeck,
        load_banks,
        mark_phrase_sections,
    )
    from self_talk_coach.conversation.report import build_report
    from self_talk_coach.conversation.session import (
        COMPREHENSION_EVERY,
        MAX_RECORD_SECONDS,
        ConversationSession,
        SessionDeps,
    )
    from self_talk_coach.conversation.stt import DeepgramTranscriber
    from self_talk_coach.conversation.tts import EdgeVoice
    from self_talk_coach.db import list_turns

    load_dotenv()
    rng = random.Random()
    try:
        cfg = TalkConfig.from_env(os.environ)
        deck = ScenarioDeck(
            mark_phrase_sections(load_banks(cfg.question_banks), cfg.phrase_sections), scenario, rng
        )
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    profile_path = paths.learner_profile_path
    profile = profile_path.read_text(encoding="utf-8") if profile_path.is_file() else None
    if mein_tag:
        label = MEIN_TAG
    elif scenario is None:
        label = choose_start_scenario(deck, input, typer.echo)
    else:
        label = deck.label
    is_mein_tag = label == MEIN_TAG
    partner = Partner(
        OpenAIChatClient(cfg.gateway_base_url, cfg.gateway_api_key),
        cfg.partner_model,
        cfg.fallback_model,
        build_mein_tag_prompt(profile) if is_mein_tag else build_system_prompt(profile),
        drop_recast=is_mein_tag,
    )
    picker = MeinTagDeck() if is_mein_tag else deck
    typer.echo(f"Szenario: {picker.label}")
    typer.echo(
        "SPACE = sprechen/stoppen · r = nochmal · s = langsamer · t = Text zeigen"
        " · f = Szenarien · w = nächstes Szenario · q = Ende"
    )
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
            picker=picker,
            conn=conn,
            paths=paths,
            ladder=cfg.mein_tag_ladder if is_mein_tag else cfg.ladder,
            rng=rng,
            now_iso=lambda: datetime.now(UTC).isoformat(timespec="seconds"),
            max_record_seconds=MEIN_TAG_MAX_RECORD_SECONDS if is_mein_tag else MAX_RECORD_SECONDS,
            comprehension_every=0 if is_mein_tag else COMPREHENSION_EVERY,
        )
        cid = ConversationSession(deps, scenario=picker.label, llm_label=cfg.partner_model).run()
        turns = list_turns(conn, cid)
        median = median_freeze(turns)
        shown = f"{median:.1f}" if median is not None else "–"
        typer.echo(f"Gespräch {cid} gespeichert: {len(turns)} Turns, Median-Freeze {shown} s")
        if any(t["speaker"] == "learner" for t in turns):
            typer.echo("[Bericht] wird erstellt …")
            typer.echo(build_report(report_deps(conn, paths, cfg), cid))
        else:
            typer.echo("Kein Bericht: keine Antwort aufgenommen.")


def report_deps(conn, paths: AppPaths, cfg, status=typer.echo):
    from self_talk_coach.conversation.partner import OpenAIChatClient
    from self_talk_coach.conversation.report import ReportDeps
    from self_talk_coach.mine import load_baseline, spacy_lemmatizer

    return ReportDeps(
        conn=conn,
        paths=paths,
        client=OpenAIChatClient(cfg.gateway_base_url, cfg.gateway_api_key,
                                max_tokens=REPORT_MAX_TOKENS, temperature=0.2),
        model=cfg.report_model,
        lemmatizer=spacy_lemmatizer,
        baseline=load_baseline(),
        status=status,
    )


@app.command("report")
def report_command(
    conversation_id: Annotated[int, typer.Argument(help="Conversation id (printed after stc talk).")],
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
) -> None:
    """Build (or rebuild) the session report of one conversation."""
    import os

    from dotenv import load_dotenv

    from self_talk_coach.conversation.config import ConfigError, TalkConfig
    from self_talk_coach.conversation.report import build_report

    load_dotenv()
    try:
        cfg = TalkConfig.from_env(os.environ)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
        try:
            typer.echo(build_report(report_deps(conn, paths, cfg), conversation_id))
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc


def choose_start_scenario(deck, read, echo) -> str:
    """Numbered scenario list before the first partner turn; Enter alone = all mixed."""
    for i, name in enumerate(deck.options()):
        echo(f"  {i:2}  {name}")
    echo("   m  Mein Tag (frei erzählen)")
    while True:
        answer = read("Szenario-Nummer (Enter = alle gemischt): ").strip()
        if answer.lower() == "m":
            return MEIN_TAG
        if not answer:
            return deck.choose(0)
        if answer.isdigit() and int(answer) < len(deck.options()):
            return deck.choose(int(answer))
        echo(f"Keine Nummer {answer!r}.")
