from pathlib import Path

from self_talk_coach.conversation.word_list import update_word_list
from self_talk_coach.mine import NewWord

W1 = [NewWord("Werdegang", "Erzählen Sie über Ihren Werdegang.", "career path"),
      NewWord("Baugruppe", "Baugruppen von Siemens NX.", "assembly")]


def test_sections_newest_first_and_ticks_survive_a_rerun(tmp_path: Path) -> None:
    path = tmp_path / "neue-woerter.md"
    update_word_list(path, 11, "Gespräch 11", W1[:1])
    update_word_list(path, 12, "Gespräch 12", W1)
    text = path.read_text(encoding="utf-8")
    assert text.index("## Gespräch 12") < text.index("## Gespräch 11")

    path.write_text(text.replace("- [ ] **Baugruppe**", "- [x] **Baugruppe**"), encoding="utf-8")
    update_word_list(path, 12, "Gespräch 12", W1)  # stc report 12 again
    text = path.read_text(encoding="utf-8")
    assert "- [x] **Baugruppe** — assembly · „Baugruppen von Siemens NX.“" in text
    assert "- [ ] **Werdegang** — career path" in text
    assert text.count("## Gespräch 12") == 1 and "## Gespräch 11" in text


def test_conversation_without_words_leaves_no_empty_section(tmp_path: Path) -> None:
    path = tmp_path / "neue-woerter.md"
    update_word_list(path, 3, "Gespräch 3", [])
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Neue Wörter") and "## " not in text
