"""集中管理路徑與設定,預設全部落在本機 data/ 目錄下。"""

from __future__ import annotations

from datetime import timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SQLITE_PATH = DATA_DIR / "second_brain.db"
CHROMA_DIR = DATA_DIR / "chroma"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

MAX_TAGS = 5

RSS_DEFAULT_LIMIT = 10

ANSWER_MODEL = "claude-opus-4-8"

# 資料庫裡一律存 UTC(datetime.now(timezone.utc)),只有顯示給人看的時候才轉成
# 這個時區,避免時區換算邏輯散落在儲存層。
DISPLAY_TIMEZONE = timezone(timedelta(hours=8))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
