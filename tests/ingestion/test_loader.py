from pathlib import Path

import pytest

from second_brain.ingestion.loader import load_document


def test_load_document_uses_markdown_heading_as_title(tmp_path: Path) -> None:
    file_path = tmp_path / "note.md"
    file_path.write_text("# 我的筆記\n\n內容第一段。\n", encoding="utf-8")

    document = load_document(file_path)

    assert document.title == "我的筆記"
    assert "內容第一段" in document.content
    assert document.source_path == str(file_path.resolve())


def test_load_document_falls_back_to_filename_when_no_heading(tmp_path: Path) -> None:
    file_path = tmp_path / "plain.txt"
    file_path.write_text("沒有標題的純文字內容。", encoding="utf-8")

    document = load_document(file_path)

    assert document.title == "plain"


def test_load_document_rejects_unsupported_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "data.json"
    file_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        load_document(file_path)
