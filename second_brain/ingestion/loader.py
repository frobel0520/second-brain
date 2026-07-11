"""本機 markdown/text 檔案的 loader。

只負責「讀取原始資料 → 轉成統一的 Document 格式」,不碰 embedding 或儲存邏輯。
之後要加新的資料來源,就在這個目錄下加一個新的 loader 檔案。
"""

from __future__ import annotations

import uuid
from pathlib import Path

from second_brain.models import Document

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt"}


def load_document(file_path: Path) -> Document:
    file_path = Path(file_path)

    if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"不支援的檔案類型: {file_path.suffix} "
            f"(目前支援: {', '.join(sorted(SUPPORTED_SUFFIXES))})"
        )

    content = file_path.read_text(encoding="utf-8")

    return Document(
        id=str(uuid.uuid4()),
        source_path=str(file_path.resolve()),
        title=_extract_title(content, fallback=file_path.stem),
        content=content,
    )


def _extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        if stripped:
            return fallback
    return fallback
