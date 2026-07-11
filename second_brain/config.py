"""集中管理路徑與設定,預設全部落在本機 data/ 目錄下。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SQLITE_PATH = DATA_DIR / "second_brain.db"
CHROMA_DIR = DATA_DIR / "chroma"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
