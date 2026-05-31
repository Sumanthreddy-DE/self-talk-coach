from pathlib import Path

from self_talk_coach.paths import AppPaths


def test_app_paths_uses_data_root(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path)

    assert paths.data_root == tmp_path
    assert paths.db_path == tmp_path / "db" / "self_talk_coach.sqlite"
    assert paths.media_inbox == tmp_path / "media" / "inbox"
    assert paths.media_processing == tmp_path / "media" / "processing"
    assert paths.media_processed == tmp_path / "media" / "processed"
    assert paths.media_failed == tmp_path / "media" / "failed"
    assert paths.media_archived == tmp_path / "media" / "archived"
    assert paths.exports_transcripts == tmp_path / "exports" / "transcripts"
    assert paths.exports_anki == tmp_path / "exports" / "anki"
    assert paths.exports_reports == tmp_path / "exports" / "reports"


def test_ensure_workspace_creates_directories(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path)

    paths.ensure_workspace()

    assert paths.db_path.parent.is_dir()
    assert paths.media_inbox.is_dir()
    assert paths.media_processing.is_dir()
    assert paths.media_processed.is_dir()
    assert paths.media_failed.is_dir()
    assert paths.media_archived.is_dir()
    assert paths.exports_transcripts.is_dir()
    assert paths.exports_anki.is_dir()
    assert paths.exports_reports.is_dir()
