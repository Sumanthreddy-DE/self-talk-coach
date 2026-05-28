"""Typer CLI entry point. Sub-commands wired in S6."""

import typer

app = typer.Typer(help="self-talk-coach: German vocab miner")


@app.command()
def version() -> None:
    """Print version."""
    from self_talk_coach import __version__

    typer.echo(__version__)


@app.command()
def info() -> None:
    """Print project info."""
    typer.echo("self-talk-coach — German vocab miner. See docs/exec-plans/active/")


if __name__ == "__main__":
    app()
